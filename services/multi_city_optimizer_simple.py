#!/usr/bin/env python3
"""
🎯 Multi-City Optimizer - Test Version (Simplified)
Versión simplificada para testing sin dependencias complejas
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

class MultiCityOptimizerSimple:
    """
    Optimizador multi-ciudad simplificado para testing
    """
    
    def __init__(self, config: Optional[OptimizationConfig] = None):
        """Inicializa el optimizador multi-ciudad"""
        self.config = config or OptimizationConfig()
        
        # Servicios especializados
        self.intercity_service = InterCityService()
        self.clustering_service = CityClusteringService()
        
        logger.info("🎯 MultiCityOptimizer (Simple) inicializado")
    
    def optimize_multi_city_itinerary(self, pois: List[Dict], 
                                    trip_duration_days: int,
                                    start_city: Optional[str] = None) -> MultiCityItinerary:
        """
        Optimización principal de itinerario multi-ciudad
        """
        logger.info(f"🎯 Iniciando optimización multi-ciudad para {len(pois)} POIs, {trip_duration_days} días")
        
        # Paso 1: Clustering de POIs por ciudades
        city_clusters = self.clustering_service.cluster_pois_advanced(pois)
        logger.info(f"📍 Ciudades detectadas: {[cluster.name for cluster in city_clusters]}")
        
        # Paso 2: Convertir clusters a Cities
        cities = self._convert_clusters_to_cities(city_clusters)
        
        # Paso 3: Análisis de complejidad y estrategia
        strategy = self._determine_optimization_strategy(cities)
        logger.info(f"🧠 Estrategia seleccionada: {strategy.value}")
        
        # Paso 4: Optimización según estrategia
        if strategy == OptimizationStrategy.SINGLE_CITY_ORTOOLS:
            return self._optimize_single_city_simple(pois, trip_duration_days)
        elif strategy == OptimizationStrategy.INTERCITY_HYBRID:
            return self._optimize_intercity_hybrid_simple(cities, trip_duration_days, start_city)
        else:
            return self._optimize_multi_country_simple(cities, trip_duration_days, start_city)
    
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
        """Determina estrategia de optimización según características del viaje"""
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
        elif len(countries) > 1 or max_distance > self.config.international_threshold_km:
            return OptimizationStrategy.MULTI_COUNTRY_COMPLEX
        else:
            return OptimizationStrategy.INTERCITY_HYBRID
    
    def _optimize_single_city_simple(self, pois: List[Dict], days: int) -> MultiCityItinerary:
        """Optimización simple para ciudad única"""
        logger.info("🏙️ Optimizando ciudad única (versión simple)")
        
        city_name = self._infer_city_name_from_pois(pois)
        
        single_city = City(
            name=city_name,
            center_lat=sum(poi['lat'] for poi in pois) / len(pois),
            center_lon=sum(poi['lon'] for poi in pois) / len(pois),
            country=self._infer_country_from_pois(pois),
            pois=pois
        )
        
        # Schedule simple
        daily_schedules = self._simple_daily_distribution(pois, days)
        
        return MultiCityItinerary(
            cities=[single_city],
            intercity_routes=[],
            daily_schedules=daily_schedules,
            total_duration_days=days,
            optimization_strategy=OptimizationStrategy.SINGLE_CITY_ORTOOLS,
            confidence=0.8
        )
    
    def _optimize_intercity_hybrid_simple(self, cities: List[City], days: int, 
                                        start_city: Optional[str] = None) -> MultiCityItinerary:
        """Optimización híbrida intercity simplificada"""
        logger.info(f"🌆 Optimización intercity híbrida para {len(cities)} ciudades")
        
        # Optimizar secuencia de ciudades
        optimal_sequence = self.intercity_service.find_optimal_city_sequence(
            cities, start_city
        )
        
        # Distribuir días entre ciudades
        days_per_city = self._distribute_days_among_cities(optimal_sequence, days)
        
        # Crear schedule simple
        daily_schedules = {}
        current_day = 1
        
        for city in optimal_sequence:
            city_days = days_per_city.get(city.name, 1)
            city_schedule = self._simple_daily_distribution(city.pois, city_days)
            
            # Asignar días del schedule
            for day_offset in range(city_days):
                day_pois = city_schedule.get(day_offset + 1, [])
                daily_schedules[current_day + day_offset] = day_pois
            
            current_day += city_days
        
        # Calcular distancia total aproximada
        total_distance = 0.0
        for i in range(len(optimal_sequence) - 1):
            distance = optimal_sequence[i].distance_to(optimal_sequence[i + 1])
            total_distance += distance
        
        return MultiCityItinerary(
            cities=optimal_sequence,
            intercity_routes=[],  # Simplificado
            daily_schedules=daily_schedules,
            total_duration_days=days,
            total_distance_km=total_distance,
            optimization_strategy=OptimizationStrategy.INTERCITY_HYBRID,
            confidence=0.7
        )
    
    def _optimize_multi_country_simple(self, cities: List[City], days: int,
                                     start_city: Optional[str] = None) -> MultiCityItinerary:
        """Optimización multi-país simplificada"""
        logger.info(f"🌍 Optimización multi-país para {len(cities)} ciudades")
        
        # Por simplicidad, usar la misma lógica que intercity
        return self._optimize_intercity_hybrid_simple(cities, days, start_city)
    
    def _distribute_days_among_cities(self, cities: List[City], total_days: int) -> Dict[str, int]:
        """Distribuye días optimalmente entre ciudades"""
        if not cities:
            return {}
        
        # Distribución basada en número de POIs
        city_weights = {}
        for city in cities:
            weight = len(city.pois) if city.pois else 1
            city_weights[city.name] = weight
        
        # Distribuir días proporcionalemente
        total_weight = sum(city_weights.values())
        days_distribution = {}
        
        for city_name, weight in city_weights.items():
            assigned_days = max(1, round((weight / total_weight) * total_days))
            days_distribution[city_name] = assigned_days
        
        # Ajustar si la suma no coincide
        actual_total = sum(days_distribution.values())
        if actual_total != total_days:
            max_city = max(city_weights.keys(), key=lambda x: city_weights[x])
            days_distribution[max_city] += (total_days - actual_total)
        
        logger.info(f"📅 Distribución de días: {days_distribution}")
        return days_distribution
    
    def _simple_daily_distribution(self, pois: List[Dict], days: int) -> Dict[int, List[Dict]]:
        """Distribución simple de POIs por días"""
        if not pois:
            return {}
        
        pois_per_day = max(1, len(pois) // days) if days > 0 else len(pois)
        schedule = {}
        
        for day in range(1, days + 1):
            start_idx = (day - 1) * pois_per_day
            end_idx = start_idx + pois_per_day if day < days else len(pois)
            schedule[day] = pois[start_idx:end_idx]
        
        return schedule
    
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

if __name__ == "__main__":
    """Test del MultiCityOptimizer simplificado"""
    
    print("🎯 TESTING MULTI-CITY OPTIMIZER (SIMPLE)")
    print("=" * 50)
    
    # POIs de prueba - Eurotrip simplificado
    test_pois = [
        # París
        {"name": "Eiffel Tower", "lat": 48.8584, "lon": 2.2945, "city": "Paris", "country": "France"},
        {"name": "Louvre Museum", "lat": 48.8606, "lon": 2.3376, "city": "Paris", "country": "France"},
        
        # Berlin
        {"name": "Brandenburg Gate", "lat": 52.5163, "lon": 13.3777, "city": "Berlin", "country": "Germany"}
    ]
    
    # Crear optimizer
    optimizer = MultiCityOptimizerSimple()
    
    # Test optimización
    itinerary = optimizer.optimize_multi_city_itinerary(
        pois=test_pois,
        trip_duration_days=4,
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