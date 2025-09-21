# api.py
from typing import List, Optional, Dict
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging
import asyncio
from datetime import datetime, time as dt_time, timedelta
import time as time_module

from models.schemas import Place, PlaceType, TransportMode, Coordinates, ItineraryRequest, ItineraryResponse, HotelRecommendationRequest, Activity
from settings import settings
from services.hotel_recommender import HotelRecommender
from services.google_places_service import GooglePlacesService
from utils.logging_config import setup_production_logging
from utils.performance_cache import cache_result, hash_places
from utils.hybrid_optimizer_v31 import HybridOptimizerV31

# Configurar logging optimizado
logger = setup_production_logging()

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

@app.get("/debug/suggestions")
async def debug_suggestions(lat: float = -23.6521, lon: float = -70.3958, day: int = 1):
    """Debug endpoint para probar sugerencias"""
    try:
        from services.google_places_service import GooglePlacesService
        
        places_service = GooglePlacesService()
        
        # Probar primero el método básico
        basic_suggestions = await places_service.search_nearby(
            lat=lat,
            lon=lon,
            types=['restaurant', 'tourist_attraction', 'museum'],
            limit=3
        )
        
        # Probar el método real con Google Places
        real_suggestions = await places_service.search_nearby_real(
            lat=lat,
            lon=lon,
            types=['restaurant', 'tourist_attraction', 'museum'],
            limit=3,
            day_offset=day
        )
        
        return {
            "location": {"lat": lat, "lon": lon},
            "day": day,
            "basic_suggestions": basic_suggestions,
            "real_suggestions": real_suggestions,
            "api_key_configured": bool(places_service.api_key),
            "settings": {
                "radius": settings.FREE_DAY_SUGGESTIONS_RADIUS_M,
                "limit": settings.FREE_DAY_SUGGESTIONS_LIMIT,
                "enable_real_places": settings.ENABLE_REAL_PLACES
            }
        }
        
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "error_type": str(e.__class__.__name__)
        }

