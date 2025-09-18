from typing import List, Dict, Optional
import logging
import asyncio
from utils.google_maps_client import GoogleMapsClient

class GooglePlacesService:
    def __init__(self):
        self.maps_client = GoogleMapsClient()
        self.logger = logging.getLogger(__name__)
    
    async def search_nearby(
        self, 
        lat: float, 
        lon: float, 
        types: List[str], 
        radius_m: int = 3000, 
        limit: int = 3  # Cambiado de 6 a 3
    ) -> List[Dict]:
        """
        🔍 Búsqueda robusta de lugares cercanos con manejo de errores
        """
        try:
            # Implementar búsqueda con retry
            for attempt in range(2):  # 2 intentos
                try:
                    if hasattr(self.maps_client, 'search_nearby_places'):
                        results = await self.maps_client.search_nearby_places(
                            lat, lon, types, radius_m, limit
                        )
                        return results[:limit]
                    else:
                        # Fallback: generar sugerencias sintéticas basadas en ubicación
                        return self._generate_synthetic_suggestions(lat, lon, types, limit)
                        
                except Exception as e:
                    if attempt == 0:
                        self.logger.warning(f"Primer intento de búsqueda falló: {e}")
                        await asyncio.sleep(1)  # Wait 1 second before retry
                        continue
                    else:
                        raise e
                        
        except Exception as e:
            self.logger.warning(f"Búsqueda de lugares falló: {e}")
            return []
    
    def _generate_synthetic_suggestions(self, lat: float, lon: float, types: List[str], limit: int) -> List[Dict]:
        """Generar exactamente 3 sugerencias sintéticas cuando la API falla"""
        synthetic_places = []
        
        # Base de datos simple de sugerencias por tipo (mejoradas)
        type_suggestions = {
            'restaurant': ['Restaurante local', 'Lugar de comida típica', 'Bistró familiar'],
            'tourist_attraction': ['Sitio histórico', 'Mirador', 'Plaza principal'],
            'museum': ['Centro cultural', 'Galería de arte', 'Museo local'],
            'park': ['Parque urbano', 'Plaza verde', 'Área recreativa'],
            'shopping_mall': ['Centro comercial', 'Mercado local', 'Tiendas'],
            'cafe': ['Café local', 'Lugar de café', 'Cafetería'],
            'point_of_interest': ['Lugar de interés', 'Punto destacado', 'Sitio relevante']
        }
        
        # Generar exactamente 3 sugerencias (o las que se soliciten, máximo 3)
        max_suggestions = min(limit, 3)
        
        for i in range(max_suggestions):
            place_type = types[i % len(types)]
            suggestions = type_suggestions.get(place_type, ['Lugar de interés'])
            name = suggestions[i % len(suggestions)]
            
            # Coordenadas con offset pequeño para evitar solapamiento
            offset_lat = lat + (i * 0.001)  # ~110 metros entre cada sugerencia
            offset_lon = lon + (i * 0.001)
            
            # Calcular distancia aproximada
            distance_km = self._calculate_distance(lat, lon, offset_lat, offset_lon)
            eta_minutes = max(0, int(distance_km * 1000 / 83.33))  # 5 km/h walking speed
            
            # Rating progresivo
            rating = round(4.0 + (i * 0.1), 1)  # 4.0, 4.1, 4.2
            
            synthetic_places.append({
                'name': name,
                'lat': offset_lat,
                'lon': offset_lon,
                'type': place_type,
                'rating': rating,
                'eta_minutes': eta_minutes,
                'reason': f"buen rating ({rating}⭐), {'muy cerca' if eta_minutes < 5 else 'cerca'}",
                'synthetic': True
            })
        
        return synthetic_places
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calcular distancia entre dos puntos usando fórmula haversine"""
        import math
        
        # Radio de la Tierra en km
        R = 6371.0
        
        # Convertir a radianes
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Diferencias
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        # Fórmula haversine
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
        """
        Busca lugares cercanos usando Google Places API.
        
        Args:
            lat: Latitud del centro de búsqueda
            lon: Longitud del centro de búsqueda
            radius: Radio de búsqueda en metros (default 5km)
            place_types: Lista de tipos de lugares a buscar. Si no se especifica,
                        usa una lista predeterminada de tipos turísticos
        
        Returns:
            Lista de lugares encontrados con su información completa
        """
        if place_types is None:
            place_types = [
                'tourist_attraction',
                'museum',
                'park',
                'point_of_interest',
                'natural_feature',
                'amusement_park',
                'art_gallery',
                'aquarium',
                'church',
                'city_hall',
                'historic_site'
            ]
        
        all_places = []
        for place_type in place_types:
            try:
                places = self.maps_client.search_nearby_places(
                    latitude=lat,
                    longitude=lon,
                    radius=radius,
                    place_type=place_type
                )
                if places:
                    all_places.extend(places)
            except Exception as e:
                logging.warning(f"Error buscando lugares de tipo {place_type}: {str(e)}")
                continue
        
        return all_places
    
    def categorize_places(self, places: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Categoriza lugares en tres categorías principales usando sus tipos y atributos.
        
        Args:
            places: Lista de lugares de Google Places API
        
        Returns:
            Diccionario con lugares categorizados en nature_escape, cultural_immersion, adventure_day
        """
        categories = {
            'nature_escape': [],
            'cultural_immersion': [],
            'adventure_day': []
        }
        
        nature_types = {'park', 'natural_feature', 'campground', 'beach', 'hiking_area'}
        cultural_types = {'museum', 'art_gallery', 'church', 'historic_site', 'city_hall'}
        adventure_types = {'amusement_park', 'aquarium', 'zoo', 'stadium', 'sports_complex'}
        
        for place in places:
            place_types = set(place.get('types', []))
            
            # Calcular puntuación para cada categoría
            nature_score = len(place_types.intersection(nature_types))
            cultural_score = len(place_types.intersection(cultural_types))
            adventure_score = len(place_types.intersection(adventure_types))
            
            # Asignar a la categoría con mayor puntuación
            max_score = max(nature_score, cultural_score, adventure_score)
            if max_score == 0:
                # Si no hay match directo, usar heurísticas adicionales
                if 'point_of_interest' in place_types:
                    if place.get('rating', 0) >= 4.5:
                        categories['cultural_immersion'].append(place)
                    else:
                        categories['adventure_day'].append(place)
            else:
                if max_score == nature_score:
                    categories['nature_escape'].append(place)
                elif max_score == cultural_score:
                    categories['cultural_immersion'].append(place)
                else:
                    categories['adventure_day'].append(place)
        
        return categories
    
    def get_transport_options(self, places: List[Dict]) -> Dict[str, str]:
        """
        Determina las mejores opciones de transporte basadas en la distribución de lugares.
        
        Args:
            places: Lista de lugares a analizar
        
        Returns:
            Diccionario con recomendaciones de transporte por categoría
        """
        def calculate_average_distance(coords_list):
            if len(coords_list) < 2:
                return 0
            
            total_distance = 0
            count = 0
            for i in range(len(coords_list)):
                for j in range(i + 1, len(coords_list)):
                    lat1, lon1 = coords_list[i]
                    lat2, lon2 = coords_list[j]
                    distance = self.maps_client.calculate_distance(lat1, lon1, lat2, lon2)
                    total_distance += distance
                    count += 1
            
            return total_distance / count if count > 0 else 0
        
        # Extraer coordenadas de todos los lugares
        coords = [(p['geometry']['location']['lat'], p['geometry']['location']['lng']) 
                 for p in places if 'geometry' in p and 'location' in p['geometry']]
        
        avg_distance = calculate_average_distance(coords)
        
        # Determinar recomendaciones basadas en la distancia promedio
        if avg_distance > 10:  # Si los lugares están a más de 10km en promedio
            return {
                'nature_escape': 'Tour organizado o auto recomendado',
                'cultural_immersion': 'Transporte público o taxi',
                'adventure_day': 'Tour organizado o transporte público'
            }
        elif avg_distance > 3:  # Si los lugares están entre 3-10km
            return {
                'nature_escape': 'Transporte público o auto',
                'cultural_immersion': 'Transporte público',
                'adventure_day': 'Transporte público o bicicleta'
            }
        else:  # Si los lugares están cercanos
            return {
                'nature_escape': 'Transporte público o caminando',
                'cultural_immersion': 'A pie o bicicleta',
                'adventure_day': 'A pie o transporte público'
            }
    
    def generate_day_suggestions(self, lat: float, lon: float) -> Dict[str, List[Dict]]:
        """
        Genera sugerencias completas para un día basadas en la ubicación.
        
        Args:
            lat: Latitud del centro de búsqueda
            lon: Longitud del centro de búsqueda
        
        Returns:
            Diccionario con sugerencias categorizadas y transporte recomendado
        """
        # Buscar lugares cercanos
        places = self.get_nearby_places(lat, lon)
        
        # Categorizar lugares
        categorized_places = self.categorize_places(places)
        
        # Obtener recomendaciones de transporte
        transport_options = self.get_transport_options(places)
        
        # Formatear sugerencias
        suggestions = {}
        for category in categorized_places:
            category_places = categorized_places[category][:4]  # Top 4 lugares por categoría
            
            suggestions[category] = {
                'suggestions': [place['name'] for place in category_places],
                'transport': transport_options[category],
                'places': category_places  # Incluir información completa de los lugares
            }
        
        return suggestions
