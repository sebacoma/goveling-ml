"""
🚀 HYBRID ROUTING SERVICE - FASE 2
Sistema híbrido inteligente que combina:
- OSRM para rutas urbanas (< 50km) - Rápido y gratuito
- Google para rutas intercity (> 50km) - Preciso pero pagado
- Euclidiano como fallback ultra-rápido
"""

import asyncio
import time
import requests
import logging
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.geo_utils import haversine_km

logger = logging.getLogger(__name__)

@dataclass
class RoutingResult:
    distance_km: float
    duration_minutes: float
    processing_time_ms: float
    source: str
    success: bool
    confidence: float  # 0-1, qué tan confiable es el resultado
    fallback_from: Optional[str] = None

class HybridRoutingService:
    """
    🎯 Servicio de routing híbrido inteligente
    Optimizado para velocidad y precisión según tipo de ruta
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Configuración de thresholds
        self.URBAN_THRESHOLD_KM = 50  # Umbral urbano vs intercity
        self.TIMEOUT_OSRM = 5  # Timeout OSRM en segundos
        self.TIMEOUT_GOOGLE = 10  # Timeout Google en segundos
        
        # URLs base
        self.osrm_base = "http://router.project-osrm.org"
        
        # Importar servicios existentes
        try:
            from utils.free_routing_service import FreeRoutingService
            self.google_service = FreeRoutingService()
            self.google_available = True
        except ImportError:
            self.logger.warning("⚠️ Google routing service no disponible")
            self.google_available = False
        
        # Estadísticas para monitoreo
        self.stats = {
            'osrm_calls': 0,
            'google_calls': 0,
            'euclidean_calls': 0,
            'osrm_failures': 0,
            'google_failures': 0,
            'total_time_saved_ms': 0
        }
        
        self.logger.info("🚀 HybridRoutingService inicializado")
    
    async def get_route(self, origin: Tuple[float, float], 
                       destination: Tuple[float, float],
                       mode: str = 'drive') -> RoutingResult:
        """
        🎯 Obtener ruta usando estrategia híbrida inteligente
        
        Args:
            origin: (lat, lon) punto origen
            destination: (lat, lon) punto destino  
            mode: Modo de transporte ('drive', 'walk', 'transit')
        """
        start_time = time.time()
        
        # 1. Calcular distancia euclidiana para decisión
        euclidean_distance = haversine_km(origin[0], origin[1], destination[0], destination[1])
        
        # 2. Decidir estrategia basada en distancia
        if euclidean_distance <= self.URBAN_THRESHOLD_KM:
            # Ruta urbana: OSRM primero
            result = await self._route_urban_strategy(origin, destination, mode, euclidean_distance)
        else:
            # Ruta intercity: Google primero  
            result = await self._route_intercity_strategy(origin, destination, mode, euclidean_distance)
        
        # 3. Actualizar tiempo de procesamiento total
        total_time = (time.time() - start_time) * 1000
        result.processing_time_ms = total_time
        
        # 4. Logging para monitoreo
        self.logger.info(f"🛣️ Route {origin} → {destination}: {result.source} "
                        f"({result.distance_km}km, {result.processing_time_ms:.0f}ms)")
        
        return result
    
    async def _route_urban_strategy(self, origin: Tuple, destination: Tuple, 
                                  mode: str, euclidean_distance: float) -> RoutingResult:
        """🏙️ Estrategia para rutas urbanas: OSRM → Google → Euclidiano"""
        
        # 1. Intentar OSRM primero (rápido y gratuito)
        osrm_result = await self._get_osrm_route(origin, destination, mode)
        if osrm_result and osrm_result.success:
            self.stats['osrm_calls'] += 1
            return osrm_result
        
        self.stats['osrm_failures'] += 1
        self.logger.warning(f"⚠️ OSRM falló para ruta urbana")
        
        # 2. Fallback a Google
        if self.google_available:
            google_result = await self._get_google_route(origin, destination, mode)
            if google_result and google_result.success:
                google_result.fallback_from = 'osrm'
                self.stats['google_calls'] += 1
                return google_result
        
        # 3. Fallback final a euclidiano
        return self._get_euclidean_route(origin, destination, mode, euclidean_distance)
    
    async def _route_intercity_strategy(self, origin: Tuple, destination: Tuple,
                                      mode: str, euclidean_distance: float) -> RoutingResult:
        """🛣️ Estrategia para rutas intercity: Google → OSRM → Euclidiano"""
        
        # 1. Intentar Google primero (más preciso para distancias largas)
        if self.google_available:
            google_result = await self._get_google_route(origin, destination, mode)
            if google_result and google_result.success:
                self.stats['google_calls'] += 1
                return google_result
        
        self.logger.warning(f"⚠️ Google falló para ruta intercity")
        
        # 2. Fallback a OSRM (aunque menos preciso, mejor que nada)
        osrm_result = await self._get_osrm_route(origin, destination, mode)
        if osrm_result and osrm_result.success:
            osrm_result.fallback_from = 'google'
            osrm_result.confidence = 0.7  # Menor confianza para intercity
            self.stats['osrm_calls'] += 1
            return osrm_result
        
        # 3. Fallback final a euclidiano
        return self._get_euclidean_route(origin, destination, mode, euclidean_distance)
    
    async def _get_osrm_route(self, origin: Tuple, destination: Tuple, 
                            mode: str) -> Optional[RoutingResult]:
        """🚗 Obtener ruta usando OSRM"""
        try:
            start_time = time.time()
            
            # Mapear modos de transporte
            osrm_mode = 'driving' if mode in ['drive', 'car'] else 'walking'
            
            # OSRM usa lon,lat (no lat,lon)
            url = f"{self.osrm_base}/route/v1/{osrm_mode}/{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
            params = {
                'overview': 'false',
                'steps': 'false',
                'geometries': 'geojson'
            }
            
            response = requests.get(url, params=params, timeout=self.TIMEOUT_OSRM)
            processing_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                data = response.json()
                
                if data['code'] == 'Ok' and data['routes']:
                    route = data['routes'][0]
                    
                    return RoutingResult(
                        distance_km=round(route['distance'] / 1000, 2),
                        duration_minutes=round(route['duration'] / 60, 1),
                        processing_time_ms=processing_time,
                        source='osrm',
                        success=True,
                        confidence=0.9  # Alta confianza para OSRM urbano
                    )
            
            return None
            
        except Exception as e:
            self.logger.warning(f"⚠️ OSRM error: {e}")
            return None
    
    async def _get_google_route(self, origin: Tuple, destination: Tuple,
                              mode: str) -> Optional[RoutingResult]:
        """🗺️ Obtener ruta usando Google (tu servicio actual)"""
        try:
            start_time = time.time()
            
            # Usar tu servicio existente
            result = await self.google_service.eta_between(origin, destination, mode)
            processing_time = (time.time() - start_time) * 1000
            
            if result and 'distance_km' in result:
                return RoutingResult(
                    distance_km=result.get('distance_km', 0),
                    duration_minutes=result.get('duration_minutes', 0),
                    processing_time_ms=processing_time,
                    source='google',
                    success=True,
                    confidence=0.95  # Muy alta confianza para Google
                )
            
            return None
            
        except Exception as e:
            self.logger.warning(f"⚠️ Google routing error: {e}")
            return None
    
    def _get_euclidean_route(self, origin: Tuple, destination: Tuple,
                           mode: str, euclidean_distance: float) -> RoutingResult:
        """📏 Fallback euclidiano (siempre funciona)"""
        start_time = time.time()
        
        # Calcular duración estimada según modo
        speed_factors = {
            'walk': 5,    # 5 km/h
            'drive': 25,  # 25 km/h urbano promedio
            'car': 25,
            'transit': 20,
            'bike': 15
        }
        
        speed_kmh = speed_factors.get(mode, 25)
        duration_minutes = (euclidean_distance / speed_kmh) * 60
        
        processing_time = (time.time() - start_time) * 1000
        
        self.stats['euclidean_calls'] += 1
        
        return RoutingResult(
            distance_km=euclidean_distance,
            duration_minutes=round(duration_minutes, 1),
            processing_time_ms=processing_time,
            source='euclidean',
            success=True,
            confidence=0.6,  # Baja confianza, pero siempre disponible
            fallback_from='all_services'
        )
    
    def get_stats(self) -> Dict:
        """📊 Obtener estadísticas del servicio"""
        total_calls = sum([
            self.stats['osrm_calls'],
            self.stats['google_calls'], 
            self.stats['euclidean_calls']
        ])
        
        if total_calls == 0:
            return self.stats
        
        return {
            **self.stats,
            'osrm_success_rate': (self.stats['osrm_calls'] / (self.stats['osrm_calls'] + self.stats['osrm_failures'])) * 100 if self.stats['osrm_calls'] + self.stats['osrm_failures'] > 0 else 0,
            'total_calls': total_calls,
            'osrm_usage_percent': (self.stats['osrm_calls'] / total_calls) * 100,
            'google_usage_percent': (self.stats['google_calls'] / total_calls) * 100,
            'euclidean_usage_percent': (self.stats['euclidean_calls'] / total_calls) * 100
        }
    
    def reset_stats(self):
        """🔄 Resetear estadísticas"""
        for key in self.stats:
            self.stats[key] = 0

# Test del servicio híbrido
async def test_hybrid_routing_service():
    """🧪 Test completo del servicio híbrido"""
    print("🧪 TESTING HYBRID ROUTING SERVICE")
    print("="*45)
    
    service = HybridRoutingService()
    
    # Test cases variados
    test_routes = [
        ((-33.4489, -70.6693), (-33.4372, -70.6506), "Santiago Centro → Plaza (2km) [URBANO]"),
        ((-33.4203, -70.6336), (-33.4489, -70.6693), "San Cristóbal → Centro (3km) [URBANO]"),
        ((-33.4489, -70.6693), (-33.0472, -71.6127), "Santiago → Valparaíso (120km) [INTERCITY]"),
        ((-22.9100, -68.1969), (-23.6509, -70.3975), "Atacama → Antofagasta (180km) [INTERCITY]")
    ]
    
    results = []
    
    for origin, destination, description in test_routes:
        print(f"\n🛣️ {description}")
        
        result = await service.get_route(origin, destination, 'drive')
        results.append(result)
        
        print(f"   Source: {result.source}")
        print(f"   Distance: {result.distance_km}km")
        print(f"   Duration: {result.duration_minutes}min")
        print(f"   Time: {result.processing_time_ms:.0f}ms")
        print(f"   Confidence: {result.confidence:.1%}")
        if result.fallback_from:
            print(f"   Fallback from: {result.fallback_from}")
    
    # Estadísticas finales
    print(f"\n📊 ESTADÍSTICAS DEL SERVICIO:")
    stats = service.get_stats()
    
    print(f"   Total calls: {stats['total_calls']}")
    print(f"   OSRM usage: {stats['osrm_usage_percent']:.1f}%")
    print(f"   Google usage: {stats['google_usage_percent']:.1f}%")
    print(f"   Euclidean usage: {stats['euclidean_usage_percent']:.1f}%")
    print(f"   OSRM success rate: {stats['osrm_success_rate']:.1f}%")
    
    # Calcular mejora de velocidad estimada
    avg_processing_time = sum(r.processing_time_ms for r in results) / len(results)
    baseline_time = 6880  # Tu sistema actual
    improvement = baseline_time / avg_processing_time
    
    print(f"\n⚡ RENDIMIENTO:")
    print(f"   Tiempo promedio: {avg_processing_time:.0f}ms")
    print(f"   Baseline anterior: {baseline_time}ms")
    print(f"   Mejora: {improvement:.1f}x más rápido")
    
    if improvement > 3:
        print(f"   🎉 ¡EXCELENTE MEJORA!")
    elif improvement > 2:
        print(f"   ✅ Mejora significativa")
    else:
        print(f"   ⚠️ Mejora marginal")

if __name__ == "__main__":
    asyncio.run(test_hybrid_routing_service())