@app.post("/api/v2/itinerary/generate-hybrid", response_model=ItineraryResponse, tags=["Hybrid Optimizer"])
@cache_result(expiry_minutes=5)  # 5 minutos de caché
async def generate_hybrid_itinerary_endpoint(request: ItineraryRequest):
    """
    🚀 OPTIMIZADOR HÍBRIDO INTELIGENTE V3.1 ENHANCED - MÁXIMA ROBUSTEZ
    
    ✨ NUEVAS FUNCIONALIDADES V3.1:
    - � Sugerencias inteligentes para bloques libres con duración-based filtering
    - 🚶‍♂️🚗 Clasificación precisa walking vs transport (30min threshold)
    - 🛡️ Normalización robusta de campos nulos
    - 🏨 Home base inteligente (hoteles → hubs → centroide)
    - 🛤️ Actividades especiales para transfers intercity largos
    - � Recomendaciones procesables con acciones específicas
    - � Retry automático y fallbacks sintéticos
    - ⚡ Manejo de errores de API con degradación elegante
    
    📊 CARACTERÍSTICAS TÉCNICAS CORE:
    - 🗺️ Clustering geográfico automático (agrupa lugares cercanos)
    - 🏨 Clustering basado en hoteles (si se proporcionan alojamientos)
    - ⚡ Estimación híbrida de tiempos (Haversine + Google Directions API)
    - 📅 Programación multi-día inteligente con horarios realistas
    - 🎯 Optimización nearest neighbor dentro de clusters
    - 🚶‍♂️🚗🚌 Recomendaciones automáticas de transporte por tramo
    - ⏰ Respeto de horarios, buffers y tiempos de traslado
    - 💰 Eficiente en costos (solo usa Google API cuando es necesario)
    
    🛡️ ROBUSTEZ V3.1:
    - Validación estricta de entrada con normalización automática
    - Retry automático en caso de fallos temporales
    - Fallbacks sintéticos cuando APIs fallan
    - Manejo elegante de campos nulos/missing
    - Respuestas mínimas garantizadas
    
    🏨 MODO HOTELES:
    - Envía 'accommodations' con tus hoteles/alojamientos
    - Sistema agrupa lugares por proximidad a hoteles
    - Rutas optimizadas desde/hacia alojamientos
    - Información de hotel incluida en cada actividad
    
    🗺️ MODO GEOGRÁFICO:
    - No envíes 'accommodations' o envía lista vacía
    - Comportamiento actual (clustering automático)
    - Mantiene toda la funcionalidad existente
    """
    from utils.analytics import analytics
    
    start_time = time_module.time()
    
    try:
        # 🛡️ Validación robusta de entrada
        if not request.places or len(request.places) == 0:
            raise HTTPException(
                status_code=400, 
                detail="Al menos un lugar es requerido para generar el itinerario"
            )
        
        if not request.start_date or not request.end_date:
            raise HTTPException(
                status_code=400,
                detail="Fechas de inicio y fin son requeridas"
            )
        
        # 🔧 Normalizar lugares con campos faltantes
        normalized_places = []
        for i, place in enumerate(request.places):
            try:
                # Manejo correcto de conversión para Pydantic v2
                if hasattr(place, 'model_dump'):
                    place_dict = place.model_dump()
                elif hasattr(place, 'dict'):
                    place_dict = place.dict()
                elif hasattr(place, '__dict__'):
                    place_dict = place.__dict__
                else:
                    place_dict = place
                
                # Solo log esencial en producción
                if settings.DEBUG:
                    logger.info(f"📍 Normalizando lugar {i}: {place_dict.get('name', 'sin nombre')}")
                
                # Función helper para conversión segura
                def safe_float(value, default=0.0):
                    if value is None:
                        return default
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return default
                        
                def safe_int(value, default=0):
                    if value is None:
                        return default
                    try:
                        return int(value)
                    except (ValueError, TypeError):
                        return default
                        
                def safe_str(value, default=""):
                    if value is None:
                        return default
                    return str(value)
                        
                def safe_enum_value(value, default=""):
                    """Extraer el valor del enum de PlaceType"""
                    if value is None:
                        return default
                    # Si es un enum, extraer el valor
                    if hasattr(value, 'value'):
                        return value.value
                    # Si es string que contiene el formato "PlaceType.VALUE"
                    value_str = str(value)
                    if 'PlaceType.' in value_str:
                        return value_str.split('.')[-1].lower()
                    return value_str
                
                # Obtener valores de category/type con manejo de enum
                category_value = safe_enum_value(place_dict.get('category') or place_dict.get('type'), 'general')
                type_value = safe_enum_value(place_dict.get('type') or place_dict.get('category'), 'point_of_interest')
                
                normalized_place = {
                    'place_id': place_dict.get('place_id') or place_dict.get('id') or f"place_{i}",
                    'name': safe_str(place_dict.get('name'), f"Lugar {i+1}"),
                    'lat': safe_float(place_dict.get('lat')),
                    'lon': safe_float(place_dict.get('lon')),
                    'category': category_value,
                    'type': type_value,
                    'rating': max(0.0, min(5.0, safe_float(place_dict.get('rating')))),
                    'price_level': max(0, min(4, safe_int(place_dict.get('price_level')))),
                    'address': safe_str(place_dict.get('address')),
                    'description': safe_str(place_dict.get('description'), f"Visita a {place_dict.get('name', 'lugar')}"),
                    'photos': place_dict.get('photos') or [],
                    'opening_hours': place_dict.get('opening_hours') or {},
                    'website': safe_str(place_dict.get('website')),
                    'phone': safe_str(place_dict.get('phone')),
                    'priority': max(1, min(10, safe_int(place_dict.get('priority'), 5)))
                }
                
                logger.info(f"✅ Lugar normalizado: {normalized_place['name']} ({normalized_place['lat']}, {normalized_place['lon']})")
                normalized_places.append(normalized_place)
            except Exception as e:
                logger.error(f"❌ Error normalizando lugar {i}: {e}")
                logger.error(f"   Tipo de objeto: {type(place)}")
                logger.error(f"   Contenido: {place}")
                # Continuar con lugar mínimo válido
                normalized_places.append({
                    'place_id': f"error_place_{i}",
                    'name': f"Lugar {i+1}",
                    'lat': 0.0,
                    'lon': 0.0,
                    'category': 'general',
                    'type': 'point_of_interest',
                    'rating': 0.0,
                    'price_level': 0,
                    'address': 'Dirección no disponible',
                    'description': 'Lugar con información limitada',
                    'photos': [],
                    'opening_hours': {},
                    'website': '',
                    'phone': '',
                    'priority': 5
                })
        
        # 🔍 Detectar si se enviaron hoteles/alojamientos  
        accommodations_data = None
        hotels_provided = False
        
        if request.accommodations:
            try:
                accommodations_data = []
                for acc in request.accommodations:
                    if hasattr(acc, 'model_dump'):
                        accommodations_data.append(acc.model_dump())
                    elif hasattr(acc, 'dict'):
                        accommodations_data.append(acc.dict())
                    else:
                        accommodations_data.append(acc)
                hotels_provided = len(accommodations_data) > 0
            except Exception as e:
                logger.warning(f"Error procesando accommodations: {e}")
                accommodations_data = None
        
        logger.info(f"🚀 Iniciando optimización V3.1 ENHANCED para {len(normalized_places)} lugares")
        logger.info(f"📅 Período: {request.start_date} a {request.end_date}")
        
        # Convertir fechas
        if isinstance(request.start_date, str):
            start_date = datetime.strptime(request.start_date, '%Y-%m-%d')
        else:
            start_date = datetime.combine(request.start_date, dt_time.min)
            
        if isinstance(request.end_date, str):
            end_date = datetime.strptime(request.end_date, '%Y-%m-%d')
        else:
            end_date = datetime.combine(request.end_date, dt_time.min)
        
        # 🔄 OPTIMIZACIÓN CON RETRY AUTOMÁTICO
        from utils.hybrid_optimizer_v31 import optimize_itinerary_hybrid
        
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                analytics.track_request("hybrid_itinerary_v31", {
                    "places_count": len(normalized_places),
                    "hotels_provided": hotels_provided,
                    "days_requested": (end_date - start_date).days + 1,
                    "transport_mode": request.transport_mode,
                    "attempt": attempt + 1
                })
                
                optimization_result = await optimize_itinerary_hybrid(
                    normalized_places,
                    start_date,
                    end_date,
                    request.daily_start_hour,
                    request.daily_end_hour,
                    request.transport_mode,
                    accommodations_data
                )
                
                # 🛡️ Validar resultado antes de continuar
                if not optimization_result or 'days' not in optimization_result:
                    raise ValueError("Resultado de optimización inválido")
                
                # Éxito - salir del loop de retry
                break
                
            except Exception as e:
                last_error = e
                
                # 🔍 LOGGING EXHAUSTIVO DEL ERROR
                import traceback
                error_repr = repr(e)
                error_traceback = traceback.format_exc()
                error_code = f"OPT_ERR_{attempt + 1}_{type(e).__name__}"
                
                logger.error(f"❌ {error_code}: {error_repr}")
                logger.error(f"📊 Traceback completo:\n{error_traceback}")
                logger.error(f"🔢 Intento {attempt + 1}/{max_retries} - Lugares: {len(normalized_places)}")
                
                # Analizar tipo de error específico
                if "Geographic coherence error" in str(e):
                    logger.error("🌍 Error de coherencia geográfica detectado")
                elif "google_service" in str(e):
                    logger.error("🗺️ Error de servicio Google detectado")
                elif "DBSCAN" in str(e) or "cluster" in str(e).lower():
                    logger.error("🗂️ Error de clustering detectado")
                
                if attempt < max_retries - 1:
                    # Esperar antes del siguiente intento
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
        
        # 🚨 Si todos los intentos fallaron, crear fallback mínimo
        if last_error is not None and 'optimization_result' not in locals():
            error_reason = f"{type(last_error).__name__}: {str(last_error)}"
            logger.error(f"💥 Optimización falló después de {max_retries} intentos: {error_reason}")
            
            # Respuesta de fallback básica MEJORADA - Sin duplicados
            fallback_days = {}
            day_count = (end_date - start_date).days + 1
            places_per_day = len(normalized_places) // day_count if day_count > 0 else len(normalized_places)
            remaining_places = len(normalized_places) % day_count if day_count > 0 else 0
            
            current_place_index = 0
            
            for i in range(day_count):
                current_date = start_date + timedelta(days=i)
                date_key = current_date.strftime('%Y-%m-%d')
                
                # Distribuir lugares equitativamente
                places_this_day = places_per_day + (1 if i < remaining_places else 0)
                day_places = normalized_places[current_place_index:current_place_index + places_this_day]
                current_place_index += places_this_day
                
                fallback_days[date_key] = {
                    "day": i + 1,
                    "date": date_key,
                    "activities": day_places,
                    "transfers": [],
                    "free_blocks": [],
                    "actionable_recommendations": [
                        {
                            "type": "system_error",
                            "priority": "high",
                            "title": "Optimización temporal no disponible",
                            "description": f"Error: {error_reason}. Usando itinerario básico.",
                            "action": "retry_optimization"
                        }
                    ],
                    "base": day_places[0] if day_places else None,  # Primer lugar del día como base
                    "travel_summary": {
                        "total_travel_time_s": 0,
                        "walking_time_minutes": 0,
                        "transport_time_minutes": 0
                    }
                }
            
            return ItineraryResponse(
                itinerary=list(fallback_days.values()),
                optimization_metrics={
                    "total_places": len(normalized_places),
                    "total_days": day_count,
                    "optimization_mode": "fallback_basic",
                    "error": error_reason,  # ← Propagamos error_reason aquí
                    "fallback_active": True,
                    "efficiency_score": 0.3,
                    "processing_time_seconds": time_module.time() - start_time
                },
                recommendations=[
                    f"Sistema en modo fallback - Error: {error_reason}",
                    "Intente nuevamente en unos momentos",
                    "Contacte soporte si el problema persiste"
                ]
            )
        
        # Extraer datos del resultado de optimización
        days_data = optimization_result.get("days", [])
        optimization_metrics = optimization_result.get('optimization_metrics', {})
        clusters_info = optimization_result.get('clusters_info', {})  # ← LÍNEA AÑADIDA
        
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
            f"Método híbrido V3.1: DBSCAN + Time Windows + ETAs reales",
            f"{total_activities} actividades distribuidas en {len(days_data)} días",
            f"Score de eficiencia: {optimization_result.get('optimization_metrics', {}).get('efficiency_score', 0.9):.1%}",
            f"Tiempo total de viaje: {int(total_travel_minutes)} minutos",
            f"Estrategia de empaquetado: {clusters_info.get('packing_strategy_used', 'balanced')}"
        ])
        
        # 🚗 Añadir información sobre traslados largos detectados
        if optimization_metrics.get('long_transfers_detected', 0) > 0:
            transfer_count = optimization_metrics['long_transfers_detected']
            total_intercity_time = optimization_metrics.get('total_intercity_time_hours', 0)
            total_intercity_distance = optimization_metrics.get('total_intercity_distance_km', 0)
            
            base_recommendations.extend([
                f"🚗 {transfer_count} traslado(s) interurbano(s) detectado(s)",
                f"📏 Distancia total entre ciudades: {total_intercity_distance:.0f}km", 
                f"⏱️ Tiempo total de traslados largos: {total_intercity_time:.1f}h"
            ])
            
            # Información sobre clusters (validada)
            if clusters_info:
                base_recommendations.append(f"🏨 {clusters_info.get('total_clusters', 0)} zona(s) geográfica(s) identificada(s)")
            
            # Explicar separación de clusters
            base_recommendations.append("🗺️ Clusters separados por distancia para evitar traslados imposibles el mismo día")
            
            # Añadir detalles de cada traslado si hay pocos
            if transfer_count <= 3 and 'intercity_transfers' in optimization_metrics:
                for transfer in optimization_metrics['intercity_transfers']:
                    mode_forced = "" if transfer.get('mode') == request.transport_mode else f" (modo forzado: {transfer.get('mode')})"
                    base_recommendations.append(
                        f"  • {transfer['from']} → {transfer['to']}: "
                        f"{transfer['distance_km']:.0f}km (~{transfer['estimated_time_hours']:.1f}h){mode_forced}"
                    )
            
            # Advertencia sobre modo de transporte si se forzó cambio
            if request.transport_mode == 'walk':
                base_recommendations.append(
                    "⚠️ Modo de transporte cambiado automáticamente para traslados largos (walk → drive/transit)"
                )
            
            # Información sobre hoteles recomendados (validada)
            if clusters_info and clusters_info.get('recommended_hotels', 0) > 0:
                base_recommendations.append(
                    f"🏨 {clusters_info['recommended_hotels']} hotel(es) recomendado(s) automáticamente como base"
                )
        else:
            # 🔍 CÁLCULO DINÁMICO DE ZONAS GEOGRÁFICAS
            unique_bases = set()
            intercity_transfers = []
            
            for day in days_data:
                base = day.get('base')
                if base and base.get('name'):
                    unique_bases.add(base['name'])
                
                # Recopilar transfers intercity
                for transfer in day.get('transfers', []):
                    if transfer.get('type') == 'intercity_transfer':
                        intercity_transfers.append(f"{transfer['from']} → {transfer['to']} ({transfer.get('mode', 'drive')})")
            
            unique_clusters = len(unique_bases)
            
            if unique_clusters <= 1:
                base_recommendations.append("✅ Todos los lugares están en la misma zona geográfica")
            else:
                base_recommendations.append(f"🏨 {unique_clusters} zonas geográficas identificadas")
                if intercity_transfers:
                    base_recommendations.append(f"🚗 Transfers: {', '.join(intercity_transfers)}")
        
        # Formatear respuesta para frontend simplificada
        def format_activity_for_frontend(activity, order):
            """Convertir ActivityItem o IntercityActivity a formato esperado por frontend"""
            import uuid
            
            # Detectar si es una actividad intercity
            is_intercity = getattr(activity, 'is_intercity_activity', False) or getattr(activity, 'type', '') == 'intercity_activity'
            
            if is_intercity:
                # Formateo especial para actividades intercity
                return {
                    "id": str(uuid.uuid4()),
                    "name": getattr(activity, 'name', 'Viaje intercity'),
                    "category": "intercity_transfer",
                    "rating": 0.0,
                    "image": "",
                    "description": getattr(activity, 'description', 'Viaje entre ciudades'),
                    "estimated_time": f"{getattr(activity, 'duration_minutes', 0)/60:.1f}h",
                    "priority": 0,
                    "lat": getattr(activity, 'lat', 0.0),
                    "lng": getattr(activity, 'lon', 0.0),
                    "recommended_duration": f"{getattr(activity, 'duration_minutes', 0)/60:.1f}h",
                    "best_time": f"{getattr(activity, 'start_time', 0)//60:02d}:{getattr(activity, 'start_time', 0)%60:02d}-{getattr(activity, 'end_time', 0)//60:02d}:{getattr(activity, 'end_time', 0)%60:02d}",
                    "order": order,
                    "transport_mode": getattr(activity, 'transport_mode', 'drive'),
                    "is_intercity": True
                }
            else:
                # Formateo normal para POIs con getattr para campos opcionales
                return {
                    "id": str(uuid.uuid4()),
                    "name": getattr(activity, 'name', 'Lugar sin nombre'),
                    "category": getattr(activity, 'place_type', getattr(activity, 'type', 'point_of_interest')),
                    "rating": getattr(activity, 'rating', 4.5) or 4.5,
                    "image": getattr(activity, 'image', ''),
                    "description": getattr(activity, 'description', f"Actividad en {getattr(activity, 'name', 'lugar')}"),
                    "estimated_time": f"{getattr(activity, 'duration_minutes', 60)/60:.1f}h",
                    "priority": getattr(activity, 'priority', 5),
                    "lat": getattr(activity, 'lat', 0.0),
                    "lng": getattr(activity, 'lon', 0.0),  # Frontend espera 'lng'
                    "recommended_duration": f"{getattr(activity, 'duration_minutes', 60)/60:.1f}h",
                    "best_time": f"{getattr(activity, 'start_time', 0)//60:02d}:{getattr(activity, 'start_time', 0)%60:02d}-{getattr(activity, 'end_time', 0)//60:02d}:{getattr(activity, 'end_time', 0)%60:02d}",
                    "order": order,
                    "is_intercity": False
                }
        
        # Convertir días a formato frontend
        itinerary_days = []
        day_counter = 1
        
        for day in days_data:
            # Convertir actividades del nuevo formato
            frontend_places = []
            for idx, activity in enumerate(day.get("activities", []), 1):
                frontend_place = format_activity_for_frontend(activity, idx)
                frontend_places.append(frontend_place)
            
            # Calcular tiempos del día correctamente separados
            total_activity_time = sum([getattr(act, 'duration_minutes', 0) for act in day.get("activities", [])])
            travel_summary = day.get("travel_summary", {})
            walking_time_min = travel_summary.get("walking_time_minutes", 0)
            transport_time_min = travel_summary.get("transport_time_minutes", 0)
            
            walking_time = f"{int(walking_time_min)}min" if walking_time_min < 60 else f"{walking_time_min//60}h{walking_time_min%60}min"
            transport_time = f"{int(transport_time_min)}min" if transport_time_min < 60 else f"{transport_time_min//60}h{transport_time_min%60}min"
            
            free_minutes = day.get("free_minutes", 0)
            free_time = f"{int(free_minutes)}min" if free_minutes < 60 else f"{free_minutes//60}h{free_minutes%60}min"
            
            # Determinar si es sugerido (días libres detectados)
            is_suggested = len(day.get("activities", [])) == 0
            
            day_data = {
                "day": day_counter,
                "date": day.get("date", ""),
                "places": frontend_places,
                "total_time": f"{int(total_activity_time/60)}h",
                "walking_time": walking_time,
                "transport_time": transport_time,  # Ahora separado correctamente
                "free_time": free_time,
                "is_suggested": is_suggested,
                "is_tentative": False
            }
            
            # Añadir transfers y base si existen (campos opcionales para V3.1)
            if day.get("transfers"):
                day_data["transfers"] = day["transfers"]
            if day.get("base"):
                day_data["base"] = day["base"]
            if day.get("free_blocks"):
                day_data["free_blocks"] = day["free_blocks"]
            
            itinerary_days.append(day_data)
            day_counter += 1
        
        # Estructura final para frontend
        # 📊 MÉTRICAS COMPLETAS del optimizer (incluyendo optimization_mode, fallback_active, etc.)
        optimizer_metrics = optimization_result.get("optimization_metrics", {})
        
        # 🕐 Calcular duración del procesamiento
        duration = time_module.time() - start_time
        
        formatted_result = {
            "itinerary": itinerary_days,
            "optimization_metrics": {
                # Métricas del optimizer (incluye optimization_mode, fallback_active, intercity_transfers, etc.)
                **optimizer_metrics,
                # Métricas adicionales calculadas en el API
                "total_distance_km": optimizer_metrics.get("total_distance_km", 0),
                "total_travel_time_minutes": int(total_travel_minutes),
                "processing_time_seconds": round(duration, 2),
                "hotels_provided": hotels_provided,
                "hotels_count": len(accommodations_data) if accommodations_data else 0,
                # Override el optimization_mode si se usaron hoteles
                "optimization_mode": "hotel_centroid" if hotels_provided else optimizer_metrics.get("optimization_mode", "geographic_v31")
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
