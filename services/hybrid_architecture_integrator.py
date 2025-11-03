#!/usr/bin/env python3
"""
🏗️ Arquitectura Híbrida Profesional - Integrador Principal
Combina city2graph + OSRM + H3 + OR-Tools según recomendaciones
"""

import time
import logging
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import json
import sys

# Añadir path del proyecto
sys.path.append(str(Path(__file__).parent.parent))

from services.osrm_service import OSRMService, OSRMFactory
from services.h3_spatial_partitioner import H3SpatialPartitioner, RoutingSession
from services.ortools_professional_optimizer import ProfessionalItineraryOptimizer
from services.redis_od_cache import RedisODMatrixManager
from ultrafast_chile_routing import UltraFastChileRouting

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HybridArchitectureIntegrator:
    """
    Integrador de arquitectura híbrida profesional
    
    STACK IMPLEMENTADO:
    - City2Graph: Base de datos geoespacial y indexación
    - OSRM: Motor de ruteo profesional (<0.1s por consulta)
    - H3: Particionado espacial y clustering automático
    - Cache inteligente: Matriz OD con TTL
    """
    
    def __init__(self):
        """Inicializa todos los componentes del stack"""
        logger.info("🏗️ Inicializando Arquitectura Híbrida Profesional...")
        
        # Componente 1: City2Graph (base de datos)
        self.city2graph = None
        self._initialize_city2graph()
        
        # Componente 2: H3 Partitioner (clustering)
        self.h3_partitioner = H3SpatialPartitioner(resolution=5)
        
        # Componente 3: OSRM Services (routing profesional)
        self.osrm_car = OSRMFactory.create_car_service()
        self.osrm_foot = OSRMFactory.create_foot_service()
        
        # Componente 4: OR-Tools Optimizer (TSP/VRP profesional)
        self.ortools_optimizer = ProfessionalItineraryOptimizer()
        
        # Componente 5: Redis Cache Manager (cache persistente matriz OD)
        self.redis_cache_manager = RedisODMatrixManager()
        
        # Fallback cache en memoria (si Redis no disponible)
        self.od_matrix_cache = {}
        self.cache_ttl = 3600  # 1 hora
        
        logger.info("✅ Arquitectura híbrida inicializada")
    
    def _initialize_city2graph(self):
        """Inicializa componente city2graph como base de datos"""
        try:
            logger.info("📊 Inicializando base de datos city2graph...")
            self.city2graph = UltraFastChileRouting()
            logger.info("✅ City2graph cargado como base geoespacial")
        except Exception as e:
            logger.warning(f"⚠️ City2graph no disponible: {e}")
            logger.info("💡 Continuando con OSRM puro...")
    
    def setup_routing_engine(self) -> bool:
        """
        Configura el motor de ruteo OSRM según recomendaciones
        
        Returns:
            True si el setup fue exitoso
        """
        logger.info("🔧 Configurando motor de ruteo profesional...")
        
        # Setup OSRM car profile (principal)
        if not self.osrm_car.setup_osrm_data():
            logger.error("❌ Error en setup OSRM car")
            return False
        
        if not self.osrm_car.start_server():
            logger.error("❌ Error iniciando servidor OSRM car")
            return False
        
        logger.info("✅ Motor de ruteo profesional configurado")
        return True
    
    def analyze_routing_request(self, pois: List[Dict]) -> RoutingSession:
        """
        Analiza una solicitud de ruteo y crea sesión optimizada
        
        Args:
            pois: Lista de POIs con lat/lon
            
        Returns:
            Sesión de routing con clustering automático
        """
        logger.info(f"🔍 Analizando solicitud: {len(pois)} POIs")
        
        # Usar H3 para clustering automático
        session = self.h3_partitioner.cluster_pois_auto(pois)
        
        # Detectar ciudades principales
        cities = self.h3_partitioner.detect_cities_from_pois(pois)
        
        logger.info(f"📊 Análisis completado:")
        logger.info(f"   Sesión ID: {session.session_id}")
        logger.info(f"   Clusters H3: {len(session.clusters)}")
        logger.info(f"   Ciudades detectadas: {list(cities.keys())}")
        logger.info(f"   Área total: {session.estimated_area_km2:.1f}km²")
        
        return session
    
    def calculate_od_matrix_hybrid(self, session: RoutingSession, mode: str = "car") -> Dict:
        """
        Calcula matriz origen-destino usando estrategia híbrida
        
        Args:
            session: Sesión de routing
            mode: Modo de transporte (car, foot)
            
        Returns:
            Matriz de distancias y tiempos
        """
        logger.info(f"📐 Calculando matriz OD híbrida - Modo: {mode}")
        
        # Extraer coordenadas
        coordinates = [(poi['lat'], poi['lon']) for poi in session.pois]
        
        # Inicializar variables
        strategy_used = 'UNKNOWN'
        cache_key = f"od_{session.session_id}_{mode}"
        matrix_result = None
        
        # Intentar Redis cache primero, luego cache en memoria
        def calculate_matrix_func(coords):
            return self._calculate_matrix_with_fallback(coords, mode)
        
        # Usar Redis cache manager con fallback automático
        if self.redis_cache_manager.is_healthy():
            matrix_result = self.redis_cache_manager.get_or_calculate_matrix(
                coordinates=coordinates,
                mode=mode,
                h3_cluster=session.main_cluster,
                calculation_func=calculate_matrix_func
            )
            if matrix_result:
                strategy_used = matrix_result.get('strategy', 'REDIS_CACHED')
                logger.info(f"💾 Matriz OD desde Redis cache: {strategy_used}")
        else:
            # Fallback a cache en memoria
            if cache_key in self.od_matrix_cache:
                cached_result = self.od_matrix_cache[cache_key]
                if time.time() - cached_result['timestamp'] < self.cache_ttl:
                    logger.info("💾 Matriz OD desde cache memoria (Redis no disponible)")
                    return cached_result['data']
            
            matrix_result = calculate_matrix_func(coordinates)
            strategy_used = 'MEMORY_FALLBACK'
        
        if not matrix_result:
            raise Exception("❌ Todos los motores de ruteo fallaron")
        
        # Enriquecer con metadatos
        enhanced_result = {
            **matrix_result,
            'strategy': strategy_used,
            'session_id': session.session_id,
            'poi_count': len(session.pois),
            'calculated_at': time.time()
        }
        
        # Cachear resultado
        self.od_matrix_cache[cache_key] = {
            'data': enhanced_result,
            'timestamp': time.time()
        }
        
        logger.info(f"✅ Matriz OD calculada: {strategy_used}")
        return enhanced_result
    
    def _is_osrm_available(self, mode: str) -> bool:
        """Verifica si OSRM está disponible para el modo dado"""
        try:
            osrm_service = self.osrm_car if mode == "car" else self.osrm_foot
            return osrm_service.health_check()
        except:
            return False
    
    def _calculate_city2graph_matrix(self, coordinates: List[Tuple[float, float]]) -> Dict:
        """
        Calcula matriz OD usando city2graph como fallback
        
        Args:
            coordinates: Lista de (lat, lon)
            
        Returns:
            Matriz en formato compatible con OSRM
        """
        if not self.city2graph:
            raise Exception("City2graph no disponible")
        
        n = len(coordinates)
        distances = [[0.0] * n for _ in range(n)]
        durations = [[0.0] * n for _ in range(n)]
        
        start_time = time.time()
        
        # Calcular todas las rutas
        for i in range(n):
            for j in range(n):
                if i != j:
                    try:
                        route_result = self.city2graph.route_between_coordinates(
                            coordinates[i], coordinates[j]
                        )
                        if route_result and route_result['success']:
                            distances[i][j] = route_result.get('distance_km', 0) * 1000  # convertir a metros
                            # Estimar tiempo basándose en distancia (50km/h promedio)
                            durations[i][j] = (route_result.get('distance_km', 0) / 50.0) * 3600
                        else:
                            distances[i][j] = float('inf')
                            durations[i][j] = float('inf')
                    except:
                        distances[i][j] = float('inf')
                        durations[i][j] = float('inf')
        
        query_time = time.time() - start_time
        
        return {
            'distances': distances,
            'durations': durations,
            'query_time_s': query_time,
            'sources': [{'location': [lon, lat]} for lat, lon in coordinates],
            'destinations': [{'location': [lon, lat]} for lat, lon in coordinates]
        }
    
    def optimize_itinerary_professional(self, pois: List[Dict], mode: str = "car") -> Dict:
        """
        Optimización de itinerario usando stack profesional completo
        
        Args:
            pois: Lista de POIs con información completa
            mode: Modo de transporte
            
        Returns:
            Itinerario optimizado con metadatos completos
        """
        logger.info(f"🎯 Optimización profesional: {len(pois)} POIs")
        
        start_time = time.time()
        
        # Paso 1: Análisis espacial con H3
        session = self.analyze_routing_request(pois)
        
        # Paso 2: Cálculo de matriz OD híbrida
        od_matrix = self.calculate_od_matrix_hybrid(session, mode)
        
        # Paso 3: Optimización TSP profesional con OR-Tools
        optimized_route = self._optimize_tsp_professional(pois, od_matrix, mode)
        
        # Paso 4: Post-procesamiento
        total_time = time.time() - start_time
        
        result = {
            'success': True,
            'session': session,
            'od_matrix_strategy': od_matrix.get('strategy'),
            'optimized_route': optimized_route,
            'performance': {
                'total_time_s': total_time,
                'od_calculation_time_s': od_matrix.get('query_time_s'),
                'pois_processed': len(pois),
                'clusters_analyzed': len(session.clusters)
            },
            'metadata': {
                'architecture': 'HYBRID_PROFESSIONAL',
                'components_used': [
                    'H3_SPATIAL_PARTITIONER',
                    od_matrix.get('strategy', 'UNKNOWN'),
                    optimized_route.get('algorithm_used', 'OR_TOOLS_PROFESSIONAL')
                ],
                'area_covered_km2': session.estimated_area_km2,
                'cities_detected': len(self.h3_partitioner.detect_cities_from_pois(pois))
            }
        }
        
        logger.info(f"✅ Optimización completada en {total_time:.3f}s")
        logger.info(f"   Estrategia: {od_matrix.get('strategy')}")
        logger.info(f"   Componentes: {len(result['metadata']['components_used'])}")
        
        return result
    
    def _optimize_tsp_basic(self, od_matrix: Dict) -> Dict:
        """
        Optimización TSP básica (será reemplazada por OR-Tools)
        
        Args:
            od_matrix: Matriz de distancias/tiempos
            
        Returns:
            Ruta optimizada
        """
        distances = od_matrix['distances']
        n = len(distances)
        
        if n <= 1:
            return {'route': [0], 'total_distance': 0, 'total_time': 0}
        
        # TSP básico con nearest neighbor
        unvisited = set(range(1, n))
        route = [0]
        current = 0
        total_distance = 0
        total_time = 0
        
        while unvisited:
            nearest = min(unvisited, key=lambda x: distances[current][x])
            route.append(nearest)
            total_distance += distances[current][nearest]
            total_time += od_matrix['durations'][current][nearest]
            current = nearest
            unvisited.remove(nearest)
        
        # Validar y limpiar valores numéricos
        import math
        def clean_numeric_value(value, default=0.0):
            if value is None or math.isnan(value) or math.isinf(value):
                return default
            return value
        
        return {
            'route': route,
            'total_distance_m': clean_numeric_value(total_distance, 0.0),
            'total_time_s': clean_numeric_value(total_time, 0.0),
            'algorithm': 'NEAREST_NEIGHBOR_BASIC'
        }
    
    def _optimize_tsp_professional(self, pois: List[Dict], od_matrix: Dict, mode: str) -> Dict:
        """
        Optimización TSP profesional usando OR-Tools
        
        Args:
            pois: Lista de POIs originales
            od_matrix: Matriz de distancias/tiempos de OSRM
            mode: Modo de transporte
            
        Returns:
            Resultado de optimización profesional
        """
        try:
            logger.info(f"🧮 Optimización OR-Tools profesional: {len(pois)} POIs")
            
            # Decidir si usar restricciones temporales
            has_time_constraints = any(
                poi.get('opening_hour') or poi.get('closing_hour') or poi.get('duration_minutes')
                for poi in pois
            )
            
            # Optimizar con OR-Tools
            result = self.ortools_optimizer.optimize_itinerary_advanced(
                pois=pois,
                distance_matrix=od_matrix,
                use_time_windows=has_time_constraints,
                start_time="09:00"
            )
            
            if result['success']:
                logger.info(f"✅ OR-Tools optimización exitosa: {result['algorithm_used']}")
                
                # Validar y limpiar valores numéricos
                def clean_numeric_value(value, default=0.0):
                    import math
                    if value is None or math.isnan(value) or math.isinf(value):
                        return default
                    return value
                
                return {
                    'route': result['optimized_route'],
                    'total_distance_m': clean_numeric_value(result['total_distance_km'] * 1000, 0.0),
                    'total_time_s': clean_numeric_value(result['total_time_minutes'] * 60, 0.0),
                    'algorithm_used': result['algorithm_used'],
                    'optimization_time_s': clean_numeric_value(result['optimization_time_s'], 0.0),
                    'constraints_satisfied': result['constraints_satisfied'],
                    'dropped_pois': result.get('dropped_pois', []),
                    'performance_metrics': result.get('performance_metrics', {})
                }
            else:
                logger.warning("⚠️ OR-Tools falló, usando fallback básico")
                return self._optimize_tsp_basic(od_matrix)
                
        except Exception as e:
            logger.error(f"❌ Error en OR-Tools: {e}")
            logger.info("🔄 Fallback a TSP básico")
            return self._optimize_tsp_basic(od_matrix)
    
    def _calculate_matrix_with_fallback(self, coordinates: List[Tuple[float, float]], mode: str) -> Dict:
        """
        Calcula matriz OD con estrategia de fallback híbrida
        
        Args:
            coordinates: Lista de (lat, lon)
            mode: Modo de transporte
            
        Returns:
            Matriz OD con estrategia utilizada
        """
        # Estrategia híbrida: OSRM primero, city2graph como fallback
        matrix_result = None
        strategy_used = None
        
        # Intentar OSRM (recomendado para producción)
        if self._is_osrm_available(mode):
            try:
                osrm_service = self.osrm_car if mode == "car" else self.osrm_foot
                matrix_result = osrm_service.distance_matrix(coordinates)
                strategy_used = "OSRM_PROFESSIONAL"
                logger.info("🚗 Matriz OD calculada con OSRM profesional")
            except Exception as e:
                logger.warning(f"⚠️ OSRM falló: {e}")
        
        # Fallback a city2graph si OSRM no disponible
        if not matrix_result and self.city2graph:
            try:
                matrix_result = self._calculate_city2graph_matrix(coordinates)
                strategy_used = "CITY2GRAPH_FALLBACK"
                logger.info("📊 Matriz OD calculada con city2graph (fallback)")
            except Exception as e:
                logger.warning(f"⚠️ City2graph falló: {e}")
        
        if matrix_result:
            matrix_result['strategy'] = strategy_used
        
        return matrix_result
    
    def shutdown(self):
        """Cierra todos los servicios y muestra estadísticas finales"""
        logger.info("🛑 Cerrando arquitectura híbrida...")
        
        try:
            # Mostrar estadísticas finales de Redis
            if self.redis_cache_manager.is_healthy():
                stats = self.redis_cache_manager.get_stats()
                logger.info(f"📊 Stats Redis finales: {stats.get('goveling_keys_count', 0)} keys, {stats.get('hit_rate', 0):.1f}% hit rate")
            
            if self.osrm_car:
                self.osrm_car.stop_server()
            if self.osrm_foot:
                self.osrm_foot.stop_server()
        except Exception as e:
            logger.warning(f"⚠️ Error cerrando servicios: {e}")
        
        logger.info("✅ Arquitectura híbrida cerrada")

