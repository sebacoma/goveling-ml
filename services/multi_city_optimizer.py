#!/usr/bin/env python3
"""
🎯 Multi-City Optimizer - Motor de optimización grafo-de-grafos
Implementación MVP-A de arquitectura híbrida para viajes multi-ciudad
Combina OR-Tools (intra-ciudad) + Custom Logic (inter-ciudad) + Accommodation Management
"""

import logging
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
from pathlib import Path
from enum import Enum
import math

from .intercity_service import InterCityService, City, InterCityRoute
from .city_clustering_service import CityClusteringService, CityCluster
from .hybrid_architecture_integrator import HybridArchitectureIntegrator
from .hotel_recommender import HotelRecommender

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OptimizationStrategy(Enum):
    """Estrategias de optimización disponibles"""
    SINGLE_CITY_ORTOOLS = "single_city_ortools"
    INTERCITY_HYBRID = "intercity_hybrid"
    MULTI_COUNTRY_COMPLEX = "multi_country_complex"
    CUSTOM_EUROTRIP = "custom_eurotrip"

@dataclass
class MultiCityItinerary:
    """Representa un itinerario multi-ciudad optimizado"""
    cities: List[City]
    intercity_routes: List[InterCityRoute]
    daily_schedules: Dict[int, List[Dict]]  # día -> POIs del día
    accommodations: List[Dict] = field(default_factory=list)
    total_duration_days: int = 0
    total_distance_km: float = 0.0
    optimization_strategy: OptimizationStrategy = OptimizationStrategy.INTERCITY_HYBRID
    confidence: float = 0.0
    
    @property
    def cities_count(self) -> int:
        """Número de ciudades en el itinerario"""
        return len(self.cities)
    
    @property
    def countries_count(self) -> int:
        """Número de países únicos"""
        return len(set(city.country for city in self.cities))
    
    def get_city_sequence(self) -> List[str]:
        """Retorna secuencia de nombres de ciudades"""
        return [city.name for city in self.cities]

@dataclass  
class OptimizationConfig:
    """Configuración para optimización multi-ciudad"""
    max_days_per_city: int = 3
    min_intercity_travel_time_hours: float = 2.0
    max_daily_travel_time_hours: float = 8.0
    prefer_morning_departures: bool = True
    require_accommodations: bool = True
    budget_per_day: Optional[float] = None
    
    # Thresholds de decisión
    single_city_threshold_km: float = 50.0
    intercity_threshold_km: float = 300.0
    international_threshold_km: float = 800.0

