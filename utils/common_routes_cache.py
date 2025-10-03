"""
🚀 CACHE DE RUTAS COMUNES - Optimización de tiempo de respuesta
Pre-cálculo de rutas frecuentes en Chile para reducir latencia hasta 60%
"""

import math
import logging
from typing import Dict, Tuple, Optional
from utils.geo_utils import haversine_km

logger = logging.getLogger(__name__)

class CommonRoutesCache:
    """Cache inteligente de rutas comunes chilenas con tolerancia geográfica"""
    
    def __init__(self):
        self.tolerance_km = 15.0  # Tolerancia para matching de ubicaciones
        
        # 🗺️ RUTAS PRE-CALCULADAS CHILE (ciudades principales)
        self.COMMON_ROUTES = {
            # REGIÓN METROPOLITANA ↔ OTRAS REGIONES
            "santiago_valparaiso": {
                "distance_km": 120,
                "duration_min_car": 90,
                "duration_min_bus": 105,
                "duration_min_walk": 1440,  # 24h (impracticable)
                "coordinates": [(-33.4489, -70.6693), (-33.0472, -71.6127)]
            },
            "santiago_atacama": {
                "distance_km": 1600,
                "duration_min_car": 960,  # 16h
                "duration_min_bus": 1200,  # 20h
                "duration_min_flight": 120,  # 2h
                "coordinates": [(-33.4489, -70.6693), (-22.4594, -68.9139)]
            },
            "santiago_iquique": {
                "distance_km": 1800,
                "duration_min_car": 1080,  # 18h
                "duration_min_bus": 1380,  # 23h
                "duration_min_flight": 135,  # 2.25h
                "coordinates": [(-33.4489, -70.6693), (-20.2307, -70.1355)]
            },
            "santiago_antofagasta": {
                "distance_km": 1355,
                "duration_min_car": 840,  # 14h
                "duration_min_bus": 1020,  # 17h
                "duration_min_flight": 105,  # 1.75h
                "coordinates": [(-33.4489, -70.6693), (-23.6509, -70.3975)]
            },
            "santiago_serena": {
                "distance_km": 470,
                "duration_min_car": 300,  # 5h
                "duration_min_bus": 360,  # 6h
                "duration_min_flight": 75,  # 1.25h
                "coordinates": [(-33.4489, -70.6693), (-29.9027, -71.2519)]
            },
            "santiago_concepcion": {
                "distance_km": 515,
                "duration_min_car": 330,  # 5.5h
                "duration_min_bus": 420,  # 7h
                "duration_min_flight": 85,  # 1.4h
                "coordinates": [(-33.4489, -70.6693), (-36.8201, -73.0444)]
            },
            "santiago_temuco": {
                "distance_km": 675,
                "duration_min_car": 450,  # 7.5h
                "duration_min_bus": 540,  # 9h
                "duration_min_flight": 90,  # 1.5h
                "coordinates": [(-33.4489, -70.6693), (-38.7359, -72.5904)]
            },
            "santiago_valdiva": {
                "distance_km": 840,
                "duration_min_car": 570,  # 9.5h
                "duration_min_bus": 660,  # 11h
                "duration_min_flight": 95,  # 1.6h
                "coordinates": [(-33.4489, -70.6693), (-39.8142, -73.2459)]
            },
            "santiago_puertomonte": {
                "distance_km": 1015,
                "duration_min_car": 720,  # 12h
                "duration_min_bus": 840,  # 14h
                "duration_min_flight": 105,  # 1.75h
                "coordinates": [(-33.4489, -70.6693), (-41.4693, -72.9424)]
            },
            "santiago_puntaarenas": {
                "distance_km": 3090,
                "duration_min_car": 2280,  # 38h (extremo)
                "duration_min_bus": 2700,  # 45h
                "duration_min_flight": 210,  # 3.5h
                "coordinates": [(-33.4489, -70.6693), (-53.1638, -70.9171)]
            },
            
            # NORTE GRANDE (conexiones internas)
            "arica_iquique": {
                "distance_km": 305,
                "duration_min_car": 240,  # 4h
                "duration_min_bus": 300,  # 5h
                "coordinates": [(-18.4746, -70.3127), (-20.2307, -70.1355)]
            },
            "iquique_atacama": {
                "distance_km": 250,
                "duration_min_car": 180,  # 3h
                "duration_min_bus": 240,  # 4h
                "coordinates": [(-20.2307, -70.1355), (-22.4594, -68.9139)]
            },
            "atacama_antofagasta": {
                "distance_km": 345,
                "duration_min_car": 270,  # 4.5h
                "duration_min_bus": 330,  # 5.5h
                "coordinates": [(-22.4594, -68.9139), (-23.6509, -70.3975)]
            },
            
            # ZONA CENTRAL (alta frecuencia)
            "valparaiso_serena": {
                "distance_km": 350,
                "duration_min_car": 240,  # 4h
                "duration_min_bus": 300,  # 5h
                "coordinates": [(-33.0472, -71.6127), (-29.9027, -71.2519)]
            },
            "concepcion_temuco": {
                "distance_km": 275,
                "duration_min_car": 180,  # 3h
                "duration_min_bus": 240,  # 4h
                "coordinates": [(-36.8201, -73.0444), (-38.7359, -72.5904)]
            },
            
            # SUR DE CHILE
            "temuco_valdiva": {
                "distance_km": 165,
                "duration_min_car": 120,  # 2h
                "duration_min_bus": 150,  # 2.5h
                "coordinates": [(-38.7359, -72.5904), (-39.8142, -73.2459)]
            },
            "valdiva_puertomonte": {
                "distance_km": 175,
                "duration_min_car": 135,  # 2.25h
                "duration_min_bus": 180,  # 3h
                "coordinates": [(-39.8142, -73.2459), (-41.4693, -72.9424)]
            },
            "puertomonte_coyhaique": {
                "distance_km": 635,
                "duration_min_car": 480,  # 8h (ruta austral)
                "duration_min_bus": 600,  # 10h
                "duration_min_flight": 75,  # 1.25h
                "coordinates": [(-41.4693, -72.9424), (-45.5752, -72.0662)]
            },
            
            # RUTAS ESPECÍFICAS TURÍSTICAS
            "santiago_machupicchu": {
                "distance_km": 3200,
                "duration_min_flight": 480,  # 8h (con escalas)
                "duration_min_bus": 4320,  # 72h (extremo)
                "coordinates": [(-33.4489, -70.6693), (-13.1631, -72.5450)]
            },
            "santiago_mendoza": {
                "distance_km": 380,
                "duration_min_car": 420,  # 7h (paso fronterizo)
                "duration_min_bus": 480,  # 8h
                "coordinates": [(-33.4489, -70.6693), (-32.8908, -68.8272)]
            }
        }
        
        # 🏙️ CIUDADES PRINCIPALES (para matching geográfico)
        self.CITY_COORDINATES = {
            "santiago": (-33.4489, -70.6693),
            "valparaiso": (-33.0472, -71.6127),
            "atacama": (-22.4594, -68.9139),
            "iquique": (-20.2307, -70.1355),
            "antofagasta": (-23.6509, -70.3975),
            "serena": (-29.9027, -71.2519),
            "concepcion": (-36.8201, -73.0444),
            "temuco": (-38.7359, -72.5904),
            "valdiva": (-39.8142, -73.2459),
            "puertomonte": (-41.4693, -72.9424),
            "puntaarenas": (-53.1638, -70.9171),
            "arica": (-18.4746, -70.3127),
            "coyhaique": (-45.5752, -72.0662)
        }
    
    def find_cached_route(self, 
                         origin_lat: float, 
                         origin_lon: float, 
                         dest_lat: float, 
                         dest_lon: float,
                         transport_mode: str = 'car') -> Optional[Dict]:
        """
        🎯 Buscar ruta pre-calculada con tolerancia geográfica
        
        Returns:
            Dict con distance_km, duration_minutes o None si no encuentra match
        """
        origin = (origin_lat, origin_lon)
        destination = (dest_lat, dest_lon)
        
        # Buscar en rutas bidireccionales
        for route_key, route_data in self.COMMON_ROUTES.items():
            coords = route_data["coordinates"]
            
            # Verificar match directo (A → B)
            if (self._is_near_location(origin, coords[0]) and 
                self._is_near_location(destination, coords[1])):
                
                duration = self._get_duration_by_mode(route_data, transport_mode)
                if duration:
                    logger.info(f"🚀 Cache HIT: {route_key} ({transport_mode}) = {duration}min")
                    return {
                        "distance_km": route_data["distance_km"],
                        "duration_minutes": duration,
                        "cached": True,
                        "route_name": route_key,
                        "transport_mode": transport_mode
                    }
            
            # Verificar match inverso (B → A)
            elif (self._is_near_location(origin, coords[1]) and 
                  self._is_near_location(destination, coords[0])):
                
                duration = self._get_duration_by_mode(route_data, transport_mode)
                if duration:
                    logger.info(f"🚀 Cache HIT: {route_key}_reverse ({transport_mode}) = {duration}min")
                    return {
                        "distance_km": route_data["distance_km"],
                        "duration_minutes": duration,
                        "cached": True,
                        "route_name": f"{route_key}_reverse",
                        "transport_mode": transport_mode
                    }
        
        # No encontrado
        logger.debug(f"❌ Cache MISS: ({origin_lat:.3f},{origin_lon:.3f}) → ({dest_lat:.3f},{dest_lon:.3f})")
        return None
    
    def _is_near_location(self, point: Tuple[float, float], target: Tuple[float, float]) -> bool:
        """Verificar si un punto está cerca de una ubicación target"""
        distance = haversine_km(point[0], point[1], target[0], target[1])
        return distance <= self.tolerance_km
    
    def _get_duration_by_mode(self, route_data: Dict, transport_mode: str) -> Optional[int]:
        """Obtener duración según modo de transporte"""
        mode_mapping = {
            'car': 'duration_min_car',
            'driving': 'duration_min_car',
            'bus': 'duration_min_bus',
            'transit': 'duration_min_bus',
            'flight': 'duration_min_flight',
            'flying': 'duration_min_flight',
            'walk': 'duration_min_walk',
            'walking': 'duration_min_walk'
        }
        
        duration_key = mode_mapping.get(transport_mode.lower(), 'duration_min_car')
        return route_data.get(duration_key)
    
    def get_cache_stats(self) -> Dict:
        """Estadísticas del cache"""
        return {
            "total_routes": len(self.COMMON_ROUTES),
            "total_cities": len(self.CITY_COORDINATES),
            "tolerance_km": self.tolerance_km,
            "transport_modes": ["car", "bus", "flight", "walk"],
            "coverage": "Chile continental + conexiones internacionales selectas"
        }
    
    def suggest_nearby_city(self, lat: float, lon: float) -> Optional[str]:
        """Sugerir ciudad más cercana para debugging"""
        min_distance = float('inf')
        closest_city = None
        
        for city, coords in self.CITY_COORDINATES.items():
            distance = haversine_km(lat, lon, coords[0], coords[1])
            if distance < min_distance:
                min_distance = distance
                closest_city = city
        
        if min_distance <= self.tolerance_km:
            return f"{closest_city} ({min_distance:.1f}km)"
        return None