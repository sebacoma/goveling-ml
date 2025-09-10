# api.py
from typing import List, Optional, Dict
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging
from datetime import datetime, time as dt_time
import time as time_module

from models.schemas_new import Place, PlaceType, TransportMode, Coordinates, ItineraryRequest, ItineraryResponse, HotelRecommendationRequest, Activity
from settings import settings
from services.hotel_recommender import HotelRecommender

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
                "🗺️ Itinerario optimizado con clustering geográfico automático",
                "📊 Agrupación inteligente por proximidad geográfica"
            ])
            
        base_recommendations.extend([
            f"⚡ Método híbrido: Haversine + Google Directions API",
            f"📅 {total_activities} actividades distribuidas en {len(days_data)} días",
            f"🎯 Score de eficiencia: {optimization_result.get('optimization_metrics', {}).get('efficiency_score', 0.9):.1%}",
            f"🚶‍♂️ Tiempo total de viaje: {int(total_travel_minutes)} minutos"
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
                from services.recommendation_engine import RecommendationEngine
                
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
                    recommendation_engine = RecommendationEngine()
                    
                    # Calcular ubicación central del usuario
                    avg_lat = sum(act.coordinates.latitude for act in user_activities) / len(user_activities)
                    avg_lon = sum(act.coordinates.longitude for act in user_activities) / len(user_activities)
                    user_location = {"latitude": avg_lat, "longitude": avg_lon}
                    
                    # Generar recomendaciones
                    ml_recommendations = recommendation_engine.generate_recommendations(
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
        
        # 🗓️ GENERAR SUGERENCIAS ESPECÍFICAS PARA DÍAS LIBRES
        if empty_days:
            logging.info(f"🗓️ Detectados {len(empty_days)} días completamente libres")
            
            # Sugerencias categorizadas por tipo de día libre
            for empty_day in empty_days:
                day_suggestions = [
                    {
                        "type": "day_trip_suggestion",
                        "category": "nature_escape",
                        "title": f"Escape a la Naturaleza - {empty_day['date']}",
                        "suggestions": [
                            "🏔️ Excursión a Cajón del Maipo y Embalse El Yeso",
                            "🍷 Tour de viñas en Casablanca o Maipo Alto", 
                            "🏔️ Teleférico y senderismo en Cerro San Cristóbal",
                            "🌊 Excursión a Valparaíso y Viña del Mar (día completo)"
                        ],
                        "duration": "8-10 horas",
                        "transport": "Auto recomendado o tour organizado"
                    },
                    {
                        "type": "day_trip_suggestion", 
                        "category": "cultural_immersion",
                        "title": f"Inmersión Cultural - {empty_day['date']}",
                        "suggestions": [
                            "🎨 Recorrido completo por museos: MNBA + MAC + Bellas Artes",
                            "🏛️ Tour arquitectónico: Centro Histórico + Barrio Yungay",
                            "🛍️ Experiencia gastronómica: Mercados + Barrio Italia",
                            "📚 Ruta literaria: Casa de Neruda + Biblioteca Nacional"
                        ],
                        "duration": "6-8 horas",
                        "transport": "🚶 A pie + Metro"
                    },
                    {
                        "type": "day_trip_suggestion",
                        "category": "adventure_day", 
                        "title": f"Día de Aventura - {empty_day['date']}",
                        "suggestions": [
                            "🎿 Sky Costanera + Parque Arauco (shopping y panorámica)",
                            "🚴 Cicletada por Providencia + Parque Bicentenario",
                            "🎢 Fantasilandia (parque de diversiones)",
                            "🦁 Zoológico Nacional + Parque Metropolitano completo"
                        ],
                        "duration": "6-8 horas", 
                        "transport": "🚌 Transporte público"
                    }
                ]
                
                # Añadir sugerencias específicas al día
                formatted_result.setdefault("free_day_suggestions", []).extend(day_suggestions)
            
            # Añadir resumen en recommendations generales
            formatted_result["recommendations"].extend([
                f"🗓️ {len(empty_days)} día(s) completamente libre(s) detectado(s)",
                "💡 Sugerencias de día completo disponibles en 'free_day_suggestions'",
                "🎯 Considera tours de día completo o excursiones fuera de Santiago"
            ])
            
            logging.info(f"🗓️ Generadas sugerencias para {len(empty_days)} días libres")
        
        # 🏨 RECOMENDACIONES DE HOTELES AUTOMÁTICAS (si no se proporcionaron accommodations)
        if not hotels_provided and places_data:
            try:
                hotel_recommender = HotelRecommender()
                hotel_recommendations = hotel_recommender.recommend_hotels(
                    places_data, 
                    max_recommendations=3,  # Top 3 hoteles
                    price_preference="any"
                )
                
                if hotel_recommendations:
                    formatted_result["suggested_accommodations"] = hotel_recommender.format_recommendations_for_api(hotel_recommendations)
                    
                    # 🏨 MEJORAR EL LODGING CON LA MEJOR RECOMENDACIÓN
                    best_hotel = hotel_recommendations[0]
                    for day in formatted_result["days"]:
                        day["lodging"] = {
                            "name": best_hotel.name,
                            "lat": best_hotel.lat,
                            "lon": best_hotel.lon,
                            "address": best_hotel.address,
                            "rating": best_hotel.rating,
                            "price_range": best_hotel.price_range,
                            "convenience_score": best_hotel.convenience_score,
                            "type": "recommended_hotel"
                        }
                    
                    # Añadir mensaje en recomendaciones generales
                    formatted_result["recommendations"].append(
                        f"🏨 Mejor alojamiento recomendado: {best_hotel.name} (score: {best_hotel.convenience_score:.2f})"
                    )
                    
                    logging.info(f"🏨 {len(hotel_recommendations)} recomendaciones de hoteles añadidas automáticamente")
                    
            except Exception as e:
                logging.warning(f"⚠️ No se pudieron generar recomendaciones de hoteles automáticas: {e}")
        
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host=getattr(settings, 'API_HOST', '0.0.0.0'),
        port=getattr(settings, 'API_PORT', 8000),
        reload=getattr(settings, 'DEBUG', True)
    )