class MultiCityOptimizer:
    """
    Optimizador principal para viajes multi-ciudad
    
    Arquitectura grafo-de-grafos:
    1. Grafo Intercity: Conexiones entre ciudades (TSP)
    2. Grafos Intracity: Optimización dentro de cada ciudad (OR-Tools)
    3. Scheduling: Asignación temporal y accommodations
    """
    
    def __init__(self, config: Optional[OptimizationConfig] = None):
        """
        Inicializa el optimizador multi-ciudad
        
        Args:
            config: Configuración personalizada
        """
        self.config = config or OptimizationConfig()
        
        # Servicios especializados
        self.intercity_service = InterCityService()
        self.clustering_service = CityClusteringService()
        self.hybrid_integrator = HybridArchitectureIntegrator()
        self.hotel_recommender = HotelRecommender()
        
        # Cache de optimizaciones
        self.optimization_cache: Dict[str, MultiCityItinerary] = {}
        
        logger.info("🎯 MultiCityOptimizer inicializado")
    
    def optimize_multi_city_itinerary(self, pois: List[Dict], 
                                    trip_duration_days: int,
                                    start_city: Optional[str] = None) -> MultiCityItinerary:
        """
        Optimización principal de itinerario multi-ciudad
        
        Args:
            pois: Lista de POIs a visitar
            trip_duration_days: Duración del viaje en días
            start_city: Ciudad de inicio preferida
            
        Returns:
            Itinerario multi-ciudad optimizado
        """
        logger.info(f"🎯 Iniciando optimización multi-ciudad para {len(pois)} POIs, {trip_duration_days} días")
        
        # Paso 1: Clustering de POIs por ciudades
        city_clusters = self.clustering_service.cluster_pois_advanced(pois)
        logger.info(f"📍 Ciudades detectadas: {[cluster.name for cluster in city_clusters]}")
        
        # Paso 2: Convertir clusters a Cities para intercity service
        cities = self._convert_clusters_to_cities(city_clusters)
        
        # Paso 3: Análisis de complejidad y estrategia
        strategy = self._determine_optimization_strategy(cities)
        logger.info(f"🧠 Estrategia seleccionada: {strategy.value}")
        
        # Paso 4: Optimización según estrategia
        if strategy == OptimizationStrategy.SINGLE_CITY_ORTOOLS:
            return self._optimize_single_city(pois, trip_duration_days)
        elif strategy == OptimizationStrategy.INTERCITY_HYBRID:
            return self._optimize_intercity_hybrid(cities, trip_duration_days, start_city)
        elif strategy == OptimizationStrategy.MULTI_COUNTRY_COMPLEX:
            return self._optimize_multi_country(cities, trip_duration_days, start_city)
        else:
            return self._optimize_custom_eurotrip(cities, trip_duration_days, start_city)
    
    def _convert_clusters_to_cities(self, clusters: List[CityCluster]) -> List[City]:
        """Convierte CityCluster a City para compatibilidad"""
        cities = []
        for cluster in clusters:
            city = City(
                name=cluster.name,
                center_lat=cluster.center_lat,
                center_lon=cluster.center_lon,
                country=cluster.country,
                pois=cluster.pois
            )
            cities.append(city)
        return cities
    
    def _determine_optimization_strategy(self, cities: List[City]) -> OptimizationStrategy:
        """
        Determina estrategia de optimización según características del viaje
        
        Args:
            cities: Lista de ciudades detectadas
            
        Returns:
            Estrategia óptima de optimización
        """
        if len(cities) <= 1:
            return OptimizationStrategy.SINGLE_CITY_ORTOOLS
        
        # Calcular métricas de decisión
        max_distance = 0.0
        countries = set()
        
        for i, city1 in enumerate(cities):
            countries.add(city1.country)
            for j, city2 in enumerate(cities[i+1:], i+1):
                distance = city1.distance_to(city2)
                max_distance = max(max_distance, distance)
        
        # Reglas de decisión
        if len(cities) == 2 and max_distance <= self.config.intercity_threshold_km:
            return OptimizationStrategy.INTERCITY_HYBRID
        elif len(countries) > 2 or max_distance > self.config.international_threshold_km:
            return OptimizationStrategy.MULTI_COUNTRY_COMPLEX
        elif len(cities) <= 4 and max_distance <= self.config.international_threshold_km:
            return OptimizationStrategy.INTERCITY_HYBRID
        else:
            return OptimizationStrategy.CUSTOM_EUROTRIP
    
    def _optimize_single_city(self, pois: List[Dict], days: int) -> MultiCityItinerary:
        """
        Optimización para ciudad única usando OR-Tools
        
        Args:
            pois: POIs de la ciudad
            days: Duración del viaje
            
        Returns:
            Itinerario optimizado de ciudad única
        """
        logger.info("🏙️ Optimizando ciudad única con OR-Tools")
        
        # Usar el integrador híbrido para OR-Tools
        try:
            result = self.hybrid_integrator.optimize_itinerary(
                pois=pois,
                duration_days=days,
                optimization_level="professional"
            )
            
            if result['success']:
                # Convertir resultado a MultiCityItinerary
                city_name = self._infer_city_name_from_pois(pois)
                
                single_city = City(
                    name=city_name,
                    center_lat=sum(poi['lat'] for poi in pois) / len(pois),
                    center_lon=sum(poi['lon'] for poi in pois) / len(pois),
                    country=self._infer_country_from_pois(pois),
                    pois=pois
                )
                
                return MultiCityItinerary(
                    cities=[single_city],
                    intercity_routes=[],
                    daily_schedules=self._convert_ortools_to_daily_schedule(result['itinerary']),
                    total_duration_days=days,
                    optimization_strategy=OptimizationStrategy.SINGLE_CITY_ORTOOLS,
                    confidence=result.get('confidence', 0.9)
                )
            else:
                # Fallback a optimización básica
                logger.warning("OR-Tools falló, usando fallback básico")
                return self._create_fallback_itinerary(pois, days)
                
        except Exception as e:
            logger.error(f"Error en OR-Tools: {e}")
            return self._create_fallback_itinerary(pois, days)
    
    def _optimize_intercity_hybrid(self, cities: List[City], days: int, 
                                 start_city: Optional[str] = None) -> MultiCityItinerary:
        """
        Optimización híbrida intercity: TSP + OR-Tools por ciudad
        
        Args:
            cities: Lista de ciudades
            days: Duración total del viaje
            start_city: Ciudad de inicio
            
        Returns:
            Itinerario intercity optimizado
        """
        logger.info(f"🌆 Optimización intercity híbrida para {len(cities)} ciudades")
        
        # Paso 1: Optimizar secuencia de ciudades (TSP intercity)
        optimal_sequence = self.intercity_service.find_optimal_city_sequence(
            cities, start_city
        )
        
        # Paso 2: Calcular rutas intercity
        intercity_routes = self.intercity_service.calculate_intercity_routes(optimal_sequence)
        
        # Paso 3: Distribuir días entre ciudades
        days_per_city = self._distribute_days_among_cities(cities, days)
        
        # Paso 4: Optimizar cada ciudad individualmente con OR-Tools
        daily_schedules = {}
        current_day = 1
        
        for i, city in enumerate(optimal_sequence):
            city_days = days_per_city.get(city.name, 1)
            
            # Optimizar POIs de esta ciudad
            if city.pois:
                city_schedule = self._optimize_city_pois_with_ortools(
                    city.pois, city_days
                )
                
                # Asignar días del schedule
                for day_offset in range(city_days):
                    daily_schedules[current_day + day_offset] = city_schedule.get(day_offset + 1, [])
                
            current_day += city_days
        
        # Paso 5: Gestión de accommodations
        accommodations = self._plan_intercity_accommodations(optimal_sequence, days_per_city)
        
        return MultiCityItinerary(
            cities=optimal_sequence,
            intercity_routes=[route for route in intercity_routes if route.origin_city in optimal_sequence and route.destination_city in optimal_sequence],
            daily_schedules=daily_schedules,
            accommodations=accommodations,
            total_duration_days=days,
            total_distance_km=sum(route.distance_km for route in intercity_routes),
            optimization_strategy=OptimizationStrategy.INTERCITY_HYBRID,
            confidence=0.8
        )
    
    def _optimize_multi_country(self, cities: List[City], days: int,
                              start_city: Optional[str] = None) -> MultiCityItinerary:
        """
        Optimización para viajes multi-país complejos
        
        Args:
            cities: Lista de ciudades
            days: Duración del viaje
            start_city: Ciudad de inicio
            
        Returns:
            Itinerario multi-país optimizado
        """
        logger.info(f"🌍 Optimización multi-país para {len(cities)} ciudades")
        
        # Agrupar ciudades por país para optimización regional
        cities_by_country = self._group_cities_by_country(cities)
        logger.info(f"🗺️ Países detectados: {list(cities_by_country.keys())}")
        
        # Optimizar secuencia de países (macro-routing)
        country_sequence = self._optimize_country_sequence(cities_by_country, start_city)
        
        # Distribuir días entre países
        days_per_country = self._distribute_days_among_countries(cities_by_country, days)
        
        # Optimizar dentro de cada país
        all_cities_sequence = []
        all_routes = []
        daily_schedules = {}
        current_day = 1
        
        for country in country_sequence:
            country_cities = cities_by_country[country]
            country_days = days_per_country[country]
            
            # Optimizar ciudades dentro del país
            country_itinerary = self._optimize_intercity_hybrid(
                country_cities, country_days
            )
            
            # Integrar al itinerario global
            all_cities_sequence.extend(country_itinerary.cities)
            all_routes.extend(country_itinerary.intercity_routes)
            
            # Ajustar días del schedule
            for day_offset, day_pois in country_itinerary.daily_schedules.items():
                daily_schedules[current_day + day_offset - 1] = day_pois
            
            current_day += country_days
        
        # Accommodations internacionales
        accommodations = self._plan_international_accommodations(all_cities_sequence)
        
        return MultiCityItinerary(
            cities=all_cities_sequence,
            intercity_routes=all_routes,
            daily_schedules=daily_schedules,
            accommodations=accommodations,
            total_duration_days=days,
            optimization_strategy=OptimizationStrategy.MULTI_COUNTRY_COMPLEX,
            confidence=0.7  # Menor confianza por complejidad
        )
    
    def _optimize_custom_eurotrip(self, cities: List[City], days: int,
                                start_city: Optional[str] = None) -> MultiCityItinerary:
        """
        Optimización especializada para Eurotrip
        
        Args:
            cities: Ciudades europeas
            days: Duración del viaje
            start_city: Ciudad de inicio
            
        Returns:
            Itinerario Eurotrip optimizado
        """
        logger.info(f"✈️ Optimización Eurotrip especializada para {len(cities)} ciudades")
        
        # Eurotrip usa clustering geográfico + transporte optimizado
        return self._optimize_multi_country(cities, days, start_city)
    
    # ===== MÉTODOS AUXILIARES =====
    
    def _distribute_days_among_cities(self, cities: List[City], total_days: int) -> Dict[str, int]:
        """Distribuye días optimalmente entre ciudades"""
        if not cities:
            return {}
        
        # Distribución basada en número de POIs y importancia de la ciudad
        city_weights = {}
        for city in cities:
            weight = len(city.pois) if city.pois else 1
            # Bonus para ciudades con nombres conocidos
            if city.name.lower() in ['paris', 'london', 'rome', 'berlin', 'madrid']:
                weight *= 1.5
            city_weights[city.name] = weight
        
        # Distribuir días proporcionalamente
        total_weight = sum(city_weights.values())
        days_distribution = {}
        
        for city_name, weight in city_weights.items():
            assigned_days = max(1, round((weight / total_weight) * total_days))
            days_distribution[city_name] = assigned_days
        
        # Ajustar si la suma no coincide
        actual_total = sum(days_distribution.values())
        if actual_total != total_days:
            # Ajustar la ciudad con más peso
            max_city = max(city_weights.keys(), key=lambda x: city_weights[x])
            days_distribution[max_city] += (total_days - actual_total)
        
        logger.info(f"📅 Distribución de días: {days_distribution}")
        return days_distribution
    
    def _optimize_city_pois_with_ortools(self, pois: List[Dict], days: int) -> Dict[int, List[Dict]]:
        """Optimiza POIs de una ciudad usando OR-Tools"""
        try:
            result = self.hybrid_integrator.optimize_itinerary(
                pois=pois,
                duration_days=days,
                optimization_level="professional"
            )
            
            if result['success']:
                return self._convert_ortools_to_daily_schedule(result['itinerary'])
            else:
                # Fallback: distribución simple por días
                return self._simple_daily_distribution(pois, days)
                
        except Exception as e:
            logger.warning(f"OR-Tools falló para ciudad, usando distribución simple: {e}")
            return self._simple_daily_distribution(pois, days)
    
    def _convert_ortools_to_daily_schedule(self, ortools_itinerary: List[Dict]) -> Dict[int, List[Dict]]:
        """Convierte resultado de OR-Tools a schedule por días"""
        schedule = {}
        current_day = 1
        
        for item in ortools_itinerary:
            if item.get('type') == 'poi':
                if current_day not in schedule:
                    schedule[current_day] = []
                schedule[current_day].append(item)
            elif item.get('type') == 'day_end':
                current_day += 1
        
        return schedule
    
    def _simple_daily_distribution(self, pois: List[Dict], days: int) -> Dict[int, List[Dict]]:
        """Distribución simple de POIs por días (fallback)"""
        pois_per_day = max(1, len(pois) // days)
        schedule = {}
        
        for day in range(1, days + 1):
            start_idx = (day - 1) * pois_per_day
            end_idx = start_idx + pois_per_day if day < days else len(pois)
            schedule[day] = pois[start_idx:end_idx]
        
        return schedule
    
    def _plan_intercity_accommodations(self, cities: List[City], 
                                     days_per_city: Dict[str, int]) -> List[Dict]:
        """Planifica accommodations para viaje intercity"""
        accommodations = []
        
        for city in cities:
            city_days = days_per_city.get(city.name, 1)
            if city_days > 1:  # Solo si se queda más de 1 día
                try:
                    # Usar hotel recommender para encontrar accommodation
                    hotels = self.hotel_recommender.find_hotels_near_pois(
                        city.pois, 
                        nights=city_days - 1
                    )
                    
                    if hotels:
                        accommodations.append({
                            'city': city.name,
                            'hotel': hotels[0],  # Mejor hotel
                            'nights': city_days - 1,
                            'coordinates': (city.center_lat, city.center_lon)
                        })
                        
                except Exception as e:
                    logger.warning(f"Error buscando hotel en {city.name}: {e}")
        
        return accommodations
    
    def _group_cities_by_country(self, cities: List[City]) -> Dict[str, List[City]]:
        """Agrupa ciudades por país"""
        countries = {}
        for city in cities:
            if city.country not in countries:
                countries[city.country] = []
            countries[city.country].append(city)
        return countries
    
    def _optimize_country_sequence(self, cities_by_country: Dict[str, List[City]], 
                                 start_city: Optional[str] = None) -> List[str]:
        """Optimiza secuencia de países a visitar"""
        # Implementación simple: ordenar por proximidad geográfica
        if not cities_by_country:
            return []
        
        countries = list(cities_by_country.keys())
        if len(countries) <= 1:
            return countries
        
        # Si hay ciudad de inicio, empezar por su país
        if start_city:
            for country, cities in cities_by_country.items():
                if any(city.name == start_city for city in cities):
                    countries.remove(country)
                    return [country] + countries
        
        return countries  # Por ahora, orden original
    
    def _distribute_days_among_countries(self, cities_by_country: Dict[str, List[City]], 
                                       total_days: int) -> Dict[str, int]:
        """Distribuye días entre países"""
        # Distribución proporcional al número de ciudades/POIs
        country_weights = {}
        for country, cities in cities_by_country.items():
            weight = sum(len(city.pois) for city in cities if city.pois)
            country_weights[country] = max(1, weight)
        
        total_weight = sum(country_weights.values())
        days_per_country = {}
        
        for country, weight in country_weights.items():
            days = max(1, round((weight / total_weight) * total_days))
            days_per_country[country] = days
        
        return days_per_country
    
    def _plan_international_accommodations(self, cities: List[City]) -> List[Dict]:
        """Planifica accommodations para viaje internacional"""
        # Simplified accommodation planning
        accommodations = []
        
        for city in cities:
            if len(city.pois) >= 2:  # Solo ciudades con múltiples POIs
                accommodations.append({
                    'city': city.name,
                    'country': city.country,
                    'type': 'hotel',
                    'coordinates': city.coordinates,
                    'nights': 1  # Default 1 noche por ciudad
                })
        
        return accommodations
    
    def _infer_city_name_from_pois(self, pois: List[Dict]) -> str:
        """Infiere nombre de ciudad desde POIs"""
        for poi in pois:
            if 'city' in poi and poi['city']:
                return poi['city']
        return f"City_{len(pois)}_POIs"
    
    def _infer_country_from_pois(self, pois: List[Dict]) -> str:
        """Infiere país desde POIs"""
        for poi in pois:
            if 'country' in poi and poi['country']:
                return poi['country']
        return "Unknown"
    
    def _create_fallback_itinerary(self, pois: List[Dict], days: int) -> MultiCityItinerary:
        """Crea itinerario básico como fallback"""
        city_name = self._infer_city_name_from_pois(pois)
        
        fallback_city = City(
            name=city_name,
            center_lat=sum(poi['lat'] for poi in pois) / len(pois),
            center_lon=sum(poi['lon'] for poi in pois) / len(pois),
            country=self._infer_country_from_pois(pois),
            pois=pois
        )
        
        # Schedule simple
        daily_schedules = self._simple_daily_distribution(pois, days)
        
        return MultiCityItinerary(
            cities=[fallback_city],
            intercity_routes=[],
            daily_schedules=daily_schedules,
            total_duration_days=days,
            optimization_strategy=OptimizationStrategy.SINGLE_CITY_ORTOOLS,
            confidence=0.5  # Baja confianza por ser fallback
        )

if __name__ == "__main__":
    """Test básico del MultiCityOptimizer"""
    
    print("🎯 TESTING MULTI-CITY OPTIMIZER")
    print("=" * 50)
    
    # POIs de prueba - Eurotrip simplificado
    test_pois = [
        # París
        {"name": "Eiffel Tower", "lat": 48.8584, "lon": 2.2945, "city": "Paris", "country": "France"},
        {"name": "Louvre Museum", "lat": 48.8606, "lon": 2.3376, "city": "Paris", "country": "France"},
        
        # Amsterdam
        {"name": "Van Gogh Museum", "lat": 52.3584, "lon": 4.8811, "city": "Amsterdam", "country": "Netherlands"},
        
        # Berlin
        {"name": "Brandenburg Gate", "lat": 52.5163, "lon": 13.3777, "city": "Berlin", "country": "Germany"}
    ]
    
    # Crear optimizer
    optimizer = MultiCityOptimizer()
    
    # Test optimización
    itinerary = optimizer.optimize_multi_city_itinerary(
        pois=test_pois,
        trip_duration_days=6,
        start_city="Paris"
    )
    
    print(f"✅ Itinerario optimizado:")
    print(f"   Ciudades: {itinerary.get_city_sequence()}")
    print(f"   Estrategia: {itinerary.optimization_strategy.value}")
    print(f"   Duración: {itinerary.total_duration_days} días")
    print(f"   Confianza: {itinerary.confidence:.2f}")
    print(f"   Países: {itinerary.countries_count}")
    
    # Schedule por días
    print(f"\n📅 SCHEDULE POR DÍAS:")
    for day, pois in itinerary.daily_schedules.items():
        print(f"   Día {day}: {[poi.get('name', 'POI') for poi in pois]}")