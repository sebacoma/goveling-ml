# api.py
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging
import asyncio
from datetime import datetime, time as dt_time, timedelta
import time as time_module

from models.schemas import Place, PlaceType, TransportMode, Coordinates, ItineraryRequest, ItineraryResponse, HotelRecommendationRequest, Activity, MultiCityOptimizationRequest, MultiCityItineraryResponse, MultiCityAnalysisRequest, MultiCityAnalysisResponse
from settings import settings
from services.hotel_recommender import HotelRecommender
from services.google_places_service import GooglePlacesService
from services.multi_city_optimizer_simple import MultiCityOptimizerSimple
from services.city_clustering_service import CityClusteringService
from utils.logging_config import setup_production_logging
from utils.performance_cache import cache_result, hash_places
from utils.hybrid_optimizer_v31 import HybridOptimizerV31
from utils.global_city2graph import global_city2graph, get_semantic_status, enhance_places_with_semantic_context
from utils.global_real_city2graph import global_real_city2graph, get_real_semantic_status, enhance_places_with_real_semantic_context, get_global_real_semantic_clustering
from services.hybrid_city2graph_service import get_hybrid_service
from utils.geo_utils import haversine_km
from services.ortools_monitoring import ortools_monitor, get_monitoring_dashboard, get_benchmark_report

# Configurar logging optimizado
logger = setup_production_logging()

# Servicio híbrido global (se inicializa al startup)
hybrid_routing_service = None

def calculate_real_route(origin_lat: float, origin_lon: float, 
                        dest_lat: float, dest_lon: float) -> Dict:
    """Calcula ruta real usando el servicio híbrido, con fallback a haversine"""
    
    # Fallback a haversine si el servicio no está disponible
    def haversine_fallback():
        distance_km = haversine_km(origin_lat, origin_lon, dest_lat, dest_lon)
        # Estimación simple de tiempo basada en distancia
        estimated_speed = 50  # km/h promedio
        travel_time_minutes = (distance_km / estimated_speed) * 60
        return {
            "distance_km": distance_km,
            "travel_time_minutes": travel_time_minutes,
            "method": "haversine_fallback",
            "estimated_speed_kmh": estimated_speed
        }
    
    service = get_or_initialize_hybrid_service()
    
    if service is None:
        logger.debug("🔄 Usando fallback haversine (servicio híbrido no disponible)")
        return haversine_fallback()
    
    try:
        result = service.route(origin_lat, origin_lon, dest_lat, dest_lon)
        
        if result:
            return {
                "distance_km": result.distance_m / 1000,
                "travel_time_minutes": result.travel_time_s / 60,
                "method": "hybrid_routing",
                "estimated_speed_kmh": result.estimated_speed_kmh,
                "highway_types": list(set(result.highway_types))
            }
        else:
            logger.debug("🔄 Ruta híbrida falló, usando fallback haversine")
            return haversine_fallback()
            
    except Exception as e:
        logger.debug(f"🔄 Error en routing híbrido: {e}, usando fallback haversine")
        return haversine_fallback()

# ========================================================================
# 🧠 CITY2GRAPH DECISION ALGORITHM - FASE 1 (NO AFECTA ENDPOINTS ACTUALES)
# ========================================================================

async def should_use_city2graph(request: ItineraryRequest) -> Dict[str, Any]:
    """
    🧠 Algoritmo inteligente para decidir qué optimizador usar
    
    Analiza la complejidad del request y determina si City2Graph agregaría valor
    vs. usar el sistema clásico (más rápido y confiable).
    
    Returns:
        Dict con decisión, score de complejidad, factores y reasoning
    """
    from utils.geo_utils import haversine_km
    
    # 🔴 Validaciones de seguridad - Master switches
    if not settings.ENABLE_CITY2GRAPH:
        return {
            "use_city2graph": False, 
            "reason": "city2graph_disabled",
            "complexity_score": 0.0,
            "factors": {}
        }
    
    # 📊 Calcular factores de complejidad
    complexity_factors = {}
    
    # Factor 1: Cantidad de lugares (peso: 3)
    places_count = len(request.places)
    complexity_factors["places_complexity"] = {
        "value": places_count,
        "score": min(places_count / settings.CITY2GRAPH_MIN_PLACES, 2.0) * 3,
        "threshold": settings.CITY2GRAPH_MIN_PLACES,
        "description": f"{places_count} lugares ({'complejo' if places_count >= settings.CITY2GRAPH_MIN_PLACES else 'simple'})"
    }
    
    # Factor 2: Duración del viaje (peso: 3)  
    trip_days = (request.end_date - request.start_date).days + 1  # +1 para incluir día final
    complexity_factors["duration_complexity"] = {
        "value": trip_days,
        "score": min(trip_days / settings.CITY2GRAPH_MIN_DAYS, 2.0) * 3,
        "threshold": settings.CITY2GRAPH_MIN_DAYS,
        "description": f"{trip_days} días ({'largo' if trip_days >= settings.CITY2GRAPH_MIN_DAYS else 'corto'})"
    }
    
    # Factor 3: Multi-ciudad detection (peso: 2)
    cities_detected = await _detect_multiple_cities_from_places(request.places)
    complexity_factors["multi_city"] = {
        "cities": cities_detected,
        "score": 2.0 if len(cities_detected) > 1 else 0.0,
        "description": f"{len(cities_detected)} ciudades detectadas: {', '.join(cities_detected) if cities_detected else 'ninguna'}"
    }
    
    # Factor 4: Tipos de lugares semánticos (peso: 1)
    semantic_types = _count_semantic_place_types(request.places)
    complexity_factors["semantic_richness"] = {
        "semantic_types": semantic_types,
        "score": min(len(semantic_types) / settings.CITY2GRAPH_SEMANTIC_TYPES_THRESHOLD, 1.0) * 1.0,
        "description": f"{len(semantic_types)} tipos semánticos: {', '.join(semantic_types) if semantic_types else 'ninguno'}"
    }
    
    # Factor 5: Distribución geográfica (peso: 1)
    geo_spread_km = _calculate_geographic_spread(request.places)
    complexity_factors["geographic_spread"] = {
        "spread_km": geo_spread_km,
        "score": min(geo_spread_km / settings.CITY2GRAPH_GEO_SPREAD_THRESHOLD_KM, 1.0) * 1.0,
        "description": f"{geo_spread_km:.1f}km dispersión geográfica"
    }
    
    # 📊 Score total (máximo: 10)
    total_score = sum(factor["score"] for factor in complexity_factors.values())
    
    # 🎯 Decisión final
    use_city2graph = total_score >= settings.CITY2GRAPH_COMPLEXITY_THRESHOLD
    
    # 🌍 Validación por ciudades habilitadas
    if use_city2graph and settings.CITY2GRAPH_CITIES:
        enabled_cities = [city.strip().lower() for city in settings.CITY2GRAPH_CITIES.split(",") if city.strip()]
        if enabled_cities:
            cities_in_enabled = [city for city in cities_detected if city.lower() in enabled_cities]
            if not cities_in_enabled:
                use_city2graph = False
                complexity_factors["city_restriction"] = {
                    "enabled_cities": enabled_cities,
                    "detected_cities": cities_detected,
                    "description": "Ciudades detectadas no están en lista habilitada"
                }
    
    return {
        "use_city2graph": use_city2graph,
        "complexity_score": round(total_score, 2),
        "factors": complexity_factors,
        "reasoning": _generate_decision_reasoning(complexity_factors, total_score, use_city2graph),
        "timestamp": datetime.now().isoformat()
    }

def _count_semantic_place_types(places: List[Dict]) -> List[str]:
    """Contar tipos de lugares semánticamente ricos que se benefician de City2Graph"""
    semantic_types = set()
    
    for place in places:
        # Extraer type del place (puede ser enum o string)
        place_type = ""
        if hasattr(place, 'type'):
            if hasattr(place.type, 'value'):
                place_type = place.type.value  # Enum
            else:
                place_type = str(place.type)   # String
        elif isinstance(place, dict) and 'type' in place:
            place_type = str(place['type'])
        
        place_type = place_type.lower()
        
        # Lugares que se benefician de análisis semántico City2Graph
        if place_type in [
            "museum", "tourist_attraction", "park", "art_gallery",
            "church", "synagogue", "mosque", "cemetery", "natural_feature",
            "university", "library", "town_hall", "courthouse",
            "locality", "neighborhood", "sublocality", "administrative_area",
            "cultural_center", "historical_site", "monument"
        ]:
            semantic_types.add(place_type)
    
    return list(semantic_types)

async def _detect_multiple_cities_from_places(places: List[Dict]) -> List[str]:
    """Detectar si el itinerario cruza múltiples ciudades"""
    cities = set()
    
    for place in places:
        # Extraer ciudad del nombre o coordenadas
        city = await _extract_city_from_place(place)
        if city:
            cities.add(city.lower())
    
    return list(cities)

