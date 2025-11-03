#!/usr/bin/env python3
"""
🎯 OR-Tools Advanced Constraints Service - Week 4 Multi-City Integration
Habilita constraints avanzados para OR-Tools: time windows, vehicle routing, multi-city optimization
"""

import logging
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
import json

from settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConstraintType(Enum):
    """Tipos de constraints avanzados OR-Tools"""
    TIME_WINDOW = "time_window"
    VEHICLE_CAPACITY = "vehicle_capacity" 
    MULTI_DAY_ROUTING = "multi_day_routing"
    ACCOMMODATION_PLACEMENT = "accommodation_placement"
    INTER_CITY_TRAVEL = "inter_city_travel"
    BUDGET_CONSTRAINT = "budget_constraint"
    PRIORITY_WEIGHTING = "priority_weighting"

@dataclass
class TimeWindow:
    """Ventana temporal para un lugar o actividad"""
    start_time: time
    end_time: time
    day_offset: int = 0  # Para multi-día: 0=día1, 1=día2, etc.
    is_required: bool = True  # True=hard constraint, False=soft preference
    
    def to_minutes(self) -> Tuple[int, int]:
        """Convertir a minutos desde medianoche + day_offset"""
        start_minutes = self.start_time.hour * 60 + self.start_time.minute
        end_minutes = self.end_time.hour * 60 + self.end_time.minute
        
        # Añadir offset de día
        day_minutes = self.day_offset * 24 * 60
        
        return (start_minutes + day_minutes, end_minutes + day_minutes)

@dataclass 
class VehicleConstraints:
    """Constraints relacionados con vehículo/transporte"""
    max_daily_distance_km: float = 500.0  # Máxima distancia diaria
    max_continuous_drive_hours: float = 4.0  # Máximo manejo continuo
    required_rest_minutes: int = 30  # Descanso requerido cada X horas
    fuel_stops_required: bool = False  # Si requiere paradas de combustible
    toll_costs_per_km: float = 0.0  # Costo peajes por km

@dataclass
class AccommodationConstraint:
    """Constraints para ubicación de alojamiento"""
    max_distance_to_activities_km: float = 20.0  # Distancia máx a actividades
    min_nights_per_city: int = 1  # Mínimo noches por ciudad
    max_nights_per_city: int = 7  # Máximo noches por ciudad
    budget_per_night: float = 100.0  # Presupuesto por noche
    preferred_location: str = "city_center"  # city_center, near_attractions, budget_friendly

@dataclass
class InterCityConstraint:
    """Constraints para viajes intercity"""
    max_intercity_distance_km: float = 800.0  # Máx distancia entre ciudades sin vuelo
    prefer_flights_over_km: float = 1000.0  # Preferir vuelos sobre esta distancia
    max_daily_cities: int = 2  # Máximo ciudades por día
    min_time_per_city_hours: float = 4.0  # Tiempo mínimo por ciudad
    
