"""
🆓 FREE ROUTING SERVICE - Servicio de rutas completamente gratuito
Combina múltiples fuentes: OSRM + OpenRoute + Fallback inteligente
"""

import asyncio
import logging
from typing import Dict, Tuple, Optional
from utils.osrm_service import OSRMService
from utils.openroute_service import OpenRouteService
from utils.geo_utils import haversine_km

class FreeRoutingService:
    def __init__(self):
        self.osrm = OSRMService()
        self.openroute = OpenRouteService()
        self.logger = logging.getLogger(__name__)
        
    async def eta_between(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        transport_mode: str = 'walk'
    ) -> Dict:
        """
        🎯 ETA inteligente con múltiples fuentes gratuitas
        Prioridad: OSRM → OpenRoute → Fallback inteligente
        """
        
        # Para distancias muy cortas, usar cálculo directo
        distance_km = haversine_km(origin[0], origin[1], destination[0], destination[1])
        
        if distance_km < 0.1:  # Menos de 100m
            return self._micro_distance_eta(distance_km, transport_mode)
        
        # Intentar servicios en orden de prioridad
        services = [
            ('OSRM', self.osrm.eta_between),
            ('OpenRoute', self.openroute.eta_between)
        ]
        
        for service_name, service_func in services:
            try:
                result = await asyncio.wait_for(
                    service_func(origin, destination, transport_mode),
                    timeout=8.0
                )
                
                if result.get('status') in ['OK', 'FALLBACK_CALCULATION']:
                    self.logger.debug(f"✅ ETA obtenida de {service_name}")
                    result['primary_source'] = service_name.lower()
                    return self._validate_and_adjust_eta(result, distance_km, transport_mode)
                    
            except asyncio.TimeoutError:
                self.logger.warning(f"⏱️ {service_name} timeout")
                continue
            except Exception as e:
                self.logger.warning(f"❌ {service_name} error: {e}")
                continue
        
        # Fallback inteligente final
        self.logger.info(f"🔄 Usando fallback inteligente para {distance_km:.1f}km")
        return self._intelligent_fallback(origin, destination, transport_mode, distance_km)
    
    def _micro_distance_eta(self, distance_km: float, transport_mode: str) -> Dict:
        """ETA para distancias muy cortas (<100m)"""
        if transport_mode in ['walk', 'walking']:
            # Caminar 100m = ~1.5 minutos a velocidad normal
            duration_minutes = max(1.0, (distance_km / 5.0) * 60)
        else:
            # En carro, tiempo mínimo por semáforos/tráfico urbano
            duration_minutes = max(2.0, (distance_km / 20.0) * 60)
        
        return {
            'distance_km': distance_km,
            'duration_minutes': duration_minutes,
            'status': 'OK',
            'google_enhanced': False,
            'source': 'micro_distance_calculation',
            'primary_source': 'direct_calculation'
        }
    
    def _intelligent_fallback(
        self, 
        origin: Tuple[float, float], 
        destination: Tuple[float, float],
        transport_mode: str,
        distance_km: float
    ) -> Dict:
        """Fallback con velocidades ajustadas por contexto urbano/rural"""
        
        # Detectar contexto urbano vs rural por densidad de coordenadas
        is_urban = self._detect_urban_context(origin, destination)
        
        # Velocidades ajustadas por contexto
        if is_urban:
            speeds = {
                'walk': 4.5,     # Más lento por semáforos
                'walking': 4.5,
                'drive': 25.0,   # Mucho más lento por tráfico urbano
                'car': 25.0,
                'transit': 20.0,
                'bicycle': 12.0
            }
            buffer_factor = 1.4  # 40% buffer urbano
        else:
            speeds = {
                'walk': 5.5,     # Más rápido en campo/suburbios
                'walking': 5.5,
                'drive': 70.0,   # Velocidad de carretera
                'car': 70.0,
                'transit': 45.0,
                'bicycle': 18.0
            }
            buffer_factor = 1.2  # 20% buffer rural
        
        speed_kmh = speeds.get(transport_mode, 5.0)
        duration_minutes = (distance_km / speed_kmh) * 60 * buffer_factor
        
        context = "urban" if is_urban else "rural"
        
        return {
            'distance_km': distance_km,
            'duration_minutes': duration_minutes,
            'status': 'INTELLIGENT_FALLBACK',
            'google_enhanced': False,
            'source': f'intelligent_fallback_{context}',
            'primary_source': 'fallback_calculation',
            'context_detected': context,
            'speed_used_kmh': speed_kmh,
            'buffer_applied': f"{int((buffer_factor-1)*100)}%"
        }
    
    def _detect_urban_context(self, origin: Tuple[float, float], destination: Tuple[float, float]) -> bool:
        """Detectar si es contexto urbano basado en coordenadas"""
        # Heurística simple: coordenadas con muchos decimales = área urbana densa
        lat_precision = len(str(origin[0]).split('.')[-1])
        lon_precision = len(str(origin[1]).split('.')[-1])
        
        # Más de 4 decimales sugiere precisión urbana
        return (lat_precision + lon_precision) >= 8
    
    def _validate_and_adjust_eta(self, result: Dict, haversine_distance_km: float, transport_mode: str) -> Dict:
        """Validar y ajustar ETA por coherencia - prioriza distancia por calles reales"""
        reported_distance = result.get('distance_km', haversine_distance_km)
        duration_minutes = result.get('duration_minutes', 0)
        
        # Validar coherencia de distancias pero mantener la reportada por APIs
        distance_diff = abs(reported_distance - haversine_distance_km)
        if distance_diff > 0.1:  # Diferencia > 100m
            self.logger.info(f"📏 Discrepancia: API={reported_distance:.1f}km vs línea_recta={haversine_distance_km:.1f}km - usando distancia por calles")
            # Mantener la distancia reportada por API (más precisa para rutas reales)
            # Solo usar Haversine si la discrepancia es extrema (>200% diferencia)
            if distance_diff > haversine_distance_km * 2.0:
                self.logger.warning(f"⚠️ Discrepancia extrema detectada - usando distancia Haversine como fallback")
                result['distance_km'] = haversine_distance_km
                result['fallback_to_haversine'] = True
            else:
                # Mantener distancia por calles (reportada por API)
                result['distance_validated'] = True
        
        # Validar velocidades mínimas/máximas razonables
        if duration_minutes > 0:
            implied_speed_kmh = (result['distance_km'] / duration_minutes) * 60
            
            speed_limits = {
                'walk': (2.0, 8.0),      # 2-8 km/h
                'walking': (2.0, 8.0),
                'drive': (10.0, 120.0),   # 10-120 km/h
                'car': (10.0, 120.0),
                'transit': (8.0, 80.0),   # 8-80 km/h
                'bicycle': (8.0, 30.0)    # 8-30 km/h
            }
            
            min_speed, max_speed = speed_limits.get(transport_mode, (1.0, 150.0))
            
            if implied_speed_kmh < min_speed or implied_speed_kmh > max_speed:
                # Ajustar a velocidad razonable
                target_speed = min_speed * 1.5 if implied_speed_kmh < min_speed else max_speed * 0.8
                result['duration_minutes'] = (result['distance_km'] / target_speed) * 60
                result['speed_adjusted'] = True
                self.logger.debug(f"🔧 Velocidad ajustada de {implied_speed_kmh:.1f} a {target_speed:.1f} km/h")
        
        return result
    
    async def get_distance_km(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        transport_mode: str = 'drive'
    ) -> Optional[float]:
        """
        📏 Obtener solo la distancia entre dos puntos
        """
        try:
            result = await self.eta_between(
                (origin_lat, origin_lon),
                (dest_lat, dest_lon),
                transport_mode
            )
            return result.get('distance_km') if result else None
        except Exception as e:
            self.logger.debug(f"Error obteniendo distancia: {e}")
            # Fallback a distancia haversine
            return haversine_km(origin_lat, origin_lon, dest_lat, dest_lon)