#!/usr/bin/env python3
"""
🌍 InterCity Service - Motor de ruteo intercity profesional
Implementación MVP-A para arquitectura multi-ciudad
Maneja routing entre ciudades con OSRM + clustering inteligente
"""

import logging
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from geopy.distance import geodesic
import math
import json
from pathlib import Path

from .osrm_service import OSRMFactory, OSRMService
from .h3_spatial_partitioner import H3SpatialPartitioner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class City:
    """Representa una ciudad en el sistema multi-ciudad"""
    name: str
    center_lat: float
    center_lon: float
    country: str
    pois: List[Dict] = None  # POIs pertenecientes a esta ciudad
    
    def __post_init__(self):
        if self.pois is None:
            self.pois = []
    
    @property
    def coordinates(self) -> Tuple[float, float]:
        """Retorna (lat, lon) del centro de la ciudad"""
        return (self.center_lat, self.center_lon)
    
    def add_poi(self, poi: Dict):
        """Añade un POI a esta ciudad"""
        self.pois.append(poi)
    
    def distance_to(self, other_city: 'City') -> float:
        """Calcula distancia geodésica a otra ciudad en km"""
        return geodesic(self.coordinates, other_city.coordinates).kilometers

@dataclass
class InterCityRoute:
    """Representa una ruta entre ciudades"""
    origin_city: City
    destination_city: City
    distance_km: float
    travel_time_hours: float
    transport_mode: str = "car"
    
    @property
    def is_long_distance(self) -> bool:
        """True si requiere más de 8 horas de viaje"""
        return self.travel_time_hours > 8
    
    @property
    def requires_overnight(self) -> bool:
        """True si requiere pernoctar en el camino"""
        return self.travel_time_hours > 10