async def _extract_city_from_place(place: Dict) -> Optional[str]:
    """Extraer ciudad de un lugar (por nombre o coordenadas)"""
    
    # Método 1: Extraer de nombre del lugar
    if hasattr(place, 'name'):
        place_name = place.name
    elif isinstance(place, dict) and 'name' in place:
        place_name = place['name']
    else:
        place_name = ""
    
    # Ciudades chilenas conocidas en nombres
    known_cities = [
        "santiago", "valparaíso", "viña", "concepción", "antofagasta", 
        "la serena", "iquique", "puerto montt", "temuco", "rancagua",
        "talca", "arica", "chillán", "osorno", "calama", "copiapó",
        "valdivia", "punta arenas", "quilpué", "curicó"
    ]
    
    place_name_lower = place_name.lower()
    for city in known_cities:
        if city in place_name_lower:
            return city
    
    # Método 2: TODO - Reverse geocoding con coordenadas (implementar si es necesario)
    # Por ahora retornar None si no se detecta ciudad en nombre
    
    return None

def _calculate_geographic_spread(places: List[Dict]) -> float:
    """Calcular dispersión geográfica máxima en km"""
    from utils.geo_utils import haversine_km
    
    if len(places) < 2:
        return 0.0
    
    coordinates = []
    for place in places:
        # Extraer coordenadas del place
        lat, lon = None, None
        
        if hasattr(place, 'coordinates'):
            if hasattr(place.coordinates, 'latitude'):
                lat, lon = place.coordinates.latitude, place.coordinates.longitude
            elif isinstance(place.coordinates, dict):
                lat, lon = place.coordinates.get('latitude'), place.coordinates.get('longitude')
        elif isinstance(place, dict) and 'coordinates' in place:
            coords = place['coordinates']
            if isinstance(coords, dict):
                lat, lon = coords.get('latitude'), coords.get('longitude')
        
        if lat is not None and lon is not None:
            coordinates.append((float(lat), float(lon)))
    
    if len(coordinates) < 2:
        return 0.0
    
    # Calcular distancia máxima entre cualquier par de lugares
    max_distance = 0.0
    for i in range(len(coordinates)):
        for j in range(i + 1, len(coordinates)):
            distance = haversine_km(
                coordinates[i][0], coordinates[i][1],
                coordinates[j][0], coordinates[j][1]
            )
            max_distance = max(max_distance, distance)
    
    return max_distance

def _generate_decision_reasoning(factors: Dict, total_score: float, use_city2graph: bool) -> str:
    """Generar explicación human-readable de la decisión"""
    
    reasoning_parts = []
    
    # Factores principales que influyen
    high_impact_factors = []
    for factor_name, factor_data in factors.items():
        if factor_data.get("score", 0) >= 1.0:
            high_impact_factors.append(factor_data.get("description", factor_name))
    
    if high_impact_factors:
        reasoning_parts.append(f"Factores de complejidad: {'; '.join(high_impact_factors)}")
    
    # Decisión y justificación
    threshold = settings.CITY2GRAPH_COMPLEXITY_THRESHOLD
    if use_city2graph:
        reasoning_parts.append(f"Score {total_score:.1f} ≥ {threshold} → City2Graph recomendado para análisis profundo")
    else:
        reasoning_parts.append(f"Score {total_score:.1f} < {threshold} → Sistema clásico óptimo (rápido y confiable)")
    
    return ". ".join(reasoning_parts)

# ========================================================================

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

# ========================================================================
# 🧠 CITY2GRAPH TESTING ENDPOINTS - FASE 1 (PARA VALIDACIÓN)
# ========================================================================

@app.get("/city2graph/config")
async def get_city2graph_config():
    """Obtener configuración actual de City2Graph (para debugging)"""
    return {
        "enabled": settings.ENABLE_CITY2GRAPH,
        "min_places": settings.CITY2GRAPH_MIN_PLACES,
        "min_days": settings.CITY2GRAPH_MIN_DAYS,
        "complexity_threshold": settings.CITY2GRAPH_COMPLEXITY_THRESHOLD,
        "enabled_cities": settings.CITY2GRAPH_CITIES.split(",") if settings.CITY2GRAPH_CITIES else [],
        "timeout_s": settings.CITY2GRAPH_TIMEOUT_S,
        "fallback_enabled": settings.CITY2GRAPH_FALLBACK_ENABLED,
        "user_percentage": settings.CITY2GRAPH_USER_PERCENTAGE,
        "track_decisions": settings.CITY2GRAPH_TRACK_DECISIONS
    }

@app.post("/city2graph/test-decision")
async def test_city2graph_decision(request: ItineraryRequest):
    """
    🧪 Testing endpoint para probar algoritmo de decisión City2Graph
    
    NO AFECTA el sistema productivo - solo retorna qué decisión tomaría
    """
    try:
        decision = await should_use_city2graph(request)
        
        # Log para debugging si está habilitado
        if settings.DEBUG:
            logger.info(f"🧪 Test decisión City2Graph: {decision['use_city2graph']} (score: {decision['complexity_score']})")
        
        return {
            "status": "success",
            "decision": decision,
            "request_summary": {
                "places_count": len(request.places),
                "trip_days": (request.end_date - request.start_date).days + 1,
                "start_date": request.start_date.isoformat(),
                "end_date": request.end_date.isoformat()
            },
            "note": "Esta es solo una simulación - no afecta el sistema productivo"
        }
        
    except Exception as e:
        logger.error(f"❌ Error en test de decisión: {e}")
        raise HTTPException(status_code=500, detail=f"Error en algoritmo de decisión: {str(e)}")

@app.get("/city2graph/stats")
async def get_city2graph_stats():
    """Estadísticas de uso de City2Graph (placeholder para métricas futuras)"""
    return {
        "status": "phase_2",
        "message": "Dual optimizer architecture implementada con Circuit Breaker",
        "current_config": {
            "enabled": settings.ENABLE_CITY2GRAPH,
            "cities_enabled": settings.CITY2GRAPH_CITIES,
            "complexity_threshold": settings.CITY2GRAPH_COMPLEXITY_THRESHOLD,
            "circuit_breaker_enabled": True
        },
        "next_phase": "Integration Testing & Performance Benchmarks"
    }

