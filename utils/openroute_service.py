"""
🗺️ OpenRouteService - Alternativa gratuita a Google Directions
Límites: 2,000 requests/día gratuito
"""

import aiohttp
import logging
from typing import Dict, Tuple, Optional
from utils.google_cache import cache_google_api
from utils.geo_utils import haversine_km
from settings import settings

class OpenRouteService:
    def __init__(self):
        self.base_url = "https://api.openrouteservice.org/v2"
        self.api_key = getattr(settings, 'OPENROUTE_API_KEY', None)
        self.logger = logging.getLogger(__name__)
        
        # Mapeo de modos de transporte
        self.transport_modes = {
            'walk': 'foot-walking',
            'walking': 'foot-walking',
            'drive': 'driving-car',
            'car': 'driving-car',
            'transit': 'driving-car',  # Fallback a carro
            'bicycle': 'cycling-regular'
        }
    
    @cache_google_api(ttl=3600)
    async def eta_between(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        transport_mode: str = 'walk'
    ) -> Dict:
        """Obtener ETA usando OpenRouteService"""
        
        if not self.api_key:
            self.logger.warning("⚠️ OpenRouteService API key no configurada - usando fallback")
            return self._fallback_eta(origin, destination, transport_mode)
        
        try:
            # Convertir modo de transporte
            ors_mode = self.transport_modes.get(transport_mode, 'foot-walking')
            
            # Construir URL - OpenRoute usa [lon, lat] no [lat, lon]
            start_coords = f"{origin[1]},{origin[0]}"
            end_coords = f"{destination[1]},{destination[0]}"
            
            url = f"{self.base_url}/directions/{ors_mode}"
            
            params = {
                'api_key': self.api_key,
                'start': start_coords,
                'end': end_coords,
                'format': 'json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_openroute_response(data)
                    else:
                        self.logger.warning(f"OpenRoute error {response.status}")
                        return self._fallback_eta(origin, destination, transport_mode)
                        
        except Exception as e:
            self.logger.warning(f"OpenRoute request failed: {e}")
            return self._fallback_eta(origin, destination, transport_mode)
    
    def _parse_openroute_response(self, data: Dict) -> Dict:
        """Parsear respuesta de OpenRouteService"""
        try:
            route = data['routes'][0]
            summary = route['summary']
            
            distance_m = summary['distance']
            duration_s = summary['duration']
            
            return {
                'distance_km': distance_m / 1000.0,
                'duration_minutes': duration_s / 60.0,
                'status': 'OK',
                'google_enhanced': False,
                'source': 'openroute'
            }
        except (KeyError, IndexError) as e:
            self.logger.error(f"Error parsing OpenRoute response: {e}")
            raise
    
    def _fallback_eta(self, origin: Tuple[float, float], destination: Tuple[float, float], mode: str) -> Dict:
        """Fallback usando cálculo directo"""
        
        distance_km = haversine_km(origin[0], origin[1], destination[0], destination[1])
        
        # Velocidades promedio
        speeds = {
            'walk': 5.0,     # 5 km/h
            'walking': 5.0,
            'drive': 50.0,   # 50 km/h en ciudad
            'car': 50.0,
            'transit': 30.0, # 30 km/h promedio
            'bicycle': 15.0  # 15 km/h
        }
        
        speed_kmh = speeds.get(mode, 5.0)
        duration_minutes = (distance_km / speed_kmh) * 60 * 1.2  # 20% buffer
        
        return {
            'distance_km': distance_km,
            'duration_minutes': duration_minutes,
            'status': 'FALLBACK_CALCULATION',
            'google_enhanced': False,
            'source': 'fallback_calculation'
        }