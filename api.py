# api.py
from typing import List, Optional, Dict
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging
from datetime import datetime, time as dt_time
import time as time_module

from models.schemas import Place, PlaceType, TransportMode, Coordinates, ItineraryRequest, ItineraryResponse, HotelRecommendationRequest, Activity
from settings import settings
from services.hotel_recommender import HotelRecommender
from services.google_places_service import GooglePlacesService

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Goveling ML API",
    description="API de optimización de itinerarios con ML v2.2 - Con soporte para hoteles",
    version="2.2.0"
)

# Configurar CORS para permitir todas las solicitudes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite todos los orígenes
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],  # Permite todos los métodos
    allow_headers=["*"],  # Permite todos los headers
    expose_headers=["*"],  # Expone todos los headers
    max_age=600,  # Cache preflight requests por 10 minutos
)

@app.get("/health")
async def health_check():
    """Health check básico"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.2.0"
    }

@app.post("/api/v2/itinerary/generate-hybrid", response_model=ItineraryResponse, tags=["Hybrid Optimizer"])
async def generate_hybrid_itinerary_endpoint(request: ItineraryRequest):
    """
    🚀 OPTIMIZADOR HÍBRIDO INTELIGENTE v2.2 - CON DETECCIÓN AUTOMÁTICA DE HOTELES
    
    ✨ FUNCIONALIDADES NUEVAS:
    - 🏨 Detección automática de hoteles/alojamientos como centroides
    - 🚗 Recomendaciones inteligentes de transporte 
    - 🔍 Modo automático: Con/Sin hoteles
    - ↩️ Completamente retrocompatible
    
    📊 CARACTERÍSTICAS TÉCNICAS:
    - 🗺️ Clustering geográfico automático (agrupa lugares cercanos)
    - 🏨 Clustering basado en hoteles (si se proporcionan alojamientos)
    - ⚡ Estimación híbrida de tiempos (Haversine + Google Directions API)
    - 📅 Programación multi-día inteligente con horarios realistas
    - 🎯 Optimización nearest neighbor dentro de clusters
    - 🚶‍♂️🚗🚌 Recomendaciones automáticas de transporte por tramo
    - ⏰ Respeto de horarios, buffers y tiempos de traslado
    - 💰 Eficiente en costos (solo usa Google API cuando es necesario)
    
    🏨 MODO HOTELES:
    - Envía 'accommodations' con tus hoteles/alojamientos
    - Sistema agrupa lugares por proximidad a hoteles
    - Rutas optimizadas desde/hacia alojamientos
    - Información de hotel incluida en cada actividad
    
    🗺️ MODO GEOGRÁFICO:
    - No envíes 'accommodations' o envía lista vacía
    - Comportamiento actual (clustering automático)
    - Mantiene toda la funcionalidad existente
    
    VENTAJAS:
    - Horarios más realistas y precisos
    - Distribución equilibrada entre días
    - Reducción de tiempo total de viaje
    - Agrupación inteligente por zonas geográficas o hoteles
    - Recomendaciones de transporte personalizadas
    """
    from utils.analytics import analytics
    
    start_time = time_module.time()
    
    try:
        # 🔍 Detectar si se enviaron hoteles/alojamientos
        accommodations_data = None
        hotels_provided = False
        
        if request.accommodations:
            accommodations_data = [acc.dict() if hasattr(acc, 'dict') else acc 
                                 for acc in request.accommodations]
            hotels_provided = True
            
            analytics.track_request("hybrid_itinerary_with_hotels", {
                "places_count": len(request.places),
                "hotels_count": len(accommodations_data),
                "days_requested": (request.end_date - request.start_date).days + 1,
                "transport_mode": request.transport_mode
            })
            
            logging.info(f"🏨 Detectados {len(accommodations_data)} hoteles - modo centroides")
        else:
            analytics.track_request("hybrid_itinerary_geographic", {
                "places_count": len(request.places),
                "days_requested": (request.end_date - request.start_date).days + 1,
                "transport_mode": request.transport_mode
            })
            
            logging.info("🗺️ Modo clustering geográfico automático")
        
        logging.info(f"🚀 Iniciando optimización HÍBRIDA para {len(request.places)} lugares")
        logging.info(f"📅 Período: {request.start_date} a {request.end_date} ({(request.end_date - request.start_date).days + 1} días)")
        
        # Convertir lugares a formato dict con campos normalizados
        places_data = []
        for place in request.places:
            if hasattr(place, 'dict'):  # Es un objeto Pydantic
                place_dict = {
                    'name': place.name,
                    'lat': place.lat,
                    'lon': place.lon,  # Usamos directamente lon
                    'type': str(place.type.value) if place.type else None,  # Usamos directamente type
                    'priority': place.priority,
                    'rating': place.rating,
                    'image': place.image,
                    'address': place.address
                }
            else:
                place_dict = place
            places_data.append(place_dict)
        
        # Usar optimizador híbrido con detección automática
        from utils.hybrid_optimizer import optimize_itinerary_hybrid
        
        # Convertir fechas
        if isinstance(request.start_date, str):
            start_date = datetime.strptime(request.start_date, '%Y-%m-%d')
        else:
            start_date = datetime.combine(request.start_date, dt_time.min)
            
        if isinstance(request.end_date, str):
            end_date = datetime.strptime(request.end_date, '%Y-%m-%d')
        else:
            end_date = datetime.combine(request.end_date, dt_time.min)
        
        # 🚀 OPTIMIZACIÓN CON DETECCIÓN AUTOMÁTICA
        optimization_result = await optimize_itinerary_hybrid(
            places_data,
            start_date,
            end_date,
            request.daily_start_hour,
            request.daily_end_hour,
            request.transport_mode,
            accommodations_data  # ← Detección automática (puede ser None)
        )
        
        # Extraer datos del resultado de optimización
        days_data = optimization_result.get("days", [])
        
        # Contar actividades totales
        total_activities = sum(len(day.get("activities", [])) for day in days_data)
        
        # Calcular tiempo total de viaje
        total_travel_minutes = sum([
            day.get("travel_summary", {}).get("total_travel_time_s", 0) / 60
            for day in days_data
        ])
        
        # Determinar el modo de optimización usado
        optimization_mode = "hotel_centroid" if hotels_provided else "geographic_clustering"
        
        # Formatear respuesta inteligente basada en el modo usado
        base_recommendations = []
        
        if hotels_provided:
            base_recommendations.extend([
                "🏨 Itinerario optimizado con hoteles como centroides",
                f"📍 {len(accommodations_data)} hotel(es) usado(s) como base",
                "⚡ Rutas optimizadas desde/hacia alojamientos",
                "🚗 Recomendaciones de transporte por tramo"
            ])
        else:
            base_recommendations.extend([
                "Itinerario optimizado con clustering geográfico automático",
                "Agrupación inteligente por proximidad geográfica"
            ])
            
        base_recommendations.extend([
            f"Método híbrido: Haversine + Google Directions API",
            f"{total_activities} actividades distribuidas en {len(days_data)} días",
            f"Score de eficiencia: {optimization_result.get('optimization_metrics', {}).get('efficiency_score', 0.9):.1%}",
            f"Tiempo total de viaje: {int(total_travel_minutes)} minutos"
        ])
        
        # Formatear respuesta para ItineraryResponse con información completa
        formatted_result = {
            "days": days_data,  # Ya viene en el formato correcto del hybrid optimizer
            "unassigned": [],   # El optimizador híbrido maneja todo inteligentemente
            "total_activities": total_activities,
            "total_travel_time_minutes": float(total_travel_minutes),
            "average_activities_per_day": round(total_activities / max(1, len(days_data)), 1),
            "generated_at": datetime.now().isoformat(),
            "model_version": "2.2.0-hybrid-hotels",
            "optimization_metrics": {
                "efficiency_score": optimization_result.get("optimization_metrics", {}).get("efficiency_score", 0.9),
                "total_distance_km": optimization_result.get("optimization_metrics", {}).get("total_distance_km", 0),
                "avg_travel_per_activity_min": round(total_travel_minutes / max(1, total_activities), 1),
                "google_maps_enhanced": bool(settings.GOOGLE_MAPS_API_KEY),
                # Nuevas métricas para hoteles
                "optimization_mode": optimization_mode,
                "hotels_provided": hotels_provided,
                "hotels_count": len(accommodations_data) if accommodations_data else 0,
                "accommodation_based_clustering": hotels_provided,
                "geographic_clustering": not hotels_provided,
                "transport_recommendations": True
            },
            "recommendations": base_recommendations,
            "system_info": {
                "optimizer": "hybrid_intelligent_v2.2",
                "version": "2.2.0",
                "google_maps_api": bool(settings.GOOGLE_MAPS_API_KEY),
                "generated_at": datetime.now().isoformat(),
                # Nuevas características del sistema
                "auto_hotel_detection": True,
                "backward_compatible": True,
                "hotel_centroid_clustering": hotels_provided,
                "geographic_clustering": not hotels_provided,
                "transport_recommendations": True,
                "features": {
                    "geographic_clustering": True,
                    "hybrid_travel_times": True,
                    "multi_day_scheduling": True,
                    "nearest_neighbor_optimization": True,
                    "realistic_time_windows": True,
                    "hotel_centroid_clustering": hotels_provided,
                    "transport_recommendations": True,
                    "auto_detection": True
                }
            }
        }
        
        # 🧠 GENERAR RECOMENDACIONES AUTOMÁTICAS PARA DÍAS LIBRES
        auto_recommendations = []
        
        # 1. Detectar días completamente vacíos (sin actividades)
        empty_days = []
        total_days_requested = (request.end_date - request.start_date).days + 1
        days_with_activities = len(formatted_result["days"])
        
        if days_with_activities < total_days_requested:
            # Generar fechas faltantes
            from datetime import timedelta
            current_date = request.start_date
            existing_dates = {day["date"] for day in formatted_result["days"]}
            
            for i in range(total_days_requested):
                date_str = current_date.strftime('%Y-%m-%d')
                if date_str not in existing_dates:
                    empty_days.append({
                        "date": date_str,
                        "free_minutes": 540,  # 9 horas completas (9:00-18:00)
                        "activities_count": 0,
                        "type": "completely_free"
                    })
                current_date += timedelta(days=1)
        
        # 2. Detectar días con poco contenido o tiempo libre excesivo
        partial_free_days = []
        for day in formatted_result["days"]:
            free_minutes = day.get("free_minutes", 0)
            activities_count = len(day.get("activities", []))
            
            # Criterios para día "libre" o con espacio para más actividades
            if free_minutes > 120 or activities_count <= 3:  # Más de 2h libres o pocas actividades
                partial_free_days.append({
                    "date": day["date"],
                    "free_minutes": free_minutes,
                    "activities_count": activities_count,
                    "existing_activities": day.get("activities", []),
                    "type": "partially_free"
                })
        
        # Combinar ambos tipos de días libres
        free_days_detected = empty_days + partial_free_days
        
        # Si hay días con espacio libre, generar recomendaciones
        if free_days_detected:
            try:
                from services.recommendation_service import RecommendationService
                
                # Crear actividades del usuario para el análisis ML
                user_activities = []
                for day in formatted_result["days"]:
                    for activity in day.get("activities", []):
                        # Convertir a formato esperado por el motor de recomendaciones
                        user_activity = Activity(
                            place=activity["place"],
                            start=activity["start"],
                            end=activity["end"],
                            duration_h=activity["duration_h"],
                            lat=activity["lat"],
                            lon=activity["lon"],
                            type=activity["type"],
                            name=activity.get("name", activity["place"]),
                            category=activity.get("category", str(activity["type"]).lower()),
                            estimated_duration=activity["duration_h"],
                            priority=activity.get("priority", 7),
                            coordinates=Coordinates(
                                latitude=activity["lat"],
                                longitude=activity["lon"]
                            )
                        )
                        user_activities.append(user_activity)
                
                # Generar recomendaciones si tenemos suficientes datos
                if len(user_activities) >= 2:
                    recommendation_service = RecommendationService()
                    
                    # Calcular ubicación central del usuario
                    avg_lat = sum(act.coordinates.latitude for act in user_activities) / len(user_activities)
                    avg_lon = sum(act.coordinates.longitude for act in user_activities) / len(user_activities)
                    user_location = {"latitude": avg_lat, "longitude": avg_lon}
                    
                    # Generar recomendaciones
                    ml_recommendations = await recommendation_service.generate_recommendations(
                        user_activities=user_activities,
                        free_days=len(free_days_detected),
                        user_location=user_location,
                        preferences=request.preferences or {}
                    )
                    
                    # Formatear recomendaciones para la respuesta
                    logging.info(f"🔍 Debug: Procesando {len(ml_recommendations)} recomendaciones")
                    for i, rec_data in enumerate(ml_recommendations[:8]):  # Top 8 recomendaciones
                        try:
                            activity = rec_data['activity']
                            score = rec_data['score']
                            
                            auto_recommendations.append({
                                "type": "ml_recommendation",
                                "place_name": activity.name,
                                "category": activity.category,
                                "estimated_duration": activity.estimated_duration,
                                "coordinates": {
                                    "latitude": activity.coordinates.latitude,
                                    "longitude": activity.coordinates.longitude
                                },
                                "score": round(score.total_score, 2),
                                "confidence": round(score.confidence, 2),
                                "reasoning": rec_data['reasoning'],
                                "suggested_day": rec_data.get('suggested_day'),
                                "score_breakdown": {
                                    "preference": round(score.preference_score, 2),
                                    "geographic": round(score.geographic_score, 2),
                                    "temporal": round(score.temporal_score, 2),
                                    "novelty": round(score.novelty_score, 2)
                                }
                            })
                            logging.info(f"✅ Recomendación {i+1} añadida: {activity.name}")
                        except Exception as e:
                            logging.error(f"❌ Error procesando recomendación {i+1}: {e}")
                    
                    # Añadir info sobre días libres detectados
                    formatted_result["free_days_analysis"] = {
                        "days_with_free_time": len(free_days_detected),
                        "total_free_minutes": sum(day["free_minutes"] for day in free_days_detected),
                        "recommendation_opportunities": [
                            f"Día {day['date']}: {day['free_minutes']} min libres, {day['activities_count']} actividades"
                            for day in free_days_detected
                        ]
                    }
                    
                    logging.info(f"🧠 Recomendaciones ML generadas automáticamente: {len(auto_recommendations)} sugerencias")
                    
            except Exception as e:
                logging.warning(f"⚠️ No se pudieron generar recomendaciones ML automáticas: {e}")
                auto_recommendations.append({
                    "type": "system_note",
                    "message": "Sistema de recomendaciones ML no disponible en este momento"
                })
        
        # Añadir recomendaciones a la respuesta
        logging.info(f"🔍 Debug final: auto_recommendations tiene {len(auto_recommendations)} elementos")
        if auto_recommendations:
            formatted_result["ml_recommendations"] = auto_recommendations
            formatted_result["system_info"]["ml_recommendations"] = True
            formatted_result["system_info"]["recommendation_engine"] = "multi_algorithm_v1.0"
            logging.info(f"✅ Recomendaciones ML añadidas a la respuesta final")
        else:
            logging.warning(f"⚠️ No hay recomendaciones para añadir a la respuesta")
        
        # 🗓️ GENERAR SUGERENCIAS ESPECÍFICAS PARA DÍAS LIBRES (dinámico, sin ciudades hardcodeadas)
        if empty_days:
            logging.info(f"🗓️ Detectados {len(empty_days)} días completamente libres")

            # 1) Determinar un centro (lat, lon) para buscar alrededor
            def _first_valid_coord():
                # usa lodging si existe, luego primera actividad, luego primer place
                for day in formatted_result.get("days", []):
                    if isinstance(day, dict) and day.get("lodging") and all(k in day["lodging"] for k in ("lat", "lon")):
                        return day["lodging"]["lat"], day["lodging"]["lon"]
                for day in formatted_result.get("days", []):
                    for act in day.get("activities", []):
                        if "lat" in act and "lon" in act:
                            return act["lat"], act["lon"]
                for p in places_data:
                    if p.get("lat") is not None and p.get("lon") is not None:
                        return p["lat"], p["lon"]
                return None, None

            activities_lat, activities_lon = [], []
            for day in formatted_result.get("days", []):
                for act in day.get("activities", []):
                    if "lat" in act and "lon" in act:
                        activities_lat.append(act["lat"])
                        activities_lon.append(act["lon"])

            if activities_lat and activities_lon:
                centroid_lat = sum(activities_lat) / len(activities_lat)
                centroid_lon = sum(activities_lon) / len(activities_lon)
            else:
                centroid_lat, centroid_lon = _first_valid_coord()

            if centroid_lat is None or centroid_lon is None:
                logging.warning("⚠️ No hay coordenadas para sugerencias dinámicas; se omite generación de free_day_suggestions.")
            else:
                # 2) Consultar sugerencias dinámicas alrededor del centro
                places_service = GooglePlacesService()
                try:
                    # Puedes ajustar radius_m y limit_per_category según tu UX
                    dynamic = places_service.generate_day_suggestions(
                        lat=centroid_lat,
                        lon=centroid_lon,
                        # categories=None -> usa las default del servicio (nature, culture, food, etc.)
                        radius_m=3000,
                        limit_per_category=6,
                    )
                    categories = dynamic.get("categories", {})
                    # Orden sugerido de categorías (si existen)
                    category_order = ["nature", "culture", "food", "shopping", "family", "viewpoints", "nightlife"]
                    ordered_categories = [c for c in category_order if c in categories] or list(categories.keys())

                    # 3) Armar payload de sugerencias por día libre (sin hardcodear por ciudad)
                    def build_day_suggestions(date_str: str) -> dict:
                        items = []
                        for cat in ordered_categories:
                            for poi in categories.get(cat, [])[:3]:  # toma top 3 por categoría
                                items.append({
                                    "category": cat,
                                    "name": poi.get("name"),
                                    "address": poi.get("address"),
                                    "lat": poi.get("lat"),
                                    "lon": poi.get("lon"),
                                    "rating": poi.get("rating"),
                                    "user_ratings_total": poi.get("user_ratings_total"),
                                    "distance_km": poi.get("distance_km"),
                                    "open_now": poi.get("open_now"),
                                    "source": poi.get("source"),
                                    "score": poi.get("score")
                                })
                        # Ordena por score (desc), luego distancia (asc)
                        items.sort(key=lambda x: (-float(x.get("score") or 0), float(x.get("distance_km") or 1e9)))
                        # Limita a 12 para no saturar
                        items = items[:12]

                        return {
                            "type": "free_day",
                            "date": date_str,
                            "title": f"Día libre - {date_str}",
                            "origin": {"latitude": centroid_lat, "longitude": centroid_lon},
                            "suggestions": items,
                            "note": "Sugerencias cercanas generadas dinámicamente a partir de datos externos (Google/OSM)."
                        }

                    for empty_day in empty_days:
                        formatted_result.setdefault("free_day_suggestions", []).append(
                            build_day_suggestions(empty_day["date"])
                        )

                    formatted_result["recommendations"].extend([
                        f"{len(empty_days)} día(s) completamente libre(s) detectado(s)",
                        "Se generaron sugerencias cercanas en 'free_day_suggestions' basadas en datos alrededor del centro del itinerario."
                    ])
                    logging.info(f"🗓️ Generadas sugerencias dinámicas para {len(empty_days)} días libres")
                except Exception as e:
                    logging.warning(f"⚠️ Error generando sugerencias dinámicas: {e}")
                    # Fallback ultra simple (sin ciudades ni strings específicos)
                    for empty_day in empty_days:
                        formatted_result.setdefault("free_day_suggestions", []).append({
                            "type": "free_day",
                            "date": empty_day["date"],
                            "title": f"Día libre - {empty_day['date']}",
                            "origin": {"latitude": centroid_lat, "longitude": centroid_lon},
                            "suggestions": [],
                            "note": "No fue posible obtener sugerencias dinámicas en este momento."
                        })
        
        # RECOMENDACIONES DE HOTELES AUTOMÁTICAS (si no se proporcionaron accommodations)
            logging.info(f"🗓️ Detectados {len(empty_days)} días completamente libres")
            
            # Determinar la ciudad basada en el centroide de actividades
            activities_lat = []
            activities_lon = []
            for day in formatted_result["days"]:
                for activity in day.get("activities", []):
                    activities_lat.append(activity["lat"])
                    activities_lon.append(activity["lon"])
            
            # Calcular centroide y determinar la ciudad usando Google Places API
            if activities_lat and activities_lon:
                avg_lat = sum(activities_lat) / len(activities_lat)
                avg_lon = sum(activities_lon) / len(activities_lon)
                
                try:
                    from utils.google_maps_client import GoogleMapsClient
                    maps_client = GoogleMapsClient()
                    
                    # Usar reverse geocoding para obtener información de la ubicación
                    location_info = maps_client.reverse_geocode(avg_lat, avg_lon)
                    
                    # Extraer ciudad y país de los resultados
                    city = maps_client.extract_city_from_geocoding(location_info)
                    country = maps_client.extract_country_from_geocoding(location_info)
                    
                    logging.info(f"Ciudad detectada mediante Google Maps API: {city}, {country}")
                except Exception as e:
                    logging.warning(f"No se pudo determinar la ciudad mediante Google Maps API: {e}")
                    # Determinar ciudad basado en las coordenadas promedio
                    if avg_lat and avg_lon:
                        if -23.7 <= avg_lat <= -23.5:  # Antofagasta
                            city = "antofagasta"
                        elif -22.5 <= avg_lat <= -22.3:  # Calama
                            city = "calama"
                        else:  # Santiago u otra zona central por defecto
                            city = "santiago"
                    else:
                        city = "santiago"  # Ciudad por defecto
            else:
                # Si no hay actividades, usar coordenadas del hotel o lodging si existe
                lodging_found = False
                for day in formatted_result["days"]:
                    if "lodging" in day and "lat" in day["lodging"] and "lon" in day["lodging"]:
                        try:
                            from utils.google_maps_client import GoogleMapsClient
                            maps_client = GoogleMapsClient()
                            
                            # Usar reverse geocoding para el lodging
                            location_info = maps_client.reverse_geocode(
                                day["lodging"]["lat"], 
                                day["lodging"]["lon"]
                            )
                            
                            # Extraer ciudad del lodging
                            city = maps_client.extract_city_from_geocoding(location_info)
                            lodging_found = True
                            break
                        except Exception as e:
                            logging.warning(f"No se pudo determinar la ciudad del lodging: {e}")
                            continue
                
                if not lodging_found:
                    # Si no se pudo determinar la ciudad, intentar usar el nombre del lodging
                    if "lodging" in day and "name" in day["lodging"]:
                        city = day["lodging"]["name"].split(',')[0].strip().lower()
                    else:
                        city = "unknown"
            
            logging.info(f"🗓️ Detectados {len(empty_days)} días completamente libres")
            
            # Marcar días libres detectados
            for empty_day in empty_days:
                free_day_info = {
                    "type": "free_day",
                    "date": empty_day['date'],
                    "title": f"Día Libre - {empty_day['date']}",
                    "description": "Día disponible para actividades adicionales o descanso",
                    "suggestions": [
                        "💡 Explora lugares locales de interés",
                        "🍽️ Prueba la gastronomía local",
                        "🛍️ Visita mercados o centros comerciales",
                        "🚶 Camina por el centro de la ciudad",
                        "☕ Relájate en cafeterías locales"
                    ]
                }
                
                # Agregar información del día libre
                formatted_result.setdefault("free_day_suggestions", []).append(free_day_info)
            
            # Añadir resumen en recommendations generales si hay días libres
            if empty_days:
                formatted_result["recommendations"].extend([
                    f"{len(empty_days)} día(s) completamente libre(s) detectado(s)",
                    "Considera actividades locales o tiempo de descanso"
                ])
                
                logging.info(f"🗓️ Generadas sugerencias para {len(empty_days)} días libres")
        
            # RECOMENDACIONES DE HOTELES AUTOMÁTICAS (si no se proporcionaron accommodations)
            if not hotels_provided and places_data:
                try:
                    # Determinar la ciudad basada en las actividades
                    activities_lat = [p.get('lat', None) for p in places_data if p.get('lat') is not None]
                    activities_lon = [p.get('lon', None) for p in places_data if p.get('lon') is not None]
                    
                    if activities_lat and activities_lon:
                        avg_lat = sum(activities_lat) / len(activities_lat)
                        avg_lon = sum(activities_lon) / len(activities_lon)
                        
                        try:
                            # Inicializar recomendador con la ciudad correcta
                            hotel_recommender = HotelRecommender()
                            hotel_recommendations = hotel_recommender.recommend_hotels(
                                places_data, 
                                max_recommendations=3,  # Top 3 hoteles
                                price_preference="any",
                                city_coords={'lat': avg_lat, 'lon': avg_lon}  # Pasar coordenadas de la ciudad
                            )
                            
                            if hotel_recommendations:
                                activity_center = {
                                    'lat': avg_lat,
                                    'lon': avg_lon
                                }
                                
                                # Calcular radio de búsqueda basado en la dispersión de las actividades
                                from math import sqrt
                                std_lat = sqrt(sum((lat - activity_center['lat'])**2 for lat in activities_lat) / len(activities_lat))
                                std_lon = sqrt(sum((lon - activity_center['lon'])**2 for lon in activities_lon) / len(activities_lon))
                                search_radius = max(std_lat, std_lon) * 2  # Radio adaptativo basado en la dispersión
                                
                                def distance_to_center(hotel):
                                    return sqrt((hotel.lat - activity_center['lat'])**2 + (hotel.lon - activity_center['lon'])**2)
                                
                                # Filtrar hoteles dentro del radio adaptativo
                                city_hotels = [h for h in hotel_recommendations if distance_to_center(h) < search_radius]
                                
                                if city_hotels:
                                    formatted_result["suggested_accommodations"] = hotel_recommender.format_recommendations_for_api(city_hotels[:3])
                                    best_hotel = city_hotels[0]
                                    formatted_result["recommendations"].append(
                                        f"Mejor alojamiento recomendado: {best_hotel.name} (score: {best_hotel.convenience_score:.2f})"
                                    )
                        except Exception as e:
                            logging.warning(f"Error al recomendar hoteles: {str(e)}")
                            
                                                        # Si falló la recomendación, intentar mejorar el lodging con recomendaciones por ciudad
                            try:
                                # Determinar ciudad del día basado en sus actividades (simple heurística por latitud)
                                city = "santiago"  # valor por defecto
                                first_day_with_activities_idx = None

                                for idx, day in enumerate(formatted_result.get("days", [])):
                                    day_activities = day.get("activities", [])
                                    if day_activities and first_day_with_activities_idx is None:
                                        first_day_with_activities_idx = idx

                                    if day_activities:
                                        day_lat = sum(act["lat"] for act in day_activities) / len(day_activities)
                                        if -23.7 <= day_lat <= -23.5:      # Antofagasta
                                            city = "antofagasta"
                                        elif -22.5 <= day_lat <= -22.3:    # Calama
                                            city = "calama"
                                        else:                               # Santiago (u otra zona central)
                                            city = "santiago"

                                # Solo continúa si tenemos una lista de hoteles para filtrar
                                if hotel_recommendations:
                                    city_hotels = [
                                        h for h in hotel_recommendations if (
                                            (-23.7 <= h.lat <= -23.5 and -70.5 <= h.lon <= -70.3 and city == "antofagasta") or
                                            (-22.5 <= h.lat <= -22.3 and -69.0 <= h.lon <= -68.8 and city == "calama") or
                                            (-33.5 <= h.lat <= -33.3 and -70.7 <= h.lon <= -70.5 and city == "santiago")
                                        )
                                    ]

                                    if city_hotels:
                                        best_hotel = city_hotels[0]

                                        # Asignar lodging al primer día con actividades (si existe), para no usar una variable 'day' fuera de su bucle
                                        if first_day_with_activities_idx is not None:
                                            target_day = formatted_result["days"][first_day_with_activities_idx]
                                            target_day["lodging"] = {
                                                "name": best_hotel.name,
                                                "lat": best_hotel.lat,
                                                "lon": best_hotel.lon,
                                                "address": best_hotel.address,
                                                "rating": best_hotel.rating,
                                                "price_range": best_hotel.price_range,
                                                "convenience_score": best_hotel.convenience_score,
                                                "type": "recommended_hotel"
                                            }

                                        # Mensaje de recomendación global
                                        formatted_result["recommendations"].append(
                                            f"Mejor alojamiento recomendado: {best_hotel.name} (score: {best_hotel.convenience_score:.2f})"
                                        )
                                        logging.info("Hotel recommendations añadidas automáticamente")
                            except Exception as e:
                                logging.warning(f"⚠️ No se pudieron procesar las recomendaciones de hoteles por ciudad: {e}")
                except Exception as e:
                    logging.warning(f"Error procesando coordenadas de actividades: {str(e)}")
        # Log success
        duration = time_module.time() - start_time
        analytics.track_request(f"hybrid_itinerary_{optimization_mode}_success", {
            "efficiency_score": optimization_result.get("optimization_metrics", {}).get("efficiency_score", 0.9),
            "total_activities": total_activities,
            "days_used": len(days_data),
            "processing_time_seconds": round(duration, 2),
            "optimization_mode": optimization_mode,
            "hotels_provided": hotels_provided,
            "hotels_count": len(accommodations_data) if accommodations_data else 0
        })
        
        if hotels_provided:
            logging.info(f"✅ Optimización híbrida CON HOTELES completada en {duration:.2f}s")
            logging.info(f"🏨 {len(accommodations_data)} hoteles usados como centroides")
        else:
            logging.info(f"✅ Optimización híbrida GEOGRÁFICA completada en {duration:.2f}s")
            
        logging.info(f"🎯 Resultado: {total_activities} actividades, score {optimization_result.get('optimization_metrics', {}).get('efficiency_score', 0.9):.1%}")
        
        # Debug final antes del return
        if "ml_recommendations" in formatted_result:
            logging.info(f"🔍 FINAL: ml_recommendations presente con {len(formatted_result['ml_recommendations'])} elementos")
        else:
            logging.warning(f"⚠️ FINAL: ml_recommendations NO está en formatted_result")
        
        return ItineraryResponse(**formatted_result)
        
    except Exception as e:
        # Log error
        analytics.track_error("hybrid_itinerary_error", str(e), {
            "places_count": len(request.places),
            "error_type": type(e).__name__
        })
        
        logging.error(f"❌ Error generating hybrid itinerary: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error generating hybrid itinerary: {str(e)}"
        )

@app.post("/api/v2/hotels/recommend")
async def recommend_hotels_endpoint(request: HotelRecommendationRequest):
    """
    🏨 Recomendar hoteles basado en lugares a visitar
    
    Analiza la ubicación de los lugares del itinerario y recomienda
    hoteles óptimos basado en proximidad geográfica y conveniencia.
    """
    try:
        start_time = time_module.time()
        
        # Convertir lugares del request a formato interno
        places_data = []
        for place in request.places:
            places_data.append({
                'name': place.name,
                'lat': place.lat,
                'lon': place.lon,
                'type': place.type.value if hasattr(place.type, 'value') else str(place.type),
                'priority': getattr(place, 'priority', 5)
            })
        
        # Inicializar recomendador
        hotel_recommender = HotelRecommender()
        
        # Generar recomendaciones
        recommendations = hotel_recommender.recommend_hotels(
            places_data,
            max_recommendations=request.max_recommendations,
            price_preference=request.price_preference
        )
        
        # Formatear recomendaciones como una lista
        formatted_hotels = []
        if recommendations:
            centroid = hotel_recommender.calculate_geographic_centroid(places_data)
            for hotel in recommendations:
                formatted_hotel = {
                    "name": hotel.name,
                    "lat": hotel.lat,
                    "lon": hotel.lon,
                    "address": hotel.address,
                    "rating": hotel.rating,
                    "price_range": hotel.price_range,
                    "convenience_score": hotel.convenience_score,
                    "type": "hotel",
                    "distance_to_centroid_km": hotel.distance_to_centroid_km,
                    "avg_distance_to_places_km": hotel.avg_distance_to_places_km,
                    "analysis": {
                        "places_analyzed": len(places_data),
                        "activity_centroid": {
                            "latitude": round(centroid[0], 6),
                            "longitude": round(centroid[1], 6)
                        }
                    }
                }
                formatted_hotels.append(formatted_hotel)
        
        # Métricas de rendimiento
        duration = time_module.time() - start_time
        
        # Añadir métricas de rendimiento a cada hotel
        for hotel in formatted_hotels:
            hotel["performance"] = {
                "processing_time_s": round(duration, 2),
                "generated_at": datetime.now().isoformat()
            }
        
        logging.info(f"🏨 Recomendaciones de hoteles generadas en {duration:.2f}s")
        logging.info(f"📊 Mejor opción: {recommendations[0].name if recommendations else 'Ninguna'}")
        
        return formatted_hotels  # Retornamos la lista de hoteles
        
    except Exception as e:
        logging.error(f"❌ Error recomendando hoteles: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error generating hotel recommendations: {str(e)}"
        )

@app.post("/api/v2/places/suggest")
async def suggest_places_endpoint(coords: Coordinates):
    """
    🌍 Sugerir lugares para visitar cerca de una ubicación
    
    Analiza la ubicación proporcionada y sugiere lugares interesantes 
    cercanos, categorizados por tipo de actividad.
    """
    try:
        start_time = time_module.time()
        
        # Inicializar servicio de Google Places
        places_service = GooglePlacesService()
        
        # Generar sugerencias
        suggestions = places_service.generate_day_suggestions(
            lat=coords.latitude,
            lon=coords.longitude
        )
        
        # Métricas de rendimiento
        duration = time_module.time() - start_time
        
        # Añadir métricas al resultado
        suggestions["performance"] = {
            "processing_time_s": round(duration, 2),
            "generated_at": datetime.now().isoformat(),
            "coordinates": {
                "latitude": coords.latitude,
                "longitude": coords.longitude
            }
        }
        
        logging.info(f"🌍 Sugerencias de lugares generadas en {duration:.2f}s")
        
        return suggestions
        
    except Exception as e:
        logging.error(f"❌ Error generando sugerencias de lugares: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error generating place suggestions: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host=getattr(settings, 'API_HOST', '0.0.0.0'),
        port=getattr(settings, 'API_PORT', 8000),
        reload=getattr(settings, 'DEBUG', True)
    )
