#!/usr/bin/env python3
"""
🧮 OR-Tools Professional TSP/VRP Solver
Implementa optimización avanzada según recomendaciones profesionales
"""

import time
import logging
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
import numpy as np

# OR-Tools imports
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class POI:
    """Point of Interest con metadatos completos"""
    id: int
    name: str
    lat: float
    lon: float
    rating: Optional[float] = None
    category: Optional[str] = None
    duration_minutes: int = 60  # Tiempo de visita por defecto
    opening_hour: int = 9       # Hora apertura (24h format)
    closing_hour: int = 18      # Hora cierre (24h format)
    is_mandatory: bool = True   # Must-visit vs optional
    priority: int = 1           # 1=alta, 2=media, 3=baja

@dataclass
class TimeWindow:
    """Ventana de tiempo para restricciones horarias"""
    start_minutes: int  # Minutos desde medianoche
    end_minutes: int    # Minutos desde medianoche
    
    @classmethod
    def from_hours(cls, start_hour: int, end_hour: int) -> 'TimeWindow':
        """Crear ventana desde horas (ej: 9:00-18:00)"""
        return cls(
            start_minutes=start_hour * 60,
            end_minutes=end_hour * 60
        )

@dataclass
class OptimizationResult:
    """Resultado de optimización TSP/VRP"""
    success: bool
    route: List[int]  # Orden de visita (indices POI)
    total_distance_m: float
    total_time_minutes: float
    optimization_time_s: float
    algorithm_used: str
    constraints_satisfied: bool
    dropped_pois: List[int] = None  # POIs que no se pudieron incluir
    
