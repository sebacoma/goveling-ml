"""
🚀 HYBRID OPTIMIZER V3.1 - ENHANCED VERSION
Mejoras implementadas:
- Packing strategies (compact/balanced/cluster_first)
- Time windows por tipo de lugar
- Transfers intercity con nombres reales
- Métricas detalladas separadas
- Sugerencias dinámicas para días libres
- Lodging recommendations por cluster
- Validaciones horarias con Google Places
"""

import math
import asyncio
import logging
import asyncio
import json
import time
import os
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import numpy as np
from sklearn.cluster import DBSCAN

from utils.free_routing_service import FreeRoutingService
from utils.geo_utils import haversine_km
from services.hotel_recommender import HotelRecommender
from services.google_places_service import GooglePlacesService
from utils.google_cache import cache_google_api, parallel_google_calls
from settings import settings

# =========================================================================
# CUSTOM EXCEPTIONS FOR ROBUST ERROR HANDLING
# =========================================================================

class OptimizerError(Exception):
    """Base exception for optimizer errors"""
    pass

class RoutingServiceError(OptimizerError):
    """Routing service related errors"""
    pass

class GooglePlacesError(OptimizerError):
    """Google Places API related errors"""
    pass

class QuotaExceededError(GooglePlacesError):
    """API quota exceeded"""
    pass

class CircuitBreakerOpenError(OptimizerError):
    """Circuit breaker is open"""
    pass

class InvalidCoordinatesError(OptimizerError):
    """Invalid coordinates provided"""
    pass

# =========================================================================
# CIRCUIT BREAKER PATTERN
# =========================================================================

class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=30, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self._state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        
    def is_open(self):
        if self._state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self._state = "HALF_OPEN"
                return False
            return True
        return False
        
    def record_success(self):
        self.failure_count = 0
        self._state = "CLOSED"
        
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self._state = "OPEN"
    
    def is_closed(self):
        """Verificar si el circuit breaker está cerrado (funcionando normalmente)"""
        return self._state == "CLOSED"
            
    async def call(self, func, *args, **kwargs):
        if self.is_open():
            raise CircuitBreakerOpenError(f"Circuit breaker is open for {func.__name__}")
            
        try:
            result = await asyncio.wait_for(func(*args, **kwargs), timeout=self.timeout)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise

@dataclass
class TimeWindow:
    start: int  # minutos desde medianoche
    end: int

@dataclass
class Cluster:
    label: int
    centroid: Tuple[float, float]
    places: List[Dict]
    home_base: Optional[Dict] = None
    home_base_source: str = "none"
    suggested_accommodations: List[Dict] = field(default_factory=list)
    additional_suggestions: List[Dict] = field(default_factory=list)  # 🌟 Sugerencias adicionales para clusters remotos

@dataclass
@dataclass
class TransferItem:
    type: str = "transfer"
    from_place: str = ""
    to_place: str = ""
    distance_km: float = 0.0
    duration_minutes: int = 0
    recommended_mode: str = "walk"
    is_intercity: bool = False
    overnight: bool = False
    is_return_to_hotel: bool = False  # Nueva bandera para marcar regreso al hotel
    from_lat: float = 0.0  # Coordenadas del origen
    from_lon: float = 0.0
    to_lat: float = 0.0    # Coordenadas del destino
    to_lon: float = 0.0

@dataclass
class ActivityItem:
    type: str = "activity"
    name: str = ""
    lat: float = 0.0
    lon: float = 0.0
    place_type: str = ""
    duration_minutes: int = 60
    start_time: int = 540
    end_time: int = 600
    priority: int = 5
    rating: float = 4.5
    image: str = ""
    address: str = ""
    time_window_preferred: Optional[TimeWindow] = None
    quality_flag: Optional[str] = None  # Agregar quality flag

@dataclass
class FreeBlock:
    start_time: int
    end_time: int
    duration_minutes: int
    suggestions: List[Dict] = field(default_factory=list)
    note: str = ""

