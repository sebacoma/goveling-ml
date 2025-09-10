"""
🏨 Sistema de Recomendación de Hoteles
Recomienda hoteles basado en la ubicación de los lugares a visitar
"""

import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import math

@dataclass
class HotelRecommendation:
    name: str
    lat: float
    lon: float
    type: str = "hotel"
    address: str = ""
    rating: float = 0.0
    price_range: str = "medium"  # low, medium, high
    distance_to_centroid_km: float = 0.0
    avg_distance_to_places_km: float = 0.0
    convenience_score: float = 0.0
    reasoning: str = ""

class HotelRecommender:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Base de datos de hoteles por ciudad
        self.hotel_database = {
            "santiago": [
                {
                    "name": "Hotel Sheraton Santiago",
                    "lat": -33.4172,
                    "lon": -70.6060,
                    "address": "Av. Santa María 1742, Providencia",
                    "rating": 4.6,
                    "price_range": "high"
                },
            {
                "name": "W Santiago",
                "lat": -33.4150,
                "lon": -70.6100,
                "address": "Isidora Goyenechea 3000, Las Condes",
                "rating": 4.7,
                "price_range": "high"
            },
            {
                "name": "Hotel Plaza San Francisco",
                "lat": -33.4372,
                "lon": -70.6506,
                "address": "Alameda 816, Santiago Centro",
                "rating": 4.5,
                "price_range": "medium"
            },
            {
                "name": "Hotel Carrera",
                "lat": -33.4378,
                "lon": -70.6511,
                "address": "Teatinos 180, Santiago Centro",
                "rating": 4.2,
                "price_range": "medium"
            },
            {
                "name": "Ibis Santiago Providencia",
                "lat": -33.4372,
                "lon": -70.6172,
                "address": "Eliodoro Yáñez 1800, Providencia",
                "rating": 4.0,
                "price_range": "low"
            },
            {
                "name": "Hotel Director Vitacura",
                "lat": -33.3890,
                "lon": -70.5950,
                "address": "Av. Vitacura 3600, Vitacura",
                "rating": 4.4,
                "price_range": "high"
            },
            {
                "name": "Hotel Magnolia Santiago Centro",
                "lat": -33.4389,
                "lon": -70.6507,
                "address": "Huérfanos 539, Santiago Centro",
                "rating": 4.1,
                "price_range": "medium"
            },
            {
                "name": "Best Western Los Condes",
                "lat": -33.4089,
                "lon": -70.5950,
                "address": "Vitacura 4873, Las Condes",
                "rating": 4.0,
                "price_range": "medium"
            },
            {
                "name": "Hotel Boutique Castillo Rojo",
                "lat": -33.4262,
                "lon": -70.6344,
                "address": "Constitución 195, Bellavista",
                "rating": 4.3,
                "price_range": "medium"
            },
            {
                "name": "Hotel NH Ciudad de Santiago",
                "lat": -33.4350,
                "lon": -70.6450,
                "address": "Av. O'Higgins 136, Santiago Centro",
                "rating": 4.2,
                "price_range": "medium"
            }
        ],
        "antofagasta": [
            {
                "name": "Hotel Terrado Antofagasta",
                "lat": -23.646929,
                "lon": -70.4031467,
                "address": "Avenida Balmaceda 2575, Antofagasta",
                "rating": 4.5,
                "price_range": "high"
            },
            {
                "name": "Hotel Antofagasta",
                "lat": -23.6500,
                "lon": -70.3977,
                "address": "Av. Grecia 1490, Antofagasta",
                "rating": 4.3,
                "price_range": "medium"
            },
            {
                "name": "Ibis Antofagasta",
                "lat": -23.6435,
                "lon": -70.3955,
                "address": "Av. Grecia 1171, Antofagasta",
                "rating": 4.0,
                "price_range": "low"
            }
        ],
        "calama": [
            {
                "name": "Hotel Diego de Almagro Calama",
                "lat": -22.4583,
                "lon": -68.9204,
                "address": "Av. Granaderos 3452, Calama",
                "rating": 4.2,
                "price_range": "medium"
            },
            {
                "name": "Park Plaza Calama",
                "lat": -22.4595,
                "lon": -68.9215,
                "address": "Av. Balmaceda 2634, Calama",
                "rating": 4.1,
                "price_range": "medium"
            }
        ]
    }
    
    def haversine_km(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calcular distancia usando fórmula de Haversine"""
        R = 6371  # Radio de la Tierra en km
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def calculate_geographic_centroid(self, places: List[Dict]) -> Tuple[float, float]:
        """Calcular el centroide geográfico de los lugares"""
        if not places:
            # Default a Santiago centro si no hay lugares
            return -33.4489, -70.6693
        
        # Calcular promedio ponderado por prioridad
        total_lat = 0
        total_lon = 0
        total_weight = 0
        
        for place in places:
            weight = place.get('priority', 5)  # Usar prioridad como peso
            total_lat += place['lat'] * weight
            total_lon += place['lon'] * weight
            total_weight += weight
        
        centroid_lat = total_lat / total_weight
        centroid_lon = total_lon / total_weight
        
        self.logger.info(f"🎯 Centroide calculado: ({centroid_lat:.4f}, {centroid_lon:.4f})")
        return centroid_lat, centroid_lon
    
    def calculate_convenience_score(self, hotel: Dict, places: List[Dict], centroid: Tuple[float, float]) -> float:
        """Calcular score de conveniencia para un hotel"""
        hotel_lat, hotel_lon = hotel['lat'], hotel['lon']
        centroid_lat, centroid_lon = centroid
        
        # 1. Distancia al centroide (30% del score)
        distance_to_centroid = self.haversine_km(hotel_lat, hotel_lon, centroid_lat, centroid_lon)
        centroid_score = max(0, 1 - (distance_to_centroid / 10))  # Normalizar a 10km max
        
        # 2. Distancia promedio a todos los lugares (40% del score)
        total_distance = 0
        for place in places:
            distance = self.haversine_km(hotel_lat, hotel_lon, place['lat'], place['lon'])
            weight = place.get('priority', 5) / 10  # Normalizar prioridad
            total_distance += distance * weight
        
        avg_distance = total_distance / len(places) if places else 0
        distance_score = max(0, 1 - (avg_distance / 8))  # Normalizar a 8km max
        
        # 3. Rating del hotel (20% del score)
        rating_score = hotel.get('rating', 3.0) / 5.0
        
        # 4. Bonus por estar en zona central (10% del score)
        centro_bonus = 0
        if distance_to_centroid < 2:  # Muy cerca del centroide
            centro_bonus = 0.2
        elif distance_to_centroid < 5:  # Relativamente cerca
            centro_bonus = 0.1
        
        # Calcular score final
        final_score = (
            centroid_score * 0.3 + 
            distance_score * 0.4 + 
            rating_score * 0.2 + 
            centro_bonus * 0.1
        )
        
        return min(1.0, final_score)
    
    def determine_city(self, lat: float) -> str:
        """Determinar ciudad basado en la latitud"""
        if -23.7 <= lat <= -23.5:  # Antofagasta
            return "antofagasta"
        elif -22.5 <= lat <= -22.4:  # Calama
            return "calama"
        else:  # Default a Santiago
            return "santiago"
    
    def recommend_hotels(self, places: List[Dict], max_recommendations: int = 5, 
                        price_preference: str = "any") -> List[HotelRecommendation]:
        """
        Recomendar hoteles basado en ubicación de lugares
        
        Args:
            places: Lista de lugares a visitar
            max_recommendations: Número máximo de recomendaciones
            price_preference: "low", "medium", "high", "any"
        """
        if not places:
            self.logger.warning("No hay lugares para recomendar hoteles")
            return []
        
        # Calcular centroide geográfico
        centroid = self.calculate_geographic_centroid(places)
        
        # Determinar ciudad basado en el centroide
        city = self.determine_city(centroid[0])
        
        # Filtrar hoteles por preferencia de precio
        available_hotels = self.hotel_database[city]
        if price_preference != "any":
            available_hotels = [h for h in available_hotels if h['price_range'] == price_preference]
        
        # Calcular scores para cada hotel
        recommendations = []
        
        for hotel in available_hotels:
            # Calcular métricas
            distance_to_centroid = self.haversine_km(
                hotel['lat'], hotel['lon'], centroid[0], centroid[1]
            )
            
            # Calcular distancia promedio a lugares
            total_distance = 0
            for place in places:
                distance = self.haversine_km(hotel['lat'], hotel['lon'], place['lat'], place['lon'])
                total_distance += distance
            avg_distance_to_places = total_distance / len(places)
            
            # Calcular convenience score
            convenience_score = self.calculate_convenience_score(hotel, places, centroid)
            
            # Generar reasoning
            reasoning_parts = []
            if distance_to_centroid < 2:
                reasoning_parts.append("Muy cerca del centro de tus actividades")
            elif distance_to_centroid < 5:
                reasoning_parts.append("Ubicación conveniente para tus planes")
            
            if hotel['rating'] >= 4.5:
                reasoning_parts.append("Hotel de alta calidad")
            elif hotel['rating'] >= 4.0:
                reasoning_parts.append("Buena calidad y servicio")
            
            if avg_distance_to_places < 3:
                reasoning_parts.append("Fácil acceso a tus destinos")
            
            reasoning = " • ".join(reasoning_parts) if reasoning_parts else "Opción disponible en la zona"
            
            # Crear recomendación
            recommendation = HotelRecommendation(
                name=hotel['name'],
                lat=hotel['lat'],
                lon=hotel['lon'],
                type="hotel",
                address=hotel['address'],
                rating=hotel['rating'],
                price_range=hotel['price_range'],
                distance_to_centroid_km=round(distance_to_centroid, 2),
                avg_distance_to_places_km=round(avg_distance_to_places, 2),
                convenience_score=round(convenience_score, 3),
                reasoning=reasoning
            )
            
            recommendations.append(recommendation)
        
        # Ordenar por convenience score (descendente)
        recommendations.sort(key=lambda x: x.convenience_score, reverse=True)
        
        # Limitar número de recomendaciones
        recommendations = recommendations[:max_recommendations]
        
        self.logger.info(f"🏨 Generadas {len(recommendations)} recomendaciones de hoteles")
        
        return recommendations
    
    def format_recommendations_for_api(self, recommendations: List[HotelRecommendation]) -> List[Dict]:
        """Formatear recomendaciones para respuesta API"""
        return [
            {
                "name": rec.name,
                "lat": rec.lat,
                "lon": rec.lon,
                "type": rec.type,
                "address": rec.address,
                "rating": rec.rating,
                "price_range": rec.price_range,
                "distance_to_centroid_km": rec.distance_to_centroid_km,
                "avg_distance_to_places_km": rec.avg_distance_to_places_km,
                "convenience_score": rec.convenience_score,
                "reasoning": rec.reasoning,
                "recommendation_rank": i + 1,
                "selection_criteria": {
                    "based_on": "geographic_proximity_to_planned_activities",
                    "factors": [
                        "distance_to_activity_centroid",
                        "average_distance_to_all_places", 
                        "hotel_rating",
                        "central_location_bonus"
                    ],
                    "algorithm": "weighted_convenience_score"
                }
            }
            for i, rec in enumerate(recommendations)
        ]
