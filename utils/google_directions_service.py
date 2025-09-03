import aiohttp
import asyncio
import logging
from typing import List, Dict, Tuple, Optional
from settings import settings

class GoogleDirectionsService:
    """Servicio simplificado que usa solo Google Directions API"""
    
    def __init__(self):
        self.api_key = settings.GOOGLE_MAPS_API_KEY
        self.base_url = "https://maps.googleapis.com/maps/api/directions/json"
        
    def is_available(self) -> bool:
        """Verificar si la API key está disponible"""
        return bool(self.api_key)
    
    async def get_route_info(
        self, 
        origin: Tuple[float, float], 
        destination: Tuple[float, float],
        mode: str = "walking"
    ) -> Dict:
        """
        Obtener información de ruta real usando Directions API
        
        Args:
            origin: (lat, lon) punto de origen
            destination: (lat, lon) punto de destino  
            mode: walking, driving, transit, bicycling
            
        Returns:
            {
                "duration_minutes": float,
                "distance_km": float,
                "polyline": str,
                "status": str
            }
        """
        if not self.is_available():
            return self._fallback_route_info(origin, destination, mode)
        
        try:
            # Mapear modos de transporte
            google_modes = {
                "walk": "walking",
                "drive": "driving", 
                "transit": "transit",
                "bike": "bicycling"
            }
            
            google_mode = google_modes.get(mode, "walking")
            
            params = {
                "origin": f"{origin[0]},{origin[1]}",
                "destination": f"{destination[0]},{destination[1]}",
                "mode": google_mode,
                "key": self.api_key,
                "language": "es",
                "units": "metric"
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(self.base_url, params=params) as response:
                    if response.status != 200:
                        logging.warning(f"Google API HTTP error: {response.status}")
                        return self._fallback_route_info(origin, destination, mode)
                    
                    data = await response.json()
                    
                    if data.get("status") == "OK" and data.get("routes"):
                        route = data["routes"][0]
                        leg = route["legs"][0]
                        
                        return {
                            "duration_minutes": leg["duration"]["value"] / 60.0,
                            "distance_km": leg["distance"]["value"] / 1000.0,
                            "polyline": route.get("overview_polyline", {}).get("points", ""),
                            "status": "OK",
                            "google_enhanced": True
                        }
                    else:
                        logging.warning(f"Google Directions API error: {data.get('status')}")
                        return self._fallback_route_info(origin, destination, mode)
                        
        except asyncio.TimeoutError:
            logging.warning("Google Directions API timeout")
            return self._fallback_route_info(origin, destination, mode)
        except Exception as e:
            logging.error(f"Error calling Google Directions API: {e}")
            return self._fallback_route_info(origin, destination, mode)
    
    def _fallback_route_info(
        self, 
        origin: Tuple[float, float], 
        destination: Tuple[float, float], 
        mode: str
    ) -> Dict:
        """Fallback usando cálculos simples cuando Google API no está disponible"""
        from utils.geo_utils import haversine_km, estimate_travel_minutes
        
        distance_km = haversine_km(origin[0], origin[1], destination[0], destination[1])
        duration_min = estimate_travel_minutes(origin[0], origin[1], destination[0], destination[1], mode)
        
        return {
            "duration_minutes": duration_min,
            "distance_km": distance_km,
            "polyline": "",
            "status": "FALLBACK",
            "google_enhanced": False
        }
    
    async def get_optimized_route_order(
        self, 
        waypoints: List[Tuple[float, float]],
        start_point: Tuple[float, float],
        mode: str = "walking"
    ) -> List[int]:
        """
        Obtener orden optimizado de waypoints usando nearest neighbor con tiempos reales
        
        Returns:
            Lista de índices en el orden optimizado
        """
        if len(waypoints) <= 1:
            return list(range(len(waypoints)))
        
        logging.info(f"🗺️ Optimizando orden de {len(waypoints)} waypoints")
        
        # Algoritmo nearest neighbor con tiempos reales
        unvisited = list(range(len(waypoints)))
        route_order = []
        current_location = start_point
        
        while unvisited:
            # Encontrar el waypoint más cercano en tiempo
            min_time = float('inf')
            nearest_idx = None
            nearest_list_idx = None
            
            # Obtener tiempos a todos los waypoints no visitados
            tasks = []
            for i, wp_idx in enumerate(unvisited):
                task = self.get_route_info(
                    current_location, 
                    waypoints[wp_idx], 
                    mode
                )
                tasks.append((task, wp_idx, i))
            
            # Ejecutar todas las consultas en paralelo
            results = await asyncio.gather(*[task for task, _, _ in tasks], return_exceptions=True)
            
            # Encontrar el más cercano
            for result, wp_idx, list_idx in zip(results, [t[1] for t in tasks], [t[2] for t in tasks]):
                if isinstance(result, Exception):
                    continue
                    
                travel_time = result.get('duration_minutes', float('inf'))
                if travel_time < min_time:
                    min_time = travel_time
                    nearest_idx = wp_idx
                    nearest_list_idx = list_idx
            
            if nearest_idx is not None:
                route_order.append(nearest_idx)
                current_location = waypoints[nearest_idx]
                unvisited.pop(nearest_list_idx)
            else:
                # Si no se pudo obtener información, agregar el primero
                nearest_idx = unvisited.pop(0)
                route_order.append(nearest_idx)
                current_location = waypoints[nearest_idx]
        
        logging.info(f"✅ Orden optimizado: {route_order}")
        return route_order
    
    async def calculate_total_route_info(
        self,
        locations: List[Tuple[float, float]],
        mode: str = "walking"
    ) -> Dict:
        """
        Calcular información total de una ruta secuencial
        """
        if len(locations) < 2:
            return {
                "total_duration_minutes": 0,
                "total_distance_km": 0,
                "segments": []
            }
        
        # Obtener información de cada segmento
        tasks = []
        for i in range(len(locations) - 1):
            task = self.get_route_info(locations[i], locations[i + 1], mode)
            tasks.append(task)
        
        segments = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Calcular totales
        total_duration = 0
        total_distance = 0
        valid_segments = []
        
        for segment in segments:
            if isinstance(segment, Exception):
                continue
            
            total_duration += segment.get('duration_minutes', 0)
            total_distance += segment.get('distance_km', 0)
            valid_segments.append(segment)
        
        return {
            "total_duration_minutes": total_duration,
            "total_distance_km": total_distance,
            "segments": valid_segments,
            "google_enhanced": any(s.get('google_enhanced', False) for s in valid_segments)
        }
