"""
Funciones de recomendación para el API principal usando búsqueda dinámica de lugares
"""
import logging
from typing import List, Dict, Any
from datetime import datetime
from services.places_search_service import PlacesSearchService
from services.recommendation_service import RecommendationService

async def generate_recommendations(formatted_result: Dict[str, Any], empty_days: List[Dict]) -> Dict[str, Any]:
    """
    Generar recomendaciones dinámicas usando múltiples fuentes de datos
    """
    logging.info(f"🗓️ Detectados {len(empty_days)} días completamente libres")
    
    try:
        # Extraer todas las actividades y calcular centro de actividad
        activities_for_recommendations = []
        total_lat = 0
        total_lon = 0
        for day in formatted_result["days"]:
            for activity in day.get("activities", []):
                activities_for_recommendations.append(activity)
                total_lat += activity.get('lat', 0)
                total_lon += activity.get('lon', 0)
        
        if activities_for_recommendations:
            center_lat = total_lat / len(activities_for_recommendations)
            center_lon = total_lon / len(activities_for_recommendations)
        else:
            # Si no hay actividades, usar el centro del lodging si existe
            for day in formatted_result["days"]:
                if day.get("lodging"):
                    center_lat = day["lodging"].get("lat", 0)
                    center_lon = day["lodging"].get("lon", 0)
                    break
            else:
                raise ValueError("No hay actividades ni lodging para determinar el centro de búsqueda")

        # Buscar lugares cercanos usando el nuevo servicio
        places_service = PlacesSearchService()
        nearby_places = await places_service.search_places(
            lat=center_lat,
            lon=center_lon,
            radius=5000  # 5km de radio
        )
        
        # Generar sugerencias para cada día libre
        free_day_suggestions = []
        for empty_day in empty_days:
            day_suggestions = []
            
            # Mapeo de categorías a títulos amigables
            category_titles = {
                'nature_escape': '🏞️ Escape a la Naturaleza',
                'cultural_immersion': '🏛️ Inmersión Cultural',
                'food_and_drinks': '🍽️ Gastronomía Local',
                'shopping': '🛍️ Compras y Mercados',
                'entertainment': '🎭 Entretenimiento',
                'sports_and_recreation': '🏃 Deportes y Recreación'
            }
            
            # Generar sugerencias por categoría
            for category, places in nearby_places['places'].items():
                if places:  # Solo incluir categorías con lugares
                    suggestion = {
                        "type": "day_trip_suggestion",
                        "category": category,
                        "title": f"{category_titles.get(category, category.title())} - {empty_day['date']}",
                        "suggestions": [
                            {
                                "name": place["name"],
                                "rating": place.get("rating", 0),
                                "distance_km": round(place.get("distance", 0), 1),
                                "vicinity": place.get("vicinity", ""),
                                "coordinates": {
                                    "lat": place["lat"],
                                    "lon": place["lon"]
                                }
                            }
                            for place in places[:5]  # Top 5 lugares por categoría
                        ],
                        "duration": "2-3 horas por lugar",
                        "transport": "🚶 A pie o 🚕 Taxi según distancia"
                    }
                    day_suggestions.append(suggestion)
            
            if day_suggestions:
                free_day_suggestions.extend(day_suggestions)
        
        # Actualizar el resultado formateado
        if free_day_suggestions:
            formatted_result["free_day_suggestions"] = free_day_suggestions
            formatted_result["places_metadata"] = nearby_places['metadata']
            
            # Añadir resumen en recommendations generales
            formatted_result["recommendations"].extend([
                f"🗓️ {len(empty_days)} día(s) completamente libre(s) detectado(s)",
                f"🎯 {nearby_places['metadata']['total_places']} lugares de interés encontrados en un radio de {nearby_places['metadata']['radius_km']}km",
                "💡 Sugerencias personalizadas disponibles en 'free_day_suggestions'",
                "� Los lugares están ordenados por calificación y proximidad"
            ])
        
        logging.info(f"✅ Recomendaciones generadas exitosamente: {nearby_places['metadata']['total_places']} lugares encontrados")
        
    except Exception as e:
        logging.error(f"❌ Error generando recomendaciones: {e}")
        formatted_result["recommendations"].extend([
            "⚠️ No se pudieron generar recomendaciones automáticas",
            "🔍 Por favor, consulta sitios turísticos cercanos a tus actividades"
        ])
    
    return formatted_result
