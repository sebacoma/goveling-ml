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
from utils.common_routes_cache import CommonRoutesCache

# Configurar logging optimizado
logger = setup_production_logging()

# 🚀 Inicializar cache de rutas comunes globalmente para máxima eficiencia
routes_cache = CommonRoutesCache()

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

@app.get("/cache/routes/stats")
async def cache_routes_stats():
    """🚀 Estadísticas del cache de rutas comunes"""
    try:
        stats = routes_cache.get_cache_stats()
        return {
            "status": "success",
            "cache_stats": stats,
            "sample_routes": [
                "santiago_valparaiso (120km, 90min car)",
                "santiago_atacama (1600km, 16h car)", 
                "santiago_concepcion (515km, 5.5h car)",
                "valparaiso_serena (350km, 4h car)"
            ],
            "performance_boost": "Hasta 60% más rápido para rutas conocidas"
        }
    except Exception as e:
        logger.error(f"❌ Error obteniendo stats de cache: {e}")
        return {"status": "error", "detail": str(e)}

@app.get("/cache/routes/benchmark")
async def cache_routes_benchmark():
    """⚡ Benchmark de performance: Cache vs API calls"""
    import time
    from utils.free_routing_service import FreeRoutingService
    
    try:
        routing_service = FreeRoutingService()
        
        # Rutas de test (conocidas vs desconocidas)
        test_routes = [
            {
                "name": "Santiago → Valparaíso",
                "origin": (-33.4489, -70.6693),
                "destination": (-33.0472, -71.6127),
                "expected_cache": True
            },
            {
                "name": "Santiago → Atacama", 
                "origin": (-33.4489, -70.6693),
                "destination": (-22.4594, -68.9139),
                "expected_cache": True
            },
            {
                "name": "Ubicación Random",
                "origin": (-35.1234, -71.5678),
                "destination": (-36.9876, -72.1234), 
                "expected_cache": False
            }
        ]
        
        results = []
        
        for route in test_routes:
            # Medir tiempo de respuesta
            start_time = time.time()
            
            result = await routing_service.eta_between(
                route["origin"], 
                route["destination"], 
                'car'
            )
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            is_cached = result.get('cached', False)
            
            results.append({
                "route": route["name"],
                "response_time_ms": round(response_time_ms, 2),
                "cached": is_cached,
                "expected_cache": route["expected_cache"],
                "cache_match": is_cached == route["expected_cache"],
                "distance_km": result.get('distance_km', 0),
                "duration_minutes": result.get('duration_minutes', 0),
                "source": result.get('source', 'unknown')
            })
        
        # Calcular estadísticas
        cached_times = [r["response_time_ms"] for r in results if r["cached"]]
        non_cached_times = [r["response_time_ms"] for r in results if not r["cached"]]
        
        avg_cached = sum(cached_times) / len(cached_times) if cached_times else 0
        avg_non_cached = sum(non_cached_times) / len(non_cached_times) if non_cached_times else 0
        
        performance_improvement = 0
        if avg_non_cached > 0:
            performance_improvement = ((avg_non_cached - avg_cached) / avg_non_cached) * 100
        
        return {
            "status": "success",
            "benchmark_results": results,
            "performance_stats": {
                "avg_cached_response_ms": round(avg_cached, 2),
                "avg_non_cached_response_ms": round(avg_non_cached, 2),
                "performance_improvement_percent": round(performance_improvement, 1),
                "cache_hit_rate": len(cached_times) / len(results) * 100
            },
            "recommendations": [
                "✅ Cache funciona correctamente" if performance_improvement > 0 else "⚠️ Verificar cache",
                f"🚀 Mejora de velocidad: {performance_improvement:.1f}%" if performance_improvement > 0 else "No improvement detected"
            ]
        }
        
    except Exception as e:
        logger.error(f"❌ Error en benchmark: {e}")
        import traceback
        return {
            "status": "error", 
            "detail": str(e),
            "traceback": traceback.format_exc()
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

@app.post("/create_itinerary", response_model=ItineraryResponse, tags=["Core"])
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
                
                # Determinar quality flag si rating < 4.5
                rating_value = max(0.0, min(5.0, safe_float(place_dict.get('rating'))))
                quality_flag = None
                if rating_value > 0 and rating_value < 4.5:
                    quality_flag = "user_provided_below_threshold"
                    logger.info(f"⚠️ Lugar con rating bajo: {place_dict.get('name', 'lugar')} ({rating_value}⭐) - marcado como user_provided")
                
                normalized_place = {
                    'place_id': place_dict.get('place_id') or place_dict.get('id') or f"place_{i}",
                    'name': safe_str(place_dict.get('name'), f"Lugar {i+1}"),
                    'lat': safe_float(place_dict.get('lat')),
                    'lon': safe_float(place_dict.get('lon')),
                    'category': category_value,
                    'type': type_value,
                    'rating': rating_value,
                    'price_level': max(0, min(4, safe_int(place_dict.get('price_level')))),
                    'address': safe_str(place_dict.get('address')),
                    'description': safe_str(place_dict.get('description'), f"Visita a {place_dict.get('name', 'lugar')}"),
                    'photos': place_dict.get('photos') or [],
                    'opening_hours': place_dict.get('opening_hours') or {},
                    'website': safe_str(place_dict.get('website')),
                    'phone': safe_str(place_dict.get('phone')),
                    'priority': max(1, min(10, safe_int(place_dict.get('priority'), 5))),
                    'quality_flag': quality_flag  # Agregar quality flag
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
        
        # 🏨 DETECCIÓN Y RECOMENDACIÓN AUTOMÁTICA DE ACCOMMODATIONS
        # 1. Detectar si hay accommodations en places ORIGINALES
        accommodations_in_places = [
            place for place in normalized_places 
            if place.get('type', '').lower() == 'accommodation' or place.get('place_type', '').lower() == 'accommodation'
        ]
        
        # 2. Flag para indicar si NO había accommodations originalmente
        no_original_accommodations = len(accommodations_in_places) == 0 and not request.accommodations
        
        # 3. Si no hay accommodations, recomendar automáticamente
        if no_original_accommodations:
            logger.info("🤖 No se encontraron accommodations, recomendando hotel automáticamente...")
            try:
                from services.hotel_recommender import HotelRecommender
                hotel_recommender = HotelRecommender()
                
                # Recomendar el mejor hotel basado en los lugares de entrada
                recommendations = hotel_recommender.recommend_hotels(
                    normalized_places, 
                    max_recommendations=1, 
                    price_preference="mid"
                )
                
                if recommendations:
                    best_hotel = recommendations[0]
                    # Agregar el hotel recomendado a la lista de lugares
                    hotel_place = {
                        'name': best_hotel.name,
                        'lat': best_hotel.lat,
                        'lon': best_hotel.lon,
                        'type': 'accommodation',
                        'place_type': 'accommodation',
                        'rating': best_hotel.rating,
                        'address': best_hotel.address,
                        'category': 'accommodation',
                        'user_ratings_total': 100,  # Valor por defecto
                        'description': f"Hotel recomendado automáticamente: {best_hotel.name}",
                        'estimated_time': '1h',
                        'image': '',
                        'website': '',
                        'phone': '',
                        'priority': 5,
                        '_auto_recommended': True  # FLAG para identificar hoteles recomendados automáticamente
                    }
                    normalized_places.append(hotel_place)
                    logger.info(f"✅ Hotel recomendado agregado: {best_hotel.name} ({best_hotel.rating}⭐)")
                    logger.info(f"🔍 DEBUG: Hotel agregado con _auto_recommended=True y {len(normalized_places)} lugares totales")
                else:
                    logger.warning("⚠️ No se pudo recomendar ningún hotel automáticamente")
                    
            except Exception as e:
                logger.error(f"❌ Error recomendando hotel automáticamente: {e}")
        
        # 🔍 Detectar si se enviaron hoteles/alojamientos explícitamente
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
                
                # Pasar información extra al optimizer
                extra_info = {
                    'no_original_accommodations': no_original_accommodations
                }
                
                optimization_result = await optimize_itinerary_hybrid(
                    normalized_places,
                    start_date,
                    end_date,
                    request.daily_start_hour,
                    request.daily_end_hour,
                    request.transport_mode,
                    accommodations_data,
                    extra_info=extra_info
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
        
        # 🔧 CORREGIR ALIASES EN INTERCITY TRANSFERS TEMPRANO (antes de recommendations)
        if 'intercity_transfers' in optimization_metrics and days_data:
            # Construir bases referenciales desde days_data
            temp_bases = []
            for day in days_data:
                base = day.get('base', {})
                if base:
                    temp_bases.append(base)
            
            # Corregir aliases en optimization_metrics
            corrected_transfers = []
            for transfer in optimization_metrics['intercity_transfers']:
                corrected_transfer = transfer.copy()
                
                from_lat = transfer.get('from_lat', 0)
                from_lon = transfer.get('from_lon', 0)
                to_lat = transfer.get('to_lat', 0)
                to_lon = transfer.get('to_lon', 0)
                
                for base in temp_bases:
                    base_lat = base.get('lat', 0)
                    base_lon = base.get('lon', 0)
                    
                    # Corregir FROM
                    if (abs(base_lat - from_lat) < 0.01 and abs(base_lon - from_lon) < 0.01):
                        corrected_transfer['from'] = base.get('name', transfer.get('from', ''))
                    
                    # Corregir TO
                    if (abs(base_lat - to_lat) < 0.01 and abs(base_lon - to_lon) < 0.01):
                        corrected_transfer['to'] = base.get('name', transfer.get('to', ''))
                
                corrected_transfers.append(corrected_transfer)
            
            optimization_metrics['intercity_transfers'] = corrected_transfers
        
        # Contar actividades totales
        total_activities = sum(len(day.get("activities", [])) for day in days_data)
        

        
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
            # f"Tiempo total de viaje: {int(total_travel_minutes)} minutos", # Calculado después
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
        def get_value(activity, key, default=None):
            """Helper para obtener valor tanto de objetos como diccionarios"""
            if isinstance(activity, dict):
                return activity.get(key, default)
            else:
                return getattr(activity, key, default)
        
        def calculate_dynamic_duration(activity):
            """Calcular duración dinámica basada en tipo de actividad y distancia"""
            # Si ya tiene duration_minutes, usarlo
            if get_value(activity, 'duration_minutes', 0) > 0:
                return get_value(activity, 'duration_minutes', 0)
            
            # Para transfers, verificar si ya tiene tiempo calculado en el nombre
            activity_name = str(get_value(activity, 'name', ''))
            activity_name_lower = activity_name.lower()
            is_transfer = (get_value(activity, 'category', '') == 'transfer' or 
                          get_value(activity, 'type', '') == 'transfer' or
                          'traslado' in activity_name_lower or 'transfer' in activity_name_lower)
            
            if is_transfer:
                # Primero verificar si el nombre ya incluye duración calculada
                import re
                # Buscar patrones como "(68min)" o "(3h)" o "(2.5h)" 
                minutes_match = re.search(r'\((\d+)min\)', activity_name)
                hours_match = re.search(r'\((\d+(?:\.\d+)?)h\)', activity_name)
                
                if minutes_match:
                    calculated_minutes = int(minutes_match.group(1))
                    logger.info(f"✅ Usando duración del optimizador (min): '{activity_name}' = {calculated_minutes}min")
                    return calculated_minutes
                elif hours_match:
                    calculated_hours = float(hours_match.group(1))
                    calculated_minutes = int(calculated_hours * 60)
                    logger.info(f"✅ Usando duración del optimizador (h): '{activity_name}' = {calculated_hours}h → {calculated_minutes}min")
                    return calculated_minutes
                distance_km = get_value(activity, 'distance_km', 0)
                transport_mode = get_value(activity, 'transport_mode', request.transport_mode if hasattr(request, 'transport_mode') else 'walk')
                # Si no hay distance_km, intentar calcular con coordenadas
                if distance_km <= 0:
                    origin_lat = get_value(activity, 'origin_lat')
                    origin_lon = get_value(activity, 'origin_lon')
                    dest_lat = get_value(activity, 'lat')
                    dest_lon = get_value(activity, 'lon')
                    
                    if all([origin_lat, origin_lon, dest_lat, dest_lon]):
                        from utils.geo_utils import haversine_km  
                        distance_km = haversine_km(origin_lat, origin_lon, dest_lat, dest_lon)
                        logger.debug(f"🔧 Calculando distancia para transfer '{activity_name}': {distance_km:.2f}km")
                
                if distance_km > 0:
                    # 🚀 CACHE CHECK: Verificar rutas comunes pre-calculadas
                    origin_lat = get_value(activity, 'origin_lat')
                    origin_lon = get_value(activity, 'origin_lon')
                    dest_lat = get_value(activity, 'lat')
                    dest_lon = get_value(activity, 'lon')
                    
                    if all([origin_lat, origin_lon, dest_lat, dest_lon]):
                        cached_route = routes_cache.find_cached_route(
                            origin_lat, origin_lon, dest_lat, dest_lon, transport_mode
                        )
                        if cached_route:
                            cached_time = cached_route['duration_minutes']
                            logger.info(f"🚀 Cache HIT transfer: '{activity_name}' = {cached_time}min (ruta: {cached_route['route_name']})")
                            return cached_time
                    
                    # Velocidades realistas por modo (fallback si no hay cache)
                    speeds = {
                        'walk': 4.5,      # 4.5 km/h caminando
                        'walking': 4.5,
                        'drive': 45.0,    # 45 km/h en ciudad/carretera
                        'car': 45.0,
                        'transit': 30.0,  # 30 km/h transporte público
                        'bicycle': 15.0   # 15 km/h bicicleta
                    }
                    
                    speed_kmh = speeds.get(transport_mode, 4.5)
                    duration_minutes = (distance_km / speed_kmh) * 60
                    
                    # Buffer adicional para transfers largos
                    if distance_km > 30:  # Intercity
                        duration_minutes *= 1.2  # 20% buffer
                    else:  # Urbano
                        duration_minutes *= 1.1  # 10% buffer
                    
                    calculated_time = max(5, int(duration_minutes))
                    logger.info(f"✅ Transfer dinámico: '{activity_name}' = {distance_km:.2f}km → {calculated_time}min ({transport_mode})")
                    return calculated_time
                else:
                    # Fallback para transfers sin coordenadas: tiempo estimado por modo
                    fallback_times = {
                        'walk': 20,    # 20 min caminando urbano
                        'walking': 20,
                        'drive': 15,   # 15 min conduciendo urbano  
                        'car': 15,
                        'transit': 25, # 25 min transporte público
                        'bicycle': 12  # 12 min bicicleta
                    }
                    fallback_time = fallback_times.get(transport_mode, 20)
                    logger.warning(f"⚠️ Transfer sin coordenadas '{activity_name}' - usando fallback: {fallback_time}min")
                    return fallback_time
            
            # Valores por defecto según tipo de actividad
            activity_defaults = {
                'hotel': 30,           # Check-in/check-out
                'restaurant': 90,      # Comida
                'museum': 120,         # Visita museo
                'tourist_attraction': 90,  # Atracción turística
                'park': 60,           # Parque
                'cafe': 45,           # Café
                'shopping_mall': 120, # Compras
            }
            
            category = get_value(activity, 'category', get_value(activity, 'type', 'point_of_interest'))
            return activity_defaults.get(category, 60)  # 1 hora por defecto

        def format_time_window(activity, all_activities=None, activity_index=None):
            """Formatear ventana de tiempo para actividades, especialmente transfers"""
            start_time = get_value(activity, 'start_time', 0)
            end_time = get_value(activity, 'end_time', 0)
            
            # Para transfers, calcular tiempo basado en actividad anterior si no tiene tiempos válidos
            is_transfer = (get_value(activity, 'category', '') == 'transfer' or 
                          get_value(activity, 'type', '') == 'transfer' or
                          'traslado' in str(get_value(activity, 'name', '')).lower() or
                          'viaje' in str(get_value(activity, 'name', '')).lower() or
                          'regreso' in str(get_value(activity, 'name', '')).lower())
            
            if is_transfer and (start_time == 0 or start_time == end_time) and all_activities and activity_index is not None:
                # Usar tiempo de la actividad anterior + su duración como inicio del transfer
                if activity_index > 0:
                    prev_activity = all_activities[activity_index - 1]
                    prev_end_time = get_value(prev_activity, 'end_time', 0)
                    transfer_duration = calculate_dynamic_duration_with_context(activity, all_activities, activity_index)
                    
                    if prev_end_time > 0:
                        start_time = prev_end_time
                        end_time = start_time + transfer_duration
            
            # Si aún no hay tiempos válidos, omitir best_time
            if start_time == 0 and end_time == 0:
                return None
            
            # Validar que los tiempos estén en rango válido (0-1440 minutos = 24h)
            if start_time < 0 or start_time >= 1440 or end_time < 0 or end_time >= 1440:
                return None
            
            return f"{start_time//60:02d}:{start_time%60:02d}-{end_time//60:02d}:{end_time%60:02d}"

        def calculate_dynamic_duration_with_context(activity, all_activities, activity_index):
            """Calcular duración dinámica con acceso a actividades adyacentes para inferir coordenadas"""
            # Si ya tiene duration_minutes, usarlo
            if get_value(activity, 'duration_minutes', 0) > 0:
                return get_value(activity, 'duration_minutes', 0)
            
            # Para transfers, verificar si ya tiene tiempo calculado en el nombre
            activity_name = str(get_value(activity, 'name', ''))
            activity_name_lower = activity_name.lower()
            is_transfer = (get_value(activity, 'category', '') == 'transfer' or 
                          get_value(activity, 'type', '') == 'transfer' or
                          'traslado' in activity_name_lower or 'transfer' in activity_name_lower or
                          'viaje' in activity_name_lower or 'regreso' in activity_name_lower)
            
            if is_transfer:
                # Primero verificar si el nombre ya incluye duración calculada
                import re
                minutes_match = re.search(r'\((\d+)min\)', activity_name)
                hours_match = re.search(r'\((\d+(?:\.\d+)?)h\)', activity_name)
                
                if minutes_match:
                    calculated_minutes = int(minutes_match.group(1))
                    logger.info(f"✅ Usando duración del optimizador (min): '{activity_name}' = {calculated_minutes}min")
                    return calculated_minutes
                elif hours_match:
                    calculated_hours = float(hours_match.group(1))
                    calculated_minutes = int(calculated_hours * 60)
                    logger.info(f"✅ Usando duración del optimizador (h): '{activity_name}' = {calculated_hours}h → {calculated_minutes}min")
                    return calculated_minutes
                
                # Si no hay tiempo en el nombre, intentar inferir coordenadas de actividades adyacentes
                origin_coords = None
                dest_coords = None
                
                # Actividad anterior (origen del transfer)
                if activity_index > 0:
                    prev_activity = all_activities[activity_index - 1]
                    prev_lat = get_value(prev_activity, 'lat', 0.0)
                    prev_lon = get_value(prev_activity, 'lon', 0.0)
                    if prev_lat != 0.0 and prev_lon != 0.0:
                        origin_coords = (prev_lat, prev_lon)
                
                # Actividad siguiente (destino del transfer)
                if activity_index < len(all_activities) - 1:
                    next_activity = all_activities[activity_index + 1]
                    next_lat = get_value(next_activity, 'lat', 0.0)
                    next_lon = get_value(next_activity, 'lon', 0.0)
                    if next_lat != 0.0 and next_lon != 0.0:
                        dest_coords = (next_lat, next_lon)
                
                # Calcular distancia si tenemos ambas coordenadas
                if origin_coords and dest_coords:
                    from utils.geo_utils import haversine_km
                    distance_km = haversine_km(origin_coords[0], origin_coords[1], dest_coords[0], dest_coords[1])
                    
                    # Velocidades realistas por modo de transporte
                    transport_mode = get_value(activity, 'transport_mode', request.transport_mode if hasattr(request, 'transport_mode') else 'drive')
                    speeds = {
                        'walk': 4.5,      # 4.5 km/h caminando
                        'walking': 4.5,
                        'drive': 45.0,    # 45 km/h en ciudad/carretera
                        'car': 45.0,
                        'transit': 30.0,  # 30 km/h transporte público
                        'bicycle': 15.0   # 15 km/h bicicleta
                    }
                    
                    speed_kmh = speeds.get(transport_mode, 45.0)
                    duration_minutes = (distance_km / speed_kmh) * 60
                    
                    # Buffer adicional para transfers largos
                    if distance_km > 30:  # Intercity
                        duration_minutes *= 1.2  # 20% buffer
                    else:  # Urbano
                        duration_minutes *= 1.1  # 10% buffer
                    
                    calculated_time = max(5, int(duration_minutes))
                    logger.info(f"✅ Transfer dinámico calculado: '{activity_name}' = {distance_km:.2f}km → {calculated_time}min ({transport_mode})")
                    return calculated_time
                else:
                    # Fallback para transfers sin coordenadas
                    transport_mode = get_value(activity, 'transport_mode', request.transport_mode if hasattr(request, 'transport_mode') else 'drive')
                    fallback_times = {
                        'walk': 20,    # 20 min caminando urbano
                        'walking': 20,
                        'drive': 15,   # 15 min conduciendo urbano  
                        'car': 15,
                        'transit': 25, # 25 min transporte público
                        'bicycle': 12  # 12 min bicicleta
                    }
                    fallback_time = fallback_times.get(transport_mode, 15)
                    logger.warning(f"⚠️ Transfer sin coordenadas válidas '{activity_name}' - usando fallback: {fallback_time}min")
                    return fallback_time
            
            # Valores por defecto según tipo de actividad (no transfers)
            activity_defaults = {
                'hotel': 30,           # Check-in/check-out
                'restaurant': 90,      # Comida
                'museum': 120,         # Visita museo
                'tourist_attraction': 90,  # Atracción turística
                'park': 60,           # Parque
                'cafe': 45,           # Café
                'shopping_mall': 120, # Compras
            }
            
            category = get_value(activity, 'category', get_value(activity, 'type', 'point_of_interest'))
            return activity_defaults.get(category, 60)  # 1 hora por defecto

        def format_activity_for_frontend(activity, order, all_activities=None, activity_index=None):
            """Convertir ActivityItem o IntercityActivity a formato esperado por frontend"""
            import uuid
            
            # Detectar si es una actividad intercity
            is_intercity = get_value(activity, 'is_intercity_activity', False) or get_value(activity, 'type', '') == 'intercity_activity'
            
            if is_intercity:
                # Las actividades intercity NO deben aparecer como places individuales
                # Solo aparecen en optimization_metrics.intercity_transfers
                return None
            else:
                # Detectar si es un transfer para agregar coordenadas de origen y destino
                is_transfer = (get_value(activity, 'category', '') == 'transfer' or 
                              get_value(activity, 'type', '') == 'transfer')
                
                base_data = {
                    "id": str(uuid.uuid4()),
                    "name": get_value(activity, 'name', 'Lugar sin nombre'),
                    "category": get_value(activity, 'place_type', get_value(activity, 'type', 'point_of_interest')),
                    "rating": get_value(activity, 'rating', 4.5) or 4.5,
                    "image": get_value(activity, 'image', ''),
                    "description": get_value(activity, 'description', f"Actividad en {get_value(activity, 'name', 'lugar')}"),
                    "estimated_time": f"{(calculate_dynamic_duration_with_context(activity, all_activities or [], activity_index or 0) if all_activities and activity_index is not None else calculate_dynamic_duration(activity))/60:.1f}h",
                    "priority": get_value(activity, 'priority', 5),
                    "lat": get_value(activity, 'lat', 0.0),
                    "lng": get_value(activity, 'lon', 0.0),  # Frontend espera 'lng'
                    "recommended_duration": f"{get_value(activity, 'duration_minutes', 60)/60:.1f}h",
                    "best_time": format_time_window(activity, all_activities, activity_index),
                    "order": order,
                    "is_intercity": False,
                    "quality_flag": get_value(activity, 'quality_flag', None)  # Agregar quality flag al frontend
                }
                
                # Para transfers, agregar coordenadas de origen y destino
                if is_transfer:
                    # Obtener coordenadas FROM del optimizer (si están disponibles)
                    from_lat = get_value(activity, 'from_lat', 0.0)
                    from_lng = get_value(activity, 'from_lon', 0.0)  # Intenta 'from_lon' primero
                    if from_lng == 0.0:  # Si no encuentra, intenta 'from_lng'
                        from_lng = get_value(activity, 'from_lng', 0.0)
                    
                    # Si no hay coordenadas FROM del optimizer, calcular desde el place anterior
                    if (from_lat == 0.0 and from_lng == 0.0 and all_activities and activity_index is not None):
                        if activity_index > 0:
                            # Caso normal: tomar del place anterior en el mismo día
                            prev_activity = all_activities[activity_index - 1]
                            prev_lat = get_value(prev_activity, 'lat', 0.0)
                            # Intentar ambos formatos para longitude
                            prev_lng = get_value(prev_activity, 'lng', 0.0)
                            if prev_lng == 0.0:
                                prev_lng = get_value(prev_activity, 'lon', 0.0)
                            
                            # Debug: verificar si el lugar anterior tiene coordenadas válidas
                            if prev_lat == 0.0 and prev_lng == 0.0:
                                # Si el anterior tampoco tiene coordenadas, buscar más atrás
                                for j in range(activity_index - 2, -1, -1):
                                    candidate = all_activities[j]
                                    cand_lat = get_value(candidate, 'lat', 0.0)
                                    # Intentar ambos formatos para longitude
                                    cand_lng = get_value(candidate, 'lng', 0.0)
                                    if cand_lng == 0.0:
                                        cand_lng = get_value(candidate, 'lon', 0.0)
                                    if cand_lat != 0.0 or cand_lng != 0.0:
                                        prev_lat = cand_lat
                                        prev_lng = cand_lng
                                        break
                            
                            from_lat = prev_lat
                            from_lng = prev_lng
                        elif activity_index == 0 and hasattr(format_activity_for_frontend, '_day_data'):
                            # Caso especial: primer transfer del día, buscar en día anterior
                            day_data = format_activity_for_frontend._day_data
                            current_day = day_data.get('current_day', 1)
                            
                            if current_day > 1:
                                # Buscar el último place del día anterior
                                prev_day_activities = day_data.get('prev_day_activities', [])
                                if prev_day_activities:
                                    last_prev_activity = prev_day_activities[-1]
                                    # Si el último era un transfer, usar su destino (to_lat/to_lng)
                                    if get_value(last_prev_activity, 'category') == 'transfer':
                                        from_lat = get_value(last_prev_activity, 'lat', 0.0)  # Destino del transfer anterior
                                        from_lng = get_value(last_prev_activity, 'lng', 0.0)
                                        if from_lng == 0.0:
                                            from_lng = get_value(last_prev_activity, 'lon', 0.0)
                                    else:
                                        from_lat = get_value(last_prev_activity, 'lat', 0.0)
                                        from_lng = get_value(last_prev_activity, 'lng', 0.0)
                                        if from_lng == 0.0:
                                            from_lng = get_value(last_prev_activity, 'lon', 0.0)
                    
                    base_data.update({
                        "from_lat": from_lat,
                        "from_lng": from_lng,
                        "to_lat": get_value(activity, 'lat', 0.0),  # Destino
                        "to_lng": get_value(activity, 'lon', 0.0),   # Destino (frontend espera 'lng')
                        "from_place": get_value(activity, 'from_place', ''),
                        "to_place": get_value(activity, 'to_place', ''),
                        "distance_km": get_value(activity, 'distance_km', 0.0),
                        "transport_mode": get_value(activity, 'recommended_mode', 'walk')
                    })
                
                return base_data
        
        # Convertir días a formato frontend
        itinerary_days = []
        day_counter = 1
        prev_day_activities = []
        
        for day in days_data:
            # Configurar información de contexto para transfers intercity
            format_activity_for_frontend._day_data = {
                'current_day': day_counter,
                'prev_day_activities': prev_day_activities
            }
            
            # Separar places y transfers
            frontend_places = []
            day_transfers = []
            activities = day.get("activities", [])
            place_order = 1
            transfer_order = 1
            
            for idx, activity in enumerate(activities):
                # Detectar si es un transfer
                is_transfer = (get_value(activity, 'category', '') == 'transfer' or 
                              get_value(activity, 'type', '') == 'transfer' or
                              'traslado' in str(get_value(activity, 'name', '')).lower() or
                              'viaje' in str(get_value(activity, 'name', '')).lower() or
                              'regreso' in str(get_value(activity, 'name', '')).lower())
                
                if is_transfer:
                    # Agregar a transfers del día
                    transfer_data = format_activity_for_frontend(activity, transfer_order, activities, idx)
                    if transfer_data is not None:
                        # Cambiar el campo 'order' por 'transfer_order' para claridad
                        transfer_data['transfer_order'] = transfer_order
                        del transfer_data['order']  # Remover el campo 'order' original
                        day_transfers.append(transfer_data)
                        transfer_order += 1
                else:
                    # Agregar a places del día
                    place_data = format_activity_for_frontend(activity, place_order, activities, idx)
                    if place_data is not None:
                        frontend_places.append(place_data)
                        place_order += 1
            
            # Guardar actividades de este día para el siguiente (incluir ambos types)
            prev_day_activities = frontend_places + day_transfers
            
            # Calcular tiempos del día correctamente desde frontend_places
            total_activity_time_min = 0
            transport_time_min = 0
            walking_time_min = 0
            
            for place in frontend_places:
                estimated_hours = float(place.get('estimated_time', '0h').replace('h', ''))
                estimated_minutes = estimated_hours * 60
                
                # Sumar al tiempo total
                total_activity_time_min += estimated_minutes
                
                # Clasificar entre transporte y actividades
                is_transfer = (place.get('category') == 'transfer' or 
                              'traslado' in place.get('name', '').lower() or
                              'viaje' in place.get('name', '').lower() or
                              'regreso' in place.get('name', '').lower())
                
                if is_transfer:
                    # Clasificar entre walking y transport basado en duración
                    if estimated_minutes <= 30:  # <= 30min = walking
                        walking_time_min += estimated_minutes
                    else:  # > 30min = transport
                        transport_time_min += estimated_minutes
            
            # Formatear tiempos
            total_time_hours = total_activity_time_min / 60
            walking_time = f"{int(walking_time_min)}min" if walking_time_min < 60 else f"{int(walking_time_min//60)}h{int(walking_time_min%60)}min" if walking_time_min%60 > 0 else f"{int(walking_time_min//60)}h"
            transport_time = f"{int(transport_time_min)}min" if transport_time_min < 60 else f"{int(transport_time_min//60)}h{int(transport_time_min%60)}min" if transport_time_min%60 > 0 else f"{int(transport_time_min//60)}h"
            
            # Calcular tiempo libre (horas del día - tiempo total)
            daily_start_hour = request.daily_start_hour if hasattr(request, 'daily_start_hour') else 9
            daily_end_hour = request.daily_end_hour if hasattr(request, 'daily_end_hour') else 18
            available_hours = daily_end_hour - daily_start_hour
            free_hours = max(0, available_hours - total_time_hours)
            free_time = f"{int(free_hours)}h{int((free_hours % 1) * 60)}min" if free_hours % 1 > 0 else f"{int(free_hours)}h"
            
            # Determinar si es sugerido (días libres detectados)
            is_suggested = len(day.get("activities", [])) == 0
            
            day_data = {
                "day": day_counter,
                "date": day.get("date", ""),
                "places": frontend_places,
                "transfers": day_transfers,
                "total_places": len(frontend_places),
                "total_transfers": len(day_transfers),
                "total_time": f"{total_time_hours:.1f}h",
                "walking_time": walking_time,
                "transport_time": transport_time,  # Ahora separado correctamente
                "free_time": free_time,
                "is_suggested": is_suggested,
                "is_tentative": False
            }
            
            # Base si existe (campo opcional para V3.1)
            if day.get("base"):
                day_data["base"] = day["base"]
            if day.get("free_blocks"):
                day_data["free_blocks"] = day["free_blocks"]
            
            itinerary_days.append(day_data)
            day_counter += 1
        
        # 📊 RECALCULAR MÉTRICAS GLOBALES SUMANDO LOS DÍAS
        total_transport_minutes = 0
        total_walking_minutes = 0
        
        # Convertir strings como "24min" o "1h30min" a minutos
        def parse_time_string(time_str):
            if not time_str or time_str == "0min":
                return 0
            minutes = 0
            if "h" in time_str:
                parts = time_str.split("h")
                hours = int(parts[0]) if parts[0] else 0
                minutes += hours * 60
                if len(parts) > 1 and parts[1]:
                    min_part = parts[1].replace("min", "")
                    if min_part:
                        minutes += int(min_part)
            elif "min" in time_str:
                minutes = int(time_str.replace("min", ""))
            return minutes
        
        for day in itinerary_days:
            # Extraer minutos de transport_time y walking_time
            transport_str = day.get("transport_time", "0min")
            walking_str = day.get("walking_time", "0min")
            
            total_transport_minutes += parse_time_string(transport_str)
            total_walking_minutes += parse_time_string(walking_str)
        
        total_travel_minutes = total_transport_minutes + total_walking_minutes
        
        # Estructura final para frontend
        # 📊 MÉTRICAS COMPLETAS del optimizer (incluyendo optimization_mode, fallback_active, etc.)
        # NOTA: Los aliases ya fueron corregidos temprano, usar optimization_metrics directamente
        optimizer_metrics = optimization_metrics
        
        # � CORREGIR ALIASES EN INTERCITY TRANSFERS - usar nombres reales de bases
        if 'intercity_transfers' in optimizer_metrics and itinerary_days:
            corrected_transfers = []
            
            for transfer in optimizer_metrics['intercity_transfers']:
                corrected_transfer = transfer.copy()
                
                # Buscar la base real del día de origen usando coordenadas
                from_lat = transfer.get('from_lat', 0)
                from_lon = transfer.get('from_lon', 0)
                
                # Buscar la base real del día de destino usando coordenadas  
                to_lat = transfer.get('to_lat', 0)
                to_lon = transfer.get('to_lon', 0)
                
                # Corregir nombre FROM usando bases reales
                for day in itinerary_days:
                    base = day.get('base', {})
                    if base:
                        base_lat = base.get('lat', 0)
                        base_lon = base.get('lon', 0)
                        
                        # Si las coordenadas coinciden con FROM, usar el nombre real
                        if (abs(base_lat - from_lat) < 0.01 and 
                            abs(base_lon - from_lon) < 0.01):
                            corrected_transfer['from'] = base.get('name', transfer.get('from', ''))
                        
                        # Si las coordenadas coinciden con TO, usar el nombre real
                        if (abs(base_lat - to_lat) < 0.01 and 
                            abs(base_lon - to_lon) < 0.01):
                            corrected_transfer['to'] = base.get('name', transfer.get('to', ''))
                
                corrected_transfers.append(corrected_transfer)
            
            # Reemplazar los transfers corregidos
            optimizer_metrics['intercity_transfers'] = corrected_transfers
        
        #  Calcular duración del procesamiento
        duration = time_module.time() - start_time
        
        # 🔧 CORREGIR ALIASES EN day['transfers'] TAMBIÉN
        for day in itinerary_days:
            if 'transfers' in day:
                for transfer in day['transfers']:
                    if transfer.get('type') == 'intercity_transfer':
                        # Obtener coordenadas del transfer
                        from_lat = transfer.get('from_lat', 0)
                        from_lon = transfer.get('from_lon', 0)
                        to_lat = transfer.get('to_lat', 0) 
                        to_lon = transfer.get('to_lon', 0)
                        
                        # Corregir nombres usando bases reales
                        for check_day in itinerary_days:
                            base = check_day.get('base', {})
                            if base:
                                base_lat = base.get('lat', 0)
                                base_lon = base.get('lon', 0)
                                
                                # Corregir FROM
                                if (abs(base_lat - from_lat) < 0.01 and 
                                    abs(base_lon - from_lon) < 0.01):
                                    transfer['from'] = base.get('name', transfer.get('from', ''))
                                
                                # Corregir TO
                                if (abs(base_lat - to_lat) < 0.01 and 
                                    abs(base_lon - to_lon) < 0.01):
                                    transfer['to'] = base.get('name', transfer.get('to', ''))
        
        formatted_result = {
            "itinerary": itinerary_days,
            "optimization_metrics": {
                # Métricas del optimizer (incluye optimization_mode, fallback_active, intercity_transfers, etc.)
                **optimizer_metrics,
                # Métricas adicionales calculadas en el API (recalculadas desde días)
                "total_distance_km": optimizer_metrics.get("total_distance_km", 0),
                "total_travel_time_minutes": int(total_travel_minutes),
                "transport_time_minutes": total_transport_minutes,  # Suma de transporte
                "walking_time_minutes": total_walking_minutes,     # Suma de caminata
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
        
        # ⚠️ GENERAR RECOMENDACIONES PARA LUGARES CON QUALITY FLAGS
        quality_recommendations = []
        for day in itinerary_days:
            for place in day.get("places", []):
                if place.get("quality_flag") == "user_provided_below_threshold":
                    # Lugar proporcionado por usuario con rating < 4.5
                    place_name = place.get("name", "lugar")
                    place_rating = place.get("rating", 0)
                    quality_recommendations.append(
                        f"⚠️ '{place_name}' ({place_rating}⭐) tiene rating bajo. "
                        f"Considera alternativas cercanas con mejor valoración."
                    )
        
        if quality_recommendations:
            base_recommendations.extend(quality_recommendations)
        
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

@app.post("/recommend_hotels")
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