class ORToolsTSPSolver:
    """
    Solver TSP/VRP profesional usando OR-Tools
    Implementa VRPTW (Vehicle Routing Problem with Time Windows)
    """
    
    def __init__(self):
        """Inicializa solver OR-Tools"""
        logger.info("🧮 OR-Tools TSP Solver iniciado")
        self.manager = None
        self.routing = None
        self.solution = None
    
    def solve_tsp_basic(self, distance_matrix: List[List[float]]) -> OptimizationResult:
        """
        Resuelve TSP básico sin restricciones temporales
        
        Args:
            distance_matrix: Matriz NxN de distancias en metros
            
        Returns:
            Resultado de optimización
        """
        logger.info(f"🔄 Resolviendo TSP básico: {len(distance_matrix)}x{len(distance_matrix)} matriz")
        
        start_time = time.time()
        
        try:
            # Crear manager y modelo de routing
            self.manager = pywrapcp.RoutingIndexManager(
                len(distance_matrix),  # Número de nodos
                1,                    # Número de vehículos
                0                     # Depósito (inicio/fin)
            )
            
            self.routing = pywrapcp.RoutingModel(self.manager)
            
            # Función de distancia
            def distance_callback(from_index, to_index):
                from_node = self.manager.IndexToNode(from_index)
                to_node = self.manager.IndexToNode(to_index)
                return int(distance_matrix[from_node][to_node])
            
            transit_callback_index = self.routing.RegisterTransitCallback(distance_callback)
            self.routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
            
            # Configurar parámetros de búsqueda
            search_parameters = pywrapcp.DefaultRoutingSearchParameters()
            search_parameters.first_solution_strategy = (
                routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
            )
            search_parameters.local_search_metaheuristic = (
                routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
            )
            search_parameters.time_limit.FromSeconds(1)  # Límite 1 segundo (ultrarrápido)
            
            # Resolver
            solution = self.routing.SolveWithParameters(search_parameters)
            optimization_time = time.time() - start_time
            
            if solution:
                return self._extract_solution_basic(solution, distance_matrix, optimization_time)
            else:
                logger.error("❌ OR-Tools no encontró solución")
                return OptimizationResult(
                    success=False,
                    route=[],
                    total_distance_m=0.0,
                    total_time_minutes=0.0,
                    optimization_time_s=optimization_time,
                    algorithm_used="OR_TOOLS_TSP_FAILED",
                    constraints_satisfied=False
                )
                
        except Exception as e:
            logger.error(f"❌ Error en OR-Tools TSP: {e}")
            return OptimizationResult(
                success=False,
                route=[],
                total_distance_m=0.0,
                total_time_minutes=0.0,
                optimization_time_s=time.time() - start_time,
                algorithm_used="OR_TOOLS_ERROR",
                constraints_satisfied=False
            )
    
    def solve_vrptw(self, 
                    distance_matrix: List[List[float]], 
                    time_matrix: List[List[float]],
                    pois: List[POI],
                    start_time_minutes: int = 540) -> OptimizationResult:
        """
        Resuelve VRPTW (Vehicle Routing with Time Windows)
        
        Args:
            distance_matrix: Matriz de distancias (metros)
            time_matrix: Matriz de tiempos (minutos)
            pois: Lista de POIs con restricciones temporales
            start_time_minutes: Hora inicio del tour (540 = 9:00 AM)
            
        Returns:
            Resultado de optimización avanzada
        """
        logger.info(f"🔄 Resolviendo VRPTW: {len(pois)} POIs con ventanas de tiempo")
        
        start_time = time.time()
        
        try:
            # Crear manager y modelo
            self.manager = pywrapcp.RoutingIndexManager(
                len(pois), 1, 0
            )
            self.routing = pywrapcp.RoutingModel(self.manager)
            
            # Callback de distancia
            def distance_callback(from_index, to_index):
                from_node = self.manager.IndexToNode(from_index)
                to_node = self.manager.IndexToNode(to_index)
                return int(distance_matrix[from_node][to_node])
            
            transit_callback_index = self.routing.RegisterTransitCallback(distance_callback)
            self.routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
            
            # Callback de tiempo
            def time_callback(from_index, to_index):
                from_node = self.manager.IndexToNode(from_index)
                to_node = self.manager.IndexToNode(to_index)
                travel_time = int(time_matrix[from_node][to_node])
                service_time = pois[from_node].duration_minutes if from_node < len(pois) else 0
                return travel_time + service_time
            
            time_callback_index = self.routing.RegisterTransitCallback(time_callback)
            
            # Dimensión de tiempo
            time_dimension_name = 'Time'
            self.routing.AddDimension(
                time_callback_index,
                60,  # Slack máximo (buffer tiempo)
                1440,  # Capacidad máxima (24 horas)
                False,  # Fix start cumul to zero
                time_dimension_name
            )
            time_dimension = self.routing.GetDimensionOrDie(time_dimension_name)
            
            # Agregar ventanas de tiempo para cada POI
            for poi_idx, poi in enumerate(pois):
                if poi_idx == 0:  # Depósito (punto inicial)
                    time_dimension.CumulVar(self.manager.NodeToIndex(poi_idx)).SetRange(
                        start_time_minutes, start_time_minutes + 600  # 10 horas máximo
                    )
                else:
                    # Ventana de tiempo del POI
                    window_start = poi.opening_hour * 60
                    window_end = poi.closing_hour * 60
                    
                    time_dimension.CumulVar(self.manager.NodeToIndex(poi_idx)).SetRange(
                        window_start, window_end
                    )
            
            # Restricciones de prioridad para POIs obligatorios
            for poi_idx, poi in enumerate(pois):
                if poi.is_mandatory and poi_idx > 0:  # No aplicar al depósito
                    self.routing.AddDisjunction([self.manager.NodeToIndex(poi_idx)], 10000)
            
            # Configurar búsqueda
            search_parameters = pywrapcp.DefaultRoutingSearchParameters()
            search_parameters.first_solution_strategy = (
                routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
            )
            search_parameters.local_search_metaheuristic = (
                routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
            )
            search_parameters.time_limit.FromSeconds(2)  # 2 segundos límite (ultrarrápido)
            
            # Resolver
            solution = self.routing.SolveWithParameters(search_parameters)
            optimization_time = time.time() - start_time
            
            if solution:
                return self._extract_solution_vrptw(solution, distance_matrix, time_matrix, pois, optimization_time)
            else:
                logger.warning("⚠️ VRPTW no encontró solución, fallback a TSP básico")
                # Fallback a TSP básico
                return self.solve_tsp_basic(distance_matrix)
                
        except Exception as e:
            logger.error(f"❌ Error en VRPTW: {e}")
            # Fallback a TSP básico
            return self.solve_tsp_basic(distance_matrix)
    
    def _extract_solution_basic(self, 
                               solution, 
                               distance_matrix: List[List[float]], 
                               optimization_time: float) -> OptimizationResult:
        """Extrae solución de TSP básico"""
        
        route = []
        total_distance = 0
        
        index = self.routing.Start(0)
        while not self.routing.IsEnd(index):
            node = self.manager.IndexToNode(index)
            route.append(node)
            previous_index = index
            index = solution.Value(self.routing.NextVar(index))
            if not self.routing.IsEnd(index):
                from_node = self.manager.IndexToNode(previous_index)
                to_node = self.manager.IndexToNode(index)
                total_distance += distance_matrix[from_node][to_node]
        
        # Estimar tiempo (50 km/h promedio + 60 min por POI)
        estimated_time = (total_distance / 1000 / 50) * 60 + len(route) * 60
        
        logger.info(f"✅ TSP resuelto: {len(route)} POIs, {total_distance/1000:.1f}km")
        
        return OptimizationResult(
            success=True,
            route=route,
            total_distance_m=total_distance,
            total_time_minutes=estimated_time,
            optimization_time_s=optimization_time,
            algorithm_used="OR_TOOLS_TSP_BASIC",
            constraints_satisfied=True
        )
    
    def _extract_solution_vrptw(self, 
                               solution,
                               distance_matrix: List[List[float]],
                               time_matrix: List[List[float]],
                               pois: List[POI],
                               optimization_time: float) -> OptimizationResult:
        """Extrae solución de VRPTW con ventanas de tiempo"""
        
        route = []
        total_distance = 0
        total_time = 0
        dropped_pois = []
        
        # Extraer ruta del vehículo 0
        index = self.routing.Start(0)
        time_dimension = self.routing.GetDimensionOrDie('Time')
        
        while not self.routing.IsEnd(index):
            node = self.manager.IndexToNode(index)
            route.append(node)
            
            # Calcular tiempo acumulado
            time_var = time_dimension.CumulVar(index)
            total_time = solution.Value(time_var)
            
            previous_index = index
            index = solution.Value(self.routing.NextVar(index))
            
            # Calcular distancia
            if not self.routing.IsEnd(index):
                from_node = self.manager.IndexToNode(previous_index)
                to_node = self.manager.IndexToNode(index)
                total_distance += distance_matrix[from_node][to_node]
        
        # Identificar POIs que no fueron incluidos
        all_nodes = set(range(len(pois)))
        visited_nodes = set(route)
        dropped_pois = list(all_nodes - visited_nodes)
        
        constraints_ok = len(dropped_pois) == 0
        
        logger.info(f"✅ VRPTW resuelto: {len(route)} POIs visitados, {len(dropped_pois)} omitidos")
        
        return OptimizationResult(
            success=True,
            route=route,
            total_distance_m=total_distance,
            total_time_minutes=total_time,
            optimization_time_s=optimization_time,
            algorithm_used="OR_TOOLS_VRPTW",
            constraints_satisfied=constraints_ok,
            dropped_pois=dropped_pois
        )

