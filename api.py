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
        
        # Formatear respuesta para frontend simplificada
        def format_place_for_frontend(activity, order):
            """Convertir actividad interna a formato esperado por frontend"""
            import uuid
            return {
                "id": str(uuid.uuid4()),  # Generar ID único
                "name": activity.get("place", ""),
                "category": activity.get("type", "point_of_interest"),
                "rating": activity.get("rating", 4.5),  # Rating por defecto
                "image": activity.get("image", ""),  # Placeholder para imagen
                "description": f"Actividad en {activity.get('place', 'este lugar')}",
                "estimated_time": f"{activity.get('duration_h', 1)}h",
                "priority": activity.get("priority", 5),
                "lat": activity.get("lat", 0),
                "lng": activity.get("lon", 0),  # Frontend espera 'lng' no 'lon'
                "recommended_duration": f"{activity.get('duration_h', 1)}h",
                "best_time": f"{activity.get('start', '09:00')}-{activity.get('end', '10:00')}",
                "order": order
            }
        
        # Convertir días a formato frontend
        itinerary_days = []
        day_counter = 1
        
        for day in days_data:
            # Convertir actividades
            frontend_places = []
            for idx, activity in enumerate(day.get("activities", []), 1):
                frontend_place = format_place_for_frontend(activity, idx)
                frontend_places.append(frontend_place)
            
            # Calcular tiempos del día
            total_activity_time = sum([act.get("duration_h", 1) for act in day.get("activities", [])])
            travel_time_minutes = day.get("travel_summary", {}).get("total_travel_time_s", 0) // 60
            walking_time = f"{int(travel_time_minutes)}min" if travel_time_minutes < 60 else f"{travel_time_minutes//60}h{travel_time_minutes%60}min"
            free_minutes = day.get("free_minutes", 0)
            free_time = f"{int(free_minutes)}min" if free_minutes < 60 else f"{free_minutes//60}h{free_minutes%60}min"
            
            # Determinar si es sugerido (días libres detectados)
            is_suggested = len(day.get("activities", [])) == 0
            
            day_data = {
                "day": day_counter,
                "date": day.get("date", ""),
                "places": frontend_places,
                "total_time": f"{int(total_activity_time)}h",
                "walking_time": walking_time,
                "transport_time": walking_time,  # Por ahora igual que walking_time
                "free_time": free_time,
                "is_suggested": is_suggested,
                "is_tentative": False
            }
            
            itinerary_days.append(day_data)
            day_counter += 1
        
        # Estructura final para frontend
        formatted_result = {
            "itinerary": itinerary_days,
            "optimization_metrics": {
                "efficiency_score": optimization_result.get("optimization_metrics", {}).get("efficiency_score", 0.9),
                "total_distance_km": optimization_result.get("optimization_metrics", {}).get("total_distance_km", 0),
                "total_travel_time_minutes": int(total_travel_minutes)
            },
            "recommendations": base_recommendations
        }
        
        # 🧠 GENERAR RECOMENDACIONES AUTOMÁTICAS PARA DÍAS LIBRES
        auto_recommendations = []
        
        # 1. Detectar días completamente vacíos (sin actividades)
        empty_days = []
        total_days_requested = (request.end_date - request.start_date).days + 1
        days_with_activities = len(days_data)
        
        if days_with_activities < total_days_requested:
            # Generar fechas faltantes
            from datetime import timedelta
            current_date = request.start_date
            existing_dates = {day["date"] for day in days_data}
            
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
        for day in days_data:
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