class InterCityService:
    """
    Servicio principal para optimización intercity
    
    Funcionalidades:
    - Clustering de POIs por ciudades usando H3
    - Ruteo intercity con OSRM
    - Detección de viajes de larga distancia
    - Cálculo de rutas intercity optimales
    """
    
    def __init__(self, cache_dir: str = "cache"):
        """
        Inicializa el servicio intercity
        
        Args:
            cache_dir: Directorio para cache persistente
        """
        self.osrm = OSRMFactory.create_car_service()
        self.h3_partitioner = H3SpatialPartitioner()
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Cache de ciudades y rutas
        self.cities_cache: Dict[str, City] = {}
        self.routes_cache: Dict[Tuple[str, str], InterCityRoute] = {}
        
        # Configuraciones
        self.city_clustering_threshold_km = 50  # Radio máximo para considerar misma ciudad
        self.max_intercity_distance_km = 2000   # Distancia máxima permitida intercity
        
        logger.info("🌍 InterCityService inicializado")
    
    def cluster_pois_by_cities(self, pois: List[Dict]) -> List[City]:
        """
        Agrupa POIs por ciudades usando clustering espacial H3
        
        Args:
            pois: Lista de POIs con lat, lon, name
            
        Returns:
            Lista de ciudades con POIs asignados
        """
        logger.info(f"🏙️  Clustering {len(pois)} POIs por ciudades...")
        
        if not pois:
            return []
        
        # Extraer coordenadas para clustering
        coordinates = [(poi['lat'], poi['lon']) for poi in pois]
        
        # Usar H3 para clustering inicial
        routing_session = self.h3_partitioner.cluster_pois_auto(pois)
        
        cities = []
        # Agrupar POIs por clusters H3
        from collections import defaultdict
        cluster_groups = defaultdict(list)
        
        for poi in pois:
            h3_id = self.h3_partitioner.coordinate_to_h3(poi['lat'], poi['lon'])
            cluster_groups[h3_id].append(poi)
        
        for h3_id, cluster_pois in cluster_groups.items():
            if not cluster_pois:
                continue
            
            # Calcular centro del cluster
            center_lat = sum(poi['lat'] for poi in cluster_pois) / len(cluster_pois)
            center_lon = sum(poi['lon'] for poi in cluster_pois) / len(cluster_pois)
            
            # Determinar nombre de ciudad (usar el POI más representativo)
            city_name = self._determine_city_name(cluster_pois)
            country = self._determine_country(cluster_pois)
            
            # Crear ciudad
            city = City(
                name=city_name,
                center_lat=center_lat,
                center_lon=center_lon,
                country=country,
                pois=cluster_pois
            )
            
            cities.append(city)
            
            # Cachear ciudad
            self.cities_cache[city.name] = city
        
        logger.info(f"✅ Clustering completado: {len(cities)} ciudades identificadas")
        return cities
    
    def _determine_city_name(self, pois: List[Dict]) -> str:
        """
        Determina el nombre de ciudad más representativo del cluster
        
        Args:
            pois: POIs del cluster
            
        Returns:
            Nombre de ciudad inferido
        """
        # Buscar nombres de ciudades en los POIs
        city_names = []
        for poi in pois:
            # Extraer ciudad desde address o city fields
            if 'city' in poi:
                city_names.append(poi['city'])
            elif 'address' in poi and isinstance(poi['address'], dict):
                if 'city' in poi['address']:
                    city_names.append(poi['address']['city'])
        
        if city_names:
            # Usar la ciudad más común
            from collections import Counter
            most_common = Counter(city_names).most_common(1)
            return most_common[0][0]
        
        # Fallback: usar nombre del primer POI
        return pois[0].get('name', 'Unknown City')
    
    def _determine_country(self, pois: List[Dict]) -> str:
        """
        Determina el país del cluster de POIs
        
        Args:
            pois: POIs del cluster
            
        Returns:
            Nombre del país inferido
        """
        for poi in pois:
            if 'country' in poi:
                return poi['country']
            elif 'address' in poi and isinstance(poi['address'], dict):
                if 'country' in poi['address']:
                    return poi['address']['country']
        
        # Fallback basado en coordenadas (muy básico)
        lat = pois[0]['lat']
        if -56 <= lat <= -17:  # Aproximadamente Chile
            return "Chile"
        elif 41 <= lat <= 51:   # Aproximadamente Europa Central
            return "Europe"
        
        return "Unknown"
    
    def calculate_intercity_routes(self, cities: List[City]) -> List[InterCityRoute]:
        """
        Calcula rutas óptimas entre todas las ciudades
        
        Args:
            cities: Lista de ciudades
            
        Returns:
            Lista de rutas intercity posibles
        """
        logger.info(f"🛣️  Calculando rutas entre {len(cities)} ciudades...")
        
        routes = []
        
        # Calcular todas las combinaciones ciudad-ciudad
        for i, origin_city in enumerate(cities):
            for j, dest_city in enumerate(cities):
                if i == j:
                    continue
                
                # Verificar cache
                cache_key = (origin_city.name, dest_city.name)
                if cache_key in self.routes_cache:
                    routes.append(self.routes_cache[cache_key])
                    continue
                
                # Calcular distancia geodésica
                geodesic_distance = origin_city.distance_to(dest_city)
                
                # Saltar distancias muy largas
                if geodesic_distance > self.max_intercity_distance_km:
                    logger.warning(f"⚠️  Distancia muy larga: {origin_city.name} -> {dest_city.name} ({geodesic_distance:.0f}km)")
                    continue
                
                # Calcular ruta real con OSRM
                route_data = self.osrm.route(
                    origin_city.coordinates, 
                    dest_city.coordinates
                )
                
                if route_data:
                    real_distance_km = route_data['distance_m'] / 1000
                    travel_time_hours = route_data['duration_s'] / 3600
                    
                    intercity_route = InterCityRoute(
                        origin_city=origin_city,
                        destination_city=dest_city,
                        distance_km=real_distance_km,
                        travel_time_hours=travel_time_hours
                    )
                    
                    routes.append(intercity_route)
                    self.routes_cache[cache_key] = intercity_route
                    
                    logger.debug(f"✅ Ruta: {origin_city.name} -> {dest_city.name} "
                               f"({real_distance_km:.0f}km, {travel_time_hours:.1f}h)")
                else:
                    logger.warning(f"❌ No se pudo calcular ruta: {origin_city.name} -> {dest_city.name}")
        
        logger.info(f"✅ {len(routes)} rutas intercity calculadas")
        return routes
    
    def find_optimal_city_sequence(self, cities: List[City], 
                                 start_city: Optional[str] = None) -> List[City]:
        """
        Encuentra secuencia óptima de ciudades (TSP simplificado)
        
        Args:
            cities: Lista de ciudades a visitar
            start_city: Nombre de ciudad inicial (opcional)
            
        Returns:
            Secuencia optimizada de ciudades
        """
        logger.info(f"🎯 Optimizando secuencia de {len(cities)} ciudades...")
        
        if len(cities) <= 1:
            return cities
        
        # Implementación greedy simple (mejorar con OR-Tools más adelante)
        if start_city:
            current_city = next((c for c in cities if c.name == start_city), cities[0])
        else:
            current_city = cities[0]
        
        remaining_cities = [c for c in cities if c.name != current_city.name]
        sequence = [current_city]
        
        while remaining_cities:
            # Encontrar ciudad más cercana
            distances = [(city, current_city.distance_to(city)) 
                        for city in remaining_cities]
            nearest_city, _ = min(distances, key=lambda x: x[1])
            
            sequence.append(nearest_city)
            remaining_cities.remove(nearest_city)
            current_city = nearest_city
        
        total_distance = sum(
            seq_cities[i].distance_to(seq_cities[i+1])
            for i, seq_cities in enumerate([sequence]) 
            for i in range(len(sequence)-1)
        )
        
        logger.info(f"✅ Secuencia optimizada - Distancia total: {total_distance:.0f}km")
        return sequence
    
    def analyze_multi_city_complexity(self, cities: List[City]) -> Dict:
        """
        Analiza la complejidad del viaje multi-ciudad
        
        Args:
            cities: Lista de ciudades
            
        Returns:
            Análisis de complejidad y recomendaciones
        """
        if len(cities) <= 1:
            return {
                "complexity": "simple",
                "total_cities": len(cities),
                "requires_intercity_optimization": False,
                "recommendation": "single_city_optimization"
            }
        
        # Calcular estadísticas
        all_distances = []
        for i, city1 in enumerate(cities):
            for j, city2 in enumerate(cities[i+1:], i+1):
                distance = city1.distance_to(city2)
                all_distances.append(distance)
        
        max_distance = max(all_distances) if all_distances else 0
        avg_distance = sum(all_distances) / len(all_distances) if all_distances else 0
        
        # Determinar complejidad
        if len(cities) == 2 and max_distance <= 100:
            complexity = "simple_intercity"
        elif len(cities) <= 3 and max_distance <= 300:
            complexity = "medium_intercity"
        elif len(cities) <= 5 and max_distance <= 800:
            complexity = "complex_intercity"
        else:
            complexity = "international_complex"
        
        # Detectar países únicos
        countries = set(city.country for city in cities)
        
        return {
            "complexity": complexity,
            "total_cities": len(cities),
            "total_countries": len(countries),
            "max_intercity_distance_km": max_distance,
            "avg_intercity_distance_km": avg_distance,
            "requires_intercity_optimization": True,
            "requires_accommodation": max_distance > 300,
            "requires_international_planning": len(countries) > 1,
            "estimated_trip_days": self._estimate_trip_days(cities, max_distance),
            "recommendation": self._get_optimization_recommendation(complexity)
        }
    
    def _estimate_trip_days(self, cities: List[City], max_distance: float) -> int:
        """Estima días necesarios para el viaje"""
        base_days = len(cities)  # 1 día por ciudad mínimo
        
        if max_distance > 500:
            base_days += 2  # Días adicionales para viajes largos
        elif max_distance > 200:
            base_days += 1
        
        return base_days
    
    def _get_optimization_recommendation(self, complexity: str) -> str:
        """Retorna recomendación de optimización según complejidad"""
        recommendations = {
            "simple_intercity": "hybrid_with_ortools",
            "medium_intercity": "intercity_with_accommodation",
            "complex_intercity": "full_multi_city_architecture", 
            "international_complex": "specialized_international_planning"
        }
        return recommendations.get(complexity, "custom_solution_needed")
    
    def save_cache(self):
        """Guarda cache persistente de ciudades y rutas"""
        cache_file = self.cache_dir / "intercity_cache.json"
        
        # Convertir cache a formato serializable
        cache_data = {
            "cities": {
                name: {
                    "name": city.name,
                    "center_lat": city.center_lat,
                    "center_lon": city.center_lon,
                    "country": city.country,
                    "pois_count": len(city.pois)
                }
                for name, city in self.cities_cache.items()
            },
            "routes": {
                f"{key[0]}->{key[1]}": {
                    "distance_km": route.distance_km,
                    "travel_time_hours": route.travel_time_hours,
                    "transport_mode": route.transport_mode
                }
                for key, route in self.routes_cache.items()
            }
        }
        
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)
        
        logger.info(f"💾 Cache guardado: {cache_file}")