class ProfessionalItineraryOptimizer:
    """
    Optimizador de itinerarios profesional que combina OR-Tools + OSRM
    """
    
    def __init__(self):
        """Inicializa optimizador profesional"""
        self.tsp_solver = ORToolsTSPSolver()
        logger.info("🏗️ Professional Itinerary Optimizer iniciado")
    
    def optimize_itinerary_advanced(self,
                                   pois: List[Dict],
                                   distance_matrix: Dict,
                                   use_time_windows: bool = False,
                                   start_time: str = "09:00") -> Dict:
        """
        Optimización avanzada de itinerario
        
        Args:
            pois: Lista de POIs con metadatos
            distance_matrix: Resultado de OSRM con distancias/tiempos
            use_time_windows: Usar restricciones horarias VRPTW
            start_time: Hora inicio en formato "HH:MM"
            
        Returns:
            Itinerario optimizado con OR-Tools
        """
        logger.info(f"🎯 Optimización avanzada: {len(pois)} POIs")
        
        # Convertir POIs a objetos estructurados
        structured_pois = []
        for i, poi in enumerate(pois):
            structured_poi = POI(
                id=i,
                name=poi.get('name', f'POI_{i}'),
                lat=poi['lat'],
                lon=poi['lon'],
                rating=poi.get('rating'),
                category=poi.get('category'),
                duration_minutes=poi.get('duration_minutes', 60),
                opening_hour=poi.get('opening_hour', 9),
                closing_hour=poi.get('closing_hour', 18),
                is_mandatory=poi.get('is_mandatory', True),
                priority=poi.get('priority', 1)
            )
            structured_pois.append(structured_poi)
        
        # Extraer matrices
        distances = distance_matrix['distances']  # En metros
        durations = distance_matrix['durations']  # En segundos
        
        # Convertir tiempos a minutos
        time_matrix_minutes = [[duration / 60 for duration in row] for row in durations]
        
        # Decidir algoritmo según configuración
        if use_time_windows and len(structured_pois) > 1:
            # VRPTW con restricciones temporales
            start_minutes = self._parse_time_to_minutes(start_time)
            result = self.tsp_solver.solve_vrptw(
                distances, time_matrix_minutes, structured_pois, start_minutes
            )
        else:
            # TSP básico (más rápido)
            result = self.tsp_solver.solve_tsp_basic(distances)
        
        # Procesar resultado
        if result.success:
            optimized_pois = [pois[i] for i in result.route]
            
            return {
                'success': True,
                'optimized_route': result.route,
                'optimized_pois': optimized_pois,
                'total_distance_km': result.total_distance_m / 1000,
                'total_time_minutes': result.total_time_minutes,
                'optimization_time_s': result.optimization_time_s,
                'algorithm_used': result.algorithm_used,
                'constraints_satisfied': result.constraints_satisfied,
                'dropped_pois': result.dropped_pois or [],
                'performance_metrics': {
                    'pois_optimized': len(result.route),
                    'efficiency_gain': f"{len(pois) - len(result.dropped_pois or [])}/{len(pois)}",
                    'algorithm_speed': f"{result.optimization_time_s:.3f}s"
                }
            }
        else:
            return {
                'success': False,
                'error': 'Optimización falló',
                'fallback_route': list(range(len(pois))),
                'algorithm_used': result.algorithm_used
            }
    
    def _parse_time_to_minutes(self, time_str: str) -> int:
        """Convierte HH:MM a minutos desde medianoche"""
        hours, minutes = map(int, time_str.split(':'))
        return hours * 60 + minutes