if __name__ == "__main__":
    """Test de la arquitectura híbrida completa"""
    
    print("🏗️ TESTING ARQUITECTURA HÍBRIDA PROFESIONAL")
    print("=" * 60)
    
    # Crear integrador
    integrator = HybridArchitectureIntegrator()
    
    # POIs de prueba
    test_pois = [
        {"name": "BLACK ANTOFAGASTA", "lat": -23.6509, "lon": -70.3975, "rating": 4.2},
        {"name": "La Franchuteria", "lat": -23.6400, "lon": -70.4100, "rating": 4.4},
        {"name": "McDonald's Antofagasta", "lat": -23.6600, "lon": -70.3800, "rating": 3.8}
    ]
    
    try:
        # Test sin OSRM (solo con componentes disponibles)
        logger.info("🧪 Testing con componentes disponibles...")
        
        result = integrator.optimize_itinerary_professional(test_pois)
        
        print(f"\n✅ RESULTADO ARQUITECTURA HÍBRIDA:")
        print(f"   Éxito: {result['success']}")
        print(f"   Tiempo total: {result['performance']['total_time_s']:.3f}s")
        print(f"   Estrategia OD: {result['od_matrix_strategy']}")
        print(f"   Componentes: {result['metadata']['components_used']}")
        print(f"   Área cubierta: {result['metadata']['area_covered_km2']:.1f}km²")
        print(f"   Ciudades detectadas: {result['metadata']['cities_detected']}")
        
        # Mostrar ruta optimizada
        route = result['optimized_route']
        print(f"\n🗺️ RUTA OPTIMIZADA:")
        print(f"   Orden: {route['route']}")
        print(f"   Distancia total: {route.get('total_distance_m', 0)/1000:.1f}km")
        print(f"   Tiempo total: {route.get('total_time_s', 0)/60:.1f}min")
        
    except Exception as e:
        print(f"❌ Error en test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        integrator.shutdown()
    
    print(f"\n🎯 PRÓXIMOS PASOS:")
    print(f"   1. Completar setup OSRM para routing <0.1s")
    print(f"   2. Implementar OR-Tools para TSP profesional")
    print(f"   3. Añadir cache Redis para matriz OD")
    print(f"   4. Integrar con API FastAPI")