if __name__ == "__main__":
    """Test básico del InterCity Service"""
    
    print("🌍 TESTING INTERCITY SERVICE")
    print("=" * 50)
    
    # POIs de prueba - Eurotrip
    test_pois = [
        {"name": "Eiffel Tower", "lat": 48.8584, "lon": 2.2945, "city": "Paris", "country": "France"},
        {"name": "Louvre Museum", "lat": 48.8606, "lon": 2.3376, "city": "Paris", "country": "France"},
        {"name": "Van Gogh Museum", "lat": 52.3584, "lon": 4.8811, "city": "Amsterdam", "country": "Netherlands"},
        {"name": "Anne Frank House", "lat": 52.3752, "lon": 4.8840, "city": "Amsterdam", "country": "Netherlands"},
        {"name": "Brandenburg Gate", "lat": 52.5163, "lon": 13.3777, "city": "Berlin", "country": "Germany"},
        {"name": "Museum Island", "lat": 52.5170, "lon": 13.4019, "city": "Berlin", "country": "Germany"},
    ]
    
    # Crear servicio
    service = InterCityService()
    
    # Test clustering
    cities = service.cluster_pois_by_cities(test_pois)
    print(f"✅ Ciudades identificadas: {[city.name for city in cities]}")
    
    # Test análisis de complejidad
    analysis = service.analyze_multi_city_complexity(cities)
    print(f"✅ Análisis de complejidad:")
    for key, value in analysis.items():
        print(f"   {key}: {value}")
    
    # Test secuencia óptima
    optimal_sequence = service.find_optimal_city_sequence(cities)
    print(f"✅ Secuencia óptima: {[city.name for city in optimal_sequence]}")