if __name__ == "__main__":
    """Test del optimizador OR-Tools profesional"""
    
    print("🧮 TESTING OR-TOOLS PROFESSIONAL OPTIMIZER")
    print("=" * 60)
    
    # Crear optimizador
    optimizer = ProfessionalItineraryOptimizer()
    
    # Test POIs con restricciones
    test_pois = [
        {
            "name": "Hotel Start", "lat": -23.6509, "lon": -70.3975,
            "duration_minutes": 0, "opening_hour": 0, "closing_hour": 24,
            "is_mandatory": True, "priority": 1
        },
        {
            "name": "BLACK ANTOFAGASTA", "lat": -23.6509, "lon": -70.3975,
            "rating": 4.2, "duration_minutes": 90, "opening_hour": 11, "closing_hour": 23,
            "is_mandatory": True, "priority": 1, "category": "restaurant"
        },
        {
            "name": "La Franchuteria", "lat": -23.6400, "lon": -70.4100,
            "rating": 4.4, "duration_minutes": 120, "opening_hour": 10, "closing_hour": 22,
            "is_mandatory": True, "priority": 1, "category": "restaurant"
        },
        {
            "name": "McDonald's Antofagasta", "lat": -23.6600, "lon": -70.3800,
            "rating": 3.8, "duration_minutes": 45, "opening_hour": 6, "closing_hour": 24,
            "is_mandatory": False, "priority": 3, "category": "fast_food"
        }
    ]
    
    # Matriz de distancias simulada (en metros)
    distance_matrix = {
        'distances': [
            [0, 1000, 2000, 1500],
            [1000, 0, 1800, 800],
            [2000, 1800, 0, 2200],
            [1500, 800, 2200, 0]
        ],
        'durations': [  # En segundos
            [0, 180, 300, 240],
            [180, 0, 250, 150],
            [300, 250, 0, 320],
            [240, 150, 320, 0]
        ]
    }
    
    print(f"📊 Testing con {len(test_pois)} POIs")
    
    # Test TSP básico
    print(f"\n🔄 Test 1: TSP Básico (sin restricciones)")
    result_basic = optimizer.optimize_itinerary_advanced(
        test_pois, distance_matrix, use_time_windows=False
    )
    
    print(f"✅ Resultado TSP básico:")
    print(f"   Éxito: {result_basic['success']}")
    print(f"   Ruta: {result_basic.get('optimized_route', [])}")
    print(f"   Algoritmo: {result_basic.get('algorithm_used')}")
    print(f"   Tiempo optimización: {result_basic.get('optimization_time_s', 0):.3f}s")
    print(f"   Distancia total: {result_basic.get('total_distance_km', 0):.1f}km")
    
    # Test VRPTW avanzado
    print(f"\n🔄 Test 2: VRPTW (con ventanas de tiempo)")
    result_advanced = optimizer.optimize_itinerary_advanced(
        test_pois, distance_matrix, use_time_windows=True, start_time="09:00"
    )
    
    print(f"✅ Resultado VRPTW avanzado:")
    print(f"   Éxito: {result_advanced['success']}")
    print(f"   Ruta: {result_advanced.get('optimized_route', [])}")
    print(f"   Algoritmo: {result_advanced.get('algorithm_used')}")
    print(f"   Tiempo optimización: {result_advanced.get('optimization_time_s', 0):.3f}s")
    print(f"   Restricciones OK: {result_advanced.get('constraints_satisfied', False)}")
    print(f"   POIs omitidos: {len(result_advanced.get('dropped_pois', []))}")
    
    print(f"\n🎯 OR-Tools implementación completada")
    print(f"✅ Listo para integración con OSRM + H3")