class HybridOptimizerV31:
    def __init__(self):
        self.routing_service = FreeRoutingService()
        self.hotel_recommender = HotelRecommender()
        self.places_service = GooglePlacesService()
        self.logger = logging.getLogger(__name__)
        
        # 🛡️ Robustez: Circuit breakers para APIs externas
        self.routing_circuit_breaker = CircuitBreaker(failure_threshold=3, timeout=15, recovery_timeout=60)
        self.places_circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=20, recovery_timeout=120)
        
        # Circuit breaker principal (alias para compatibilidad con tests)
        self.circuit_breaker = self.places_circuit_breaker
        
        # 🔧 Configuración robusta
        self.max_retries = 3
        self.backoff_factor = 2
        self.emergency_fallback_enabled = True
        
        # 🚀 Cache de performance para distancias
        self.distance_cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        
        # 📦 Batch processing configuration
        self.batch_size = 5
        self.max_concurrent_requests = 10
        self.batch_delay = 0.1  # 100ms entre batches
        
        # ⚡ Lazy loading configuration
        self.immediate_days_threshold = 3
        self.lazy_placeholders = {}
        
        # 💾 Persistent cache (inicializado vacío)
        self.persistent_cache = {}
        
        # 💾 Cargar cache persistente al inicializar
        self.load_persistent_cache()
        
    # =========================================================================
    # 🛡️ ROBUST API WRAPPERS - ERROR HANDLING GRANULAR
    # =========================================================================
    
    async def routing_service_robust(self, origin: Tuple[float, float], destination: Tuple[float, float], mode: str = 'walk'):
        """🚗 Routing service robusto con fallbacks múltiples"""
        for attempt in range(self.max_retries + 1):
            try:
                # Usar circuit breaker para proteger API
                result = await self.routing_circuit_breaker.call(
                    self.routing_service.eta_between, origin, destination, mode
                )
                return result
                
            except CircuitBreakerOpenError:
                self.logger.warning(f"⚡ Circuit breaker abierto para routing - usando fallback directo")
                return self._emergency_routing_fallback(origin, destination, mode)
                
            except (asyncio.TimeoutError, ConnectionError) as e:
                self.logger.warning(f"🌐 Routing API timeout/conexión (intento {attempt + 1}): {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.backoff_factor ** attempt)
                    continue
                return self._emergency_routing_fallback(origin, destination, mode)
                
            except Exception as e:
                self.logger.error(f"❌ Routing error crítico (intento {attempt + 1}): {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.backoff_factor ** attempt)
                    continue
                return self._emergency_routing_fallback(origin, destination, mode)
        
        # Si llegamos aquí, usar fallback de emergencia
        return self._emergency_routing_fallback(origin, destination, mode)
    
    async def places_service_robust(self, lat: float, lon: float, **kwargs):
        """🏪 Google Places service robusto con fallbacks"""
        for attempt in range(self.max_retries + 1):
            try:
                # Usar circuit breaker para proteger API
                result = await self.places_circuit_breaker.call(
                    self.places_service.search_nearby, lat, lon, **kwargs
                )
                return result
                
            except CircuitBreakerOpenError:
                self.logger.warning(f"⚡ Circuit breaker abierto para Google Places - usando fallback")
                return self._emergency_places_fallback(lat, lon, **kwargs)
                
            except QuotaExceededError:
                self.logger.error("💰 Cuota Google Places excedida - usando fallback sintético")
                return self._synthetic_places_fallback(lat, lon, **kwargs)
                
            except (asyncio.TimeoutError, ConnectionError) as e:
                self.logger.warning(f"🌐 Places API timeout/conexión (intento {attempt + 1}): {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.backoff_factor ** attempt)
                    continue
                return self._emergency_places_fallback(lat, lon, **kwargs)
                
            except Exception as e:
                self.logger.error(f"❌ Places error crítico (intento {attempt + 1}): {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.backoff_factor ** attempt)
                    continue
                return self._emergency_places_fallback(lat, lon, **kwargs)
        
        # Si llegamos aquí, usar fallback de emergencia
        return self._emergency_places_fallback(lat, lon, **kwargs)
    
    def _emergency_routing_fallback(self, origin: Tuple[float, float], destination: Tuple[float, float], mode: str):
        """⚡ Fallback de emergencia para routing usando distancia euclidiana"""
        from utils.geo_utils import haversine_km
        
        distance_km = haversine_km(origin[0], origin[1], destination[0], destination[1])
        
        # Estimaciones conservadoras basadas en modo de transporte
        speed_estimates = {
            'walk': 4,      # 4 km/h
            'bicycle': 15,   # 15 km/h  
            'drive': 30,     # 30 km/h (considerando tráfico urbano)
            'transit': 20    # 20 km/h (metro + caminata)
        }
        
        speed = speed_estimates.get(mode, 4)
        duration_hours = distance_km / speed
        duration_minutes = int(duration_hours * 60)
        
        self.logger.info(f"🚨 Fallback routing: {distance_km:.1f}km, {duration_minutes}min ({mode})")
        
        return {
            'duration_minutes': max(duration_minutes, 5),  # Mínimo 5 min
            'distance_km': distance_km,
            'fallback_used': True,
            'fallback_reason': 'routing_service_unavailable'
        }
    
    def _emergency_places_fallback(self, lat: float, lon: float, **kwargs):
        """⚡ Fallback de emergencia para places - lugares sintéticos básicos"""
        radius = kwargs.get('radius', 1000)
        place_type = kwargs.get('type', 'point_of_interest')
        
        # Generar lugares sintéticos básicos en un radio
        fallback_places = []
        for i in range(3):  # 3 lugares básicos
            # Offset pequeño aleatorio
            lat_offset = (i - 1) * 0.005  # ~500m
            lon_offset = (i - 1) * 0.005
            
            fallback_places.append({
                'name': f'Lugar {i + 1}',
                'lat': lat + lat_offset,
                'lon': lon + lon_offset,
                'type': place_type,
                'rating': 4.0,
                'fallback_generated': True,
                'address': 'Dirección no disponible',
                'place_id': f'fallback_{lat}_{lon}_{i}'
            })
        
        self.logger.info(f"🚨 Places fallback: {len(fallback_places)} lugares sintéticos generados")
        
        return fallback_places
    
    def _synthetic_places_fallback(self, lat: float, lon: float, **kwargs):
        """🎭 Fallback sintético más elaborado para Places API"""
        place_type = kwargs.get('type', 'point_of_interest')
        types = kwargs.get('types', [place_type])
        
        # Lugares sintéticos según tipo
        synthetic_templates = {
            'restaurant': ['Restaurante local', 'Café', 'Comida rápida'],
            'tourist_attraction': ['Sitio histórico', 'Mirador', 'Plaza'],
            'lodging': ['Hotel', 'Hostal', 'Casa de huéspedes'],
            'point_of_interest': ['Lugar de interés', 'Centro comercial', 'Parque']
        }
        
        # Usar el primer tipo de la lista
        primary_type = types[0] if types else place_type
        templates = synthetic_templates.get(primary_type, synthetic_templates['point_of_interest'])
        
        synthetic_places = []
        for i, template in enumerate(templates):
            lat_offset = (i - 1) * 0.003
            lon_offset = (i - 1) * 0.003
            
            synthetic_places.append({
                'name': template,
                'lat': lat + lat_offset,
                'lon': lon + lon_offset,
                'type': primary_type,
                'rating': 4.0 + (i * 0.1),
                'synthetic': True,
                'address': 'Dirección no disponible',
                'place_id': f'synthetic_{primary_type}_{i}_{int(time.time())}'
            })
        
        self.logger.info(f"🎭 Synthetic places: {len(synthetic_places)} {primary_type} generados")
        return synthetic_places
    
    async def places_service_real_robust(self, lat: float, lon: float, **kwargs):
        """🏨 Google Places REAL service robusto (para hoteles y lugares críticos)"""
        for attempt in range(self.max_retries + 1):
            try:
                # Usar circuit breaker para proteger API
                result = await self.places_circuit_breaker.call(
                    self.places_service.search_nearby_real, lat, lon, **kwargs
                )
                return result
                
            except CircuitBreakerOpenError:
                self.logger.warning(f"⚡ Circuit breaker abierto para Google Places Real - usando fallback")
                return self._synthetic_places_fallback(lat, lon, **kwargs)
                
            except QuotaExceededError:
                self.logger.error("💰 Cuota Google Places Real excedida - usando fallback sintético")
                return self._synthetic_places_fallback(lat, lon, **kwargs)
                
            except (asyncio.TimeoutError, ConnectionError) as e:
                self.logger.warning(f"🌐 Places Real API timeout/conexión (intento {attempt + 1}): {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.backoff_factor ** attempt)
                    continue
                return self._synthetic_places_fallback(lat, lon, **kwargs)
                
            except Exception as e:
                self.logger.error(f"❌ Places Real error crítico (intento {attempt + 1}): {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.backoff_factor ** attempt)
                    continue
                return self._synthetic_places_fallback(lat, lon, **kwargs)
        
        # Si llegamos aquí, usar fallback de emergencia
        return self._synthetic_places_fallback(lat, lon, **kwargs)
    
    def validate_coordinates(self, lat_or_places, lon=None):
        """🧭 Validación robusta de coordenadas - soporte para coordenadas individuales o lista de places"""
        # Si es una sola coordenada
        if lon is not None:
            return self._validate_single_coordinate(lat_or_places, lon)
        
        # Si es una lista de places
        places = lat_or_places
        validated = []
        invalid_count = 0
        
        for i, place in enumerate(places):
            try:
                lat = float(place.get('lat', 0))
                lon = float(place.get('lon', 0))
                name = place.get('name', f'Lugar {i+1}')
                
                # Validar rangos válidos
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    self.logger.warning(f"🚫 Coordenadas inválidas: {name} ({lat}, {lon})")
                    invalid_count += 1
                    
                    # Intentar corrección automática si está cerca de rango válido
                    if self._attempt_coordinate_correction(lat, lon):
                        corrected_lat, corrected_lon = self._attempt_coordinate_correction(lat, lon)
                        place['lat'] = corrected_lat
                        place['lon'] = corrected_lon
                        place['coordinates_corrected'] = True
                        self.logger.info(f"✅ Coordenadas corregidas: {name} -> ({corrected_lat}, {corrected_lon})")
                        validated.append(place)
                    continue
                
                # Detectar coordenadas (0,0) sospechosas
                if abs(lat) < 0.001 and abs(lon) < 0.001:
                    self.logger.warning(f"🤔 Coordenadas sospechosas (0,0): {name}")
                    invalid_count += 1
                    continue
                    
                # Detectar coordenadas que podrían estar intercambiadas
                if abs(lat) > abs(lon) and abs(lon) > 90:
                    self.logger.warning(f"🔄 Posibles coordenadas intercambiadas: {name} ({lat}, {lon})")
                    # Intercambiar y validar
                    if -90 <= lon <= 90 and -180 <= lat <= 180:
                        place['lat'] = lon
                        place['lon'] = lat
                        place['coordinates_swapped'] = True
                        self.logger.info(f"✅ Coordenadas intercambiadas: {name} -> ({lon}, {lat})")
                        validated.append(place)
                        continue
                
                # Coordenadas válidas
                validated.append(place)
                
            except (ValueError, TypeError) as e:
                self.logger.error(f"❌ Error procesando coordenadas de {place.get('name', 'lugar desconocido')}: {e}")
                invalid_count += 1
                continue
        
        if invalid_count > 0:
            self.logger.warning(f"⚠️ Se excluyeron {invalid_count} lugares con coordenadas inválidas")
        
        self.logger.info(f"✅ Validación completa: {len(validated)}/{len(places)} lugares válidos")
        return validated
    
    def _validate_single_coordinate(self, lat: float, lon: float) -> Tuple[float, float]:
        """🎯 Validar una sola coordenada"""
        try:
            lat = float(lat)
            lon = float(lon)
            
            # Validar rangos válidos
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return (lat, lon)
            else:
                self.logger.warning(f"🚫 Coordenadas inválidas: ({lat}, {lon})")
                # Intentar corrección automática
                correction = self._attempt_coordinate_correction(lat, lon)
                if correction:
                    return correction
                # Si no se puede corregir, usar coordenadas por defecto (Santiago, Chile)
                return (-33.4489, -70.6693)
                
        except (ValueError, TypeError) as e:
            self.logger.error(f"❌ Error validando coordenadas ({lat}, {lon}): {e}")
            return (-33.4489, -70.6693)  # Coordenadas por defecto
    
    def _attempt_coordinate_correction(self, lat: float, lon: float) -> Optional[Tuple[float, float]]:
        """🔧 Intenta corregir coordenadas ligeramente fuera de rango"""
        corrected_lat = lat
        corrected_lon = lon
        
        # Corregir latitud
        if lat > 90:
            corrected_lat = 90
        elif lat < -90:
            corrected_lat = -90
            
        # Corregir longitud
        if lon > 180:
            corrected_lon = lon - 360 if lon <= 360 else 180
        elif lon < -180:
            corrected_lon = lon + 360 if lon >= -360 else -180
        
        # Solo devolver si la corrección es pequeña (< 5 grados)
        if abs(lat - corrected_lat) <= 5 and abs(lon - corrected_lon) <= 5:
            return corrected_lat, corrected_lon
        
        return None
    
    def _get_cache_key(self, lat1: float, lon1: float, lat2: float, lon2: float, mode: str) -> str:
        """🗝️ Generar clave de cache para distancias (redondeada para mejor hit rate)"""
        # Redondear coordenadas a 3 decimales (~100m precisión) para mejorar hit rate
        lat1_r = round(lat1, 3)
        lon1_r = round(lon1, 3)
        lat2_r = round(lat2, 3)
        lon2_r = round(lon2, 3)
        
        # Orden consistente para (A->B) = (B->A)
        if (lat1_r, lon1_r) <= (lat2_r, lon2_r):
            return f"{lat1_r},{lon1_r}-{lat2_r},{lon2_r}-{mode}"
        else:
            return f"{lat2_r},{lon2_r}-{lat1_r},{lon1_r}-{mode}"
    
    async def routing_service_cached(self, origin: Tuple[float, float], destination: Tuple[float, float], mode: str = 'walk'):
        """🚀 Routing service con cache inteligente de distancias"""
        cache_key = self._get_cache_key(origin[0], origin[1], destination[0], destination[1], mode)
        
        # Verificar cache
        if cache_key in self.distance_cache:
            self.cache_hits += 1
            cached_result = self.distance_cache[cache_key].copy()
            cached_result['cache_hit'] = True
            self.logger.debug(f"⚡ Cache HIT: {cache_key} ({self.cache_hits} hits)")
            return cached_result
        
        # Cache miss - llamar servicio robusto
        self.cache_misses += 1
        result = await self.routing_service_robust(origin, destination, mode)
        
        # Cachear resultado si es válido
        if result and result.get('duration_minutes', 0) > 0:
            self.distance_cache[cache_key] = result.copy()
            
            # Limitar tamaño del cache (mantener últimos 1000)
            if len(self.distance_cache) > 1000:
                # Remover las primeras 200 entradas (FIFO simple)
                keys_to_remove = list(self.distance_cache.keys())[:200]
                for key in keys_to_remove:
                    del self.distance_cache[key]
                self.logger.info(f"🧹 Cache limpiado: {len(keys_to_remove)} entradas removidas")
        
        result['cache_hit'] = False
        self.logger.debug(f"📊 Cache MISS: {cache_key} ({self.cache_misses} misses)")
        return result
    
    def get_cache_stats(self) -> Dict:
        """📊 Estadísticas del cache de distancias"""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate_percent': round(hit_rate, 2),
            'cache_size': len(self.distance_cache),
            'total_requests': total_requests,
            'persistent_cache': hasattr(self, 'persistent_cache') and len(self.persistent_cache) > 0,
            'batch_config': {
                'batch_size': self.batch_size,
                'max_concurrent': self.max_concurrent_requests,
                'batch_delay_ms': int(self.batch_delay * 1000)
            }
        }
    
    # =========================================================================
    # 🚀 BATCH PROCESSING & ASYNC OPTIMIZATION - SEMANA 2
    # =========================================================================
    
    async def batch_places_search(self, locations: List[Tuple[float, float]], **common_kwargs):
        """📦 Batch processing para múltiples búsquedas de Google Places"""
        if not locations:
            return []
        
        self.logger.info(f"📦 Iniciando batch search: {len(locations)} ubicaciones")
        
        # Dividir en batches
        batches = [locations[i:i + self.batch_size] for i in range(0, len(locations), self.batch_size)]
        all_results = []
        
        for batch_idx, batch in enumerate(batches):
            self.logger.debug(f"🔄 Procesando batch {batch_idx + 1}/{len(batches)} ({len(batch)} ubicaciones)")
            
            # Crear semáforo para limitar concurrencia
            semaphore = asyncio.Semaphore(min(self.max_concurrent_requests, len(batch)))
            
            # Crear tareas para el batch actual
            batch_tasks = [
                self._throttled_places_search(lat, lon, semaphore, **common_kwargs)
                for lat, lon in batch
            ]
            
            # Ejecutar batch en paralelo
            try:
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # Procesar resultados del batch
                for i, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        self.logger.warning(f"⚠️ Error en ubicación {batch_idx * self.batch_size + i}: {result}")
                        all_results.append([])  # Lista vacía para error
                    else:
                        all_results.append(result)
                
            except Exception as e:
                self.logger.error(f"❌ Error crítico en batch {batch_idx + 1}: {e}")
                # Agregar listas vacías para todo el batch fallido
                all_results.extend([[]] * len(batch))
            
            # Delay entre batches para respetar rate limits
            if batch_idx < len(batches) - 1:  # No delay después del último batch
                await asyncio.sleep(self.batch_delay)
        
        total_places = sum(len(results) for results in all_results)
        self.logger.info(f"✅ Batch processing completado: {total_places} lugares encontrados total")
        
        return all_results
    
    async def _throttled_places_search(self, lat: float, lon: float, semaphore: asyncio.Semaphore, **kwargs):
        """🎛️ Búsqueda throttled de Places con semáforo"""
        async with semaphore:
            try:
                return await self.places_service_robust(lat, lon, **kwargs)
            except Exception as e:
                self.logger.warning(f"⚠️ Throttled search falló para ({lat:.3f}, {lon:.3f}): {e}")
                return []
    
    async def parallel_routing_calculations(self, route_pairs: List[Tuple[Tuple[float, float], Tuple[float, float], str]]):
        """🚗 Cálculos de routing en paralelo con throttling"""
        if not route_pairs:
            return []
        
        self.logger.info(f"🗺️ Calculando {len(route_pairs)} rutas en paralelo")
        
        # Crear semáforo para limitar concurrencia
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        
        # Crear tareas para todas las rutas
        routing_tasks = [
            self._throttled_routing_calculation(origin, destination, mode, semaphore)
            for origin, destination, mode in route_pairs
        ]
        
        # Ejecutar todas las tareas en paralelo
        try:
            results = await asyncio.gather(*routing_tasks, return_exceptions=True)
            
            # Procesar resultados
            successful_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.warning(f"⚠️ Error en ruta {i}: {result}")
                    # Usar fallback directo para rutas fallidas
                    origin, destination, mode = route_pairs[i]
                    fallback_result = self._emergency_routing_fallback(origin, destination, mode)
                    successful_results.append(fallback_result)
                else:
                    successful_results.append(result)
            
            self.logger.info(f"✅ Routing paralelo completado: {len(successful_results)} rutas calculadas")
            return successful_results
            
        except Exception as e:
            self.logger.error(f"❌ Error crítico en routing paralelo: {e}")
            # Fallback completo - calcular todas las rutas con fallback
            return [self._emergency_routing_fallback(origin, destination, mode) 
                   for origin, destination, mode in route_pairs]
    
    async def _throttled_routing_calculation(self, origin: Tuple[float, float], destination: Tuple[float, float], 
                                           mode: str, semaphore: asyncio.Semaphore):
        """🎛️ Cálculo de ruta throttled con semáforo"""
        async with semaphore:
            return await self.routing_service_cached(origin, destination, mode)
    
    # =========================================================================
    # 🎯 LAZY LOADING & SMART SUGGESTIONS - SEMANA 2
    # =========================================================================
    
    async def generate_suggestions_lazy(self, day_number: int, location: Tuple[float, float], 
                                      duration_minutes: int, **kwargs) -> Dict:
        """🎯 Lazy loading de sugerencias - solo genera para días inmediatos"""
        
        # Configuración lazy loading
        immediate_days_threshold = 3  # Solo generar para los primeros 3 días
        
        if day_number <= immediate_days_threshold:
            # Generar sugerencias completas para días inmediatos
            self.logger.info(f"🔄 Generando sugerencias completas para día {day_number}")
            
            try:
                suggestions = await self.places_service_robust(
                    lat=location[0],
                    lon=location[1],
                    types=['tourist_attraction', 'restaurant', 'point_of_interest'],
                    radius_m=5000,
                    limit=5,
                    **kwargs
                )
                
                return {
                    "immediate_suggestions": suggestions[:3],  # Top 3 sugerencias inmediatas
                    "lazy_placeholders": {},  # No hay placeholders para días inmediatos
                    "suggestions": suggestions[:3],  # Mantener compatibilidad
                    "lazy_loaded": False,
                    "generation_time": duration_minutes // 60,  # Estimación en horas
                    "note": f"Sugerencias para {duration_minutes // 60}h de tiempo libre ({len(suggestions)} lugares reales encontrados)"
                }
                
            except Exception as e:
                self.logger.warning(f"⚠️ Error generando sugerencias para día {day_number}: {e}")
                return self._generate_placeholder_suggestions(day_number, location, duration_minutes)
        
        else:
            # Placeholder para días lejanos - se cargarán bajo demanda
            self.logger.info(f"📋 Generando placeholder para día {day_number} (lazy loading)")
            placeholder_id = f"day_{day_number}_placeholder"
            
            # Registrar placeholder en el sistema
            self.lazy_placeholders[placeholder_id] = {
                "day_number": day_number,
                "location": location,
                "duration_minutes": duration_minutes,
                "status": "pending",
                "created_at": datetime.now().isoformat()
            }
            
            return {
                "immediate_suggestions": [],  # No hay sugerencias inmediatas para días lejanos
                "lazy_placeholders": {placeholder_id: self.lazy_placeholders[placeholder_id]},
                "suggestions": [],  # Mantener compatibilidad
                "lazy_loaded": True,
                "load_endpoint": f"/api/suggestions/day/{day_number}",
                "location": location,
                "duration_minutes": duration_minutes,
                "note": f"Sugerencias para {duration_minutes // 60}h se cargarán cuando sea necesario",
                "load_instruction": "Las sugerencias se generarán automáticamente 24h antes de la fecha"
            }
    
    def _generate_placeholder_suggestions(self, day_number: int, location: Tuple[float, float], 
                                        duration_minutes: int) -> Dict:
        """📋 Generar sugerencias placeholder básicas"""
        basic_suggestions = [
            {
                "name": "Explorar la zona local",
                "lat": location[0] + 0.001,
                "lon": location[1] + 0.001,
                "type": "point_of_interest",
                "rating": 4.0,
                "placeholder": True
            },
            {
                "name": "Encontrar restaurante cercano",
                "lat": location[0] - 0.001,
                "lon": location[1] - 0.001,
                "type": "restaurant",
                "rating": 4.0,
                "placeholder": True
            }
        ]
        
        return {
            "suggestions": basic_suggestions,
            "lazy_loaded": False,
            "placeholder_generated": True,
            "note": f"Sugerencias básicas para {duration_minutes // 60}h de tiempo libre"
        }
    
    async def load_lazy_suggestions(self, placeholder_id: str) -> Dict:
        """🔄 Cargar sugerencias lazy bajo demanda usando placeholder_id"""
        self.logger.info(f"🎯 Cargando sugerencias lazy para placeholder: {placeholder_id}")
        
        # Verificar si el placeholder existe
        if placeholder_id not in self.lazy_placeholders:
            self.logger.warning(f"⚠️ Placeholder {placeholder_id} no encontrado")
            return None
        
        placeholder_data = self.lazy_placeholders[placeholder_id]
        day_number = placeholder_data["day_number"]
        location = placeholder_data["location"]
        duration_minutes = placeholder_data["duration_minutes"]
        
        try:
            # Generar sugerencias completas ahora que se necesitan
            suggestions = await self.places_service_robust(
                lat=location[0],
                lon=location[1],
                types=['tourist_attraction', 'restaurant', 'museum', 'park'],
                radius_m=10000,  # Radio más amplio para días lejanos
                limit=8
            )
            
            # Actualizar estado del placeholder
            self.lazy_placeholders[placeholder_id]["status"] = "loaded"
            self.lazy_placeholders[placeholder_id]["loaded_at"] = datetime.now().isoformat()
            
            return {
                "suggestions": suggestions,
                "lazy_loaded": True,
                "loaded_on_demand": True,
                "day_number": day_number,
                "placeholder_id": placeholder_id,
                "note": f"Sugerencias cargadas bajo demanda para {duration_minutes // 60}h ({len(suggestions)} lugares encontrados)"
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error cargando sugerencias lazy: {e}")
            return self._generate_placeholder_suggestions(day_number, location, duration_minutes)
    
    # =========================================================================
    # 💾 PERSISTENT CACHE SYSTEM - SEMANA 2
    # =========================================================================
    
    def _get_cache_filename(self) -> str:
        """📁 Obtener nombre del archivo de cache"""
        return "goveling_distance_cache.json"
    
    def load_persistent_cache(self):
        """💾 Cargar cache persistente desde disco"""
        cache_file = self._get_cache_filename()
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    self.distance_cache = cached_data.get('distances', {})
                    
                    # Cargar estadísticas si existen
                    stats = cached_data.get('stats', {})
                    self.cache_hits = stats.get('cache_hits', 0)
                    self.cache_misses = stats.get('cache_misses', 0)
                    
                    self.logger.info(f"💾 Cache persistente cargado: {len(self.distance_cache)} entradas")
                    return True
            else:
                self.logger.info("📄 No existe cache persistente, empezando desde cero")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error cargando cache persistente: {e}")
            return False
    
    def _get_cache_filename(self):
        """📂 Obtener nombre de archivo de cache"""
        return "/Users/sebastianconcha/Developer/goveling/goveling ML/cache_persistent.json"
    
    def save_persistent_cache(self):
        """💾 Guardar cache persistente a disco"""
        cache_file = self._get_cache_filename()
        try:
            cache_data = {
                'distances': self.distance_cache,
                'stats': {
                    'cache_hits': self.cache_hits,
                    'cache_misses': self.cache_misses,
                    'last_updated': time.time()
                },
                'metadata': {
                    'version': '3.1',
                    'total_entries': len(self.distance_cache)
                }
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
                
            self.logger.info(f"💾 Cache persistente guardado: {len(self.distance_cache)} entradas")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error guardando cache persistente: {e}")
            return False
    
    def cleanup_old_cache_entries(self, max_age_days: int = 30):
        """🧹 Limpiar entradas antiguas del cache"""
        if not self.distance_cache:
            return 0
        
        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 3600
        removed_count = 0
        
        # Crear nueva copia del cache sin entradas antiguas
        new_cache = {}
        for key, value in self.distance_cache.items():
            try:
                # Si el valor tiene timestamp y es muy antiguo, no incluirlo
                entry_timestamp = value.get('timestamp', current_time)
                
                # Convertir timestamp a float si es string ISO
                if isinstance(entry_timestamp, str):
                    from datetime import datetime
                    entry_time = datetime.fromisoformat(entry_timestamp.replace('Z', '+00:00')).timestamp()
                else:
                    entry_time = entry_timestamp
                
                if current_time - entry_time <= max_age_seconds:
                    new_cache[key] = value
                else:
                    removed_count += 1
                    
            except Exception as e:
                # Si hay error parseando timestamp, mantener la entrada
                self.logger.warning(f"⚠️ Error parseando timestamp para {key}: {e}")
                new_cache[key] = value
        
        self.distance_cache = new_cache
        
        if removed_count > 0:
            self.logger.info(f"🧹 Cache cleanup: {removed_count} entradas antiguas removidas")
            
        return removed_count
    
    async def routing_service_persistent_cached(self, origin: Tuple[float, float], destination: Tuple[float, float], mode: str = 'walk'):
        """🚀 Routing service con cache persistente"""
        cache_key = self._get_cache_key(origin[0], origin[1], destination[0], destination[1], mode)
        
        # Verificar cache
        if cache_key in self.distance_cache:
            self.cache_hits += 1
            cached_result = self.distance_cache[cache_key].copy()
            cached_result['cache_hit'] = True
            cached_result['persistent_cache'] = True
            self.logger.debug(f"💾 Persistent cache HIT: {cache_key}")
            return cached_result
        
        # Cache miss - llamar servicio robusto
        self.cache_misses += 1
        result = await self.routing_service_robust(origin, destination, mode)
        
        # Cachear resultado con timestamp
        if result and result.get('duration_minutes', 0) > 0:
            result['timestamp'] = time.time()
            self.distance_cache[cache_key] = result.copy()
            
            # Auto-save cada 50 nuevas entradas
            if self.cache_misses % 50 == 0:
                self.save_persistent_cache()
        
        result['cache_hit'] = False
        result['persistent_cache'] = True
        return result
    
    def finalize_optimization(self):
        """🎯 Finalizar optimización - guardar cache y limpiar recursos"""
        try:
            # Guardar cache persistente
            self.save_persistent_cache()
            
            # Cleanup de entradas antiguas
            removed = self.cleanup_old_cache_entries(max_age_days=30)
            
            # Log de estadísticas finales
            stats = self.get_cache_stats()
            self.logger.info(f"🎯 Optimización finalizada:")
            self.logger.info(f"  💾 Cache guardado: {stats['cache_size']} entradas")
            self.logger.info(f"  ⚡ Hit rate final: {stats['hit_rate_percent']}%")
            if removed > 0:
                self.logger.info(f"  🧹 Limpieza: {removed} entradas antiguas removidas")
                
        except Exception as e:
            self.logger.error(f"❌ Error en finalización: {e}")
        
    # =========================================================================
    # 1. CLUSTERING POIs (UNCHANGED FROM V3.0)
    # =========================================================================
    
    def cluster_pois(self, places: List[Dict]) -> List[Cluster]:
        """🗺️ Clustering POIs usando DBSCAN con métrica Haversine"""
        pois = [p for p in places if p.get('type', '').lower() != 'accommodation']
        
        if not pois:
            self.logger.warning("No hay POIs para clustering")
            return []
        
        self.logger.info(f"🗺️ Clustering {len(pois)} POIs")
        
        coordinates = np.array([[p['lat'], p['lon']] for p in pois])
        eps_km = self._choose_eps_km(coordinates)
        eps_rad = eps_km / 6371.0
        
        clustering = DBSCAN(
            eps=eps_rad,
            min_samples=settings.CLUSTER_MIN_SAMPLES,
            metric='haversine'
        ).fit(np.radians(coordinates))
        
        clusters = {}
        for i, label in enumerate(clustering.labels_):
            if label == -1:
                label = f"noise_{i}"
            
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(pois[i])
        
        cluster_objects = []
        for label, cluster_places in clusters.items():
            centroid = self._calculate_centroid(cluster_places)
            cluster_obj = Cluster(
                label=label,
                centroid=centroid,
                places=cluster_places
            )
            cluster_objects.append(cluster_obj)
        
        # 🔒 GARANTÍA: Siempre al menos 1 cluster (no levantamos excepción)
        if not cluster_objects:
            self.logger.warning("⚠️ DBSCAN no creó clusters - creando cluster único de emergencia")
            centroid = self._calculate_centroid(pois)
            emergency_cluster = Cluster(
                label="emergency_single",
                centroid=centroid,
                places=pois
            )
            cluster_objects = [emergency_cluster]
        
        self.logger.info(f"✅ {len(cluster_objects)} clusters creados")
        return cluster_objects
    
    def create_clusters(self, places: List[Dict], hotel: Optional[Dict] = None) -> List[Cluster]:
        """🎯 Alias para cluster_pois - compatibilidad con tests y análisis"""
        self.logger.info(f"🎯 create_clusters llamado con {len(places)} lugares")
        return self.cluster_pois(places)
    
    def _choose_eps_km(self, coordinates: np.ndarray) -> float:
        """Elegir eps dinámicamente"""
        if len(coordinates) < 5:
            return settings.CLUSTER_EPS_KM_RURAL
        
        lat_range = np.max(coordinates[:, 0]) - np.min(coordinates[:, 0])
        lon_range = np.max(coordinates[:, 1]) - np.min(coordinates[:, 1])
        total_span = math.sqrt(lat_range**2 + lon_range**2)
        
        return settings.CLUSTER_EPS_KM_RURAL if total_span > 0.5 else settings.CLUSTER_EPS_KM_URBAN
    
    def _calculate_centroid(self, places: List[Dict]) -> Tuple[float, float]:
        """Calcular centroide geográfico"""
        lats = [p['lat'] for p in places]
        lons = [p['lon'] for p in places]
        return (sum(lats) / len(lats), sum(lons) / len(lons))
    
    # =========================================================================
    # 2. ENHANCED HOME BASE ASSIGNMENT CON SUGERENCIAS
    # =========================================================================
    
    async def assign_home_base_to_clusters(
        self, 
        clusters: List[Cluster], 
        accommodations: Optional[List[Dict]] = None,
        all_places: Optional[List[Dict]] = None
    ) -> List[Cluster]:
        """
        🏨 ASIGNAR HOME BASE INTELIGENTE:
        1. Buscar accommodations en la lista original de lugares (NO en clusters)
        2. Usar accommodations del usuario si se proporcionan  
        3. Recomendar hoteles para clusters sin accommodation
        """
        self.logger.info(f"🏨 Asignando home_base a {len(clusters)} clusters")
        
        # 🧠 ESTABLECER CONTEXTO PARA DETECCIÓN DE CLUSTERS REMOTOS
        self._all_clusters_for_remote_detection = clusters
        
        # 1. Primero, extraer accommodations de la lista ORIGINAL de lugares (not from clusters)
        all_accommodations = []
        if all_places:
            all_accommodations = [
                place for place in all_places 
                if place.get('place_type') == 'accommodation' or place.get('type') == 'accommodation'
            ]
            self.logger.info(f"🏨 Accommodations encontradas en lugares originales: {len(all_accommodations)}")
            
            # DEBUG: Mostrar detalles de accommodations encontradas
            for i, acc in enumerate(all_accommodations):
                auto_flag = acc.get('_auto_recommended', False)
                self.logger.info(f"🔍 DEBUG Accommodation {i+1}: {acc.get('name', 'Sin nombre')} (_auto_recommended: {auto_flag})")
            
            # Para cada accommodation, asignarla al cluster más cercano
            for accommodation in all_accommodations:
                closest_cluster = None
                min_distance = float('inf')
                
                for cluster in clusters:
                    # Calcular distancia del accommodation al centroide del cluster
                    distance = haversine_km(
                        accommodation['lat'], accommodation['lon'],
                        cluster.centroid[0], cluster.centroid[1]
                    )
                    if distance < min_distance:
                        min_distance = distance
                        closest_cluster = cluster
                
                # Asignar accommodation al cluster más cercano si no tiene base aún
                if closest_cluster and not closest_cluster.home_base:
                    closest_cluster.home_base = accommodation.copy()
                    
                    # Verificar si fue agregado automáticamente por nuestro sistema
                    if accommodation.get('_auto_recommended', False):
                        closest_cluster.home_base_source = "auto_recommended_by_system"
                        self.logger.info(f"  ✅ Cluster {closest_cluster.label}: {accommodation['name']} (recomendado automáticamente por el sistema, distancia: {min_distance:.1f}km)")
                    else:
                        closest_cluster.home_base_source = "auto_detected_in_original_places"
                        self.logger.info(f"  ✅ Cluster {closest_cluster.label}: {accommodation['name']} (detectado en lugares originales, distancia: {min_distance:.1f}km)")
        
        # 2. Asignar accommodations del usuario a clusters sin base
        if accommodations:
            clusters_without_base = [c for c in clusters if not c.home_base]
            self.logger.info(f"🏨 DEBUG: {len(clusters_without_base)} clusters sin base necesitan accommodations del usuario")
            self.logger.info(f"🏨 DEBUG: Accommodations disponibles: {len(accommodations)}")
            
            self._assign_user_hotels_to_clusters(clusters_without_base, accommodations)
            
            # Verificar resultados después de asignación
            assigned_count = sum(1 for c in clusters if c.home_base and getattr(c, 'home_base_source', '') == 'user_provided')
            self.logger.info(f"🏨 DEBUG: {assigned_count} clusters asignados con accommodations del usuario")
        else:
            self.logger.info("🏨 DEBUG: No hay accommodations del usuario para asignar")
        
        # 3. Recomendar hoteles para clusters que aún no tienen base
        clusters_without_base = [c for c in clusters if not c.home_base]
        if clusters_without_base:
            self.logger.info(f"🤖 Recomendando hoteles para {len(clusters_without_base)} clusters sin accommodation")
            await self._recommend_hotels_for_clusters(clusters_without_base)
        
        # 4. Generar sugerencias adicionales para cada cluster
        for cluster in clusters:
            await self._generate_accommodation_suggestions(cluster)
        
        return clusters
    
    def _assign_user_hotels_to_clusters(self, clusters: List[Cluster], accommodations: List[Dict]) -> List[Cluster]:
        """Asignar hoteles del usuario"""
        self.logger.info(f"🔍 DEBUG: _assign_user_hotels_to_clusters llamada con {len(accommodations)} accommodations")
        
        for cluster in clusters:
            min_distance = float('inf')
            closest_hotel = None
            
            self.logger.info(f"🔍 DEBUG: Procesando cluster {cluster.label} en {cluster.centroid}")
            
            for hotel in accommodations:
                distance = haversine_km(
                    cluster.centroid[0], cluster.centroid[1],
                    hotel['lat'], hotel['lon']
                )
                self.logger.info(f"🔍 DEBUG: Hotel {hotel.get('name', 'Sin nombre')} a {distance:.2f}km del cluster")
                
                if distance < min_distance:
                    min_distance = distance
                    closest_hotel = hotel
            
            if closest_hotel:
                cluster.home_base = closest_hotel.copy()
                cluster.home_base_source = "user_provided"
                self.logger.info(f"✅ Cluster {cluster.label}: {closest_hotel['name']} asignado (usuario, {min_distance:.2f}km)")
            else:
                self.logger.warning(f"❌ No se pudo asignar hotel al cluster {cluster.label}")
        
        return clusters
    
    async def _recommend_hotels_for_clusters(self, clusters: List[Cluster]) -> List[Cluster]:
        """
        🏨 RECOMENDACIÓN INTELIGENTE DE HOTELES:
        Para clusters lejanos, recomendar alojamiento local + sugerencias adicionales
        """
        for cluster in clusters:
            try:
                # Primero intentar con el hotel recommender
                recommendations = self.hotel_recommender.recommend_hotels(
                    cluster.places, max_recommendations=1, price_preference="mid"
                )
                
                if recommendations:
                    top_hotel = recommendations[0]
                    cluster.home_base = {
                        'name': top_hotel.name,
                        'lat': top_hotel.lat,
                        'lon': top_hotel.lon,
                        'address': top_hotel.address,
                        'rating': top_hotel.rating,
                        'type': 'accommodation'
                    }
                    cluster.home_base_source = "recommended"
                    
                    # 🧠 LÓGICA INTELIGENTE: Si es cluster lejano, agregar sugerencias adicionales
                    await self._enrich_remote_cluster_with_local_attractions(cluster)
                    
                else:
                    # 🏨 PARA CLUSTERS REMOTOS: Buscar hoteles con Google Places
                    is_remote = await self._is_remote_cluster(cluster)
                    if is_remote:
                        await self._find_hotel_for_remote_cluster(cluster)
                    else:
                        self._set_fallback_base(cluster)
                    
                    # 🧠 ENRIQUECER INCLUSO SIN HOTEL RECOMENDADO (para clusters remotos)
                    await self._enrich_remote_cluster_with_local_attractions(cluster)
                    
            except Exception as e:
                self.logger.error(f"Error recomendando hotel: {e}")
                self._set_fallback_base(cluster)
                # 🧠 ENRIQUECER INCLUSO CON ERROR
                await self._enrich_remote_cluster_with_local_attractions(cluster)
        
        return clusters
    
    async def _enrich_remote_cluster_with_local_attractions(self, cluster: Cluster):
        """
        🌟 ENRIQUECIMIENTO INTELIGENTE: 
        Para clusters lejanos, buscar atracciones locales adicionales
        """        
        try:
            # Usar el centroide del cluster como punto de búsqueda
            search_location = cluster.centroid
            
            # 🧠 DETECCIÓN DE CLUSTER REMOTO: Verificar si hay otros clusters lejos
            is_remote_cluster = await self._is_remote_cluster(cluster)
            
            if not is_remote_cluster:
                self.logger.debug(f"🔍 Cluster {cluster.label} no es remoto - saltando enriquecimiento")
                return
            
            self.logger.info(f"🔍 CLUSTER REMOTO DETECTADO: Buscando atracciones adicionales cerca del centroide {search_location}")
            
            # Buscar lugares adicionales en el área
            additional_suggestions = []
            place_types_to_search = ['tourist_attraction', 'restaurant', 'museum', 'park']
            
            for place_type in place_types_to_search:
                # Usar Google Places robusto para encontrar atracciones locales
                local_places = await self.places_service_robust(
                    lat=search_location[0],
                    lon=search_location[1],
                    types=[place_type],
                    radius_m=10000,  # 10km de radio para clusters remotos
                    limit=3
                )
                
                # El servicio robusto siempre devuelve una lista (puede estar vacía o con fallbacks)
                self.logger.info(f"🔍 Tipo: {place_type} - Encontrados: {len(local_places)} lugares")
                
                for place in local_places[:2]:  # Solo top 2 por tipo
                        # Evitar duplicar lugares que ya están en el cluster
                        place_name = place.get('name', '')
                        if not any(existing['name'] == place_name for existing in cluster.places):
                            additional_suggestions.append({
                                'name': place_name,
                                'lat': place.get('lat', search_location[0]),
                                'lon': place.get('lon', search_location[1]),
                                'place_type': place_type,
                                'rating': place.get('rating', 4.0),
                                'suggestion_type': 'local_discovery',
                                'reason': f'Atracción adicional cerca de {place_name}',
                                'address': place.get('address', 'Dirección no disponible')
                            })
                            self.logger.info(f"  ➕ Agregado: {place_name} (⭐{place.get('rating', 4.0)})")
                        else:
                            self.logger.info(f"  ⏭️ Duplicado: {place_name} - ya está en cluster")
            
            # Agregar sugerencias al cluster
            if additional_suggestions:
                cluster.additional_suggestions = additional_suggestions
                self.logger.info(f"✅ {len(additional_suggestions)} atracciones adicionales encontradas para cluster remoto")
                
                # Log de las sugerencias encontradas
                for suggestion in additional_suggestions[:3]:
                    self.logger.info(f"   💡 {suggestion['name']} ({suggestion['place_type']})")
            else:
                self.logger.info(f"ℹ️ No se encontraron atracciones adicionales para cluster remoto")
                    
        except Exception as e:
            self.logger.warning(f"⚠️ Error enriqueciendo cluster remoto: {e}")
    
    async def _is_remote_cluster(self, target_cluster: Cluster) -> bool:
        """
        🧠 LÓGICA DE DETECCIÓN DE CLUSTER REMOTO:
        Un cluster es remoto si está a > 50km de cualquier otro cluster
        """
        if not hasattr(self, '_all_clusters_for_remote_detection'):
            return True  # Si no tenemos contexto, asumir que es remoto para ser conservador
        
        try:
            for other_cluster in self._all_clusters_for_remote_detection:
                if other_cluster.label == target_cluster.label:
                    continue
                
                # Calcular distancia entre centroides
                distance_km = await self.routing_service.get_distance_km(
                    target_cluster.centroid[0], target_cluster.centroid[1],
                    other_cluster.centroid[0], other_cluster.centroid[1]
                )
                
                if distance_km and distance_km < 50:  # 50km threshold
                    self.logger.debug(f"🔍 Cluster {target_cluster.label} está cerca de cluster {other_cluster.label} ({distance_km:.1f}km)")
                    return False
            
            self.logger.info(f"🌍 Cluster {target_cluster.label} es REMOTO (>50km de otros clusters)")
            return True
            
        except Exception as e:
            self.logger.warning(f"Error detectando cluster remoto: {e}")
            return False  # Si hay error, no enriquecer
    
    async def _find_hotel_for_remote_cluster(self, cluster: Cluster):
        """
        🏨 BUSCAR HOTEL REAL PARA CLUSTER REMOTO:
        Usar Google Places para encontrar hoteles cerca del cluster
        """
        try:
            search_location = cluster.centroid
            self.logger.info(f"🏨 Buscando hoteles reales cerca de {search_location}")
            
            # Buscar hoteles usando Google Places API REAL robusto
            hotels = await self.places_service_real_robust(
                lat=search_location[0],
                lon=search_location[1],
                radius_m=15000,  # 15km de radio para áreas remotas
                types=['lodging'],  # Tipo específico para hoteles
                limit=5,
                exclude_chains=False  # Incluir cadenas hoteleras
            )
            
            if hotels:
                # Seleccionar el mejor hotel basado en rating
                best_hotel = max(hotels, key=lambda h: h.get('rating', 0))
                
                cluster.home_base = {
                    'name': best_hotel.get('name', 'Hotel local'),
                    'lat': best_hotel.get('lat', search_location[0]),
                    'lon': best_hotel.get('lon', search_location[1]),
                    'address': best_hotel.get('address', 'Dirección no disponible'),
                    'rating': best_hotel.get('rating', 4.0),
                    'type': 'accommodation',
                    'place_id': best_hotel.get('place_id', ''),
                    'price_level': best_hotel.get('price_level', 2)
                }
                cluster.home_base_source = "google_places_hotel"
                
                self.logger.info(f"✅ Hotel encontrado para cluster remoto: {best_hotel.get('name')} (⭐{best_hotel.get('rating', 4.0)})")
                
            else:
                self.logger.warning(f"⚠️ No se encontraron hoteles para cluster remoto, usando fallback")
                self._set_fallback_base(cluster)
                
        except Exception as e:
            self.logger.error(f"❌ Error buscando hotel para cluster remoto: {e}")
            self._set_fallback_base(cluster)
    
    async def _generate_accommodation_suggestions(self, cluster: Cluster):
        """Generar Top-3 sugerencias de alojamiento por cluster"""
        try:
            suggestions = self.hotel_recommender.recommend_hotels(
                cluster.places, max_recommendations=3, price_preference="mid"
            )
            
            cluster.suggested_accommodations = [
                {
                    'name': hotel.name,
                    'lat': hotel.lat,
                    'lon': hotel.lon,
                    'rating': hotel.rating,
                    'distance_to_centroid_km': hotel.distance_to_centroid_km,
                    'convenience_score': hotel.convenience_score
                }
                for hotel in suggestions
            ]
            
        except Exception as e:
            self.logger.warning(f"No se pudieron generar sugerencias para cluster {cluster.label}: {e}")
            cluster.suggested_accommodations = []
    
    def _set_fallback_base(self, cluster: Cluster):
        """Fallback mejorado: usar mejor lugar como base virtual"""
        enhanced_base = self._select_home_base_enhanced(cluster)
        cluster.home_base = enhanced_base
        cluster.home_base_source = "enhanced_fallback"
        
    def _select_home_base_enhanced(self, cluster: Cluster) -> Dict:
        """Seleccionar home base inteligente"""
        if not cluster.places:
            return {
                'name': f"Punto base Cluster {cluster.label}",
                'lat': cluster.centroid[0] if hasattr(cluster, 'centroid') else 0,
                'lon': cluster.centroid[1] if hasattr(cluster, 'centroid') else 0,
                'address': "Ubicación central estimada",
                'rating': 0.0,
                'type': 'virtual_base'
            }
        
        # 1. Buscar hotel si existe en el cluster
        hotels = [p for p in cluster.places if p.get('type', '').lower() in ['lodging', 'hotel']]
        if hotels:
            best_hotel = max(hotels, key=lambda h: h.get('rating', 0))
            return {
                'name': best_hotel.get('name', 'Hotel'),
                'lat': best_hotel['lat'],
                'lon': best_hotel['lon'],
                'address': best_hotel.get('address', ''),
                'rating': best_hotel.get('rating', 0),
                'type': 'hotel_from_cluster'
            }
        
        # 2. Buscar centro comercial o estación de transporte
        transport_hubs = [p for p in cluster.places if p.get('type', '').lower() in 
                         ['shopping_mall', 'transit_station', 'bus_station', 'train_station']]
        if transport_hubs:
            best_hub = max(transport_hubs, key=lambda h: h.get('rating', 0))
            return {
                'name': best_hub.get('name', 'Hub de transporte'),
                'lat': best_hub['lat'],
                'lon': best_hub['lon'],
                'address': best_hub.get('address', ''),
                'rating': best_hub.get('rating', 0),
                'type': 'transport_hub'
            }
        
        # 3. Usar centroide geográfico con referencia al lugar más cercano
        avg_lat = sum(p['lat'] for p in cluster.places) / len(cluster.places)
        avg_lon = sum(p['lon'] for p in cluster.places) / len(cluster.places)
        
        # Buscar lugar más cercano al centroide
        closest_place = min(cluster.places, 
                           key=lambda p: ((p['lat'] - avg_lat) ** 2 + (p['lon'] - avg_lon) ** 2) ** 0.5)
        
        return {
            'name': f"Centro de {closest_place.get('name', 'área')}",
            'lat': avg_lat,
            'lon': avg_lon,
            'address': f"Cerca de {closest_place.get('name', 'lugares de interés')}",
            'rating': 0.0,
            'type': 'smart_centroid',
            'reference_place': closest_place.get('name', '')
        }
    
    # =========================================================================
    # 3. PACKING STRATEGIES
    # =========================================================================
    
    def pack_activities_by_strategy(
        self,
        day_assignments: Dict[str, List[Cluster]],
        strategy: str = "balanced"
    ) -> Dict[str, List[Cluster]]:
        """📦 Aplicar estrategia de empaquetado"""
        self.logger.info(f"📦 Aplicando estrategia de empaquetado: {strategy}")
        
        if strategy == "compact":
            return self._pack_compact(day_assignments)
        elif strategy == "cluster_first":
            return self._pack_cluster_first(day_assignments)
        else:  # balanced (default)
            return self._pack_balanced(day_assignments)
    
    def _pack_compact(self, day_assignments: Dict[str, List[Cluster]]) -> Dict[str, List[Cluster]]:
        """Llenar días de forma voraz desde día 1"""
        all_clusters = []
        for clusters in day_assignments.values():
            all_clusters.extend(clusters)
        
        new_assignments = {date: [] for date in day_assignments.keys()}
        day_keys = list(day_assignments.keys())
        
        current_day_idx = 0
        for cluster in all_clusters:
            if current_day_idx < len(day_keys):
                date = day_keys[current_day_idx]
                new_assignments[date].append(cluster)
                
                # Si el día actual tiene suficientes actividades, pasar al siguiente
                if len(new_assignments[date]) >= settings.MAX_ACTIVITIES_PER_DAY:
                    current_day_idx += 1
        
        return new_assignments
    
    def _pack_balanced(self, day_assignments: Dict[str, List[Cluster]]) -> Dict[str, List[Cluster]]:
        """Distribuir equilibradamente entre días disponibles"""
        all_clusters = []
        for clusters in day_assignments.values():
            all_clusters.extend(clusters)
        
        new_assignments = {date: [] for date in day_assignments.keys()}
        day_keys = list(day_assignments.keys())
        
        # Distribuir round-robin
        for i, cluster in enumerate(all_clusters):
            day_idx = i % len(day_keys)
            new_assignments[day_keys[day_idx]].append(cluster)
        
        return new_assignments
    
    def _pack_cluster_first(self, day_assignments: Dict[str, List[Cluster]]) -> Dict[str, List[Cluster]]:
        """Colocar todas las actividades de un cluster antes del siguiente"""
        # Ya está implementado en la lógica original de asignación
        return day_assignments
    
    # =========================================================================
    # 4. TIME WINDOWS POR TIPO DE LUGAR
    # =========================================================================
    
    def get_preferred_time_window(self, place_type: str, daily_window: TimeWindow) -> List[TimeWindow]:
        """🕐 Obtener ventanas horarias preferidas por tipo"""
        place_type = place_type.lower()
        
        if place_type == 'restaurant':
            return [
                TimeWindow(
                    start=settings.RESTAURANT_LUNCH_START * 60,
                    end=settings.RESTAURANT_LUNCH_END * 60
                ),
                TimeWindow(
                    start=settings.RESTAURANT_DINNER_START * 60,
                    end=settings.RESTAURANT_DINNER_END * 60
                )
            ]
        elif place_type == 'museum':
            return [TimeWindow(
                start=max(daily_window.start, settings.MUSEUM_PREFERRED_START * 60),
                end=min(daily_window.end, settings.MUSEUM_PREFERRED_END * 60)
            )]
        elif place_type == 'shopping':
            return [TimeWindow(
                start=max(daily_window.start, settings.SHOPPING_PREFERRED_START * 60),
                end=min(daily_window.end, settings.SHOPPING_PREFERRED_END * 60)
            )]
        else:
            return [daily_window]  # Usar ventana completa del día
    
    # =========================================================================
    # 4.5. NORMALIZACIÓN Y CLASIFICACIÓN DE CAMPOS
    # =========================================================================
    
    def _normalize_place_fields(self, place: Dict) -> Dict:
        """Normalizar y completar campos nulos de un lugar"""
        normalized = {
            'place_id': place.get('place_id', f"unknown_{hash(place.get('name', 'unnamed'))}"),
            'name': self._generate_smart_name(place),
            'lat': place.get('lat', 0.0),
            'lon': place.get('lon', 0.0),
            'category': place.get('category', place.get('type', 'general')),
            'type': place.get('type', place.get('category', 'point_of_interest')),
            'rating': max(0.0, min(5.0, place.get('rating', 0.0))),
            'price_level': max(0, min(4, place.get('price_level', 0))),
            'address': place.get('address', 'Dirección no disponible'),
            'description': place.get('description', f"Visita a {place.get('name', 'lugar')}"),
            'photos': place.get('photos', []),
            'opening_hours': place.get('opening_hours', {}),
            'website': place.get('website', ''),
            'phone': place.get('phone', ''),
            'priority': max(1, min(10, place.get('priority', 5))),
            'image': place.get('image', place.get('photos', [{}])[0].get('url', '') if place.get('photos') else '')
        }
        
        # Validaciones adicionales
        if not isinstance(normalized['photos'], list):
            normalized['photos'] = []
        if not isinstance(normalized['opening_hours'], dict):
            normalized['opening_hours'] = {}
            
        return normalized
    
    def _generate_smart_name(self, place: Dict) -> str:
        """Generar nombre inteligente basado en el tipo de lugar/actividad"""
        # Si ya tiene nombre válido, usarlo
        existing_name = place.get('name', '')
        if existing_name and existing_name != '' and 'sin nombre' not in existing_name.lower():
            return existing_name
        
        # Para transfers, generar nombres descriptivos
        place_type = place.get('type', '')
        category = place.get('category', '')
        
        # IMPORTANTE: Detectar transfers por type O category
        if place_type == 'transfer' or category == 'transfer':
            # Obtener información del transfer
            duration_minutes = place.get('duration_minutes', 0)
            distance_km = place.get('distance_km', 0)
            from_place = place.get('from_place', '')
            to_place = place.get('to_place', '')
            is_return_to_hotel = place.get('is_return_to_hotel', False)
            
            # Generar nombre específico según contexto
            if is_return_to_hotel:
                return "Regreso al hotel"
            elif to_place and to_place != '':
                if duration_minutes >= 180:  # 3+ horas (intercity)
                    return f"Viaje a {to_place} ({duration_minutes//60}h)"
                elif duration_minutes >= 30:  # 30+ minutos
                    return f"Traslado a {to_place} ({duration_minutes}min)"
                elif distance_km > 5:  # 5+ km
                    return f"Traslado a {to_place} ({distance_km:.0f}km)"
                else:
                    return f"Traslado a {to_place}"
            elif from_place and from_place != '':
                return f"Traslado desde {from_place}"
            elif duration_minutes >= 180:  # Transfer largo sin destino específico
                return f"Traslado largo ({duration_minutes//60}h)"
            elif duration_minutes >= 30:
                return f"Traslado ({duration_minutes}min)"
            elif distance_km > 5:
                return f"Traslado ({distance_km:.0f}km)"
            elif duration_minutes > 0:
                return f"Traslado corto ({duration_minutes}min)"
            else:
                return "Traslado"
        
        # Para otros tipos sin nombre
        type_names = {
            'restaurant': 'Restaurante',
            'tourist_attraction': 'Atracción turística', 
            'museum': 'Museo',
            'park': 'Parque',
            'accommodation': 'Alojamiento',
            'shopping_mall': 'Centro comercial',
            'cafe': 'Café',
            'church': 'Iglesia',
            'hotel': 'Hotel',
            'lodging': 'Hotel'
        }
        
        return type_names.get(place_type, 'Lugar de interés')
    
    def _transfer_item_to_dict(self, transfer_item: TransferItem) -> Dict:
        """Convertir TransferItem a diccionario normalizado"""
        # Crear diccionario base con información del transfer
        transfer_dict = {
            'place_id': f"transfer_{hash(str(transfer_item.from_place) + str(transfer_item.to_place))}",
            'type': 'transfer',
            'category': 'transfer',
            'from_place': transfer_item.from_place,
            'to_place': transfer_item.to_place, 
            'distance_km': transfer_item.distance_km,
            'duration_minutes': transfer_item.duration_minutes,
            'recommended_mode': transfer_item.recommended_mode,
            'is_intercity': transfer_item.is_intercity,
            'is_return_to_hotel': getattr(transfer_item, 'is_return_to_hotel', False),
            'rating': 4.5,  # Rating por defecto para transfers
            'priority': 5,
            'lat': getattr(transfer_item, 'to_lat', 0.0),  # Usar coordenadas del destino
            'lon': getattr(transfer_item, 'to_lon', 0.0),
            'from_lat': getattr(transfer_item, 'from_lat', 0.0),  # Coordenadas del origen
            'from_lon': getattr(transfer_item, 'from_lon', 0.0)
        }
        
        # Aplicar normalización para generar nombre inteligente
        return self._normalize_place_fields(transfer_dict)
        
    def _classify_transport_time(self, travel_minutes: float) -> Dict[str, float]:
        """Clasificar tiempo de transporte entre walking y transport"""
        if travel_minutes <= 30:  # Hasta 30 min = walking
            return {
                'walking_time': round(travel_minutes, 1),
                'transport_time': 0.0,
                'transport_mode': 'walking'
            }
        else:  # Más de 30 min = transport
            return {
                'walking_time': 0.0,
                'transport_time': round(travel_minutes, 1),
                'transport_mode': 'transport'
            }
            
    def _create_intercity_activity(self, transfer, current_time: int):
        """Crear actividad especial para transfers intercity largos"""
        if transfer.duration_minutes < 180:  # Menos de 3 horas
            return None
            
        # Actividades sugeridas según duración
        if transfer.duration_minutes >= 480:  # 8+ horas
            activity_type = "overnight_journey"
            suggestion = "Viaje nocturno - considera descanso"
        elif transfer.duration_minutes >= 360:  # 6+ horas  
            activity_type = "scenic_journey"
            suggestion = "Viaje panorámico - disfruta el paisaje"
        else:  # 3-6 horas
            activity_type = "comfortable_journey"
            suggestion = "Tiempo para relajarse o trabajar"
            
        # Crear objeto similar a ActivityItem pero más simple
        from dataclasses import dataclass
        
        @dataclass
        class IntercityActivity:
            type: str = "intercity_activity"
            name: str = ""
            lat: float = 0.0
            lon: float = 0.0
            place_type: str = ""
            duration_minutes: int = 0
            start_time: int = 0
            end_time: int = 0
            description: str = ""
            rating: float = 0.0
            address: str = ""
            transport_mode: str = ""
            is_intercity_activity: bool = True
            
        return IntercityActivity(
            type="intercity_activity",
            name=f"Viaje {transfer.from_place} → {transfer.to_place}",
            lat=0.0,  # Ruta intermedia
            lon=0.0,
            place_type=activity_type,
            duration_minutes=transfer.duration_minutes,
            start_time=current_time,
            end_time=current_time + transfer.duration_minutes,
            description=suggestion,
            rating=0,
            address=f"Ruta {transfer.from_place} - {transfer.to_place}",
            transport_mode=transfer.recommended_mode,
            is_intercity_activity=True
        )
        
    def _generate_actionable_recommendations(self, activities, transfers, free_blocks, daily_window) -> List[Dict]:
        """Generar recomendaciones procesables con acciones específicas"""
        recommendations = []
        
        # 1. Recomendaciones basadas en tiempo libre
        total_free_minutes = sum(block.duration_minutes if hasattr(block, 'duration_minutes') else 0 for block in free_blocks)
        
        if total_free_minutes > 180:  # 3+ horas libres
            recommendations.append({
                "type": "time_optimization",
                "priority": "high", 
                "title": "Mucho tiempo libre disponible",
                "description": f"Tienes {total_free_minutes} minutos libres. Considera agregar más actividades.",
                "action": "add_activities",
                "actionable_data": {
                    "suggested_types": ["museum", "shopping", "sightseeing"],
                    "available_blocks": len(free_blocks),
                    "longest_block_minutes": max((block.duration_minutes if hasattr(block, 'duration_minutes') else 0) for block in free_blocks) if free_blocks else 0
                }
            })
        
        # 2. Recomendaciones de transporte
        long_transfers = [t for t in transfers if isinstance(t, dict) and t.get('duration_minutes', 0) > 120]
        if long_transfers:
            recommendations.append({
                "type": "transport_optimization",
                "priority": "medium",
                "title": f"{len(long_transfers)} transfers largos detectados",
                "description": "Considera optimizar rutas o cambiar modo de transporte.",
                "action": "optimize_transport",
                "actionable_data": {
                    "long_transfers": [
                        {
                            "from": t.get("from", ""),
                            "to": t.get("to", ""), 
                            "duration": t.get("duration_minutes", 0),
                            "mode": t.get("mode", "")
                        } for t in long_transfers
                    ]
                }
            })
        
        # 3. Recomendaciones de balance actividades
        restaurant_count = sum(1 for act in activities if hasattr(act, 'place_type') and 'restaurant' in act.place_type.lower())
        
        if restaurant_count == 0:
            recommendations.append({
                "type": "meal_planning",
                "priority": "high",
                "title": "Sin comidas programadas",
                "description": "Considera agregar restaurantes para almuerzo y cena.",
                "action": "add_restaurants",
                "actionable_data": {
                    "lunch_time": "12:00-15:00",
                    "dinner_time": "19:00-22:00",
                    "suggested_cuisines": ["local", "traditional", "popular"]
                }
            })
        elif restaurant_count == 1:
            recommendations.append({
                "type": "meal_planning", 
                "priority": "medium",
                "title": "Solo una comida programada",
                "description": "Considera agregar otra opción de comida.",
                "action": "add_meal",
                "actionable_data": {
                    "missing_meal_type": "lunch" if restaurant_count == 1 else "dinner"
                }
            })
        
        # 4. Recomendaciones por horarios
        day_start_hour = daily_window.start // 60
        day_end_hour = daily_window.end // 60
        
        if day_end_hour - day_start_hour > 14:  # Día muy largo
            recommendations.append({
                "type": "schedule_optimization",
                "priority": "medium", 
                "title": "Día muy intenso",
                "description": f"Día de {day_end_hour - day_start_hour} horas. Considera agregar descansos.",
                "action": "add_breaks",
                "actionable_data": {
                    "day_length_hours": day_end_hour - day_start_hour,
                    "suggested_break_times": ["14:00-15:00", "17:00-18:00"]
                }
            })
        
        return recommendations

    # =========================================================================
    # 5. ENHANCED ROUTING CON TRANSFERS MEJORADOS
    # =========================================================================
    
    async def route_day_enhanced(
        self,
        date: str,
        assigned_clusters: List[Cluster],
        daily_window: TimeWindow,
        transport_mode: str,
        previous_day_end_location: Optional[Tuple[float, float]] = None,
        day_number: int = 1,
        extra_info: Optional[Dict] = None
    ) -> Dict:
        """🗓️ Routing mejorado con transfers con nombres reales"""
        self.logger.info(f"🗓️ Routing día {date} con {len(assigned_clusters)} clusters")
        
        timeline = []
        transfers = []
        activities_scheduled = []
        
        current_time = daily_window.start
        current_location = previous_day_end_location
        
        # Si no hay ubicación previa, usar la base del primer cluster
        if current_location is None and assigned_clusters:
            main_cluster = assigned_clusters[0]
            if main_cluster.home_base:
                current_location = (main_cluster.home_base['lat'], main_cluster.home_base['lon'])
            elif main_cluster.places:
                current_location = (main_cluster.places[0]['lat'], main_cluster.places[0]['lon'])
        
        # NUEVO: Para el primer día, agregar transfer inicial desde el hotel
        if day_number == 1 and current_location and assigned_clusters:
            # Crear objeto de actividad de check-in similar a IntercityActivity
            from dataclasses import dataclass
            
            @dataclass
            class HotelActivity:
                type: str = "accommodation"
                name: str = ""
                lat: float = 0.0
                lon: float = 0.0
                place_type: str = ""
                duration_minutes: int = 0
                start_time: int = 0
                end_time: int = 0
                description: str = ""
                rating: float = 0.0
                address: str = ""
            
            # Obtener nombre del hotel base del primer cluster
            main_cluster = assigned_clusters[0]
            hotel_name = "hotel"
            hotel_rating = 4.5
            hotel_address = "Hotel base del viaje"
            
            if main_cluster.home_base:
                hotel_name = main_cluster.home_base.get('name', 'hotel')
                hotel_rating = main_cluster.home_base.get('rating', 4.5)
                hotel_address = main_cluster.home_base.get('address', 'Hotel base del viaje')
                
            # Agregar actividad de check-in o llegada al hotel
            hotel_activity = HotelActivity(
                type="accommodation",
                name=f"Check-in al {hotel_name}",
                lat=current_location[0],
                lon=current_location[1], 
                place_type="hotel",
                duration_minutes=30,
                start_time=current_time,
                end_time=current_time + 30,
                description=f"Llegada y check-in al {hotel_name}",
                rating=hotel_rating,
                address=hotel_address
            )
            
            timeline.append(hotel_activity)
            activities_scheduled.append(hotel_activity)
            current_time += 30  # Tiempo para check-in
            
            self.logger.info(f"🏨 Primer día - agregando check-in al {hotel_name} ({current_time//60:02d}:{current_time%60:02d})")
        
        # Métricas separadas
        walking_time = 0
        transport_time = 0
        intercity_transfers_count = 0
        intercity_total_minutes = 0
        total_distance = 0
        
        for cluster in assigned_clusters:
            # Transfer inter-cluster con nombres reales + actividad intercity
            if current_location and cluster.home_base:
                # Verificar si ya estamos en la ubicación del hotel base
                hotel_location = (cluster.home_base['lat'], cluster.home_base['lon'])
                
                # Calcular distancia entre ubicación actual y hotel
                distance = haversine_km(
                    current_location[0], current_location[1], 
                    hotel_location[0], hotel_location[1]
                )
                
                # Solo generar transfer si la distancia es significativa (>100m)
                if distance > 0.1:  # 0.1 km = 100 metros
                    transfer = await self._build_enhanced_transfer(
                        current_location,
                        hotel_location,
                        transport_mode,
                        cluster
                    )
                    
                    # Verificar si cabe en el día
                    if current_time + transfer.duration_minutes > daily_window.end:
                        transfer.overnight = True
                        self.logger.warning(f"  ⚠️ Transfer intercity marcado como overnight")
                        # En el próximo día empezará con este transfer
                        break
                    
                    if transfer.duration_minutes > 0:
                        # Convertir TransferItem a dict normalizado
                        transfer_dict = self._transfer_item_to_dict(transfer)
                        timeline.append(transfer_dict)
                        
                        # Crear actividad intercity si es viaje largo
                        intercity_activity = self._create_intercity_activity(transfer, current_time)
                        if intercity_activity:
                            timeline.append(intercity_activity)
                            activities_scheduled.append(intercity_activity)
                        
                        transfers.append({
                            "type": "intercity_transfer",
                            "from": transfer.from_place,
                            "to": transfer.to_place,
                            "from_lat": transfer.from_lat,
                            "from_lon": transfer.from_lon,
                            "to_lat": transfer.to_lat,
                            "to_lon": transfer.to_lon,
                            "distance_km": transfer.distance_km,
                            "duration_minutes": transfer.duration_minutes,
                            "mode": transfer.recommended_mode,
                            "time": f"{current_time//60:02d}:{current_time%60:02d}",
                            "overnight": transfer.overnight,
                            "description": f"Viaje de {transfer.from_place} a {transfer.to_place}"
                        })
                        
                        intercity_transfers_count += 1
                        intercity_total_minutes += transfer.duration_minutes
                        transport_time += transfer.duration_minutes
                        total_distance += transfer.distance_km
                        current_time += transfer.duration_minutes
                        
                        self.logger.info(f"🚗 Transfer intercity: {transfer.from_place} → {transfer.to_place} ({transfer.distance_km:.1f}km, {transfer.duration_minutes:.0f}min)")
                
                # Actualizar ubicación actual al hotel base del cluster
                current_location = hotel_location
            
            # Routear actividades del cluster con time windows
            cluster_activities, cluster_timeline = await self._route_cluster_with_time_windows(
                cluster, current_time, daily_window, transport_mode
            )
            
            activities_scheduled.extend(cluster_activities)
            timeline.extend(cluster_timeline)
            
            # Actualizar posición y tiempo
            if cluster_timeline:
                last_item = cluster_timeline[-1]
                if hasattr(last_item, 'end_time'):
                    current_time = last_item.end_time
                if hasattr(last_item, 'lat') and hasattr(last_item, 'lon'):
                    current_location = (last_item.lat, last_item.lon)
            
            # Acumular métricas intra-cluster
            for item in cluster_timeline:
                if isinstance(item, TransferItem):
                    total_distance += item.distance_km
                    if item.recommended_mode == 'walk':
                        walking_time += item.duration_minutes
                    else:
                        transport_time += item.duration_minutes
        
        # 🔍 VALIDAR COHERENCIA GEOGRÁFICA para evitar context leakage
        # Si current_location está muy lejos del cluster del día, usar la base del cluster
        suggestions_origin = current_location
        if current_location and assigned_clusters:
            main_cluster = assigned_clusters[0]  # Cluster principal del día
            if main_cluster.home_base:
                cluster_location = (main_cluster.home_base['lat'], main_cluster.home_base['lon'])
                distance_to_cluster = haversine_km(
                    current_location[0], current_location[1],
                    cluster_location[0], cluster_location[1]
                )
                
                # Si la ubicación actual está > 100km del cluster, usar la base del cluster
                if distance_to_cluster > 100:
                    suggestions_origin = cluster_location
                    self.logger.warning(f"🌍 Context leakage evitado: current_location ({current_location}) → cluster_base ({cluster_location}) - distancia: {distance_to_cluster:.1f}km")
        
        # Generar free blocks con sugerencias mejoradas y recomendaciones procesables
        free_blocks_objects = await self._generate_free_blocks_enhanced(
            current_time, daily_window.end, suggestions_origin, day_number
        )
        
        # Convertir objetos FreeBlock a diccionarios
        free_blocks = []
        for fb in free_blocks_objects:
            free_blocks.append({
                "start_time": fb.start_time,
                "end_time": fb.end_time,
                "duration_minutes": fb.duration_minutes,
                "suggestions": fb.suggestions,
                "note": fb.note
            })
        
        # Generar recomendaciones procesables
        actionable_recommendations = self._generate_actionable_recommendations(
            activities_scheduled, transfers, free_blocks, daily_window
        )
        
        total_activity_time = sum(act.duration_minutes for act in activities_scheduled)
        total_travel_time = walking_time + transport_time
        free_minutes = max(0, (daily_window.end - daily_window.start) - total_activity_time - total_travel_time)
        
        return {
            "date": date,
            "activities": timeline,  # Usar timeline completo (actividades + transfers) en lugar de solo activities_scheduled
            "timeline": timeline,
            "pure_activities": activities_scheduled,  # Mantener actividades puras por compatibilidad
            "transfers": transfers,
            "free_blocks": free_blocks,
            "actionable_recommendations": actionable_recommendations,
            "base": self._build_enhanced_base_info(assigned_clusters[0], extra_info) if assigned_clusters else None,
            "travel_summary": {
                "total_travel_time_s": total_travel_time * 60,
                "total_distance_km": total_distance,
                "walking_time_minutes": walking_time,
                "transport_time_minutes": transport_time,
                "intercity_transfers_count": intercity_transfers_count,
                "intercity_total_minutes": intercity_total_minutes
            },
            "free_minutes": free_minutes,
            "end_location": current_location
        }
    
    async def _build_enhanced_transfer(
        self,
        origin: Tuple[float, float], 
        destination: Tuple[float, float],
        transport_mode: str,
        target_cluster: Cluster
    ) -> TransferItem:
        """
        🚀 TRANSFER MEJORADO: Siempre funciona, aún si Google Directions falla
        Genera intercity_transfer cuando distancia > 30km con ETA por velocidad promedio
        """
        
        # 🗺️ Usar routing service con cache
        eta_info = await self.routing_service_cached(origin, destination, transport_mode)
        
        # Auto-selección de modo para distancias largas si es necesario
        if eta_info.get('distance_km', 0) > 30.0 and transport_mode in ["walk", "walking"]:
            self.logger.info(f"🚗 Distancia {eta_info['distance_km']:.1f}km > 30km: recalculando con drive")
            eta_info = await self.routing_service_robust(origin, destination, "drive")
        
        # Determinar nombres reales (sin fallar) - MEJORADO
        try:
            # PRIMERO: Verificar si las coordenadas corresponden a un hotel conocido en nuestro sistema
            from_place = await self._get_known_hotel_name(origin)
            
            if from_place:
                self.logger.info(f"🏨 FROM lugar: Hotel conocido encontrado: {from_place}")
            
            # Si no es un hotel conocido, usar búsqueda de Google Places
            if not from_place:
                from_place = await self._get_nearest_named_place(origin)
                self.logger.info(f"🌐 FROM lugar: Google Places devolvió: {from_place}")
                
                # MEJORA: Si no encontramos un nombre específico, intentar encontrar el hotel base más cercano
                if from_place.startswith("Lat ") or "Lugar de interés" in from_place or not from_place:
                    # Buscar hoteles cercanos como fallback
                    nearby_hotels = await self.places_service.search_nearby(
                        lat=origin[0], 
                        lon=origin[1],
                        types=['lodging', 'accommodation'],
                        radius_m=500,  # Radio más pequeño para hoteles
                        limit=1
                    )
                    if nearby_hotels:
                        from_place = nearby_hotels[0].get('name', from_place)
                    else:
                        from_place = f"Ubicación ({origin[0]:.3f}, {origin[1]:.3f})"
        except:
            from_place = f"Ubicación ({origin[0]:.3f}, {origin[1]:.3f})"
            
        try:
            # PRIMERO: Usar home_base si está disponible (más confiable)
            if target_cluster.home_base:
                to_place = target_cluster.home_base['name']
            else:
                # SEGUNDO: Verificar si las coordenadas corresponden a un hotel conocido
                to_place = await self._get_known_hotel_name(destination)
                # TERCERO: Fallback a Google Places si no es un hotel conocido
                if not to_place:
                    to_place = await self._get_nearest_named_place(destination)
        except:
            to_place = f"Destino ({destination[0]:.3f}, {destination[1]:.3f})"
        
        # Aplicar política de transporte
        final_mode = self._decide_mode_by_distance_km(eta_info['distance_km'], transport_mode)
        
        # 🚗 Forzar modo si distancia > 30km
        if eta_info['distance_km'] > 30.0:
            if final_mode in ["walk", "walking"]:
                final_mode = "drive"
                self.logger.info(f"🚗 INTERCITY: {eta_info['distance_km']:.1f}km > 30km - forzando drive")
        
        # ✅ GARANTÍA: is_intercity = True para distancias > 30km
        is_intercity = eta_info['distance_km'] > 30.0
        
        transfer = TransferItem(
            type="transfer",
            from_place=from_place,
            to_place=to_place,
            distance_km=eta_info['distance_km'],
            duration_minutes=int(eta_info['duration_minutes']),
            recommended_mode=final_mode,
            is_intercity=is_intercity,
            from_lat=origin[0],
            from_lon=origin[1],
            to_lat=destination[0],
            to_lon=destination[1]
        )
        
        if is_intercity:
            self.logger.info(f"🌍 INTERCITY TRANSFER: {from_place} → {to_place} ({eta_info['distance_km']:.1f}km, {int(eta_info['duration_minutes'])}min)")
        
        return transfer
    
    async def _inject_intercity_transfers_between_days(self, days: List[Dict]) -> None:
        """
        🌍 DETECCIÓN Y CREACIÓN DE INTERCITY TRANSFERS ENTRE DÍAS
        Detecta cuando hay cambio de cluster entre días consecutivos y crea transfers intercity
        """
        for i in range(len(days) - 1):
            curr_day = days[i]
            next_day = days[i + 1]
            
            # Verificar que ambos días tengan base
            curr_base = curr_day.get('base')
            next_base = next_day.get('base')
            
            if not curr_base or not next_base:
                continue
                
            # Calcular distancia entre bases
            distance_km = haversine_km(
                curr_base['lat'], curr_base['lon'],
                next_base['lat'], next_base['lon']
            )
            
            # Si distancia > 30km, crear intercity transfer
            if distance_km > 30:
                self.logger.info(f"🌍 Intercity transfer detectado: {curr_base['name']} → {next_base['name']} ({distance_km:.1f}km)")
                
                # Intentar ETA con routing service gratuito
                transfer_mode = "drive"
                # Usar routing service robusto
                eta_info = await self.routing_service_robust(
                    (curr_base['lat'], curr_base['lon']),
                    (next_base['lat'], next_base['lon']),
                    transfer_mode
                )
                    
                # Si routing falló o es cruce oceánico muy largo, usar heurística de vuelo
                if (eta_info.get('fallback_used') and distance_km > 1000) or distance_km > settings.FLIGHT_THRESHOLD_KM:
                    transfer_mode = "flight"
                    eta_min = int((distance_km / settings.AIR_SPEED_KMPH) * 60 + settings.AIR_BUFFERS_MIN)
                    eta_info = {
                        'distance_km': distance_km,
                        'duration_minutes': eta_min,
                        'status': 'FLIGHT_HEURISTIC',
                        'google_enhanced': False
                    }
                    self.logger.info(f"✈️ Modo vuelo aplicado: {distance_km:.1f}km → {eta_min}min")
                
                # Crear transfer intercity
                intercity_transfer = {
                    "type": "intercity_transfer",
                    "from": curr_base['name'],
                    "to": next_base['name'],
                    "from_lat": curr_base['lat'],
                    "from_lon": curr_base['lon'],
                    "to_lat": next_base['lat'],
                    "to_lon": next_base['lon'],
                    "distance_km": eta_info['distance_km'],
                    "duration_minutes": int(eta_info['duration_minutes']),
                    "mode": transfer_mode,
                    "time": "09:00",  # Asumimos traslado temprano
                    "overnight": False,
                    "has_activity": False,
                    "is_between_days": True
                }
                
                # Verificar si ya existe un transfer similar para evitar duplicados
                if 'transfers' not in next_day:
                    next_day['transfers'] = []
                
                # Buscar duplicados basados en coordenadas (más fiable que nombres)
                transfer_exists = False
                for existing_transfer in next_day['transfers']:
                    if (existing_transfer.get('type') == 'intercity_transfer' and
                        abs(existing_transfer.get('distance_km', 0) - eta_info['distance_km']) < 1.0):  # Similar distancia
                        transfer_exists = True
                        self.logger.debug(f"🔄 Transfer intercity duplicado evitado por distancia: {curr_base['name']} → {next_base['name']}")
                        break
                
                # Solo inyectar si no existe
                if not transfer_exists:
                    next_day['transfers'].insert(0, intercity_transfer)
                    
                    # Actualizar travel_summary del día destino solo si se agregó el transfer
                    travel_summary = next_day.get('travel_summary', {})
                    travel_summary['intercity_transfers_count'] = travel_summary.get('intercity_transfers_count', 0) + 1
                    travel_summary['intercity_total_minutes'] = travel_summary.get('intercity_total_minutes', 0) + int(eta_info['duration_minutes'])
                    travel_summary['transport_time_minutes'] = travel_summary.get('transport_time_minutes', 0) + int(eta_info['duration_minutes'])
                    travel_summary['total_distance_km'] = travel_summary.get('total_distance_km', 0) + eta_info['distance_km']
                    
                    self.logger.info(f"✅ Intercity transfer inyectado: {transfer_mode}, {int(eta_info['duration_minutes'])}min")

    async def _get_known_hotel_name(self, location: Tuple[float, float]) -> str:
        """Verificar si las coordenadas corresponden a un hotel conocido en nuestro sistema"""
        try:
            self.logger.info(f"🔍 Verificando hotel conocido en ({location[0]:.6f}, {location[1]:.6f})")
            
            # Importar el hotel recommender para acceder a la base de datos de hoteles
            from services.hotel_recommender import HotelRecommender
            recommender = HotelRecommender()
            
            # Verificar en todas las ciudades
            for city_name, hotels in recommender.hotel_database.items():
                for hotel in hotels:
                    hotel_lat = hotel.get('lat', 0)
                    hotel_lon = hotel.get('lon', 0)
                    
                    # Calcular distancia (usando aproximación simple)
                    distance = ((location[0] - hotel_lat) ** 2 + (location[1] - hotel_lon) ** 2) ** 0.5
                    
                    # Si está muy cerca de un hotel conocido (< 0.01 grados ≈ 1km)
                    if distance < 0.01:
                        self.logger.info(f"🏨 Hotel conocido encontrado: {hotel['name']} (distancia: {distance:.6f})")
                        return hotel['name']
                        
        except Exception as e:
            self.logger.warning(f"Error verificando hoteles conocidos: {e}")
        
        self.logger.info(f"❌ No se encontró hotel conocido en ({location[0]:.6f}, {location[1]:.6f})")
        return ""  # No encontrado

    async def _get_nearest_named_place(self, location: Tuple[float, float]) -> str:
        """Obtener el nombre del lugar más cercano"""
        try:
            # Usar búsqueda robusta de lugares cercanos
            nearby_places = await self.places_service.search_nearby(
                lat=location[0], 
                lon=location[1],
                types=['point_of_interest', 'establishment'],
                radius_m=1000,
                limit=1
            )
            
            if nearby_places:
                return nearby_places[0].get('name', f"Lat {location[0]:.3f}, Lon {location[1]:.3f}")
            
        except Exception as e:
            self.logger.warning(f"No se pudo obtener nombre del lugar: {e}")
        
        return f"Lat {location[0]:.3f}, Lon {location[1]:.3f}"

    def _build_enhanced_base_info(self, cluster: Cluster, extra_info: Optional[Dict] = None) -> Dict:
        """Construir información completa del base incluyendo si fue recomendado automáticamente"""
        if not cluster.home_base:
            return None
            
        # Copiar la información básica del home_base
        base_info = cluster.home_base.copy()
        
        # Determinar si fue recomendado automáticamente
        no_original_accommodations = extra_info and extra_info.get('no_original_accommodations', False)
        
        # Si no había acomodaciones originales, marcar como auto-recomendado
        if no_original_accommodations:
            is_auto_recommended = True
            recommendation_source = "auto_recommended_by_system"
        else:
            # Usar la lógica original basada en home_base_source
            is_auto_recommended = cluster.home_base_source in ["recommended", "auto_recommended_by_system"]
            recommendation_source = cluster.home_base_source
            
        base_info["auto_recommended"] = is_auto_recommended
        base_info["recommendation_source"] = recommendation_source
        
        self.logger.info(f"🏨 Base info: {base_info.get('name', 'Unknown')} (source: {cluster.home_base_source}, auto_recommended: {is_auto_recommended})")
        
        return base_info

    def _decide_mode_by_distance_km(self, distance_km: float, requested_mode: str) -> str:
        """Política de transporte estricta"""
        if distance_km <= settings.WALK_THRESHOLD_KM:
            return "walk"
        elif distance_km <= settings.DRIVE_THRESHOLD_KM:
            if settings.TRANSIT_AVAILABLE and requested_mode in ["walk", "transit"]:
                return "transit"
            else:
                return "drive"
        else:
            return "drive"  # Siempre drive para distancias largas
    
    async def _route_cluster_with_time_windows(
        self,
        cluster: Cluster,
        start_time: int,
        daily_window: TimeWindow,
        transport_mode: str
    ) -> Tuple[List[ActivityItem], List]:
        """
        🏨 Routear cluster con hotel como base: SALIR del hotel → actividades → REGRESAR al hotel
        """
        if not cluster.places:
            return [], []
        
        # Ordenar lugares por prioridad y time windows
        sorted_places = self._sort_places_by_time_preference(cluster.places, start_time)
        
        activities = []
        timeline = []
        current_time = start_time
        
        # 🏨 PUNTO DE PARTIDA: Siempre iniciar desde el hotel/accommodation
        hotel_location = None
        if cluster.home_base:
            hotel_location = (cluster.home_base['lat'], cluster.home_base['lon'])
            current_location = hotel_location
            self.logger.debug(f"🏨 Iniciando día desde hotel: {cluster.home_base['name']}")
        else:
            current_location = (cluster.places[0]['lat'], cluster.places[0]['lon'])
            self.logger.warning(f"⚠️ Cluster sin hotel - iniciando desde primer lugar")
        
        # Filtrar lugares que NO son accommodation (ya que el hotel es la base, no una actividad)
        activity_places = [p for p in sorted_places if p.get('place_type') != 'accommodation' and p.get('type') != 'accommodation']
        
        for place in activity_places:
            place_location = (place['lat'], place['lon'])
            
            # Transfer si es necesario
            if current_location != place_location:
                eta_info = await self.routing_service.eta_between(
                    current_location, place_location, transport_mode
                )
                
                final_mode = self._decide_mode_by_distance_km(eta_info['distance_km'], transport_mode)
                transfer = TransferItem(
                    type="transfer",
                    from_place="",
                    to_place=place['name'],
                    distance_km=eta_info['distance_km'],
                    duration_minutes=int(eta_info['duration_minutes']),
                    recommended_mode=final_mode,
                    is_intercity=False,
                    from_lat=current_location[0],
                    from_lon=current_location[1],
                    to_lat=place_location[0],
                    to_lon=place_location[1]
                )
                
                # Convertir TransferItem a dict normalizado
                transfer_dict = self._transfer_item_to_dict(transfer)
                timeline.append(transfer_dict)
                current_time += transfer.duration_minutes
            
            # Buscar time window óptima
            activity_duration = self._estimate_activity_duration(place)
            preferred_windows = self.get_preferred_time_window(place.get('type', ''), daily_window)
            
            best_start_time = self._find_best_time_slot(
                current_time, activity_duration, preferred_windows
            )
            
            if best_start_time + activity_duration > daily_window.end:
                self.logger.warning(f"    ⚠️ {place['name']} no cabe en el día - intentando sin time windows")
                # Intentar programar sin restricciones de time windows
                fallback_start = current_time
                if fallback_start + activity_duration <= daily_window.end:
                    self.logger.info(f"    ✅ {place['name']} programado sin time windows a las {fallback_start//60:02d}:{fallback_start%60:02d}")
                    best_start_time = fallback_start
                else:
                    self.logger.warning(f"    ❌ {place['name']} realmente no cabe en el día")
                    break
            
            # Crear actividad
            activity = ActivityItem(
                type="activity",
                name=place['name'],
                lat=place['lat'],
                lon=place['lon'],
                place_type=place.get('type', 'point_of_interest'),
                duration_minutes=activity_duration,
                start_time=best_start_time,
                end_time=best_start_time + activity_duration,
                priority=place.get('priority', 5),
                rating=place.get('rating', 4.5),
                image=place.get('image', ''),
                address=place.get('address', ''),
                quality_flag=place.get('quality_flag')  # Pasar quality flag
            )
            
            activities.append(activity)
            timeline.append(activity)
            current_time = activity.end_time
            current_location = place_location
        
        # 🏨 REGRESO AL HOTEL: Agregar transfer final al hotel si terminamos en otro lugar
        if hotel_location and current_location != hotel_location and activities:
            self.logger.info(f"🔄 Agregando regreso al hotel desde última actividad")
            self.logger.debug(f"Hotel: {hotel_location}, Ubicación actual: {current_location}")
            
            try:
                eta_info = await self.routing_service.eta_between(
                    current_location, hotel_location, transport_mode
                )
                
                final_mode = self._decide_mode_by_distance_km(eta_info['distance_km'], transport_mode)
                return_transfer = TransferItem(
                    type="transfer",
                    from_place="última actividad",
                    to_place=cluster.home_base['name'],
                    distance_km=eta_info['distance_km'],
                    duration_minutes=int(eta_info['duration_minutes']),
                    recommended_mode=final_mode,
                    is_intercity=False,
                    is_return_to_hotel=True,  # Marcar como regreso al hotel
                    from_lat=current_location[0],
                    from_lon=current_location[1],
                    to_lat=hotel_location[0],
                    to_lon=hotel_location[1]
                )
                
                # Convertir TransferItem a dict normalizado
                return_transfer_dict = self._transfer_item_to_dict(return_transfer)
                timeline.append(return_transfer_dict)
                self.logger.info(f"✅ Regreso al hotel agregado: {eta_info['distance_km']:.1f}km, {eta_info['duration_minutes']:.0f}min")
                
            except Exception as e:
                self.logger.warning(f"⚠️ Error calculando regreso al hotel: {e}")
        else:
            self.logger.debug(f"🔍 No se agrega regreso al hotel. Hotel: {hotel_location}, Actual: {current_location}, Actividades: {len(activities)}")
        
        return activities, timeline
    
    def _sort_places_by_time_preference(self, places: List[Dict], current_time: int) -> List[Dict]:
        """Ordenar lugares priorizando time windows y prioridad"""
        def time_preference_score(place):
            place_type = place.get('type', '').lower()
            
            # Restaurantes tienen prioridad en horarios de comida
            if place_type == 'restaurant':
                lunch_start = settings.RESTAURANT_LUNCH_START * 60
                dinner_start = settings.RESTAURANT_DINNER_START * 60
                
                if lunch_start <= current_time <= lunch_start + 180:  # 3h window
                    return 1000  # Alta prioridad para almuerzo
                elif dinner_start <= current_time <= dinner_start + 180:
                    return 1000  # Alta prioridad para cena
                else:
                    return place.get('priority', 5)
            
            return place.get('priority', 5)
        
        return sorted(places, key=time_preference_score, reverse=True)
    
    def _find_best_time_slot(
        self,
        earliest_start: int,
        duration: int,
        preferred_windows: List[TimeWindow]
    ) -> int:
        """Encontrar mejor horario dentro de ventanas preferidas"""
        for window in preferred_windows:
            if earliest_start >= window.start and earliest_start + duration <= window.end:
                return earliest_start
            elif earliest_start < window.start and window.start + duration <= window.end:
                return window.start
        
        # Si no cabe en ventanas preferidas, usar earliest_start
        return earliest_start
    
    def _estimate_activity_duration(self, place: Dict) -> int:
        """Estimar duración por tipo"""
        place_type = place.get('type', '').lower()
        
        duration_map = {
            'restaurant': 90,
            'museum': 120,
            'tourist_attraction': 90,
            'shopping': 120,
            'park': 60,
            'entertainment': 180
        }
        
        return duration_map.get(place_type, 60)
    
    # =========================================================================
    # 6. FREE DAY SUGGESTIONS ENHANCED
    # =========================================================================
    
    async def _generate_free_blocks_enhanced(
        self,
        current_time: int,
        day_end: int,
        location: Optional[Tuple[float, float]],
        day_number: int = 1
    ) -> List[FreeBlock]:
        """🆓 Generar bloques libres con sugerencias inteligentes por duración"""
        free_blocks = []
        
        if current_time < day_end:
            block_duration = day_end - current_time
            
            suggestions = []
            note = ""
            
            if location and block_duration >= 60:  # Al menos 1 hora libre
                try:
                    # Seleccionar tipos según duración del bloque libre Y día
                    types = self._select_types_by_duration_and_day(block_duration, day_number)
                    
                    # 🗺️ USAR GOOGLE PLACES API REAL con variedad por día
                    raw_suggestions = await self.places_service.search_nearby_real(
                        lat=location[0],
                        lon=location[1], 
                        types=types,
                        radius_m=settings.FREE_DAY_SUGGESTIONS_RADIUS_M,
                        limit=settings.FREE_DAY_SUGGESTIONS_LIMIT,
                        exclude_chains=True,  # Excluir cadenas conocidas
                        day_offset=day_number  # Nuevo parámetro para variedad
                    )
                    
                    # Enriquecer sugerencias con ETAs y razones
                    suggestions = await self._enrich_suggestions_real(raw_suggestions, location, block_duration)
                    
                    if suggestions:
                        real_count = sum(1 for s in suggestions if not s.get('synthetic', True))
                        if real_count > 0:
                            source_type = f"{real_count} lugares reales de alta calidad"
                            note = f"Sugerencias para {block_duration//60}h de tiempo libre ({source_type})"
                        else:
                            # No hay lugares que cumplan los criterios de calidad
                            suggestions = []
                            note = "No hay lugares cercanos que cumplan nuestros estándares de calidad (4.5⭐, 20+ reseñas)"
                    else:
                        note = "No hay lugares cercanos que cumplan nuestros estándares de calidad (4.5⭐, 20+ reseñas)"
                        
                except Exception as e:
                    self.logger.warning(f"Error generando sugerencias: {e}")
                    note = "Servicio de sugerencias temporalmente no disponible"
            
            free_block = FreeBlock(
                start_time=current_time,
                end_time=day_end,
                duration_minutes=block_duration,
                suggestions=suggestions,
                note=note
            )
            
            free_blocks.append(free_block)
        
        return free_blocks
    
    async def _generate_free_blocks(
        self, 
        start_time: int, 
        end_time: int, 
        current_location: Optional[Tuple[float, float]] = None
    ) -> List[FreeBlock]:
        """🆓 Método base para compatibilidad - genera bloques libres simples"""
        if start_time >= end_time:
            return []
        
        duration_minutes = end_time - start_time
        
        return [FreeBlock(
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            suggestions=[],
            note=f"Tiempo libre: {duration_minutes // 60}h {duration_minutes % 60}m"
        )]
    
    def _select_types_by_duration(self, duration_minutes: int) -> List[str]:
        """🕐 Seleccionar exactamente 3 tipos de lugares según duración disponible"""
        if duration_minutes >= 240:  # ≥4h - actividades largas
            return ['tourist_attraction', 'restaurant', 'museum']
        elif duration_minutes >= 120:  # 2-4h - mezcla
            return ['restaurant', 'tourist_attraction', 'cafe']
        else:  # <2h - actividades cortas
            return ['restaurant', 'cafe', 'bar']

    def _select_types_by_duration_and_day(self, duration_minutes: int, day_number: int) -> List[str]:
        """🕐 Seleccionar tipos simples: SIEMPRE una atracción turística + variedad"""
        
        # 🎯 ENFOQUE SIMPLE: Siempre incluir atracciones turísticas + variedad por día
        variety_types = ['cafe', 'restaurant', 'museum', 'park', 'point_of_interest', 'art_gallery']
        
        # Rotar el segundo y tercer tipo según el día para variedad
        day_index = (day_number - 1) % len(variety_types)
        secondary_type = variety_types[day_index]
        tertiary_type = variety_types[(day_index + 1) % len(variety_types)]
        
        # SIEMPRE incluir tourist_attraction como primer tipo
        base_types = ['tourist_attraction', secondary_type, tertiary_type]
        
        # Ajustar según duración (pero siempre con tourist_attraction)
        if duration_minutes >= 480:  # 8+ horas - día completo
            return base_types
        elif duration_minutes >= 240:  # 4-8 horas - medio día  
            return base_types[:2]  # tourist_attraction + 1 más
        elif duration_minutes >= 120:  # 2-4 horas - par de horas
            return ['tourist_attraction', 'cafe']  # Básico: atracción + café
        else:  # < 2 horas - tiempo corto
            return ['tourist_attraction', 'cafe']  # Básico también
    
    async def _enrich_suggestions(
        self, 
        raw_suggestions: List[Dict], 
        user_location: Tuple[float, float],
        block_duration: int
    ) -> List[Dict]:
        """💎 Enriquecer sugerencias con ETAs y razones + filtro por distancia coherente"""
        enriched = []
        max_distance_km = 50.0  # Máximo 50km desde la base del día
        
        for suggestion in raw_suggestions:
            try:
                # 🔍 FILTRO POR DISTANCIA: descartar sugerencias muy lejas de la base del día
                distance_km = haversine_km(
                    user_location[0], user_location[1],
                    suggestion['lat'], suggestion['lon']
                )
                
                if distance_km > max_distance_km:
                    self.logger.debug(f"🚫 Sugerencia descartada: {suggestion['name']} ({distance_km:.1f}km > {max_distance_km}km)")
                    continue
                
                # Calcular ETA real
                eta_info = await self.routing_service.eta_between(
                    user_location,
                    (suggestion['lat'], suggestion['lon']),
                    'walk'
                )
                
                # Generar razón contextual
                reason = self._generate_suggestion_reason(
                    suggestion, eta_info['duration_minutes'], block_duration
                )
                
                enriched.append({
                    'name': suggestion['name'],
                    'lat': suggestion['lat'],
                    'lon': suggestion['lon'],
                    'type': suggestion['type'],
                    'rating': suggestion.get('rating', 4.5),
                    'eta_minutes': int(eta_info['duration_minutes']),
                    'reason': reason,
                    'synthetic': suggestion.get('synthetic', False)
                })
                
            except Exception as e:
                self.logger.warning(f"Error enriqueciendo sugerencia {suggestion['name']}: {e}")
                continue
        
        return enriched

    async def _enrich_suggestions_real(
        self, 
        raw_suggestions: List[Dict], 
        user_location: Tuple[float, float],
        block_duration: int
    ) -> List[Dict]:
        """💎 Enriquecer sugerencias reales de Google Places con ETAs y razones"""
        enriched = []
        max_distance_km = 5.0  # Máximo 5km desde la base del día
        
        for suggestion in raw_suggestions:
            try:
                # 🔍 FILTRO POR DISTANCIA: descartar sugerencias muy lejas de la base del día
                distance_km = suggestion.get('distance_km', 0)
                
                if distance_km > max_distance_km:
                    self.logger.debug(f"🚫 Sugerencia descartada: {suggestion['name']} ({distance_km:.1f}km > {max_distance_km}km)")
                    continue
                
                # Si ya viene de Google Places, usar datos directamente
                if not suggestion.get('synthetic', True):
                    enriched.append({
                        'name': suggestion['name'],
                        'lat': suggestion['lat'],
                        'lon': suggestion['lon'],
                        'type': suggestion['type'],
                        'rating': suggestion.get('rating', 4.0),
                        'eta_minutes': suggestion.get('eta_minutes', 0),
                        'reason': suggestion.get('reason', f"Google Places: {suggestion.get('rating', 4.0)}⭐"),
                        'synthetic': False,
                        'source': 'google_places',
                        'place_id': suggestion.get('place_id', ''),
                        'vicinity': suggestion.get('vicinity', ''),
                        'user_ratings_total': suggestion.get('user_ratings_total', 0),  # Agregado campo de reseñas
                        'distance_km': suggestion.get('distance_km', 0),
                        'price_level': suggestion.get('price_level')
                    })
                else:
                    # Sugerencia sintética - calcular ETA
                    eta_info = await self.routing_service.eta_between(
                        user_location,
                        (suggestion['lat'], suggestion['lon']),
                        'walk'
                    )
                    
                    reason = self._generate_suggestion_reason_enhanced(
                        suggestion, eta_info['duration_minutes'], block_duration
                    )
                    
                    enriched.append({
                        'name': suggestion['name'],
                        'lat': suggestion['lat'],
                        'lon': suggestion['lon'],
                        'type': suggestion['type'],
                        'rating': suggestion.get('rating', 4.0),
                        'eta_minutes': int(eta_info['duration_minutes']),
                        'reason': reason,
                        'synthetic': True
                    })
                    
            except Exception as e:
                self.logger.warning(f"Error enriqueciendo sugerencia {suggestion.get('name', 'unknown')}: {e}")
                continue
        
        # 🔄 DEDUPLICAR POR PLACE_ID
        seen_place_ids = set()
        deduplicated = []
        
        for suggestion in enriched:
            place_id = suggestion.get('place_id', '')
            if place_id and place_id in seen_place_ids:
                self.logger.debug(f"🔄 Sugerencia duplicada evitada: {suggestion['name']} (place_id: {place_id})")
                continue
            
            if place_id:
                seen_place_ids.add(place_id)
            deduplicated.append(suggestion)
        
        return deduplicated[:3]  # Máximo 3 sugerencias deduplicadas

    def _generate_suggestion_reason_enhanced(self, suggestion: Dict, eta_minutes: int, block_duration: int) -> str:
        """📝 Generar razón contextual mejorada para la sugerencia"""
        rating = suggestion.get('rating', 4.0)
        source = suggestion.get('source', 'synthetic')
        
        if eta_minutes <= 5:
            distance_desc = "muy cerca"
        elif eta_minutes <= 15:
            distance_desc = "cerca"
        else:
            distance_desc = f"{eta_minutes}min caminando"
        
        if rating >= 4.5:
            rating_desc = f"excelente rating ({rating}⭐)"
        elif rating >= 4.0:
            rating_desc = f"buen rating ({rating}⭐)"
        else:
            rating_desc = f"rating {rating}⭐"
        
        # Indicar si es lugar real o sintético
        source_prefix = "Google Places: " if source == 'google_places' else ""
        
        return f"{source_prefix}{rating_desc}, {distance_desc}"
    
    def _generate_suggestion_reason(self, suggestion: Dict, eta_minutes: int, block_duration: int) -> str:
        """📝 Generar razón contextual para la sugerencia"""
        place_type = suggestion.get('type', '')
        rating = suggestion.get('rating', 4.5)
        name = suggestion.get('name', '')
        
        if eta_minutes <= 5:
            distance_desc = "muy cerca"
        elif eta_minutes <= 15:
            distance_desc = "cerca"
        else:
            distance_desc = f"{eta_minutes}min caminando"
        
        if rating >= 4.5:
            rating_desc = f"excelente rating ({rating}⭐)"
        elif rating >= 4.0:
            rating_desc = f"buen rating ({rating}⭐)"
        else:
            rating_desc = f"rating {rating}⭐"
        
        return f"{rating_desc}, {distance_desc}"
    
    # =========================================================================
    # 7. ENHANCED METRICS Y MAIN FUNCTION
    # =========================================================================
    
    def calculate_enhanced_metrics(self, days: List[Dict]) -> Dict:
        """Calcular métricas mejoradas y detalladas"""
        total_walking_time = sum(
            day.get('travel_summary', {}).get('walking_time_minutes', 0)
            for day in days
        )
        total_transport_time = sum(
            day.get('travel_summary', {}).get('transport_time_minutes', 0)
            for day in days
        )
        total_distance_km = sum(
            day.get('travel_summary', {}).get('total_distance_km', 0)
            for day in days
        )
        total_activities = sum(len(day.get('activities', [])) for day in days)
        
        # Métricas intercity específicas
        intercity_transfers_count = sum(
            day.get('travel_summary', {}).get('intercity_transfers_count', 0)
            for day in days
        )
        intercity_total_minutes = sum(
            day.get('travel_summary', {}).get('intercity_total_minutes', 0)
            for day in days
        )
        
        # Score de eficiencia mejorado
        total_travel_minutes = total_walking_time + total_transport_time
        efficiency_base = 0.95
        travel_penalty = min(0.4, total_travel_minutes / 480 * 0.2)
        intercity_penalty = min(0.2, intercity_total_minutes / 240 * 0.1)
        efficiency_score = max(0.1, efficiency_base - travel_penalty - intercity_penalty)
        
        # Recopilar transfers intercity
        intercity_transfers = []
        for day in days:
            for transfer in day.get('transfers', []):
                if transfer.get('type') == 'intercity_transfer':
                    duration_minutes = transfer.get('duration_minutes', 60)
                    # Formatear duración dinámicamente
                    if duration_minutes >= 60:
                        hours = duration_minutes // 60
                        mins = duration_minutes % 60
                        duration_str = f"{hours}h{mins}min" if mins > 0 else f"{hours}h"
                    else:
                        duration_str = f"{duration_minutes}min"
                    
                    intercity_transfers.append({
                        'from': transfer['from'],
                        'to': transfer['to'],
                        'from_lat': transfer.get('from_lat', 0.0),
                        'from_lon': transfer.get('from_lon', 0.0),
                        'to_lat': transfer.get('to_lat', 0.0),
                        'to_lon': transfer.get('to_lon', 0.0),
                        'distance_km': transfer['distance_km'],
                        'duration': duration_str,  # Duración formateada dinámicamente
                        'duration_minutes': duration_minutes,  # Para cálculos
                        'estimated_time_hours': duration_minutes / 60,  # Mantener compatibilidad
                        'mode': transfer['mode'],
                        'overnight': transfer.get('overnight', False)
                    })
        
        return {
            'efficiency_score': efficiency_score,
            'optimization_mode': 'geographic_v31',  # ← Modo correcto V3.1
            'fallback_active': False,  # ← No fallback
            'total_distance_km': total_distance_km,
            'total_travel_time_minutes': total_travel_minutes,
            'walking_time_minutes': total_walking_time,
            'transport_time_minutes': total_transport_time,
            'long_transfers_detected': intercity_transfers_count,
            'intercity_transfers': intercity_transfers,
            'total_intercity_time_hours': intercity_total_minutes / 60,
            'total_intercity_distance_km': sum(t['distance_km'] for t in intercity_transfers)
        }
    
    # =========================================================================
    # LEGACY METHODS (UNCHANGED)
    # =========================================================================
    
    def allocate_clusters_to_days(self, clusters: List[Cluster], start_date: datetime, end_date: datetime) -> Dict[str, List[Cluster]]:
        """🧠 SMART DISTRIBUTION - Distribución inteligente basada en contexto"""
        num_days = (end_date - start_date).days + 1
        total_places = sum(len(cluster.places) for cluster in clusters)
        
        day_assignments = {}
        current_date = start_date
        
        for day_num in range(num_days):
            date_str = current_date.strftime('%Y-%m-%d')
            day_assignments[date_str] = []
            current_date += timedelta(days=1)
        
        # 🎯 DECISIÓN CONTEXTUAL: ¿Qué estrategia usar?
        days_per_place_ratio = num_days / max(total_places, 1)
        
        self.logger.info(f"📊 Contexto: {total_places} lugares, {num_days} días (ratio: {days_per_place_ratio:.1f})")
        
        if days_per_place_ratio >= 1.5:
            # MODO RELAJADO: Mucho tiempo disponible - espaciar actividades
            self.logger.info("😌 MODO RELAJADO: Espaciando actividades (1 lugar por día máximo)")
            return self._distribute_relaxed_mode(clusters, day_assignments)
            
        elif days_per_place_ratio >= 0.8:
            # MODO BALANCEADO: Tiempo moderado - agrupar cercanos inteligentemente  
            self.logger.info("⚖️ MODO BALANCEADO: Agrupando lugares cercanos inteligentemente")
            return self._distribute_balanced_mode(clusters, day_assignments)
            
        else:
            # MODO INTENSIVO: Poco tiempo - maximizar eficiencia geográfica
            self.logger.info("🏃 MODO INTENSIVO: Maximizando eficiencia geográfica")
            return self._distribute_intensive_mode(clusters, day_assignments)
    
    def _distribute_relaxed_mode(self, clusters: List[Cluster], day_assignments: Dict[str, List[Cluster]]) -> Dict[str, List[Cluster]]:
        """😌 Distribución relajada: 1 lugar por día máximo"""
        day_keys = list(day_assignments.keys())
        day_idx = 0
        
        for cluster in clusters:
            for place in cluster.places:
                # Crear mini-cluster individual
                mini_cluster = Cluster(
                    label=f"relaxed_{place['name'][:20]}",
                    centroid=(place['lat'], place['lon']),
                    places=[place],
                    home_base=cluster.home_base
                )
                
                # Asignar a día disponible
                if day_idx < len(day_keys):
                    day_assignments[day_keys[day_idx]].append(mini_cluster)
                    day_idx += 1
                else:
                    # Si se acabaron los días, usar el día con menos actividades
                    min_day = min(day_assignments.keys(), key=lambda d: len(day_assignments[d]))
                    day_assignments[min_day].append(mini_cluster)
        
        return day_assignments
    
    def _distribute_balanced_mode(self, clusters: List[Cluster], day_assignments: Dict[str, List[Cluster]]) -> Dict[str, List[Cluster]]:
        """⚖️ Distribución balanceada: Usa evaluación inteligente de rutas múltiples"""
        day_keys = list(day_assignments.keys())
        
        for cluster in clusters:
            if len(cluster.places) == 1:
                # Lugar individual - asignar directamente
                min_day = min(day_assignments.keys(), key=lambda d: len(day_assignments[d]))
                day_assignments[min_day].append(cluster)
                
            else:
                # 🗺️ Evaluación inteligente de rutas múltiples
                hotel_location = cluster.home_base if cluster.home_base else None
                route_analysis = self._evaluate_route_sequences(cluster.places, hotel_location)
                
                suggestion = route_analysis["optimization_suggestion"]
                avg_distance = route_analysis["place_to_place_avg"]
                max_distance = route_analysis["place_to_place_max"]
                
                self.logger.info(f"🔍 Cluster {cluster.label}: {len(cluster.places)} lugares")
                self.logger.info(f"📊 Análisis rutas: avg={avg_distance:.1f}km, max={max_distance:.1f}km")
                self.logger.info(f"💡 Sugerencia: {suggestion}")
                
                if suggestion == "group_same_day":
                    # Agrupar todos en el mismo día
                    self.logger.info(f"📍 Lugares muy cercanos - agrupando en mismo día")
                    min_day = min(day_assignments.keys(), key=lambda d: len(day_assignments[d]))
                    day_assignments[min_day].append(cluster)
                    
                elif suggestion == "group_pairs":
                    # Agrupar de a pares
                    self.logger.info(f"🚶 Lugares cercanos - agrupando de a pares")
                    for i in range(0, len(cluster.places), 2):
                        places_for_day = cluster.places[i:i+2]
                        
                        mini_cluster = Cluster(
                            label=f"{cluster.label}_pair_{i//2}",
                            centroid=cluster.centroid,
                            places=places_for_day,
                            home_base=cluster.home_base
                        )
                        
                        min_day = min(day_assignments.keys(), key=lambda d: len(day_assignments[d]))
                        day_assignments[min_day].append(mini_cluster)
                        
                elif suggestion in ["distribute", "distribute_far"]:
                    # Distribuir 1 por día con estrategia inteligente
                    self.logger.info(f"🌍 Distribuyendo lugares ({suggestion})")

                    if suggestion == "distribute_far":
                        # Para lugares muy lejanos, intentar equilibrar mejor las distancias
                        sorted_places = sorted(cluster.places, key=lambda p: 
                            sum(haversine_km(p['lat'], p['lon'], other['lat'], other['lon']) 
                                for other in cluster.places if other != p))
                    else:
                        sorted_places = cluster.places
                    for i, place in enumerate(sorted_places):
                        mini_cluster = Cluster(
                            label=f"{cluster.label}_single_{i}",
                            centroid=(place['lat'], place['lon']),
                            places=[place],
                            home_base=cluster.home_base
                        )
                        
                        # Distribución más inteligente
                        day_idx = i % len(day_keys)
                        day_assignments[day_keys[day_idx]].append(mini_cluster)
                        
                else:
                    # Fallback a distribución simple
                    self.logger.warning(f"⚠️ Sugerencia desconocida '{suggestion}' - usando distribución simple")
                    for i, place in enumerate(cluster.places):
                        mini_cluster = Cluster(
                            label=f"{cluster.label}_fallback_{i}",
                            centroid=(place['lat'], place['lon']),
                            places=[place],
                            home_base=cluster.home_base
                        )
                        
                        day_idx = i % len(day_keys)
                        day_assignments[day_keys[day_idx]].append(mini_cluster)
        
        return day_assignments
    
    def _distribute_intensive_mode(self, clusters: List[Cluster], day_assignments: Dict[str, List[Cluster]]) -> Dict[str, List[Cluster]]:
        """🏃 Distribución intensiva: Maximizar eficiencia geográfica"""
        for cluster in clusters:
            # En modo intensivo, mantener clusters originales para máxima eficiencia
            min_day = min(day_assignments.keys(), key=lambda d: len(day_assignments[d]))
            day_assignments[min_day].append(cluster)
        
        return day_assignments
    
    def _calculate_max_intra_cluster_distance(self, places: List[Dict]) -> float:
        """Calcular la distancia máxima entre lugares dentro del cluster"""
        if len(places) <= 1:
            return 0.0
        
        max_distance = 0.0
        for i, place_a in enumerate(places):
            for place_b in places[i+1:]:
                distance = haversine_km(
                    place_a['lat'], place_a['lon'],
                    place_b['lat'], place_b['lon']
                )
                max_distance = max(max_distance, distance)
        
        return max_distance
    
    def _calculate_inter_cluster_distances(self, clusters: List[Cluster]) -> Dict[tuple, float]:
        """Calcular distancias entre clusters"""
        distances = {}
        
        for i, cluster_a in enumerate(clusters):
            for j, cluster_b in enumerate(clusters[i+1:], i+1):
                distance = haversine_km(
                    cluster_a.centroid[0], cluster_a.centroid[1],
                    cluster_b.centroid[0], cluster_b.centroid[1]
                )
                key = tuple(sorted([cluster_a.label, cluster_b.label]))
                distances[key] = distance
        
        return distances
    
    def _evaluate_route_sequences(self, places: List[Dict], hotel_location: Optional[Dict] = None) -> Dict:
        """
        🗺️ Evaluación inteligente de secuencias de rutas múltiples
        
        Evalúa todas las combinaciones posibles de rutas:
        - Hotel → Lugar
        - Lugar → Lugar  
        - Lugar → Hotel
        - Transferencias intercity
        
        Retorna métricas para tomar decisiones inteligentes de agrupación
        """
        if not places:
            return {"total_distance": 0, "sequences": [], "optimization_suggestion": "none"}
        
        sequences = []
        total_distance = 0
        
        # 1. Evaluar rutas Hotel → Lugar (si hay hotel)
        if hotel_location:
            for place in places:
                distance = haversine_km(
                    hotel_location['lat'], hotel_location['lon'],
                    place['lat'], place['lon']
                )
                sequences.append({
                    "type": "hotel_to_place",
                    "from": hotel_location.get('name', 'Hotel'),
                    "to": place.get('name', 'Lugar'),
                    "distance": distance
                })
                total_distance += distance
        
        # 2. Evaluar rutas Lugar → Lugar
        place_to_place_distances = []
        for i, place_a in enumerate(places):
            for j, place_b in enumerate(places[i+1:], i+1):
                distance = haversine_km(
                    place_a['lat'], place_a['lon'],
                    place_b['lat'], place_b['lon']
                )
                place_to_place_distances.append(distance)
                sequences.append({
                    "type": "place_to_place",
                    "from": place_a.get('name', f'Lugar {i+1}'),
                    "to": place_b.get('name', f'Lugar {j+1}'),
                    "distance": distance
                })
        
        # 3. Evaluar rutas Lugar → Hotel (si hay hotel)
        if hotel_location:
            for place in places:
                distance = haversine_km(
                    place['lat'], place['lon'],
                    hotel_location['lat'], hotel_location['lon']
                )
                sequences.append({
                    "type": "place_to_hotel",
                    "from": place.get('name', 'Lugar'),
                    "to": hotel_location.get('name', 'Hotel'),
                    "distance": distance
                })
        
        # 4. Análisis y recomendaciones
        avg_place_distance = sum(place_to_place_distances) / len(place_to_place_distances) if place_to_place_distances else 0
        max_place_distance = max(place_to_place_distances) if place_to_place_distances else 0
        min_place_distance = min(place_to_place_distances) if place_to_place_distances else 0
        
        # Determinar estrategia óptima
        optimization_suggestion = "distribute"  # Por defecto
        
        if len(places) <= 2:
            optimization_suggestion = "group_same_day"
        elif avg_place_distance <= 2.0:
            optimization_suggestion = "group_same_day"  # Muy cercanos
        elif avg_place_distance <= 5.0 and max_place_distance <= 8.0:
            optimization_suggestion = "group_pairs"  # Agrupar de a pares
        elif max_place_distance > 15.0:
            optimization_suggestion = "distribute_far"  # Distribuir lugares lejanos
        else:
            optimization_suggestion = "distribute"  # Distribución normal
        
        return {
            "total_distance": total_distance,
            "sequences": sequences,
            "place_to_place_avg": avg_place_distance,
            "place_to_place_max": max_place_distance,
            "place_to_place_min": min_place_distance,
            "optimization_suggestion": optimization_suggestion,
            "analysis": {
                "total_routes_evaluated": len(sequences),
                "hotel_routes": len([s for s in sequences if s["type"] in ["hotel_to_place", "place_to_hotel"]]),
                "place_routes": len([s for s in sequences if s["type"] == "place_to_place"])
            }
        }
    
    def _get_intercity_threshold(self, clusters: List[Cluster]) -> float:
        """Determinar umbral intercity"""
        return settings.INTERCITY_THRESHOLD_KM_RURAL if len(clusters) > 3 else settings.INTERCITY_THRESHOLD_KM_URBAN

    async def _generate_free_days_with_suggestions(
        self, 
        start_date: datetime, 
        end_date: datetime, 
        daily_start_hour: int = 9, 
        daily_end_hour: int = 18
    ) -> Dict:
        """
        🆕 Generar días completamente libres con sugerencias automáticas
        """
        from services.google_places_service import GooglePlacesService
        
        places_service = GooglePlacesService()
        
        # Calcular ubicación por defecto (centro de Chile para búsquedas generales)
        default_lat, default_lon = -33.4489, -70.6693  # Santiago como centro
        
        days_dict = {}
        total_days = (end_date - start_date).days + 1
        
        logging.info(f"🏖️ Generando {total_days} días libres con sugerencias")
        
        for i in range(total_days):
            current_date = start_date + timedelta(days=i)
            date_key = current_date.strftime('%Y-%m-%d')
            day_number = i + 1
            
            # Tiempo total disponible por día
            daily_minutes = (daily_end_hour - daily_start_hour) * 60
            
            # Generar sugerencias para este día con variedad inteligente
            try:
                # 🎯 DETECTAR TIPO DE DESTINO para sugerir tipos relevantes
                tourist_destinations = {
                    'san_pedro_atacama': (-22.91, -68.20, ['tourist_attraction', 'cafe', 'point_of_interest']),
                    'valparaiso': (-33.05, -71.62, ['art_gallery', 'museum', 'tourist_attraction']),
                    'santiago': (-33.45, -70.67, ['restaurant', 'museum', 'park']),
                    'antofagasta': (-23.65, -70.40, ['tourist_attraction', 'restaurant', 'cafe']),
                    'calama': (-22.49, -68.90, ['restaurant', 'shopping_mall', 'cafe']),
                }
                
                # Determinar tipos según ubicación
                suggested_types = None
                for dest_name, (dest_lat, dest_lon, dest_types) in tourist_destinations.items():
                    # Si estamos cerca de un destino conocido (dentro de ~50km)
                    distance = ((default_lat - dest_lat)**2 + (default_lon - dest_lon)**2)**0.5
                    if distance < 0.5:  # ~50km aproximadamente
                        suggested_types = dest_types
                        logging.info(f"🏛️ Detectado destino turístico: {dest_name.replace('_', ' ').title()}")
                        break
                
                # Si no detectamos destino específico, usar variedad general
                if not suggested_types:
                    suggested_types = ['tourist_attraction', 'restaurant', 'cafe', 'museum', 'park']
                
                suggestions = await places_service.search_nearby_real(
                    lat=default_lat,
                    lon=default_lon,
                    types=suggested_types,
                    limit=6,  # Más sugerencias para días libres
                    day_offset=day_number
                )
                
                # Fallback a sugerencias sintéticas si no hay reales
                if not suggestions:
                    suggestions = await places_service.search_nearby(
                        lat=default_lat,
                        lon=default_lon,
                        types=['restaurant', 'tourist_attraction', 'museum'],
                        limit=3
                    )
                    
            except Exception as e:
                logging.warning(f"Error generando sugerencias para día {day_number}: {e}")
                suggestions = []
            
            # Crear bloque libre completo con sugerencias
            free_block = {
                "start_time": daily_start_hour * 60,
                "end_time": daily_end_hour * 60,
                "duration_minutes": daily_minutes,
                "suggestions": suggestions,
                "note": f"Día libre completo con {len(suggestions)} sugerencias de lugares para explorar"
            }
            
            # Estructura del día libre
            days_dict[date_key] = {
                "day": day_number,
                "date": date_key,
                "activities": [],  # Sin actividades programadas
                "transfers": [],   # Sin transfers
                "free_blocks": [free_block],  # Un gran bloque libre con sugerencias
                "base": None,      # Sin hotel base asignado
                "travel_summary": {
                    "total_travel_time_s": 0,
                    "walking_time_minutes": 0,
                    "transport_time_minutes": 0,
                    "intercity_transfers_count": 0,
                }
            }
            
            logging.info(f"📅 Día {day_number}: {len(suggestions)} sugerencias generadas")
        
        return {
            "days": days_dict,
            "optimization_metrics": {
                "efficiency_score": 1.0,  # Máxima eficiencia para días libres
                "optimization_mode": "free_days_with_suggestions",
                "fallback_active": False,
                "total_clusters": 0,
                "total_activities": 0,
                "total_distance_km": 0,
                "total_travel_time_minutes": 0,
                "processing_time_seconds": 0.1,
                "free_days_generated": total_days
            }
        }

# =========================================================================
# MAIN FUNCTION V3.1
# =========================================================================

async def optimize_itinerary_hybrid_v31(
    places: List[Dict],
    start_date: datetime,
    end_date: datetime,
    daily_start_hour: int = 9,
    daily_end_hour: int = 18,
    transport_mode: str = 'walk',
    accommodations: Optional[List[Dict]] = None,
    packing_strategy: str = "balanced",
    extra_info: Optional[Dict] = None
) -> Dict:
    """
    🚀 HYBRID OPTIMIZER V3.1 - ENHANCED VERSION
    """
    optimizer = HybridOptimizerV31()
    time_window = TimeWindow(
        start=daily_start_hour * 60,
        end=daily_end_hour * 60
    )
    
    logging.info(f"🚀 Iniciando optimización híbrida V3.1")
    logging.info(f"📍 {len(places)} lugares, {(end_date - start_date).days + 1} días")
    logging.info(f"📦 Estrategia: {packing_strategy}")
    
    # 🛡️ VALIDACIÓN ROBUSTA DE COORDENADAS
    logging.info("🧭 Validando coordenadas de entrada...")
    places = optimizer.validate_coordinates(places)
    
    if not places:
        logging.error("❌ No hay lugares válidos después de la validación")
        return await optimizer._generate_free_days_with_suggestions(
            start_date, end_date, daily_start_hour, daily_end_hour
        )
    
    logging.info(f"✅ Validación completa: {len(places)} lugares válidos procesados")
    
    # 1. Clustering POIs
    clusters = optimizer.cluster_pois(places)
    if not clusters:
        # 🆕 DÍAS COMPLETAMENTE LIBRES CON SUGERENCIAS AUTOMÁTICAS
        logging.info("🏖️ Generando días libres con sugerencias automáticas")
        return await optimizer._generate_free_days_with_suggestions(
            start_date, end_date, daily_start_hour, daily_end_hour
        )
    
    # 2. Enhanced home base assignment
    logging.info(f"🏨 DEBUG: accommodations recibidas: {accommodations}")
    logging.info(f"🏨 DEBUG: cantidad de accommodations: {len(accommodations) if accommodations else 0}")
    if accommodations:
        for i, acc in enumerate(accommodations):
            logging.info(f"🏨 DEBUG Accommodation {i+1}: {acc.get('name', 'Sin nombre')}")
    
    clusters = await optimizer.assign_home_base_to_clusters(clusters, accommodations, places)
    
    # 3. Allocate clusters to days
    day_assignments = optimizer.allocate_clusters_to_days(clusters, start_date, end_date)
    
    # 4. Apply packing strategy
    day_assignments = optimizer.pack_activities_by_strategy(day_assignments, packing_strategy)
    
    # 5. Enhanced routing día por día
    days = []
    previous_end_location = None
    last_active_base = None
    
    # Para el primer día, identificar el hotel base como punto de partida
    first_day_hotel = None
    sorted_dates = sorted(day_assignments.keys())
    
    # Buscar el primer día con actividades para obtener su hotel base
    for date_str in sorted_dates:
        if day_assignments[date_str]:  # Día con actividades
            first_cluster = day_assignments[date_str][0]
            if hasattr(first_cluster, 'home_base') and first_cluster.home_base:
                first_day_hotel = (first_cluster.home_base['lat'], first_cluster.home_base['lon'])
                break
    
    # Crear lista ordenada de fechas para tener índice de día
    for day_index, date_str in enumerate(sorted_dates):
        day_number = day_index + 1  # Día 1, 2, 3, etc.
        assigned_clusters = day_assignments[date_str]
        
        if not assigned_clusters:
            # Día libre con sugerencias - usar ubicación del último día activo
            effective_location = previous_end_location or last_active_base
            
            # Usar función enhanced para generar sugerencias reales con variedad por día
            free_blocks_objects = await optimizer._generate_free_blocks_enhanced(
                time_window.start, time_window.end, effective_location, day_number
            )
            
            # Convertir objetos FreeBlock a diccionarios
            free_blocks = []
            for fb in free_blocks_objects:
                free_blocks.append({
                    "start_time": fb.start_time,
                    "end_time": fb.end_time,
                    "duration_minutes": fb.duration_minutes,
                    "suggestions": fb.suggestions,
                    "note": fb.note
                })
            
            # Base heredada del último día activo
            inherited_base = last_active_base if last_active_base else None
            
            days.append({
                "date": date_str,
                "activities": [],
                "timeline": [],
                "transfers": [],
                "free_blocks": free_blocks,
                "base": inherited_base,
                "travel_summary": {
                    "total_travel_time_s": 0,
                    "total_distance_km": 0,
                    "walking_time_minutes": 0,
                    "transport_time_minutes": 0,
                    "intercity_transfers_count": 0,
                    "intercity_total_minutes": 0
                },
                "free_minutes": time_window.end - time_window.start
            })
            continue
        
        # Para el primer día activo, usar el hotel base como punto de partida
        start_location = previous_end_location
        if previous_end_location is None and first_day_hotel is not None:
            start_location = first_day_hotel
            
        day_result = await optimizer.route_day_enhanced(
            date_str, assigned_clusters, time_window, transport_mode, start_location, day_number, extra_info
        )
        days.append(day_result)
        previous_end_location = day_result.get('end_location')
        
        # Actualizar la base del último día activo para herencia
        if day_result.get('base'):
            last_active_base = day_result['base']
    
    # 🌍 DETECCIÓN DE INTERCITY TRANSFERS ENTRE DÍAS
    await optimizer._inject_intercity_transfers_between_days(days)
    
    # 6. Enhanced metrics
    optimization_metrics = optimizer.calculate_enhanced_metrics(days)
    
    # 🚀 Agregar estadísticas de performance
    cache_stats = optimizer.get_cache_stats()
    optimization_metrics['cache_performance'] = cache_stats
    
    logging.info(f"✅ Optimización V3.1 completada:")
    logging.info(f"  📊 {sum(len(d['activities']) for d in days)} actividades programadas")
    logging.info(f"  🎯 Score: {optimization_metrics['efficiency_score']:.1%}")
    logging.info(f"  🚗 {optimization_metrics['long_transfers_detected']} traslados intercity")
    logging.info(f"  ⚡ Cache: {cache_stats['hit_rate_percent']:.1f}% hit rate ({cache_stats['cache_hits']} hits)")
    
    return {
        "days": days,
        "optimization_metrics": optimization_metrics,
        "clusters_info": {
            "total_clusters": len(clusters),
            "hotels_assigned": sum(1 for c in clusters if c.home_base_source != "none"),
            "recommended_hotels": sum(1 for c in clusters if c.home_base_source in ["recommended", "auto_recommended_by_system"]),
            "packing_strategy_used": packing_strategy
        },
        "additional_recommendations": {
            "intercity_suggestions": [
                {
                    "cluster_id": c.label,
                    "hotel_name": c.home_base.get('name', 'N/A') if c.home_base else 'N/A',
                    "local_attractions": c.additional_suggestions,
                    "message": f"Ya que visitarás {c.home_base.get('name', 'esta área')}, te sugerimos estas actividades adicionales en la zona:"
                }
                for c in clusters if hasattr(c, 'additional_suggestions') and c.additional_suggestions
            ]
        }
    }

# Función de compatibilidad
async def optimize_itinerary_hybrid(
    places: List[Dict],
    start_date: datetime,
    end_date: datetime,
    daily_start_hour: int = 9,
    daily_end_hour: int = 18,
    transport_mode: str = 'walk',
    accommodations: Optional[List[Dict]] = None,
    extra_info: Optional[Dict] = None
) -> Dict:
    """Wrapper para mantener compatibilidad"""
    return await optimize_itinerary_hybrid_v31(
        places, start_date, end_date, daily_start_hour, 
        daily_end_hour, transport_mode, accommodations,
        settings.DEFAULT_PACKING_STRATEGY, extra_info
    )
