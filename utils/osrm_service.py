"""
🚗 OSRM Service - Routing gratuito con Open Source Routing Machine
Servidor público gratuito sin límites estrictos
"""

import aiohttp
import logging
from typing import Dict, Tuple
from utils.google_cache import cache_google_api
from utils.geo_utils import haversine_km

class OSRMService:
    def __init__(self):
        # Servidor público de OSRM (gratuito)
        self.base_url = "https://router.project-osrm.org"
        self.logger = logging.getLogger(__name__)
    
    @cache_google_api(ttl=3600)
    async def eta_between(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        transport_mode: str = 'walk'
    ) -> Dict:
        """Obtener ETA usando OSRM"""
        
        try:
            # OSRM principalmente para driving, walking se simula
            if transport_mode in ['walk', 'walking']:
                return await self._walking_eta(origin, destination)
            else:
                return await self._driving_eta(origin, destination)
                
        except Exception as e:
            self.logger.warning(f"OSRM request failed: {e}")
            return self._fallback_eta(origin, destination, transport_mode)
    
    async def _driving_eta(self, origin: Tuple[float, float], destination: Tuple[float, float]) -> Dict:
        """ETA para conducir usando OSRM"""
        # OSRM usa formato lon,lat
        coords = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
        url = f"{self.base_url}/route/v1/driving/{coords}"
        
        params = {
            'overview': 'false',
            'alternatives': 'false',
            'steps': 'false',
            'geometries': 'polyline'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_osrm_response(data)
                else:
                    raise Exception(f"OSRM HTTP {response.status}")
    
    async def _walking_eta(self, origin: Tuple[float, float], destination: Tuple[float, float]) -> Dict:
        """ETA para caminar - usar cálculo directo mejorado"""
        
        distance_km = haversine_km(origin[0], origin[1], destination[0], destination[1])
        
        # Cálculo más preciso para caminar en ciudad
        if distance_km <= 0.5:  # ≤500m - velocidad normal
            speed_kmh = 5.0
        elif distance_km <= 2.0:  # ≤2km - velocidad ligeramente reducida  
            speed_kmh = 4.5
        else:  # >2km - velocidad más lenta por fatiga
            speed_kmh = 4.0
        
        duration_minutes = (distance_km / speed_kmh) * 60 * 1.15  # 15% buffer urbano
        
        return {
            'distance_km': distance_km,
            'duration_minutes': duration_minutes,
            'status': 'OK',
            'google_enhanced': False,
            'source': 'osrm_walking_calculated'
        }
    
    def _parse_osrm_response(self, data: Dict) -> Dict:
        """Parsear respuesta de OSRM"""
        route = data['routes'][0]
        
        distance_m = route['distance']
        duration_s = route['duration']
        
        return {
            'distance_km': distance_m / 1000.0,
            'duration_minutes': duration_s / 60.0,
            'status': 'OK',
            'google_enhanced': False,
            'source': 'osrm'
        }
    
    def _fallback_eta(self, origin: Tuple[float, float], destination: Tuple[float, float], mode: str) -> Dict:
        """Fallback usando cálculo haversine"""
        
        distance_km = haversine_km(origin[0], origin[1], destination[0], destination[1])
        
        speeds = {
            'walk': 5.0,
            'walking': 5.0,
            'drive': 45.0,   # Más conservador que Google
            'car': 45.0,
            'transit': 25.0,
            'bicycle': 15.0
        }
        
        speed_kmh = speeds.get(mode, 5.0)
        duration_minutes = (distance_km / speed_kmh) * 60 * 1.25  # 25% buffer
        
        return {
            'distance_km': distance_km,
            'duration_minutes': duration_minutes,
            'status': 'FALLBACK_OSRM',
            'google_enhanced': False,
            'source': 'fallback_haversine'
        }