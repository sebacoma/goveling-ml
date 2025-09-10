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
                    elif data.get("status") == "ZERO_RESULTS":
                        logging.warning("Google Directions ZERO_RESULTS - usando fallback ETA")
                        return self._fallback_route_info(origin, destination, mode)
                    else:
                        logging.warning(f"Google Directions API error: {data.get('status')} - usando fallback ETA")
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
        """
        🚀 FALLBACK MEJORADO: ETA con velocidad promedio configurable + buffers
        No levanta excepciones que disparen fallback_basic
        """
        from utils.geo_utils import haversine_km
        
        distance_km = haversine_km(origin[0], origin[1], destination[0], destination[1])
        
        # 🚗 Auto-selección de modo para distancias > 30km
        original_mode = mode
        if distance_km > 30.0:
            if mode == "walk" or mode == "walking":
                mode = "drive"  # Forzar driving para distancias largas
                logging.info(f"🚗 Distancia {distance_km:.1f}km > 30km: forzando mode=drive")
        
        # 🏃‍♂️ Velocidades configurables con buffers
        speed_map = {
            "walk": settings.WALK_KMH,           # 4.5 km/h
            "walking": settings.WALK_KMH,        # 4.5 km/h  
            "drive": settings.DRIVE_KMH,         # 50.0 km/h (interurbano)
            "driving": settings.DRIVE_KMH,       # 50.0 km/h
            "transit": settings.TRANSIT_KMH,     # 35.0 km/h
            "bike": 15.0,                        # Velocidad bicicleta
            "bicycling": 15.0
        }
        
        base_speed_kmh = speed_map.get(mode, settings.DRIVE_KMH)
        
        # ⏱️ Cálculo ETA base + buffers inteligentes
        base_duration_hours = distance_km / base_speed_kmh
        base_duration_min = base_duration_hours * 60
        
        # 📊 Buffers según distancia y modo
        if distance_km < 5:
            buffer_factor = 1.2  # 20% buffer para trayectos cortos
        elif distance_km < 30:
            buffer_factor = 1.3  # 30% buffer para trayectos medios
        else:
            buffer_factor = 1.4  # 40% buffer para trayectos largos (intercity)
            
        # Buffers adicionales por modo de transporte
        if mode in ["transit"]:
            buffer_factor += 0.2  # +20% para transporte público (esperas)
        elif mode in ["walk", "walking"]:
            buffer_factor += 0.1  # +10% para caminata (semáforos, etc)
        
        final_duration_min = base_duration_min * buffer_factor
        
        # 🕐 Mínimo realista
        final_duration_min = max(final_duration_min, settings.MIN_TRAVEL_MIN)
        
        logging.info(f"📊 Fallback ETA: {distance_km:.1f}km @ {base_speed_kmh}km/h = {final_duration_min:.0f}min (mode: {original_mode}→{mode})")
        
        return {
            "duration_minutes": final_duration_min,
            "distance_km": distance_km,
            "polyline": "",
            "status": "FALLBACK_ETA",
            "google_enhanced": False,
            "mode_adjusted": mode != original_mode,
            "original_mode": original_mode,
            "final_mode": mode,
            "buffer_applied": round(buffer_factor, 2)
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
    
    async def eta_between(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float], 
        mode: str = "walking"
    ) -> Dict:
        """
        🚀 Nueva función para ETAs reales entre puntos específicos
        
        Args:
            origin: (lat, lon) punto de origen
            destination: (lat, lon) punto de destino
            mode: walk, drive, transit, bike
            
        Returns:
            {
                "duration_minutes": float,
                "distance_km": float,
                "recommended_mode": str,
                "source": "google_api" | "fallback"
            }
        """
        # Usar get_route_info como base
        route_info = await self.get_route_info(origin, destination, mode)
        
        # Determinar modo recomendado basado en distancia
        distance_km = route_info.get("distance_km", 0)
        recommended_mode = self._decide_mode_by_distance(distance_km, mode)
        
        # Si el modo recomendado es diferente, recalcular
        if recommended_mode != mode:
            logging.info(f"🚗 Recalculando con modo recomendado: {mode} → {recommended_mode}")
            route_info = await self.get_route_info(origin, destination, recommended_mode)
        
        return {
            "duration_minutes": route_info.get("duration_minutes", 0),
            "distance_km": route_info.get("distance_km", 0),
            "recommended_mode": recommended_mode,
            "source": "google_api" if route_info.get("google_enhanced", False) else "fallback",
            "original_mode_requested": mode
        }
    
    def _decide_mode_by_distance(self, distance_km: float, requested_mode: str) -> str:
        """
        🚗 Política de transporte por distancia
        """
        if distance_km <= settings.WALK_THRESHOLD_KM:
            return "walk"
        elif distance_km <= settings.DRIVE_THRESHOLD_KM and settings.TRANSIT_AVAILABLE:
            # Para distancias medias, preferir transit si está disponible
            return "transit" if requested_mode in ["walk", "transit"] else "drive"
        else:
            # Para distancias largas, forzar driving
            return "drive"

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