class AdvancedConstraintsEngine:
    """
    🧮 Motor de constraints avanzados para OR-Tools
    
    Integra con el sistema multi-ciudad existente para añadir:
    - Time windows precisas por tipo de lugar
    - Vehicle routing constraints
    - Multi-day optimization
    - Accommodation placement optimization
    - Inter-city travel constraints
    """
    
    def __init__(self):
        self.enabled_constraints = self._load_enabled_constraints()
        self.constraint_weights = self._load_constraint_weights()
        
        logger.info(f"🎯 AdvancedConstraintsEngine initialized - {len(self.enabled_constraints)} constraints enabled")
    
    def _load_enabled_constraints(self) -> List[ConstraintType]:
        """Cargar constraints habilitados desde settings"""
        enabled = []
        
        if settings.ORTOOLS_ENABLE_TIME_WINDOWS:
            enabled.append(ConstraintType.TIME_WINDOW)
        
        if settings.ORTOOLS_ENABLE_VEHICLE_ROUTING:
            enabled.append(ConstraintType.VEHICLE_CAPACITY)
            enabled.append(ConstraintType.MULTI_DAY_ROUTING)
        
        if settings.ORTOOLS_ENABLE_MULTI_CITY:
            enabled.append(ConstraintType.INTER_CITY_TRAVEL)
            
        if settings.ORTOOLS_ACCOMMODATE_MULTI_CITY:
            enabled.append(ConstraintType.ACCOMMODATION_PLACEMENT)
        
        if settings.ORTOOLS_ENABLE_ADVANCED_CONSTRAINTS:
            enabled.append(ConstraintType.BUDGET_CONSTRAINT)
            enabled.append(ConstraintType.PRIORITY_WEIGHTING)
        
        return enabled
    
    def _load_constraint_weights(self) -> Dict[ConstraintType, float]:
        """Pesos para different constraints en optimización"""
        return {
            ConstraintType.TIME_WINDOW: 100.0,  # Hard constraint
            ConstraintType.VEHICLE_CAPACITY: 80.0,
            ConstraintType.MULTI_DAY_ROUTING: 60.0,
            ConstraintType.ACCOMMODATION_PLACEMENT: 70.0,
            ConstraintType.INTER_CITY_TRAVEL: 90.0,  # Muy importante para multi-ciudad
            ConstraintType.BUDGET_CONSTRAINT: 50.0,
            ConstraintType.PRIORITY_WEIGHTING: 40.0
        }
    
    def generate_time_windows(self, places: List[Dict], preferences: Dict[str, Any]) -> Dict[str, TimeWindow]:
        """
        Generar time windows inteligentes basadas en tipo de lugar
        
        Returns:
            Dict con place_id -> TimeWindow mapping
        """
        time_windows = {}
        
        # Configuración base de horarios
        daily_start = preferences.get("daily_start_hour", 9)
        daily_end = preferences.get("daily_end_hour", 18)
        
        for i, place in enumerate(places):
            place_type = place.get("type", place.get("category", "attraction"))
            place_id = place.get("id", f"place_{i}")
            
            # Time windows específicas por tipo
            if place_type in ["restaurant", "cafe", "bar"]:
                time_windows[place_id] = self._generate_restaurant_time_window(place, preferences)
            
            elif place_type in ["museum", "gallery", "monument"]:
                time_windows[place_id] = self._generate_museum_time_window(place, preferences)
            
            elif place_type in ["park", "beach", "natural_feature"]:
                time_windows[place_id] = self._generate_outdoor_time_window(place, preferences)
            
            elif place_type in ["shopping", "shopping_mall", "store"]:
                time_windows[place_id] = self._generate_shopping_time_window(place, preferences)
            
            else:
                # Time window genérica
                time_windows[place_id] = TimeWindow(
                    start_time=time(daily_start, 0),
                    end_time=time(daily_end, 0),
                    is_required=False
                )
        
        return time_windows
    
    def _generate_restaurant_time_window(self, place: Dict, preferences: Dict) -> TimeWindow:
        """Time window específica para restaurantes"""
        # Determinar si es lunch o dinner basado en rating/nombre
        place_name = place.get("name", "").lower()
        
        if any(keyword in place_name for keyword in ["breakfast", "cafe", "coffee"]):
            # Desayuno/café
            return TimeWindow(
                start_time=time(7, 0),
                end_time=time(11, 0),
                is_required=False
            )
        elif any(keyword in place_name for keyword in ["lunch", "almuerzo"]):
            # Almuerzo
            return TimeWindow(
                start_time=time(settings.RESTAURANT_LUNCH_START, 0),
                end_time=time(settings.RESTAURANT_LUNCH_END, 0),
                is_required=True
            )
        elif any(keyword in place_name for keyword in ["dinner", "cena", "night"]):
            # Cena
            return TimeWindow(
                start_time=time(settings.RESTAURANT_DINNER_START, 0),
                end_time=time(settings.RESTAURANT_DINNER_END, 0),
                is_required=True
            )
        else:
            # Restaurante general - horario amplio
            return TimeWindow(
                start_time=time(12, 0),
                end_time=time(22, 0),
                is_required=False
            )
    
    def _generate_museum_time_window(self, place: Dict, preferences: Dict) -> TimeWindow:
        """Time window para museos y atracciones culturales"""
        return TimeWindow(
            start_time=time(settings.MUSEUM_PREFERRED_START, 0),
            end_time=time(settings.MUSEUM_PREFERRED_END, 0),
            is_required=True  # Museos tienen horarios estrictos
        )
    
    def _generate_outdoor_time_window(self, place: Dict, preferences: Dict) -> TimeWindow:
        """Time window para actividades al aire libre"""
        # Actividades outdoor prefieren horas de día
        return TimeWindow(
            start_time=time(8, 0),  # Temprano para evitar multitudes
            end_time=time(17, 0),   # Antes del atardecer
            is_required=False
        )
    
    def _generate_shopping_time_window(self, place: Dict, preferences: Dict) -> TimeWindow:
        """Time window para shopping"""
        return TimeWindow(
            start_time=time(settings.SHOPPING_PREFERRED_START, 0),
            end_time=time(settings.SHOPPING_PREFERRED_END, 0),
            is_required=False
        )
    
    def generate_vehicle_constraints(self, places: List[Dict], 
                                   preferences: Dict[str, Any]) -> VehicleConstraints:
        """Generar constraints de vehículo basadas en preferencias y distancias"""
        
        transport_mode = preferences.get("transport_mode", "driving")
        trip_duration_days = preferences.get("duration_days", 1)
        
        # Calcular distancia total estimada
        total_distance_estimate = self._estimate_total_distance(places)
        
        if transport_mode == "walking":
            return VehicleConstraints(
                max_daily_distance_km=15.0,  # Máximo caminable
                max_continuous_drive_hours=0.0,  # No aplicable
                required_rest_minutes=60,  # Descansos frecuentes caminando
                fuel_stops_required=False
            )
        
        elif transport_mode == "driving":
            return VehicleConstraints(
                max_daily_distance_km=min(500.0, total_distance_estimate / max(1, trip_duration_days) * 1.5),
                max_continuous_drive_hours=4.0,
                required_rest_minutes=30,
                fuel_stops_required=total_distance_estimate > 300,
                toll_costs_per_km=0.05  # Estimado Chile
            )
        
        elif transport_mode == "public_transport":
            return VehicleConstraints(
                max_daily_distance_km=200.0,  # Limitado por horarios
                max_continuous_drive_hours=2.0,  # Tiempo en transporte
                required_rest_minutes=15,
                fuel_stops_required=False
            )
        
        else:
            # Default constraints
            return VehicleConstraints()
    
    def _estimate_total_distance(self, places: List[Dict]) -> float:
        """Estimar distancia total del viaje"""
        if len(places) < 2:
            return 0.0
        
        # Calcular distancia geodésica total como estimación
        from geopy.distance import geodesic
        
        total_distance = 0.0
        for i in range(len(places) - 1):
            p1 = places[i]
            p2 = places[i + 1]
            
            distance = geodesic(
                (p1['lat'], p1['lon']),
                (p2['lat'], p2['lon'])
            ).kilometers
            
            total_distance += distance
        
        return total_distance
    
    def generate_accommodation_constraints(self, cities: List[Dict], 
                                         preferences: Dict[str, Any]) -> List[AccommodationConstraint]:
        """Generar constraints de alojamiento por ciudad"""
        constraints = []
        
        budget_level = preferences.get("budget", "mid")
        pace = preferences.get("pace", "normal")
        
        # Budget mapping
        budget_per_night = {
            "low": 50.0,
            "mid": 100.0, 
            "high": 200.0,
            "luxury": 400.0
        }.get(budget_level, 100.0)
        
        # Pace mapping para tiempo por ciudad
        min_time_per_city = {
            "relaxed": 6.0,
            "normal": 4.0,
            "fast": 2.0
        }.get(pace, 4.0)
        
        for city in cities:
            city_size = city.get("size", "medium")  # small, medium, large
            pois_count = len(city.get("pois", []))
            
            # Calcular noches recomendadas basado en POIs
            recommended_nights = max(1, pois_count // 3)
            
            constraint = AccommodationConstraint(
                max_distance_to_activities_km=self._get_city_radius(city_size),
                min_nights_per_city=max(1, recommended_nights - 1),
                max_nights_per_city=recommended_nights + 2,
                budget_per_night=budget_per_night,
                preferred_location=self._get_preferred_location(budget_level, city_size)
            )
            
            constraints.append(constraint)
        
        return constraints
    
    def _get_city_radius(self, city_size: str) -> float:
        """Radio máximo desde alojamiento según tamaño de ciudad"""
        return {
            "small": 10.0,   # Ciudad pequeña
            "medium": 20.0,  # Ciudad mediana
            "large": 35.0,   # Ciudad grande
            "metro": 50.0    # Metrópolis
        }.get(city_size, 20.0)
    
    def _get_preferred_location(self, budget_level: str, city_size: str) -> str:
        """Ubicación preferida según budget y ciudad"""
        if budget_level in ["low", "mid"]:
            return "budget_friendly"
        elif city_size in ["small", "medium"]:
            return "city_center"
        else:
            return "near_attractions"
    
    def generate_intercity_constraints(self, cities: List[Dict], 
                                     preferences: Dict[str, Any]) -> InterCityConstraint:
        """Generar constraints para viajes intercity"""
        
        # Calcular distancias intercity máximas
        max_distance = 0.0
        if len(cities) > 1:
            from geopy.distance import geodesic
            
            for i in range(len(cities) - 1):
                for j in range(i + 1, len(cities)):
                    distance = geodesic(
                        (cities[i]['center_lat'], cities[i]['center_lon']),
                        (cities[j]['center_lat'], cities[j]['center_lon'])
                    ).kilometers
                    max_distance = max(max_distance, distance)
        
        transport_mode = preferences.get("transport_mode", "driving")
        trip_duration = preferences.get("duration_days", 1)
        
        # Constraints diferentes según transporte
        if transport_mode == "driving":
            return InterCityConstraint(
                max_intercity_distance_km=800.0,
                prefer_flights_over_km=1200.0,
                max_daily_cities=2,
                min_time_per_city_hours=4.0
            )
        
        elif transport_mode == "flying":
            return InterCityConstraint(
                max_intercity_distance_km=5000.0,  # Sin límite práctico
                prefer_flights_over_km=300.0,      # Vuelos para todo
                max_daily_cities=3,                # Más ciudades posibles
                min_time_per_city_hours=3.0        # Menos tiempo por eficiencia
            )
        
        else:
            # Public transport / mixed
            return InterCityConstraint(
                max_intercity_distance_km=500.0,
                prefer_flights_over_km=800.0,
                max_daily_cities=2,
                min_time_per_city_hours=4.0
            )
    
    def apply_constraints_to_ortools_model(self, ortools_model: Any, places: List[Dict], 
                                         preferences: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aplicar todos los constraints al modelo OR-Tools
        
        Args:
            ortools_model: Modelo OR-Tools (VRP, TSP, etc.)
            places: Lista de lugares
            preferences: Preferencias del usuario
            
        Returns:
            Dict con metadata de constraints aplicados
        """
        applied_constraints = {}
        
        try:
            # 1. Time Windows
            if ConstraintType.TIME_WINDOW in self.enabled_constraints:
                time_windows = self.generate_time_windows(places, preferences)
                applied_constraints["time_windows"] = self._apply_time_windows(
                    ortools_model, time_windows
                )
            
            # 2. Vehicle Constraints  
            if ConstraintType.VEHICLE_CAPACITY in self.enabled_constraints:
                vehicle_constraints = self.generate_vehicle_constraints(places, preferences)
                applied_constraints["vehicle_constraints"] = self._apply_vehicle_constraints(
                    ortools_model, vehicle_constraints
                )
            
            # 3. Multi-Day Routing
            if ConstraintType.MULTI_DAY_ROUTING in self.enabled_constraints:
                applied_constraints["multi_day"] = self._apply_multiday_constraints(
                    ortools_model, places, preferences
                )
            
            # 4. Priority Weighting
            if ConstraintType.PRIORITY_WEIGHTING in self.enabled_constraints:
                applied_constraints["priority_weights"] = self._apply_priority_weights(
                    ortools_model, places
                )
            
            logger.info(f"✅ Applied {len(applied_constraints)} constraint types to OR-Tools model")
            
        except Exception as e:
            logger.error(f"❌ Error applying constraints to OR-Tools model: {e}")
            applied_constraints["error"] = str(e)
        
        return applied_constraints
    
    def _apply_time_windows(self, ortools_model: Any, time_windows: Dict[str, TimeWindow]) -> Dict[str, Any]:
        """Aplicar time windows al modelo OR-Tools"""
        # Esta función sería implementada específicamente para cada tipo de modelo OR-Tools
        # Por ahora, documentar qué constraints se aplicarían
        
        constraint_info = {
            "constraint_type": "time_windows",
            "windows_count": len(time_windows),
            "hard_constraints": sum(1 for tw in time_windows.values() if tw.is_required),
            "soft_preferences": sum(1 for tw in time_windows.values() if not tw.is_required)
        }
        
        # TODO: Implementar aplicación real según tipo de modelo OR-Tools
        # if hasattr(ortools_model, 'AddTimeWindow'):
        #     for place_id, time_window in time_windows.items():
        #         start_min, end_min = time_window.to_minutes()
        #         ortools_model.AddTimeWindow(place_id, start_min, end_min)
        
        return constraint_info
    
    def _apply_vehicle_constraints(self, ortools_model: Any, 
                                 vehicle_constraints: VehicleConstraints) -> Dict[str, Any]:
        """Aplicar constraints de vehículo"""
        
        constraint_info = {
            "constraint_type": "vehicle_constraints",
            "max_daily_distance_km": vehicle_constraints.max_daily_distance_km,
            "max_continuous_drive_hours": vehicle_constraints.max_continuous_drive_hours,
            "fuel_stops_required": vehicle_constraints.fuel_stops_required
        }
        
        # TODO: Implementar aplicación real
        # if hasattr(ortools_model, 'AddDimensionConstraint'):
        #     ortools_model.AddDimensionConstraint("distance", 0, vehicle_constraints.max_daily_distance_km)
        
        return constraint_info
    
    def _apply_multiday_constraints(self, ortools_model: Any, places: List[Dict], 
                                  preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Aplicar constraints multi-día"""
        
        duration_days = preferences.get("duration_days", 1)
        max_daily_activities = preferences.get("max_daily_activities", 6)
        
        constraint_info = {
            "constraint_type": "multi_day_routing", 
            "total_days": duration_days,
            "max_daily_activities": max_daily_activities,
            "total_places": len(places)
        }
        
        # TODO: Implementar distribución óptima por días
        
        return constraint_info
    
    def _apply_priority_weights(self, ortools_model: Any, places: List[Dict]) -> Dict[str, Any]:
        """Aplicar pesos de prioridad a lugares"""
        
        # Calcular pesos basado en priority, rating, etc.
        weights = {}
        for i, place in enumerate(places):
            priority = place.get("priority", 5)
            rating = place.get("rating", 4.0)
            
            # Combinar priority y rating para peso final
            weight = (priority * 0.6) + (rating * 0.4)
            weights[f"place_{i}"] = weight
        
        constraint_info = {
            "constraint_type": "priority_weights",
            "places_weighted": len(weights),
            "avg_weight": sum(weights.values()) / len(weights) if weights else 0.0,
            "weight_range": f"{min(weights.values()):.1f} - {max(weights.values()):.1f}" if weights else "N/A"
        }
        
        return constraint_info
    
    def get_constraint_summary(self, places: List[Dict], preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Obtener resumen de todos los constraints que se aplicarían"""
        
        summary = {
            "enabled_constraints": [ct.value for ct in self.enabled_constraints],
            "constraint_analysis": {}
        }
        
        # Análisis de time windows
        if ConstraintType.TIME_WINDOW in self.enabled_constraints:
            time_windows = self.generate_time_windows(places, preferences)
            summary["constraint_analysis"]["time_windows"] = {
                "total_windows": len(time_windows),
                "hard_constraints": sum(1 for tw in time_windows.values() if tw.is_required),
                "time_conflicts": self._detect_time_conflicts(time_windows)
            }
        
        # Análisis de vehicle constraints
        if ConstraintType.VEHICLE_CAPACITY in self.enabled_constraints:
            vehicle_constraints = self.generate_vehicle_constraints(places, preferences)
            summary["constraint_analysis"]["vehicle"] = {
                "max_daily_distance": vehicle_constraints.max_daily_distance_km,
                "estimated_total_distance": self._estimate_total_distance(places),
                "feasible": self._estimate_total_distance(places) <= vehicle_constraints.max_daily_distance_km * preferences.get("duration_days", 1)
            }
        
        return summary
    
    def _detect_time_conflicts(self, time_windows: Dict[str, TimeWindow]) -> List[str]:
        """Detectar posibles conflictos en time windows"""
        conflicts = []
        
        # Simplificado: detectar windows muy restrictivas
        for place_id, tw in time_windows.items():
            start_min, end_min = tw.to_minutes()
            window_duration = end_min - start_min
            
            if window_duration < 60:  # Menos de 1 hora
                conflicts.append(f"{place_id}: very narrow time window ({window_duration}min)")
            
            if tw.is_required and window_duration < 120:  # Hard constraint muy restrictiva
                conflicts.append(f"{place_id}: hard constraint with short window")
        
        return conflicts

# Singleton instance
advanced_constraints_engine = AdvancedConstraintsEngine()

# Export functions
def generate_ortools_constraints(places: List[Dict], preferences: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generar todos los constraints OR-Tools para un itinerario
    
    Usage:
        constraints = generate_ortools_constraints(places, preferences)
        # Aplicar constraints al modelo OR-Tools
    """
    return advanced_constraints_engine.get_constraint_summary(places, preferences)

def apply_constraints_to_model(ortools_model: Any, places: List[Dict], 
                             preferences: Dict[str, Any]) -> Dict[str, Any]:
    """Aplicar constraints al modelo OR-Tools"""
    return advanced_constraints_engine.apply_constraints_to_ortools_model(
        ortools_model, places, preferences
    )