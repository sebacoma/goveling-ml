import asyncio
import aiohttp
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta 
import json
from settings import settings
from .google_cache import cache_google_api, parallel_google_calls

class GoogleMapsClient:
    """Cliente inteligente para APIs de Google Maps"""
    
    def __init__(self):
        self.api_key = settings.GOOGLE_MAPS_API_KEY
        self.base_url = "https://maps.googleapis.com/maps/api"
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    @cache_google_api(ttl=3600)  # 1 hora de caché
    async def get_place_details(self, place_name: str, lat: float, lon: float) -> Dict[str, Any]:
        """Obtener detalles completos de un lugar usando Places API"""
        try:
            # 1. Buscar lugar cercano por nombre y coordenadas
            search_url = f"{self.base_url}/place/nearbysearch/json"
            search_params = {
                'location': f"{lat},{lon}",
                'radius': 1000,  # 1km radio
                'keyword': place_name,
                'key': self.api_key
            }
            
            async with self.session.get(search_url, params=search_params) as response:
                search_data = await response.json()
            
            if not search_data.get('results'):
                # Fallback: buscar por texto
                return await self._text_search_place(place_name, lat, lon)
            
            place = search_data['results'][0]
            place_id = place.get('place_id')
            
            # 2. Obtener detalles completos
            details_url = f"{self.base_url}/place/details/json"
            details_params = {
                'place_id': place_id,
                'fields': 'name,formatted_address,geometry,opening_hours,rating,price_level,types,photos,reviews',
                'key': self.api_key
            }
            
            async with self.session.get(details_url, params=details_params) as response:
                details_data = await response.json()
            
            if details_data.get('result'):
                return self._format_place_details(details_data['result'], place_name, lat, lon)
            
        except Exception as e:
            logging.error(f"Error obteniendo detalles de lugar {place_name}: {e}")
        
        # Fallback básico
        return {
            'name': place_name,
            'lat': lat,
            'lon': lon,
            'rating': 4.0,
            'opening_hours': self._generate_default_hours(),
            'estimated_visit_duration': 1.5,
            'place_types': ['point_of_interest'],
            'price_level': 2
        }
    
    async def _text_search_place(self, place_name: str, lat: float, lon: float) -> Dict[str, Any]:
        """Búsqueda por texto como fallback"""
        try:
            search_url = f"{self.base_url}/place/textsearch/json"
            params = {
                'query': f"{place_name} near {lat},{lon}",
                'key': self.api_key
            }
            
            async with self.session.get(search_url, params=params) as response:
                data = await response.json()
            
            if data.get('results'):
                place = data['results'][0]
                return self._format_place_details(place, place_name, lat, lon)
                
        except Exception as e:
            logging.error(f"Error en text search: {e}")
        
        return None
    
    def _format_place_details(self, place_data: Dict, original_name: str, lat: float, lon: float) -> Dict[str, Any]:
        """Formatear detalles del lugar"""
        geometry = place_data.get('geometry', {}).get('location', {})
        
        return {
            'name': place_data.get('name', original_name),
            'formatted_address': place_data.get('formatted_address', ''),
            'lat': geometry.get('lat', lat),
            'lon': geometry.get('lng', lon),
            'rating': place_data.get('rating', 4.0),
            'price_level': place_data.get('price_level', 2),
            'place_types': place_data.get('types', ['point_of_interest']),
            'opening_hours': self._parse_opening_hours(place_data.get('opening_hours')),
            'estimated_visit_duration': self._estimate_visit_duration(place_data),
            'photos': place_data.get('photos', [])[:3],  # Máximo 3 fotos
            'reviews_summary': self._summarize_reviews(place_data.get('reviews', []))
        }
    
    async def get_optimal_route(self, waypoints: List[Dict], start_point: Dict, 
                              transport_mode: str = "walking", 
                              departure_time: Optional[datetime] = None) -> Dict[str, Any]:
        """Calcular ruta óptima usando Directions API"""
        try:
            # Preparar waypoints
            origin = f"{start_point['lat']},{start_point['lon']}"
            destination = origin  # Volver al punto de inicio
            
            waypoint_coords = []
            for wp in waypoints:
                waypoint_coords.append(f"{wp['lat']},{wp['lon']}")
            
            url = f"{self.base_url}/directions/json"
            params = {
                'origin': origin,
                'destination': destination,
                'waypoints': f"optimize:true|{'|'.join(waypoint_coords)}",
                'mode': self._convert_transport_mode(transport_mode),
                'key': self.api_key,
                'language': 'es'
            }
            
            # Agregar tiempo de salida si es tráfico
            if transport_mode == "driving" and departure_time:
                params['departure_time'] = int(departure_time.timestamp())
            
            async with self.session.get(url, params=params) as response:
                data = await response.json()
            
            if data.get('status') == 'OK' and data.get('routes'):
                return self._parse_route_response(data['routes'][0], waypoints)
            else:
                logging.warning(f"Google Directions API error: {data.get('status')}")
                return self._fallback_route(waypoints, start_point, transport_mode)
                
        except Exception as e:
            logging.error(f"Error calculando ruta óptima: {e}")
            return self._fallback_route(waypoints, start_point, transport_mode)
    
    async def get_distance_matrix(self, origins: List[Dict], destinations: List[Dict],
                                 transport_mode: str = "walking") -> Dict[str, Any]:
        """Calcular matriz de distancias entre múltiples puntos"""
        try:
            origin_coords = [f"{p['lat']},{p['lon']}" for p in origins]
            dest_coords = [f"{p['lat']},{p['lon']}" for p in destinations]
            
            url = f"{self.base_url}/distancematrix/json"
            params = {
                'origins': '|'.join(origin_coords),
                'destinations': '|'.join(dest_coords),
                'mode': self._convert_transport_mode(transport_mode),
                'units': 'metric',
                'key': self.api_key
            }
            
            async with self.session.get(url, params=params) as response:
                data = await response.json()
            
            if data.get('status') == 'OK':
                return self._parse_distance_matrix(data, origins, destinations)
            else:
                return self._fallback_distance_matrix(origins, destinations, transport_mode)
                
        except Exception as e:
            logging.error(f"Error en distance matrix: {e}")
            return self._fallback_distance_matrix(origins, destinations, transport_mode)
    
    def _convert_transport_mode(self, mode: str) -> str:
        """Convertir modo de transporte a formato Google Maps"""
        mode_mapping = {
            'walk': 'walking',
            'walking': 'walking',
            'drive': 'driving',
            'driving': 'driving',
            'bike': 'bicycling',
            'bicycling': 'bicycling',
            'transit': 'transit'
        }
        return mode_mapping.get(mode.lower(), 'walking')
    
    def _parse_route_response(self, route: Dict, original_waypoints: List[Dict]) -> Dict[str, Any]:
        """Parsear respuesta de Directions API"""
        legs = route.get('legs', [])
        waypoint_order = route.get('waypoint_order', list(range(len(original_waypoints))))
        
        optimized_waypoints = []
        total_distance = 0
        total_duration = 0
        
        for i, leg in enumerate(legs[:-1]):  # Excluir la última pierna (vuelta al inicio)
            if i < len(waypoint_order):
                original_index = waypoint_order[i]
                waypoint = original_waypoints[original_index].copy()
                
                waypoint.update({
                    'travel_distance_m': leg.get('distance', {}).get('value', 0),
                    'travel_duration_s': leg.get('duration', {}).get('value', 0),
                    'travel_instructions': leg.get('steps', [])[:3]  # Primeras 3 instrucciones
                })
                
                optimized_waypoints.append(waypoint)
                total_distance += leg.get('distance', {}).get('value', 0)
                total_duration += leg.get('duration', {}).get('value', 0)
        
        return {
            'optimized_waypoints': optimized_waypoints,
            'total_distance_m': total_distance,
            'total_duration_s': total_duration,
            'route_polyline': route.get('overview_polyline', {}).get('points', ''),
            'optimized': True
        }
    
    def _parse_distance_matrix(self, data: Dict, origins: List[Dict], destinations: List[Dict]) -> Dict[str, Any]:
        """Parsear matriz de distancias"""
        matrix = []
        rows = data.get('rows', [])
        
        for i, row in enumerate(rows):
            matrix_row = []
            elements = row.get('elements', [])
            
            for j, element in enumerate(elements):
                if element.get('status') == 'OK':
                    matrix_row.append({
                        'distance_m': element.get('distance', {}).get('value', 0),
                        'duration_s': element.get('duration', {}).get('value', 0),
                        'distance_text': element.get('distance', {}).get('text', ''),
                        'duration_text': element.get('duration', {}).get('text', '')
                    })
                else:
                    # Fallback usando distancia haversine
                    from utils.geo_utils import haversine_km, estimate_travel_minutes
                    dist_km = haversine_km(
                        origins[i]['lat'], origins[i]['lon'],
                        destinations[j]['lat'], destinations[j]['lon']
                    )
                    duration_min = estimate_travel_minutes(
                        origins[i]['lat'], origins[i]['lon'],
                        destinations[j]['lat'], destinations[j]['lon'],
                        'walking'
                    )
                    
                    matrix_row.append({
                        'distance_m': int(dist_km * 1000),
                        'duration_s': int(duration_min * 60),
                        'distance_text': f"{dist_km:.1f} km",
                        'duration_text': f"{duration_min:.0f} min"
                    })
            
            matrix.append(matrix_row)
        
        return {
            'distance_matrix': matrix,
            'origins': origins,
            'destinations': destinations
        }
    
    def _parse_opening_hours(self, hours_data: Optional[Dict]) -> Dict[str, Any]:
        """Parsear horarios de apertura"""
        if not hours_data:
            return self._generate_default_hours()
        
        periods = hours_data.get('periods', [])
        weekday_text = hours_data.get('weekday_text', [])
        
        return {
            'open_now': hours_data.get('open_now', True),
            'periods': periods,
            'weekday_text': weekday_text,
            'parsed_hours': self._parse_periods(periods)
        }
    
    def _generate_default_hours(self) -> Dict[str, Any]:
        """Generar horarios por defecto"""
        return {
            'open_now': True,
            'periods': [],
            'weekday_text': ['Lunes: 09:00–18:00', 'Martes: 09:00–18:00', 
                           'Miércoles: 09:00–18:00', 'Jueves: 09:00–18:00',
                           'Viernes: 09:00–18:00', 'Sábado: 10:00–17:00', 
                           'Domingo: 10:00–17:00'],
            'parsed_hours': {
                0: ('09:00', '18:00'),  # Lunes
                1: ('09:00', '18:00'),  # Martes
                2: ('09:00', '18:00'),  # Miércoles
                3: ('09:00', '18:00'),  # Jueves
                4: ('09:00', '18:00'),  # Viernes
                5: ('10:00', '17:00'),  # Sábado
                6: ('10:00', '17:00')   # Domingo
            }
        }
    
    def _parse_periods(self, periods: List[Dict]) -> Dict[int, Tuple[str, str]]:
        """Convertir períodos a formato simple"""
        parsed = {}
        for period in periods:
            open_time = period.get('open', {})
            close_time = period.get('close', {})
            
            if open_time and close_time:
                day = open_time.get('day', 0)
                open_hour = f"{open_time.get('time', '0900')[:2]}:{open_time.get('time', '0900')[2:]}"
                close_hour = f"{close_time.get('time', '1800')[:2]}:{close_time.get('time', '1800')[2:]}"
                
                parsed[day] = (open_hour, close_hour)
        
        return parsed
    
    def _estimate_visit_duration(self, place_data: Dict) -> float:
        """Estimar duración de visita basada en tipo de lugar"""
        place_types = place_data.get('types', [])
        
        duration_mapping = {
            'museum': 2.5,
            'park': 1.5,
            'restaurant': 1.25,
            'cafe': 0.75,
            'shopping_mall': 2.0,
            'church': 0.75,
            'tourist_attraction': 2.0,
            'amusement_park': 4.0,
            'zoo': 3.0,
            'aquarium': 2.5,
            'art_gallery': 1.5,
            'library': 1.0,
            'movie_theater': 2.5,
            'night_club': 3.0,
            'bar': 1.5
        }
        
        for place_type in place_types:
            if place_type in duration_mapping:
                return duration_mapping[place_type]
        
        # Fallback basado en rating y reviews
        rating = place_data.get('rating', 4.0)
        if rating >= 4.5:
            return 2.0  # Lugares muy bien valorados merecen más tiempo
        elif rating >= 4.0:
            return 1.5
        else:
            return 1.0
    
    def _summarize_reviews(self, reviews: List[Dict]) -> Dict[str, Any]:
        """Resumir reseñas del lugar"""
        if not reviews:
            return {'summary': 'Sin reseñas disponibles', 'sentiment': 'neutral'}
        
        total_rating = sum(r.get('rating', 3) for r in reviews)
        avg_rating = total_rating / len(reviews)
        
        # Análisis simple de sentimiento basado en rating
        if avg_rating >= 4.0:
            sentiment = 'positive'
        elif avg_rating >= 3.0:
            sentiment = 'neutral'  
        else:
            sentiment = 'negative'
        
        return {
            'summary': f"Promedio {avg_rating:.1f}/5 basado en {len(reviews)} reseñas",
            'sentiment': sentiment,
            'recent_reviews': [r.get('text', '')[:100] + '...' for r in reviews[:2]]
        }
    
    def _fallback_route(self, waypoints: List[Dict], start_point: Dict, transport_mode: str) -> Dict[str, Any]:
        """Fallback cuando falla Google Directions"""
        from utils.geo_utils import haversine_km, estimate_travel_minutes
        
        # Algoritmo simple de nearest neighbor
        remaining = waypoints.copy()
        optimized = []
        current_pos = start_point
        total_distance = 0
        total_duration = 0
        
        while remaining:
            # Encontrar el punto más cercano
            min_dist = float('inf')
            closest_idx = 0
            
            for i, point in enumerate(remaining):
                dist = haversine_km(
                    current_pos['lat'], current_pos['lon'],
                    point['lat'], point['lon']
                )
                if dist < min_dist:
                    min_dist = dist
                    closest_idx = i
            
            # Mover el punto más cercano a optimizado
            closest_point = remaining.pop(closest_idx)
            
            # Calcular tiempos de viaje
            duration_min = estimate_travel_minutes(
                current_pos['lat'], current_pos['lon'],
                closest_point['lat'], closest_point['lon'],
                transport_mode
            )
            
            closest_point.update({
                'travel_distance_m': int(min_dist * 1000),
                'travel_duration_s': int(duration_min * 60),
                'travel_instructions': []
            })
            
            optimized.append(closest_point)
            current_pos = closest_point
            total_distance += min_dist * 1000
            total_duration += duration_min * 60
        
        return {
            'optimized_waypoints': optimized,
            'total_distance_m': int(total_distance),
            'total_duration_s': int(total_duration),
            'route_polyline': '',
            'optimized': False  # Indica que es fallback
        }
    
    def _fallback_distance_matrix(self, origins: List[Dict], destinations: List[Dict], 
                                 transport_mode: str) -> Dict[str, Any]:
        """Fallback para distance matrix"""
        from utils.geo_utils import haversine_km, estimate_travel_minutes
        
        matrix = []
        for origin in origins:
            row = []
            for dest in destinations:
                dist_km = haversine_km(
                    origin['lat'], origin['lon'],
                    dest['lat'], dest['lon']
                )
                duration_min = estimate_travel_minutes(
                    origin['lat'], origin['lon'],
                    dest['lat'], dest['lon'],
                    transport_mode
                )
                
                row.append({
                    'distance_m': int(dist_km * 1000),
                    'duration_s': int(duration_min * 60),
                    'distance_text': f"{dist_km:.1f} km",
                    'duration_text': f"{duration_min:.0f} min"
                })
            matrix.append(row)
        
        return {
            'distance_matrix': matrix,
            'origins': origins,
            'destinations': destinations
        }
    
    @cache_google_api(ttl=1800)  # 30 minutos de caché
    async def search_nearby_places(self, lat: float, lon: float, types: List[str], radius_m: int = 3000, limit: int = 3) -> List[Dict]:
        """
        🔍 Buscar lugares cercanos usando Google Places API
        
        Args:
            lat: Latitud del punto central
            lon: Longitud del punto central 
            types: Lista de tipos de lugares (e.g., ['restaurant', 'tourist_attraction'])
            radius_m: Radio de búsqueda en metros
            limit: Número máximo de lugares a devolver
        
        Returns:
            Lista de lugares con información detallada
        """
        if not self.api_key:
            logging.warning("🔑 Google Maps API key no configurada")
            return []
        
        try:
            # Usar Places API Nearby Search
            nearby_url = f"{self.base_url}/place/nearbysearch/json"
            
            all_places = []
            
            # Buscar por cada tipo de lugar para obtener mejor diversidad
            for place_type in types:
                params = {
                    'key': self.api_key,
                    'location': f"{lat},{lon}",
                    'radius': min(radius_m, 50000),  # Máximo 50km según Google Places API
                    'type': place_type,
                    'language': 'es',  # Resultados en español
                }
                
                if not self.session:
                    self.session = aiohttp.ClientSession()
                
                async with self.session.get(nearby_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('status') == 'OK':
                            places = data.get('results', [])
                            
                            for place in places[:2]:  # Max 2 por tipo para diversidad
                                place_info = {
                                    'name': place.get('name', 'Lugar sin nombre'),
                                    'lat': place['geometry']['location']['lat'],
                                    'lon': place['geometry']['location']['lng'],
                                    'rating': place.get('rating', 4.0),
                                    'user_ratings_total': place.get('user_ratings_total', 0),
                                    'price_level': place.get('price_level', 0),
                                    'types': place.get('types', []),
                                    'place_id': place.get('place_id', ''),
                                    'vicinity': place.get('vicinity', ''),
                                    'address': place.get('vicinity', 'Dirección no disponible'),
                                    'photo_reference': None,
                                    'photo_url': '',
                                    'opening_hours': {},
                                    'website': '',
                                    'phone': '',
                                    'description': f"Lugar encontrado en Google Places con {place.get('rating', 4.0)}⭐ de rating",
                                    'synthetic': False,
                                    'google_places_verified': True
                                }
                                
                                # Agregar foto si está disponible
                                if 'photos' in place and len(place['photos']) > 0:
                                    photo_ref = place['photos'][0].get('photo_reference')
                                    if photo_ref:
                                        place_info['photo_reference'] = photo_ref
                                        place_info['photo_url'] = f"{self.base_url}/place/photo?photoreference={photo_ref}&sensor=false&maxheight=400&key={self.api_key}"
                                
                                # Información de horarios si está disponible
                                if 'opening_hours' in place:
                                    place_info['opening_hours'] = {
                                        'open_now': place['opening_hours'].get('open_now', True),
                                        'periods': place['opening_hours'].get('periods', [])
                                    }
                                
                                all_places.append(place_info)
                                
                                # Limitar total de lugares
                                if len(all_places) >= limit:
                                    break
                            
                            logging.info(f"✅ Google Places: {len(places)} lugares encontrados para {place_type}")
                        
                        elif data.get('status') == 'ZERO_RESULTS':
                            logging.info(f"🔍 Google Places: Sin resultados para {place_type} en {lat:.4f},{lon:.4f}")
                        
                        else:
                            logging.warning(f"⚠️ Google Places API error: {data.get('status')} - {data.get('error_message', 'Sin mensaje')}")
                    
                    else:
                        logging.error(f"❌ Error HTTP {response.status} consultando Google Places API")
                
                # Si ya tenemos suficientes lugares, salir del loop
                if len(all_places) >= limit:
                    break
            
            logging.info(f"🎯 Google Places: Total {len(all_places)} lugares reales encontrados")
            return all_places[:limit]
            
        except Exception as e:
            logging.error(f"💥 Error en search_nearby_places: {e}")
            return []
    
    @cache_google_api(ttl=7200)  # 2 horas de caché para geocoding
    async def reverse_geocode_city(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """
        🌍 Reverse geocoding para detectar ciudad automáticamente
        
        Args:
            lat: Latitud
            lon: Longitud
            
        Returns:
            Dict con información de la ciudad o None si falla
        """
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            url = f"{self.base_url}/geocode/json"
            params = {
                'latlng': f"{lat},{lon}",
                'key': self.api_key,
                'result_type': 'locality|administrative_area_level_1|administrative_area_level_2',
                'language': 'es'  # Respuesta en español
            }
            
            logging.debug(f"🌍 Reverse geocoding para ({lat:.4f}, {lon:.4f})")
            
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logging.warning(f"⚠️ Google Geocoding API error: {response.status}")
                    return None
                
                data = await response.json()
                
                if data.get('status') != 'OK' or not data.get('results'):
                    logging.debug(f"❌ No se encontraron resultados de geocoding")
                    return None
                
                # Procesar resultados para encontrar la ciudad
                for result in data['results']:
                    components = result.get('address_components', [])
                    
                    city_info = {
                        'city': None,
                        'state': None,
                        'country': None,
                        'country_code': None,
                        'formatted_address': result.get('formatted_address', '')
                    }
                    
                    for component in components:
                        types = component.get('types', [])
                        
                        # Buscar ciudad (locality)
                        if 'locality' in types:
                            city_info['city'] = component['long_name']
                        
                        # Buscar estado/región
                        elif 'administrative_area_level_1' in types:
                            city_info['state'] = component['long_name']
                        
                        # Buscar país
                        elif 'country' in types:
                            city_info['country'] = component['long_name']
                            city_info['country_code'] = component['short_name']
                    
                    # Si encontramos ciudad, retornar
                    if city_info['city']:
                        logging.info(f"✅ Ciudad detectada: {city_info['city']}, {city_info['country']}")
                        return city_info
                
                # Si no encontramos locality, usar administrative_area_level_2 como fallback
                for result in data['results']:
                    components = result.get('address_components', [])
                    
                    for component in components:
                        types = component.get('types', [])
                        
                        if 'administrative_area_level_2' in types:
                            city_info = {
                                'city': component['long_name'],
                                'state': None,
                                'country': None,
                                'country_code': None,
                                'formatted_address': result.get('formatted_address', '')
                            }
                            
                            # Buscar país en el mismo resultado
                            for comp in components:
                                if 'country' in comp.get('types', []):
                                    city_info['country'] = comp['long_name']
                                    city_info['country_code'] = comp['short_name']
                            
                            logging.info(f"✅ Área administrativa detectada como ciudad: {city_info['city']}")
                            return city_info
                
                logging.debug("❓ No se pudo extraer información de ciudad del geocoding")
                return None
                
        except Exception as e:
            logging.error(f"💥 Error en reverse_geocode_city: {e}")
            return None
    
    @cache_google_api(ttl=7200)  # 2 horas de caché para place details
    async def get_place_details_by_id(self, place_id: str) -> Optional[Dict[str, Any]]:
        """
        🎯 Obtener detalles completos de un lugar usando su Google Place ID
        
        Args:
            place_id: ID del lugar de Google Places (ej: ChIJ...)
            
        Returns:
            Dict con detalles del lugar o None si falla
        """
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            url = f"{self.base_url}/place/details/json"
            params = {
                'place_id': place_id,
                'key': self.api_key,
                'fields': 'address_components,formatted_address,geometry,name,place_id,types,rating,user_ratings_total',
                'language': 'es'
            }
            
            logging.debug(f"🎯 Obteniendo detalles para Place ID: {place_id}")
            
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logging.warning(f"⚠️ Google Places Details API error: {response.status}")
                    return None
                
                data = await response.json()
                
                if data.get('status') != 'OK' or not data.get('result'):
                    logging.debug(f"❌ No se encontraron detalles para Place ID: {place_id}")
                    return None
                
                result = data['result']
                
                # Procesar y estructurar la respuesta
                place_details = {
                    'place_id': result.get('place_id'),
                    'name': result.get('name'),
                    'formatted_address': result.get('formatted_address'),
                    'address_components': result.get('address_components', []),
                    'types': result.get('types', []),
                    'rating': result.get('rating'),
                    'user_ratings_total': result.get('user_ratings_total'),
                    'geometry': result.get('geometry', {})
                }
                
                logging.info(f"✅ Detalles obtenidos para: {place_details.get('name', place_id)}")
                return place_details
                
        except Exception as e:
            logging.error(f"💥 Error en get_place_details_by_id: {e}")
            return None
