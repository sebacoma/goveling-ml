"""
Servicio de Recomendaciones basado en Google Places API y similitud con lugares ancla
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from difflib import SequenceMatcher
from collections import defaultdict
from services.places_service import PlacesService
from utils.google_maps_client import GoogleMapsClient
from utils.geo_utils import haversine_km

class RecommendationService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.maps_client = GoogleMapsClient()

    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calcula similitud entre nombres usando SequenceMatcher"""
        return SequenceMatcher(None, name1.lower(), name2.lower()).ratio()

    def _extract_keywords(self, place: Dict) -> set:
        """Extrae keywords del nombre y tipo de lugar"""
        keywords = set()
        if 'name' in place:
            keywords.update(place['name'].lower().split())
        if 'type' in place:
            keywords.add(place['type'].lower())
        if 'category' in place:
            keywords.add(place['category'].lower())
        return keywords

    async def generate_recommendations(self, 
                                    anchor_activities: List[Dict],
                                    max_radius_km: float = 5,
                                    max_results: int = 20) -> Dict[str, Any]:
        """
        Generar recomendaciones basadas en ubicación actual
        """
        if not anchor_activities:
            return {
                "recommendations": [],
                "error": "No anchor activities provided",
                "generated_at": datetime.now().isoformat()
            }

        recommendations_by_anchor = defaultdict(list)
        top_picks = []
        seen_places = set()

        # 1. Calcular centro de actividades
        center = self._calculate_activity_center(anchor_activities)

        try:
            # 2. Para cada anchor, buscar lugares similares
            for anchor in anchor_activities:
                # Buscar alrededor del anchor
                nearby = await self.maps_client.search_places_nearby(
                    lat=anchor['lat'],
                    lon=anchor['lon'],
                    radius=max_radius_km * 1000,  # convertir a metros
                    place_type=anchor.get('type', 'point_of_interest')
                )

                anchor_keywords = self._extract_keywords(anchor)
                
                # Evaluar cada lugar cercano
                for place in nearby:
                    if place.get('place_id') in seen_places:
                        continue
                    
                    seen_places.add(place.get('place_id'))
                    
                    # Calcular scores
                    name_similarity = self._calculate_name_similarity(
                        anchor['name'], 
                        place.get('name', '')
                    )
                    
                    place_keywords = self._extract_keywords(place)
                    keyword_similarity = len(anchor_keywords & place_keywords) / max(
                        len(anchor_keywords | place_keywords), 1
                    )
                    
                    distance = haversine_km(
                        anchor['lat'], anchor['lon'],
                        place['geometry']['location']['lat'],
                        place['geometry']['location']['lng']
                    )
                    
                    # Score compuesto
                    similarity_score = (name_similarity * 0.3 + keyword_similarity * 0.7)
                    rating_score = place.get('rating', 0) / 5.0
                    distance_score = 1 - min(distance / max_radius_km, 1)
                    
                    total_score = (
                        similarity_score * 0.4 +
                        rating_score * 0.4 +
                        distance_score * 0.2
                    )

                    recommendation = {
                        'name': place.get('name'),
                        'type': place.get('types', [None])[0],
                        'lat': place['geometry']['location']['lat'],
                        'lon': place['geometry']['location']['lng'],
                        'rating': place.get('rating'),
                        'similar_to': anchor['name'],
                        'distance_km': round(distance, 2),
                        'score': round(total_score, 2),
                        'reasoning': [
                            f"Similar a {anchor['name']}",
                            f"A {round(distance, 1)}km de distancia",
                        ]
                    }

                    if place.get('rating'):
                        recommendation['reasoning'].append(
                            f"Rating: {place['rating']}/5.0"
                        )

                    recommendations_by_anchor[anchor['name']].append(recommendation)
                    top_picks.append(recommendation)

            # Ordenar recomendaciones por score
            for anchor_name in recommendations_by_anchor:
                recommendations_by_anchor[anchor_name].sort(
                    key=lambda x: x['score'], 
                    reverse=True
                )

            # Ordenar y limitar top picks
            top_picks.sort(key=lambda x: x['score'], reverse=True)
            top_picks = top_picks[:max_results]

            return {
                "by_anchor": dict(recommendations_by_anchor),
                "top_picks": top_picks,
                "metadata": {
                    "anchor_count": len(anchor_activities),
                    "total_recommendations": len(seen_places),
                    "center": center,
                    "radius_km": max_radius_km,
                    "generated_at": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error generando recomendaciones: {e}")
            return {
                "recommendations": [],
                "ml_recommendations": [],
                "error": str(e),
                "generated_at": datetime.now().isoformat()
            }
    
    def _calculate_activity_center(self, activities: List[Dict]) -> Dict[str, float]:
        """Calcular el centro de todas las actividades"""
        if not activities:
            # Default a Santiago si no hay actividades
            return {"latitude": -33.4489, "longitude": -70.6693}
        
        lats = []
        lons = []
        
        for activity in activities:
            if 'lat' in activity and 'lon' in activity:
                lats.append(activity['lat'])
                lons.append(activity['lon'])
        
        if not lats or not lons:
            return {"latitude": -33.4489, "longitude": -70.6693}
        
        return {
            "latitude": sum(lats) / len(lats),
            "longitude": sum(lons) / len(lons)
        }
    
    def _generate_ml_recommendations(self, 
                                   nearby_places: List[Dict], 
                                   center: Dict[str, float]) -> List[Dict]:
        """
        Generar recomendaciones personalizadas usando datos de Google Places
        """
        ml_recommendations = []
        
        # Ordenar lugares por rating y número de reseñas
        sorted_places = sorted(
            nearby_places,
            key=lambda x: (
                x.get('rating', 0) * 
                min(x.get('user_ratings_total', 0), 1000) / 1000
            ),
            reverse=True
        )
        
        # Tomar los mejores lugares
        for place in sorted_places[:5]:
            # Calcular distancia al centro
            distance = haversine_km(
                center['latitude'], center['longitude'],
                place['lat'], place['lon']
            )
            
            # Calcular scores
            rating_score = place.get('rating', 0) / 5.0
            popularity_score = min(place.get('user_ratings_total', 0), 1000) / 1000
            proximity_score = 1 - (distance / 10)  # 0-10km normalizado
            
            # Score final
            total_score = (rating_score * 0.4 + popularity_score * 0.3 + proximity_score * 0.3)
            
            # Generar razonamiento
            reasons = []
            if place.get('rating', 0) >= 4.5:
                reasons.append("Excelentes reseñas")
            if place.get('user_ratings_total', 0) > 500:
                reasons.append("Muy popular")
            if distance < 2:
                reasons.append("Cerca de tus actividades")
            if not reasons:
                reasons.append("Lugar interesante en la zona")
            
            recommendation = {
                "type": "ml_recommendation",
                "place_name": place['name'],
                "category": place.get('type', 'point_of_interest'),
                "estimated_duration": place.get('estimated_visit_duration', 2.0),
                "coordinates": {
                    "latitude": place['lat'],
                    "longitude": place['lon']
                },
                "score": round(total_score, 2),
                "confidence": round(min(rating_score + popularity_score, 1.0), 2),
                "reasoning": " • ".join(reasons),
                "score_breakdown": {
                    "rating": round(rating_score, 2),
                    "popularity": round(popularity_score, 2),
                    "proximity": round(proximity_score, 2)
                }
            }
            
            ml_recommendations.append(recommendation)
        
        return ml_recommendations