@app.get("/city2graph/circuit-breaker")
async def get_circuit_breaker_status():
    """
    🔌 Endpoint para monitorear estado del Circuit Breaker de City2Graph
    
    Útil para debugging, monitoring y dashboards de operación
    """
    try:
        # Importar función del optimizador
        from utils.hybrid_optimizer_v31 import get_circuit_breaker_status
        
        status = get_circuit_breaker_status()
        
        # Calcular tiempo desde último fallo si existe
        import time
        time_since_failure = None
        if status.get("last_failure_time"):
            time_since_failure = time.time() - status["last_failure_time"]
        
        return {
            "circuit_breaker_status": status,
            "time_since_last_failure_s": time_since_failure,
            "is_healthy": status.get("state") == "CLOSED",
            "config": {
                "failure_threshold": settings.CITY2GRAPH_FAILURE_THRESHOLD,
                "recovery_timeout": settings.CITY2GRAPH_RECOVERY_TIMEOUT,
                "timeout_s": settings.CITY2GRAPH_TIMEOUT_S,
                "fallback_enabled": settings.CITY2GRAPH_FALLBACK_ENABLED
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except ImportError as e:
        return {
            "error": "circuit_breaker_not_available",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "error": "circuit_breaker_error", 
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }

# ========================================================================

@app.on_event("startup")
async def startup_event():
    """Inicializar servicios básicos al startup de la API"""
    global hybrid_routing_service
    logger.info("🚀 API iniciada - Servicio híbrido se cargará on-demand")
    # No cargar el servicio híbrido al startup para mantener inicio rápido
    hybrid_routing_service = None

def get_or_initialize_hybrid_service():
    """Obtiene o inicializa el servicio híbrido (lazy loading)"""
    global hybrid_routing_service
    
    if hybrid_routing_service is None:
        try:
            logger.info("� Inicializando servicio híbrido (primera consulta)...")
            hybrid_routing_service = get_hybrid_service()
            logger.info("✅ Servicio híbrido inicializado correctamente")
        except Exception as e:
            logger.error(f"❌ Error inicializando servicio híbrido: {e}")
            hybrid_routing_service = "failed"  # Marcar como fallado
    
    return hybrid_routing_service if hybrid_routing_service != "failed" else None

@app.get("/routing/status")
async def routing_status():
    """Estado del servicio de routing híbrido"""
    service = get_or_initialize_hybrid_service()
    
    if service is None:
        return {
            "status": "not_ready",
            "message": "Servicio híbrido no disponible o falló al inicializar"
        }
    
    stats = service.get_stats()
    return {
        "status": "ready", 
        "service": "hybrid_city2graph",
        "stats": stats,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/route")
async def calculate_route(request: dict):
    """Calcular ruta entre dos puntos usando el servicio híbrido"""
    service = get_or_initialize_hybrid_service()
    
    if service is None:
        raise HTTPException(status_code=503, detail="Servicio de routing no disponible")
    
    try:
        origin_lat = request["origin"]["lat"]
        origin_lon = request["origin"]["lon"]
        dest_lat = request["destination"]["lat"]
        dest_lon = request["destination"]["lon"]
        
        result = service.route(origin_lat, origin_lon, dest_lat, dest_lon)
        
        if not result:
            raise HTTPException(status_code=404, detail="No se encontró ruta")
        
        # Obtener coordenadas de la ruta
        coordinates = service.get_route_coordinates(result)
        
        return {
            "status": "success",
            "route": {
                "distance_km": round(result.distance_m / 1000, 2),
                "travel_time_minutes": round(result.travel_time_s / 60, 1),
                "estimated_speed_kmh": round(result.estimated_speed_kmh, 1),
                "highway_types": list(set(result.highway_types)),
                "coordinates": coordinates[:50] if len(coordinates) > 50 else coordinates  # Limitar para API
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Campo requerido faltante: {e}")
    except Exception as e:
        logger.error(f"Error calculando ruta: {e}")
        raise HTTPException(status_code=500, detail="Error interno calculando ruta")

@app.get("/semantic/status")
async def semantic_status():
    """🧠 Estado del sistema semántico City2Graph (Demo y REAL)"""
    semantic_info = get_semantic_status()
    real_semantic_info = get_real_semantic_status()
    
    return {
        "semantic_enabled": semantic_info['enabled'],
        "service_status": semantic_info['service_status'],
        "features": semantic_info['features'],
        "real_osm_enabled": real_semantic_info['enabled'],
        "real_service_status": real_semantic_info['service_status'],
        "real_features": real_semantic_info['features'],
        "capabilities": {
            "semantic_clustering": "Agrupación inteligente por contexto urbano",
            "walkability_scoring": "Puntuación precisa de caminabilidad",
            "poi_discovery": "Descubrimiento contextual de lugares",
            "cultural_context": "Adaptación a normas culturales locales",
            "district_analysis": "Análisis semántico de distritos urbanos",
            "real_osm_data": "Descarga y análisis de datos OSM reales (sin timeout)" if real_semantic_info['enabled'] else "No disponible"
        },
        "timestamp": datetime.now().isoformat()
    }

@app.post("/semantic/analyze")
async def semantic_analyze_places(places: List[Place]):
    """🧠 Análisis semántico detallado de lugares (Demo)"""
    try:
        # Convertir places a formato dict
        places_data = []
        for place in places:
            place_dict = {
                'name': place.name,
                'lat': place.lat,
                'lon': place.lon,
                'type': place.type.value if hasattr(place.type, 'value') else str(place.type),
                'rating': getattr(place, 'rating', 4.5),
                'priority': getattr(place, 'priority', 5)
            }
            places_data.append(place_dict)
        
        # Enriquecer con contexto semántico
        enhanced_places = await enhance_places_with_semantic_context(places_data)
        
        # Obtener clustering semántico
        from utils.global_city2graph import get_global_semantic_clustering
        clustering_result = await get_global_semantic_clustering(places_data)
        
        return {
            "places_analyzed": len(places_data),
            "enhanced_places": enhanced_places,
            "semantic_clustering": clustering_result,
            "analysis_summary": {
                "semantic_strategy": clustering_result.get('strategy', 'unknown'),
                "districts_found": len(clustering_result.get('recommendations', [])),
                "optimization_insights": clustering_result.get('optimization_insights', []),
                "total_semantic_districts": len([p for p in enhanced_places if p.get('semantic_district', 'Unknown') != 'Unknown'])
            },
            "data_source": "demo_simulated",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error en análisis semántico: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error en análisis semántico: {str(e)}"
        )

@app.post("/semantic/analyze-real")
async def semantic_analyze_places_real(places: List[Place]):
    """🌍 Análisis semántico con datos OSM REALES (sin timeout)"""
    try:
        # Convertir places a formato dict
        places_data = []
        for place in places:
            place_dict = {
                'name': place.name,
                'lat': place.lat,
                'lon': place.lon,
                'type': place.type.value if hasattr(place.type, 'value') else str(place.type),
                'rating': getattr(place, 'rating', 4.5),
                'priority': getattr(place, 'priority', 5)
            }
            places_data.append(place_dict)
        
        # Enriquecer con contexto semántico REAL
        enhanced_places = await enhance_places_with_real_semantic_context(places_data)
        
        # Obtener clustering semántico REAL
        clustering_result = await get_global_real_semantic_clustering(places_data)
        
        return {
            "places_analyzed": len(places_data),
            "enhanced_places": enhanced_places,
            "semantic_clustering": clustering_result,
            "analysis_summary": {
                "semantic_strategy": clustering_result.get('strategy', 'unknown'),
                "districts_found": len(clustering_result.get('recommendations', [])),
                "optimization_insights": clustering_result.get('optimization_insights', []),
                "total_semantic_districts": len([p for p in enhanced_places if p.get('semantic_district', 'Unknown') != 'Unknown']),
                "total_real_pois": clustering_result.get('total_real_pois_analyzed', 0),
                "street_network_size": clustering_result.get('street_network_size', 0),
                "transport_network_size": clustering_result.get('transport_network_size', 0)
            },
            "data_source": "openstreetmap_complete",
            "processing_note": "Este análisis puede tomar varios minutos - descarga datos OSM reales",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error en análisis semántico REAL: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error en análisis semántico REAL: {str(e)}"
        )

@app.get("/semantic/city/{city_name}")
async def semantic_city_summary(city_name: str):
    """🏙️ Resumen semántico completo de una ciudad (Demo)"""
    try:
        # Obtener resumen de la ciudad desde el manager global
        summary = await global_city2graph.get_city_summary(city_name)
        
        return {
            "city": city_name,
            "city_summary": summary,
            "semantic_available": global_city2graph.is_semantic_enabled(),
            "data_source": "demo_simulated",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo resumen de {city_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo resumen semántico de {city_name}: {str(e)}"
        )

@app.get("/semantic/city-real/{city_name}")
async def semantic_city_summary_real(city_name: str):
    """🌍 Resumen semántico con datos OSM REALES de una ciudad"""
    try:
        # Obtener resumen de la ciudad REAL desde el manager global
        summary = await global_real_city2graph.get_real_city_summary(city_name)
        
        return {
            "city": city_name,
            "city_summary": summary,
            "real_semantic_available": global_real_city2graph.is_real_semantic_enabled(),
            "data_source": "openstreetmap_complete",
            "processing_note": "Este análisis descarga datos OSM reales - puede tomar tiempo",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo resumen REAL de {city_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo resumen semántico REAL de {city_name}: {str(e)}"
        )

# Variable global para controlar qué tipo de análisis usar
SEMANTIC_MODE = "auto"  # "demo", "real", "auto"

@app.post("/semantic/config")
async def set_semantic_mode(mode: str):
    """⚙️ Configurar modo de análisis semántico: demo, real, o auto"""
    global SEMANTIC_MODE
    
    valid_modes = ["demo", "real", "auto"]
    if mode not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"Modo inválido. Opciones válidas: {valid_modes}"
        )
    
    SEMANTIC_MODE = mode
    
    return {
        "mode_set": mode,
        "description": {
            "demo": "Usa datos simulados - rápido y confiable",
            "real": "Descarga datos OSM reales - completo pero lento",
            "auto": "Usa real si está disponible, sino demo"
        }.get(mode, ""),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/semantic/config")
async def get_semantic_mode():
    """⚙️ Obtener configuración actual del modo semántico"""
    return {
        "current_mode": SEMANTIC_MODE,
        "demo_available": get_semantic_status()['enabled'],
        "real_available": get_real_semantic_status()['enabled'],
        "timestamp": datetime.now().isoformat()
    }

@app.get("/cache/stats", tags=["Cache Management"])
async def get_cache_stats():
    """Obtener estadísticas del sistema de caché geográfico"""
    try:
        from services.google_places_service import GooglePlacesService
        places_service = GooglePlacesService()
        
        stats = places_service.get_cache_stats()
        
        return {
            "success": True,
            "cache_stats": stats,
            "recommendations": [
                f"Hit rate actual: {stats['cache_performance']['hit_rate_percentage']}%",
                f"Costo ahorrado: ${stats['cache_performance']['estimated_cost_saved_usd']:.3f} USD",
                "80-90% de reducción esperada con uso continuo"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo stats de caché: {e}")
        return {
            "success": False,
            "error": str(e),
            "cache_stats": None
        }

@app.post("/cache/clear", tags=["Cache Management"])
async def clear_cache(older_than_hours: float = 24.0):
    """Limpiar caché manualmente"""
    try:
        from utils.geographic_cache_manager import get_cache_manager
        cache_manager = get_cache_manager()
        
        cleared_count = cache_manager.clear_cache(older_than_hours=older_than_hours)
        
        return {
            "success": True,
            "cleared_entries": cleared_count,
            "message": f"Limpiadas {cleared_count} entradas > {older_than_hours}h"
        }
        
    except Exception as e:
        logger.error(f"Error limpiando caché: {e}")
        return {
            "success": False,
            "error": str(e)
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
        
        # 🔍 Detectar y consolidar TODOS los hoteles/alojamientos
        accommodations_data = []
        hotels_provided = False
        
        # 1. Procesar accommodations del campo dedicado
        if request.accommodations:
            try:
                for acc in request.accommodations:
                    if hasattr(acc, 'model_dump'):
                        accommodations_data.append(acc.model_dump())
                    elif hasattr(acc, 'dict'):
                        accommodations_data.append(acc.dict())
                    else:
                        accommodations_data.append(acc)
            except Exception as e:
                logger.warning(f"Error procesando request.accommodations: {e}")
        
        # 2. Procesar accommodations que vienen en places
        if accommodations_in_places:
            logger.info(f"🏨 Encontrados {len(accommodations_in_places)} accommodations en places")
            for acc_place in accommodations_in_places:
                logger.info(f"🏨 Agregando accommodation desde places: {acc_place.get('name', 'Sin nombre')}")
                accommodations_data.append(acc_place)
        
        # 3. Verificar si tenemos accommodations del usuario
        hotels_provided = len(accommodations_data) > 0
        
        # 🧠 ANÁLISIS SEMÁNTICO AUTOMÁTICO
        semantic_enabled = global_city2graph.is_semantic_enabled()
        if semantic_enabled:
            logger.info("🧠 Enriqueciendo lugares con contexto semántico")
            try:
                normalized_places = await enhance_places_with_semantic_context(normalized_places)
                logger.info(f"✅ {len(normalized_places)} lugares enriquecidos con contexto semántico")
            except Exception as e:
                logger.warning(f"⚠️ Error en enriquecimiento semántico: {e}")
        else:
            logger.info("🔴 Sistema semántico no disponible - usando análisis geográfico básico")
        
        logger.info(f"🚀 Iniciando optimización V3.1 ENHANCED {'CON SEMÁNTICA' if semantic_enabled else 'BÁSICA'} para {len(normalized_places)} lugares")
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
        
        # 🧠 AÑADIR INFORMACIÓN SEMÁNTICA A RECOMENDACIONES
        if semantic_info['enabled']:
            base_recommendations.append("🧠 Análisis SEMÁNTICO activado - Clustering inteligente por contexto urbano")
            if semantic_info['features']['initialized_cities']:
                cities = ', '.join(semantic_info['features']['initialized_cities'])
                base_recommendations.append(f"🏙️ Ciudades analizadas semánticamente: {cities}")
        else:
            base_recommendations.append("🔴 Análisis semántico no disponible - usando clustering geográfico básico")
        
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
                    # Velocidades realistas por modo
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
        
        # 🧠 OBTENER INFORMACIÓN SEMÁNTICA GLOBAL
        semantic_info = get_semantic_status()
        
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
                "optimization_mode": "hotel_centroid" if hotels_provided else optimizer_metrics.get("optimization_mode", "geographic_v31"),
                # 🧠 INFORMACIÓN SEMÁNTICA
                "semantic_enabled": semantic_info['enabled'],
                "semantic_features_used": semantic_info['features'] if semantic_info['enabled'] else None,
                "analysis_type": "semantic_enhanced" if semantic_info['enabled'] else "geographic_basic"
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

# ===== MULTI-CIUDAD ENDPOINTS =====

@app.post("/api/v3/multi-city/analyze", response_model=MultiCityAnalysisResponse, tags=["Multi-Ciudad"])
async def analyze_multi_city_feasibility(request: MultiCityAnalysisRequest):
    """
    🌍 Análisis de viabilidad multi-ciudad
    
    Analiza un conjunto de POIs para determinar:
    - Número de ciudades/países detectados
    - Complejidad del viaje 
    - Duración recomendada
    - Estrategia de optimización sugerida
    """
    try:
        start_time = time_module.time()
        
        # Convertir places a formato interno
        pois = []
        for place in request.places:
            poi_data = {
                'name': place.name,
                'lat': place.lat,
                'lon': place.lon,
                'category': 'attraction'
            }
            
            # Añadir campos opcionales si existen
            if hasattr(place, 'city') and place.city:
                poi_data['city'] = place.city
            if hasattr(place, 'country') and place.country:
                poi_data['country'] = place.country
            if hasattr(place, 'category') and place.category:
                poi_data['category'] = place.category
                
            pois.append(poi_data)
        
        # Inicializar servicios
        clustering_service = CityClusteringService()
        
        # Clustering de ciudades
        city_clusters = clustering_service.cluster_pois_advanced(pois)
        
        # Análisis de complejidad usando InterCity Service
        from services.intercity_service import InterCityService
        intercity_service = InterCityService()
        
        # Convertir clusters a Cities
        cities = []
        for cluster in city_clusters:
            from services.intercity_service import City
            city = City(
                name=cluster.name,
                center_lat=cluster.center_lat,
                center_lon=cluster.center_lon,
                country=cluster.country,
                pois=cluster.pois
            )
            cities.append(city)
        
        # Análisis de complejidad
        analysis = intercity_service.analyze_multi_city_complexity(cities)
        
        processing_time = (time_module.time() - start_time) * 1000
        
        # Calcular score de viabilidad
        feasibility_score = min(1.0, 1.0 - (analysis.get('max_intercity_distance_km', 0) / 3000.0))
        
        # Generar warnings
        warnings = []
        if analysis.get('max_intercity_distance_km', 0) > 1500:
            warnings.append("Distancias muy largas entre ciudades - considerar vuelos")
        if analysis.get('total_countries', 0) > 3:
            warnings.append("Viaje multi-país complejo - requiere planificación avanzada")
        if len(pois) > 20:
            warnings.append("Muchos POIs - considerar extender duración del viaje")
            
        # Mapear complexity a valores válidos
        complexity_map = {
            'simple_intercity': 'simple',
            'medium_intercity': 'intercity', 
            'complex_intercity': 'international',
            'international_complex': 'international_complex'
        }
        
        return MultiCityAnalysisResponse(
            cities_detected=analysis['total_cities'],
            countries_detected=analysis.get('total_countries', 1),
            max_intercity_distance_km=analysis.get('max_intercity_distance_km', 0),
            complexity_level=complexity_map.get(analysis['complexity'], 'complex'),
            recommended_duration_days=analysis.get('estimated_trip_days', 7),
            optimization_recommendation=analysis['recommendation'],
            feasibility_score=feasibility_score,
            warnings=warnings
        )
        
    except Exception as e:
        logger.error(f"Error en análisis multi-ciudad: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing multi-city feasibility: {str(e)}"
        )

@app.post("/api/v3/multi-city/optimize", response_model=MultiCityItineraryResponse, tags=["Multi-Ciudad"])
async def optimize_multi_city_itinerary(request: MultiCityOptimizationRequest):
    """
    🎯 Optimización completa de itinerario multi-ciudad
    
    Genera un itinerario optimizado usando la arquitectura grafo-de-grafos:
    - Clustering automático de POIs por ciudades
    - Optimización de secuencia intercity (TSP)
    - Distribución inteligente de días por ciudad
    - Planificación de accommodations
    - Análisis logístico completo
    """
    try:
        start_time = time_module.time()
        
        # Convertir request a formato interno
        pois = []
        for place in request.places:
            poi_data = {
                'name': place.name,
                'lat': place.lat,
                'lon': place.lon,
                'category': 'attraction',
                'visit_duration_hours': 2
            }
            
            # Añadir campos opcionales si existen
            if hasattr(place, 'city') and place.city:
                poi_data['city'] = place.city
            if hasattr(place, 'country') and place.country:
                poi_data['country'] = place.country
            if hasattr(place, 'category') and place.category:
                poi_data['category'] = place.category
            if hasattr(place, 'visit_duration_hours'):
                poi_data['visit_duration_hours'] = place.visit_duration_hours
                
            pois.append(poi_data)
        
        # Inicializar optimizador multi-ciudad
        optimizer = MultiCityOptimizerSimple()
        
        # Optimización principal
        itinerary = optimizer.optimize_multi_city_itinerary(
            pois=pois,
            trip_duration_days=request.duration_days,
            start_city=request.start_city
        )
        
        # Planificación de accommodations si se solicita
        accommodations_info = []
        estimated_cost = 0.0
        
        if request.include_accommodations:
            hotel_service = HotelRecommender()
            
            # Preparar ciudades para hotel service
            cities_for_hotels = []
            for city in itinerary.cities:
                cities_for_hotels.append({
                    'name': city.name,
                    'pois': city.pois,
                    'coordinates': city.coordinates
                })
            
            # Calcular días por ciudad
            days_per_city = {}
            for city in itinerary.cities:
                city_days = sum(
                    1 for day_pois in itinerary.daily_schedules.values()
                    if any(poi.get('city') == city.name for poi in day_pois)
                )
                days_per_city[city.name] = max(1, city_days)
            
            # Planificar accommodations
            accommodation_plan = hotel_service.plan_multi_city_accommodations(
                cities_for_hotels, days_per_city
            )
            
            # Convertir a formato de respuesta
            for acc in accommodation_plan.accommodations:
                hotel = acc['hotel']
                accommodations_info.append({
                    'city': acc['city'],
                    'hotel_name': hotel.name,
                    'rating': hotel.rating,
                    'price_range': hotel.price_range,
                    'nights': acc['nights'],
                    'check_in_day': acc['check_in_day'],
                    'check_out_day': acc['check_out_day'],
                    'estimated_cost_usd': 120.0 * acc['nights'],  # Estimación básica
                    'coordinates': {
                        'latitude': hotel.lat,
                        'longitude': hotel.lon
                    }
                })
            
            estimated_cost = accommodation_plan.estimated_cost
        
        # Convertir ciudades a formato de respuesta
        cities_info = []
        for city in itinerary.cities:
            cities_info.append({
                'name': city.name,
                'country': city.country,
                'coordinates': {
                    'latitude': city.center_lat,
                    'longitude': city.center_lon
                },
                'pois_count': len(city.pois),
                'assigned_days': sum(
                    1 for day_pois in itinerary.daily_schedules.values()
                    if any(poi.get('city') == city.name for poi in day_pois)
                )
            })
        
        processing_time = (time_module.time() - start_time) * 1000
        
        return MultiCityItineraryResponse(
            success=True,
            cities=cities_info,
            city_sequence=itinerary.get_city_sequence(),
            daily_schedule=itinerary.daily_schedules,
            accommodations=accommodations_info,
            total_duration_days=itinerary.total_duration_days,
            countries_count=itinerary.countries_count,
            total_distance_km=itinerary.total_distance_km,
            estimated_accommodation_cost_usd=estimated_cost,
            optimization_strategy=itinerary.optimization_strategy.value,
            confidence=itinerary.confidence,
            processing_time_ms=processing_time,
            logistics={
                'complexity': 'multi_city',
                'intercity_routes_count': len(itinerary.intercity_routes),
                'avg_pois_per_city': len(pois) / len(itinerary.cities) if itinerary.cities else 0
            }
        )
        
    except Exception as e:
        logger.error(f"Error en optimización multi-ciudad: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error optimizing multi-city itinerary: {str(e)}"
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


# ========================================================================
# 📊 OR-TOOLS MONITORING & ANALYTICS ENDPOINTS - WEEK 4
# ========================================================================

@app.get("/api/v4/monitoring/dashboard", tags=["OR-Tools Monitoring"])
async def get_ortools_monitoring_dashboard():
    """
    Get comprehensive OR-Tools monitoring dashboard
    Week 4: Real-time performance metrics, success rates, alerts
    """
    try:
        start_time = time_module.time()
        dashboard_data = await get_monitoring_dashboard()
        
        duration = time_module.time() - start_time
        dashboard_data["query_time_ms"] = round(duration * 1000, 2)
        
        logging.info(f"📊 Monitoring dashboard generated in {duration:.3f}s")
        return dashboard_data
        
    except Exception as e:
        logging.error(f"❌ Error getting monitoring dashboard: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving monitoring dashboard: {str(e)}"
        )

@app.get("/api/v4/monitoring/benchmark", tags=["OR-Tools Monitoring"])
async def get_ortools_benchmark_comparison():
    """
    Get OR-Tools vs Legacy benchmark comparison
    Week 4: Performance comparison, recommendations, status analysis
    """
    try:
        start_time = time_module.time()
        benchmark_data = await get_benchmark_report()
        
        duration = time_module.time() - start_time
        benchmark_data["query_time_ms"] = round(duration * 1000, 2)
        
        logging.info(f"🔬 Benchmark comparison generated in {duration:.3f}s")
        return benchmark_data
        
    except Exception as e:
        logging.error(f"❌ Error getting benchmark comparison: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving benchmark comparison: {str(e)}"
        )

@app.get("/api/v4/monitoring/alerts", tags=["OR-Tools Monitoring"])
async def get_active_alerts():
    """
    Get active OR-Tools production alerts
    Week 4: Real-time alert status, severity levels, alert history
    """
    try:
        start_time = time_module.time()
        
        # Get active alerts and recent alert history
        active_alerts = list(ortools_monitor.active_alerts.values())
        
        # Get recent alert history (last 24 hours)
        cutoff_time = datetime.now() - timedelta(hours=24)
        recent_alerts = [
            alert for alert in ortools_monitor.alert_history
            if alert['timestamp'] >= cutoff_time
        ]
        
        alert_summary = {
            "timestamp": datetime.now().isoformat(),
            "active_alerts": active_alerts,
            "active_count": len(active_alerts),
            "alert_history_24h": recent_alerts,
            "alerts_24h_count": len(recent_alerts),
            "severity_breakdown": {
                "HIGH": len([a for a in active_alerts if a.get('severity') == 'HIGH']),
                "MEDIUM": len([a for a in active_alerts if a.get('severity') == 'MEDIUM']),
                "LOW": len([a for a in active_alerts if a.get('severity') == 'LOW'])
            },
            "health_status": "CRITICAL" if any(a.get('severity') == 'HIGH' for a in active_alerts) 
                           else "WARNING" if active_alerts 
                           else "HEALTHY"
        }
        
        duration = time_module.time() - start_time
        alert_summary["query_time_ms"] = round(duration * 1000, 2)
        
        # Log alert status
        status = alert_summary["health_status"]
        if status == "CRITICAL":
            logging.error(f"🚨 CRITICAL: {len(active_alerts)} active alerts")
        elif status == "WARNING":
            logging.warning(f"⚠️ WARNING: {len(active_alerts)} active alerts")
        else:
            logging.info(f"✅ HEALTHY: No active alerts")
        
        return alert_summary
        
    except Exception as e:
        logging.error(f"❌ Error getting alerts: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving alerts: {str(e)}"
        )

@app.get("/api/v4/monitoring/health", tags=["OR-Tools Monitoring"])
async def get_ortools_health_status():
    """
    Get OR-Tools production health status
    Week 4: Quick health check, performance indicators, system status
    """
    try:
        start_time = time_module.time()
        
        # Get recent performance summary (last hour)
        summary = await ortools_monitor.get_performance_summary(hours=1)
        
        # Determine health status
        if not summary or summary.get("overview", {}).get("total_requests", 0) == 0:
            health_status = "NO_DATA"
            health_score = 0
        else:
            overview = summary["overview"]
            performance = summary["performance"]
            
            # Calculate health score (0-100)
            success_rate = overview["success_rate"]
            avg_time = performance["avg_execution_time_ms"]
            
            # Health scoring
            success_score = success_rate * 50  # 50 points for success rate
            time_score = max(0, 50 - (avg_time / 100))  # 50 points for speed (penalty for slow)
            health_score = min(100, success_score + time_score)
            
            # Determine status
            if health_score >= 90:
                health_status = "EXCELLENT"
            elif health_score >= 75:
                health_status = "GOOD"
            elif health_score >= 50:
                health_status = "DEGRADED"
            else:
                health_status = "CRITICAL"
        
        # Check for active alerts
        active_alerts_count = len(ortools_monitor.active_alerts)
        if active_alerts_count > 0:
            health_status = "ALERTS_ACTIVE"
        
        health_data = {
            "timestamp": datetime.now().isoformat(),
            "health_status": health_status,
            "health_score": round(health_score, 1),
            "active_alerts": active_alerts_count,
            "recent_metrics": summary.get("overview", {}),
            "performance_indicators": {
                "avg_response_time_ms": summary.get("performance", {}).get("avg_execution_time_ms", 0),
                "success_rate": summary.get("overview", {}).get("success_rate", 0),
                "requests_last_hour": summary.get("overview", {}).get("total_requests", 0)
            },
            "recommendations": []
        }
        
        # Add recommendations based on health
        if health_status == "CRITICAL":
            health_data["recommendations"].append("Immediate investigation required - OR-Tools severely degraded")
        elif health_status == "DEGRADED":
            health_data["recommendations"].append("Check distance cache and parallel optimizer performance")
        elif health_status == "ALERTS_ACTIVE":
            health_data["recommendations"].append("Review active alerts and take corrective action")
        elif health_status == "NO_DATA":
            health_data["recommendations"].append("No recent OR-Tools activity - monitor for traffic")
        
        duration = time_module.time() - start_time
        health_data["query_time_ms"] = round(duration * 1000, 2)
        
        # Log health status
        logging.info(f"🩺 OR-Tools Health: {health_status} (Score: {health_score:.1f}/100)")
        
        return health_data
        
    except Exception as e:
        logging.error(f"❌ Error getting health status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving health status: {str(e)}"
        )

@app.get("/api/v4/monitoring/metrics/summary", tags=["OR-Tools Monitoring"])
async def get_metrics_summary(hours: int = 24):
    """
    Get detailed OR-Tools metrics summary
    Week 4: Customizable time window, detailed statistics, method comparison
    """
    try:
        start_time = time_module.time()
        
        # Validate hours parameter
        if hours < 1 or hours > 168:  # Max 1 week
            raise HTTPException(
                status_code=400,
                detail="Hours parameter must be between 1 and 168 (1 week)"
            )
        
        summary = await ortools_monitor.get_performance_summary(hours=hours)
        
        duration = time_module.time() - start_time
        summary["query_time_ms"] = round(duration * 1000, 2)
        
        logging.info(f"📈 Metrics summary ({hours}h) generated in {duration:.3f}s")
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"❌ Error getting metrics summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving metrics summary: {str(e)}"
        )


# ========================================================================
# 🚶‍♂️🚗🚴‍♂️ MULTI-MODAL ROUTING ENDPOINTS
# ========================================================================

# Inicializar el router multi-modal (lazy loading)
chile_multimodal_router = None

def get_chile_router():
    """Obtener o inicializar el router multi-modal (lazy loading con S3 download)"""
    global chile_multimodal_router
    
    if chile_multimodal_router is None:
        try:
            from services.chile_multimodal_router import ChileMultiModalRouter
            
            # Intentar descargar grafos críticos desde S3 automáticamente
            try:
                from utils.s3_graphs_manager import S3GraphsManager
                s3_manager = S3GraphsManager()
                
                if s3_manager.s3_client:  # Solo si S3 está configurado
                    logger.info("☁️ Verificando grafos críticos en Amazon S3...")
                    s3_manager.ensure_critical_graphs()
                else:
                    logger.info("⚠️ S3 no configurado, usando grafos locales disponibles")
                    
            except Exception as s3_error:
                logger.warning(f"⚠️ S3 download falló: {s3_error} - usando grafos locales")
            
            # Inicializar router (con o sin cache S3)
            chile_multimodal_router = ChileMultiModalRouter()
            logger.info("✅ ChileMultiModalRouter inicializado correctamente")
            
        except Exception as e:
            logger.error(f"❌ Error inicializando ChileMultiModalRouter: {e}")
            chile_multimodal_router = "failed"
    
    return chile_multimodal_router if chile_multimodal_router != "failed" else None

@app.get("/health/multimodal", tags=["Multi-Modal Routing"])
async def multimodal_health_check():
    """
    🩺 Health check del sistema multi-modal con estadísticas de lazy loading
    Verifica estado de caches, memoria y performance del sistema
    """
    try:
        start_time = time_module.time()
        
        router = get_chile_router()
        
        if router is None:
            return {
                "status": "unavailable",
                "message": "Router multi-modal no disponible",
                "timestamp": datetime.now().isoformat()
            }
        
        # Verificar estado de caches (incluye estadísticas de memoria)
        cache_status = router.get_cache_status()
        memory_usage = router.get_memory_usage()
        performance_stats = router.get_performance_stats()
        
        # Calcular métricas de salud avanzadas
        total_cache_size_mb = sum(
            cache['size'] for cache in cache_status.values() 
            if cache['exists']
        )
        
        modes_available = [
            mode for mode, cache in cache_status.items() 
            if cache['exists']
        ]
        
        modes_in_memory = sum(cache.get('loaded_in_memory', False) for cache in cache_status.values())
        
        # Score de salud considerando disponibilidad y eficiencia
        availability_score = (len(modes_available) / 3) * 50  # 50 puntos por disponibilidad
        efficiency_score = 0
        
        # Score de eficiencia basado en hit ratio
        total_requests = performance_stats['performance_summary']['total_requests']
        if total_requests > 0:
            hit_ratio = performance_stats['performance_summary']['overall_hit_ratio']
            efficiency_score = hit_ratio * 50  # 50 puntos por eficiencia
        else:
            efficiency_score = 50  # Sin datos = score neutro
        
        health_score = availability_score + efficiency_score
        
        # Determinar estado de salud
        if health_score >= 90:
            health_status = "excellent"
        elif health_score >= 75:
            health_status = "good"
        elif health_score >= 50:
            health_status = "degraded"
        else:
            health_status = "critical"
        
        processing_time = time_module.time() - start_time
        
        return {
            "status": health_status,
            "health_score": round(health_score, 1),
            "modes_available": modes_available,
            "modes_in_memory": modes_in_memory,
            "total_modes": 3,
            "cache_status": cache_status,
            "memory_usage": memory_usage,
            "performance_stats": performance_stats['performance_summary'],
            "total_cache_size_mb": round(total_cache_size_mb, 2),
            "lazy_loading": {
                "enabled": True,
                "memory_efficiency": f"{memory_usage['total_estimated_mb']:.1f}MB in memory",
                "cache_hit_ratio": performance_stats['performance_summary']['overall_hit_ratio']
            },
            "performance": {
                "health_check_time_ms": round(processing_time * 1000, 2)
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error en health check multi-modal: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error en health check multi-modal: {str(e)}"
        )

# Función auxiliar para calcular duración de visita
def calculate_visit_duration(place_type: str) -> int:
    """Calcular duración de visita por tipo de lugar (en minutos)"""
    duration_map = {
        'restaurant': 90,
        'museum': 120,
        'tourist_attraction': 90,
        'park': 60,
        'cafe': 45,
        'shopping_mall': 120,
        'hotel': 30,
        'church': 45,
        'art_gallery': 90,
        'zoo': 180,
        'aquarium': 150,
        'amusement_park': 240,
        'bar': 90,
        'night_club': 180,
        'library': 60,
        'movie_theater': 150
    }
    return duration_map.get(place_type.lower(), 60)  # 60 minutos por defecto

# Función auxiliar para formatear actividades para el frontend
def format_activity_for_frontend_simple(activity, order, activities=None, idx=None):
    """Versión simplificada para el endpoint multimodal"""
    import uuid
    
    def get_value(obj, key, default=None):
        """Función helper para extraer valores robusta"""
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        else:
            # Es un objeto - usar getattr con manejo de errores
            try:
                return getattr(obj, key, default)
            except (AttributeError, TypeError):
                return default
    
    # Detectar si es un transfer intercity
    is_intercity = (get_value(activity, 'type') == 'intercity_transfer' or 
                   get_value(activity, 'activity_type') == 'intercity_transfer')
    
    if is_intercity:
        # Es un transfer - formato diferente
        return {
            "id": str(uuid.uuid4()),
            "name": get_value(activity, 'name', 'Transfer'),
            "transfer_type": "intercity",
            "from_place": get_value(activity, 'from_place', 'Origen'),
            "to_place": get_value(activity, 'to_place', 'Destino'),
            "distance_km": get_value(activity, 'distance_km', 0.0),
            "duration_minutes": get_value(activity, 'duration_minutes', 0),
            "transport_mode": get_value(activity, 'recommended_mode', 'drive'),
            "order": order
        }
    else:
        # Es un lugar normal
        duration_min = get_value(activity, 'duration_minutes', 60)
        return {
            "id": str(uuid.uuid4()),
            "name": get_value(activity, 'name', 'Lugar sin nombre'),
            "category": get_value(activity, 'type', get_value(activity, 'place_type', 'point_of_interest')),
            "rating": get_value(activity, 'rating', 4.5) or 4.5,
            "image": get_value(activity, 'image', ''),
            "description": get_value(activity, 'description', f"Visita a {get_value(activity, 'name', 'lugar')}"),
            "estimated_time": f"{duration_min/60:.1f}h",
            "duration_minutes": duration_min,
            "priority": get_value(activity, 'priority', 5),
            "lat": get_value(activity, 'lat', 0.0),
            "lng": get_value(activity, 'lon', get_value(activity, 'lng', 0.0)),
            "recommended_duration": f"{duration_min/60:.1f}h",
            "order": order,
            "walking_time_minutes": 0  # Por ahora simplificado
        }

@app.post("/itinerary/multimodal", response_model=ItineraryResponse, tags=["Multi-Modal Itinerary"])
async def generate_multimodal_itinerary_endpoint(request: ItineraryRequest):
    """
    🎯 Generar itinerario completo usando sistema multi-modal mejorado
    
    Este endpoint combina:
    - HybridOptimizerV31 para la planificación inteligente
    - ChileMultiModalRouter para rutas precisas
    - Optimización de transporte según distancias y condiciones
    """
    try:
        start_time = time_module.time()
        logger.info(f"🚀 Iniciando generación de itinerario multi-modal")
        logger.info(f"📍 {len(request.places)} lugares, modo: {request.transport_mode}")
        
        # Convertir fechas
        start_date = request.start_date if isinstance(request.start_date, datetime) else datetime.strptime(str(request.start_date), '%Y-%m-%d')
        end_date = request.end_date if isinstance(request.end_date, datetime) else datetime.strptime(str(request.end_date), '%Y-%m-%d')
        
        # Validaciones básicas
        if start_date > end_date:
            raise HTTPException(status_code=400, detail="La fecha de inicio debe ser anterior a la fecha de fin")
        
        # Normalizar lugares de entrada
        normalized_places = []
        for place in request.places:
            place_dict = place.dict() if hasattr(place, 'dict') else place
            place_dict['duration_minutes'] = place_dict.get('duration_minutes', 
                                                          calculate_visit_duration(place_dict.get('type', 'point_of_interest')))
            normalized_places.append(place_dict)
            
        # Configurar extra_info para el optimizador
        extra_info = {
            'use_multimodal_router': True,
            'max_walking_distance_km': request.max_walking_distance_km,
            'max_daily_activities': request.max_daily_activities,
            'preferences': request.preferences or {},
            'multimodal_router_instance': get_chile_router()
        }
        
        logger.info(f"🔧 Configuración multi-modal activada")
        
        # Usar el optimizador híbrido existente pero con router multi-modal
        from utils.hybrid_optimizer_v31 import optimize_itinerary_hybrid_v31
        
        optimization_result = await optimize_itinerary_hybrid_v31(
            normalized_places,
            start_date,
            end_date,
            request.daily_start_hour,
            request.daily_end_hour,
            request.transport_mode,
            request.accommodations or [],
            "balanced",  # packing_strategy
            extra_info
        )
        
        if not optimization_result or 'days' not in optimization_result:
            raise ValueError("Resultado de optimización multi-modal inválido")
            
        days_data = optimization_result['days']
        
        # Procesar días para frontend (usar la lógica existente)
        itinerary_days = []
        day_counter = 1
        prev_day_activities = []
        
        for day in days_data:
            # Separar places y transfers
            frontend_places = []
            day_transfers = []
            activities = day.get("activities", [])
            place_order = 1
            transfer_order = 1
            
            # Función auxiliar para extraer valores de manera robusta
            def get_activity_value(obj, key, default=None):
                """Función helper para extraer valores de actividades"""
                if obj is None:
                    return default
                if isinstance(obj, dict):
                    return obj.get(key, default)
                else:
                    try:
                        return getattr(obj, key, default)
                    except (AttributeError, TypeError):
                        return default
            
            for idx, activity in enumerate(activities):
                # Detectar si es un transfer
                if (get_activity_value(activity, 'type') == 'intercity_transfer' or 
                    get_activity_value(activity, 'activity_type') == 'intercity_transfer'):
                    # Es un transfer
                    transfer_data = format_activity_for_frontend_simple(activity, transfer_order, activities, idx)
                    if transfer_data is not None:
                        transfer_data['transfer_order'] = transfer_order
                        if 'order' in transfer_data:
                            del transfer_data['order']  # Remover el campo 'order' original
                        day_transfers.append(transfer_data)
                        transfer_order += 1
                else:
                    # Agregar a places del día
                    place_data = format_activity_for_frontend_simple(activity, place_order, activities, idx)
                    if place_data is not None:
                        frontend_places.append(place_data)
                        place_order += 1
            
            # Guardar actividades de este día para el siguiente
            prev_day_activities = frontend_places + day_transfers
            
            # Calcular tiempos del día
            total_activity_time_min = sum(p.get('duration_minutes', 0) for p in frontend_places)
            transport_time_min = sum(t.get('duration_minutes', 0) for t in day_transfers)
            walking_time_min = sum(p.get('walking_time_minutes', 0) for p in frontend_places)
            
            total_time_hours = (total_activity_time_min + transport_time_min) / 60.0
            free_hours = ((request.daily_end_hour - request.daily_start_hour) * 60 - 
                         total_activity_time_min - transport_time_min) / 60.0
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
                "free_time": free_time,
                "transport_time": f"{transport_time_min}min",
                "walking_time": f"{walking_time_min}min",
                "is_suggested": is_suggested,
                "base": day.get("base"),
                "free_blocks": day.get("free_blocks", []),
                "actionable_recommendations": day.get("actionable_recommendations", [])
            }
            
            itinerary_days.append(day_data)
            day_counter += 1
        
        # Calcular métricas finales
        optimization_metrics = optimization_result.get('optimization_metrics', {})
        total_activities = sum(len(day['places']) for day in itinerary_days)
        total_transfers = sum(len(day['transfers']) for day in itinerary_days)
        
        # Calcular tiempos totales
        total_transport_minutes = 0
        total_walking_minutes = 0
        
        def parse_time_string(time_str):
            if not time_str or time_str == "0min":
                return 0
            if "h" in time_str and "min" in time_str:
                parts = time_str.replace("h", " ").replace("min", "").split()
                return int(parts[0]) * 60 + int(parts[1])
            elif "h" in time_str:
                return int(time_str.replace("h", "")) * 60
            elif "min" in time_str:
                return int(time_str.replace("min", ""))
            return 0
            
        for day in itinerary_days:
            transport_str = day.get("transport_time", "0min")
            walking_str = day.get("walking_time", "0min")
            
            total_transport_minutes += parse_time_string(transport_str)
            total_walking_minutes += parse_time_string(walking_str)
        
        total_travel_minutes = total_transport_minutes + total_walking_minutes
        
        duration = time_module.time() - start_time
        
        # Información sobre el router multi-modal usado
        router = get_chile_router()
        router_stats = router.get_performance_stats() if router else {}
        
        logger.info(f"✅ Itinerario multi-modal generado en {duration:.2f}s")
        logger.info(f"📊 {total_activities} lugares, {total_transfers} transfers")
        logger.info(f"🚀 Router stats: {router_stats}")
        
        return ItineraryResponse(
            itinerary=itinerary_days,
            optimization_metrics={
                "total_places": total_activities,
                "total_days": len(itinerary_days),
                "optimization_mode": "multimodal_hybrid_v31",
                "efficiency_score": optimization_metrics.get('efficiency_score', 0.95),
                "total_travel_time_minutes": total_travel_minutes,
                "total_transport_time_minutes": total_transport_minutes,
                "total_walking_time_minutes": total_walking_minutes,
                "processing_time_seconds": round(duration, 2),
                "multimodal_router_stats": router_stats,
                "clusters_generated": optimization_metrics.get('clusters_generated', 0),
                "intercity_transfers_detected": optimization_metrics.get('long_transfers_detected', 0),
                "cache_performance": optimization_metrics.get('cache_performance', {})
            },
            recommendations=[
                f"Itinerario optimizado con sistema multi-modal",
                f"{total_activities} actividades distribuidas en {len(itinerary_days)} días",
                f"Tiempo total de viaje: {total_travel_minutes} minutos",
                f"Router multi-modal: {router_stats.get('cached_graphs', 0)} grafos en caché"
            ]
        )
        
    except Exception as e:
        logger.error(f"💥 Error en itinerario multi-modal: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generando itinerario multi-modal: {str(e)}")

@app.post("/route/drive", tags=["Multi-Modal Routing"])
async def route_drive(request: dict):
    """
    🚗 Calcular ruta en vehículo
    Utiliza cache de drive_service (1792MB) para routing vehicular
    """
    try:
        start_time = time_module.time()
        
        # Validar entrada
        required_fields = ['start_lat', 'start_lon', 'end_lat', 'end_lon']
        for field in required_fields:
            if field not in request:
                raise HTTPException(
                    status_code=400,
                    detail=f"Campo requerido faltante: {field}"
                )
        
        router = get_chile_router()
        if router is None:
            raise HTTPException(
                status_code=503,
                detail="Servicio de routing multi-modal no disponible"
            )
        
        # Calcular ruta
        route = router.get_route(
            start_lat=float(request['start_lat']),
            start_lon=float(request['start_lon']),
            end_lat=float(request['end_lat']),
            end_lon=float(request['end_lon']),
            mode='drive'
        )
        
        if not route or not route.get('success'):
            raise HTTPException(
                status_code=404,
                detail="No se pudo calcular la ruta en vehículo"
            )
        
        processing_time = time_module.time() - start_time
        
        # Agregar métricas de performance
        route['performance'] = {
            'processing_time_ms': round(processing_time * 1000, 2),
            'cache_source': 'chile_graph_cache.pkl'
        }
        
        logger.info(f"✅ Ruta drive: {route['distance_km']}km, {route['time_minutes']}min")
        
        return route
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error calculando ruta drive: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error calculando ruta en vehículo: {str(e)}"
        )

@app.post("/route/walk", tags=["Multi-Modal Routing"])
async def route_walk(request: dict):
    """
    🚶‍♂️ Calcular ruta peatonal
    Utiliza cache de walking (365MB) para routing peatonal
    """
    try:
        start_time = time_module.time()
        
        # Validar entrada
        required_fields = ['start_lat', 'start_lon', 'end_lat', 'end_lon']
        for field in required_fields:
            if field not in request:
                raise HTTPException(
                    status_code=400,
                    detail=f"Campo requerido faltante: {field}"
                )
        
        router = get_chile_router()
        if router is None:
            raise HTTPException(
                status_code=503,
                detail="Servicio de routing multi-modal no disponible"
            )
        
        # Calcular ruta
        route = router.get_route(
            start_lat=float(request['start_lat']),
            start_lon=float(request['start_lon']),
            end_lat=float(request['end_lat']),
            end_lon=float(request['end_lon']),
            mode='walk'
        )
        
        if not route or not route.get('success'):
            raise HTTPException(
                status_code=404,
                detail="No se pudo calcular la ruta peatonal"
            )
        
        processing_time = time_module.time() - start_time
        
        # Agregar métricas de performance
        route['performance'] = {
            'processing_time_ms': round(processing_time * 1000, 2),
            'cache_source': 'santiago_metro_walking_cache.pkl'
        }
        
        logger.info(f"✅ Ruta walk: {route['distance_km']}km, {route['time_minutes']}min")
        
        return route
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error calculando ruta walk: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error calculando ruta peatonal: {str(e)}"
        )

@app.post("/route/bike", tags=["Multi-Modal Routing"])
async def route_bike(request: dict):
    """
    🚴‍♂️ Calcular ruta en bicicleta
    Utiliza cache de cycling (323MB) para routing en bicicleta
    """
    try:
        start_time = time_module.time()
        
        # Validar entrada
        required_fields = ['start_lat', 'start_lon', 'end_lat', 'end_lon']
        for field in required_fields:
            if field not in request:
                raise HTTPException(
                    status_code=400,
                    detail=f"Campo requerido faltante: {field}"
                )
        
        router = get_chile_router()
        if router is None:
            raise HTTPException(
                status_code=503,
                detail="Servicio de routing multi-modal no disponible"
            )
        
        # Calcular ruta
        route = router.get_route(
            start_lat=float(request['start_lat']),
            start_lon=float(request['start_lon']),
            end_lat=float(request['end_lat']),
            end_lon=float(request['end_lon']),
            mode='bike'
        )
        
        if not route or not route.get('success'):
            raise HTTPException(
                status_code=404,
                detail="No se pudo calcular la ruta en bicicleta"
            )
        
        processing_time = time_module.time() - start_time
        
        # Agregar métricas de performance
        route['performance'] = {
            'processing_time_ms': round(processing_time * 1000, 2),
            'cache_source': 'santiago_metro_cycling_cache.pkl'
        }
        
        logger.info(f"✅ Ruta bike: {route['distance_km']}km, {route['time_minutes']}min")
        
        return route
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error calculando ruta bike: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error calculando ruta en bicicleta: {str(e)}"
        )

@app.post("/route/compare", tags=["Multi-Modal Routing"])
async def route_compare(request: dict):
    """
    ⚖️ Comparar rutas entre todos los modos de transporte
    Calcula simultáneamente rutas para drive, walk y bike
    """
    try:
        start_time = time_module.time()
        
        # Validar entrada
        required_fields = ['start_lat', 'start_lon', 'end_lat', 'end_lon']
        for field in required_fields:
            if field not in request:
                raise HTTPException(
                    status_code=400,
                    detail=f"Campo requerido faltante: {field}"
                )
        
        router = get_chile_router()
        if router is None:
            raise HTTPException(
                status_code=503,
                detail="Servicio de routing multi-modal no disponible"
            )
        
        # Calcular rutas para todos los modos
        routes = router.calculate_multimodal_routes(
            start_lat=float(request['start_lat']),
            start_lon=float(request['start_lon']),
            end_lat=float(request['end_lat']),
            end_lon=float(request['end_lon'])
        )
        
        processing_time = time_module.time() - start_time
        
        # Procesar resultados
        successful_routes = {
            mode: route for mode, route in routes.items() 
            if route and route.get('success')
        }
        
        if not successful_routes:
            raise HTTPException(
                status_code=404,
                detail="No se pudo calcular ninguna ruta"
            )
        
        # Análisis comparativo
        fastest_mode = min(
            successful_routes.keys(),
            key=lambda mode: successful_routes[mode]['time_minutes']
        )
        
        shortest_mode = min(
            successful_routes.keys(),
            key=lambda mode: successful_routes[mode]['distance_km']
        )
        
        # Recomendación inteligente
        if 'walk' in successful_routes and successful_routes['walk']['time_minutes'] <= 15:
            recommended_mode = 'walk'
            recommendation_reason = 'Distancia corta - caminar es eficiente y saludable'
        elif 'bike' in successful_routes and successful_routes['bike']['time_minutes'] <= 30:
            recommended_mode = 'bike'
            recommendation_reason = 'Distancia media - bicicleta es rápida y ecológica'
        else:
            recommended_mode = 'drive'
            recommendation_reason = 'Distancia larga - vehículo es la opción más práctica'
        
        comparison_result = {
            'routes': successful_routes,
            'analysis': {
                'fastest_mode': fastest_mode,
                'fastest_time_minutes': successful_routes[fastest_mode]['time_minutes'],
                'shortest_mode': shortest_mode,
                'shortest_distance_km': successful_routes[shortest_mode]['distance_km'],
                'recommended_mode': recommended_mode,
                'recommendation_reason': recommendation_reason,
                'modes_available': list(successful_routes.keys()),
                'modes_failed': [
                    mode for mode, route in routes.items()
                    if not route or not route.get('success')
                ]
            },
            'performance': {
                'processing_time_ms': round(processing_time * 1000, 2),
                'routes_calculated': len(successful_routes),
                'total_modes_attempted': len(routes)
            },
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(
            f"✅ Comparación multi-modal: {len(successful_routes)} rutas, "
            f"recomendado: {recommended_mode}"
        )
        
        return comparison_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en comparación multi-modal: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error comparando rutas multi-modales: {str(e)}"
        )

@app.post("/cache/preload", tags=["Multi-Modal Routing"])
async def preload_cache(request: dict):
    """
    🚀 Pre-cargar cache específico para optimización
    Body: {"mode": "drive|walk|bike"} o {"mode": "all"}
    """
    try:
        router = get_chile_router()
        if router is None:
            raise HTTPException(
                status_code=503,
                detail="Servicio de routing multi-modal no disponible"
            )
        
        mode = request.get('mode')
        if not mode:
            raise HTTPException(
                status_code=400,
                detail="Campo 'mode' requerido (drive|walk|bike|all)"
            )
        
        start_time = time_module.time()
        
        if mode == "all":
            # Pre-cargar todos los caches
            results = router.preload_all_caches()
            processing_time = time_module.time() - start_time
            
            successful_loads = sum(results.values())
            
            return {
                "success": True,
                "mode": "all",
                "results": results,
                "successful_loads": successful_loads,
                "total_modes": len(results),
                "processing_time_ms": round(processing_time * 1000, 2),
                "message": f"Pre-carga completada: {successful_loads}/{len(results)} caches cargados",
                "timestamp": datetime.now().isoformat()
            }
        else:
            # Pre-cargar cache específico
            if mode not in ['drive', 'walk', 'bike']:
                raise HTTPException(
                    status_code=400,
                    detail="Modo debe ser: drive, walk, bike, o all"
                )
            
            success = router.preload_cache(mode)
            processing_time = time_module.time() - start_time
            
            return {
                "success": success,
                "mode": mode,
                "processing_time_ms": round(processing_time * 1000, 2),
                "message": f"Cache {mode} {'cargado exitosamente' if success else 'falló al cargar'}",
                "timestamp": datetime.now().isoformat()
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error pre-cargando cache: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error pre-cargando cache: {str(e)}"
        )

@app.post("/cache/clear", tags=["Multi-Modal Routing"])
async def clear_cache(request: dict):
    """
    🧹 Limpiar cache de memoria para liberar RAM
    Body: {"mode": "drive|walk|bike"} o {"mode": "all"}
    """
    try:
        router = get_chile_router()
        if router is None:
            raise HTTPException(
                status_code=503,
                detail="Servicio de routing multi-modal no disponible"
            )
        
        mode = request.get('mode')
        if not mode:
            raise HTTPException(
                status_code=400,
                detail="Campo 'mode' requerido (drive|walk|bike|all)"
            )
        
        # Obtener uso de memoria antes
        memory_before = router.get_memory_usage()
        
        if mode == "all":
            router.clear_memory_cache()
            message = "Todos los caches eliminados de memoria"
        else:
            if mode not in ['drive', 'walk', 'bike']:
                raise HTTPException(
                    status_code=400,
                    detail="Modo debe ser: drive, walk, bike, o all"
                )
            
            router.clear_memory_cache(mode)
            message = f"Cache {mode} eliminado de memoria"
        
        # Obtener uso de memoria después
        memory_after = router.get_memory_usage()
        memory_freed = memory_before['total_estimated_mb'] - memory_after['total_estimated_mb']
        
        return {
            "success": True,
            "mode": mode,
            "memory_freed_mb": round(memory_freed, 2),
            "memory_before_mb": round(memory_before['total_estimated_mb'], 2),
            "memory_after_mb": round(memory_after['total_estimated_mb'], 2),
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error limpiando cache: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error limpiando cache: {str(e)}"
        )

@app.get("/cache/optimize", tags=["Multi-Modal Routing"])
async def optimize_memory():
    """
    🔧 Optimizar uso de memoria basado en patrones de uso
    Analiza estadísticas y libera memoria de caches poco utilizados
    """
    try:
        router = get_chile_router()
        if router is None:
            raise HTTPException(
                status_code=503,
                detail="Servicio de routing multi-modal no disponible"
            )
        
        # Ejecutar optimización automática
        optimization_report = router.optimize_memory()
        
        return {
            "success": True,
            "optimization_report": optimization_report,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error optimizando memoria: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error optimizando memoria: {str(e)}"
        )

@app.get("/performance/stats", tags=["Multi-Modal Routing"])
async def get_performance_statistics():
    """
    📊 Obtener estadísticas detalladas de rendimiento del sistema multi-modal
    Incluye uso de caches, hit ratios, memoria y patrones de uso
    """
    try:
        router = get_chile_router()
        if router is None:
            raise HTTPException(
                status_code=503,
                detail="Servicio de routing multi-modal no disponible"
            )
        
        # Obtener estadísticas completas
        stats = router.get_performance_stats()
        
        # Agregar timestamp
        stats['generated_at'] = datetime.now().isoformat()
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo estadísticas: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo estadísticas: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host=getattr(settings, 'API_HOST', '0.0.0.0'),
        port=getattr(settings, 'API_PORT', 8000),
        reload=getattr(settings, 'DEBUG', True)
    )
