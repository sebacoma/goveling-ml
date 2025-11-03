"""
🌍 CITY2GRAPH SERVICE - FASE 1
Servicio básico de grafos urbanos usando OSMnx para routing rápido
"""

import osmnx as ox
import networkx as nx
import geopandas as gpd
from typing import List, Dict, Tuple, Optional, Any
import logging
import time
import pickle
import os
from pathlib import Path
import hashlib

# Configurar OSMnx
ox.settings.log_console = False
ox.settings.use_cache = True

logger = logging.getLogger(__name__)

class City2GraphService:
    def __init__(self, cache_dir: str = "city2graph_cache"):
        """
        🏗️ Inicializar servicio City2graph
        """
        self.logger = logging.getLogger(__name__)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Cache en memoria para grafos
        self.graphs_cache = {}
        
        # Configuración de Chile
        self.chile_cities = {
            'santiago': {
                'bbox': (-33.40, -33.50, -70.60, -70.75),  # N, S, E, W - Área más pequeña
                'center': (-33.4489, -70.6693),
                'priority': 'high'
            },
            'valparaiso': {
                'bbox': (-33.00, -33.10, -71.55, -71.70),
                'center': (-33.0472, -71.6127),
                'priority': 'high'
            },
            'antofagasta': {
                'bbox': (-23.60, -23.70, -70.35, -70.45),
                'center': (-23.6509, -70.3975),
                'priority': 'medium'
            },
            'atacama_region': {
                'bbox': (-22.00, -24.00, -67.50, -69.00),  # Región más amplia
                'center': (-22.9100, -68.1969),
                'priority': 'medium'
            }
        }
        
        self.logger.info("🌍 City2GraphService inicializado")
    
    def _get_cache_key(self, bbox: Tuple[float, float, float, float], network_type: str) -> str:
        """🔑 Generar key única para cache"""
        bbox_str = f"{bbox[0]:.3f}_{bbox[1]:.3f}_{bbox[2]:.3f}_{bbox[3]:.3f}"
        return f"{bbox_str}_{network_type}"
    
    def _get_cache_file(self, cache_key: str) -> Path:
        """📁 Obtener ruta de archivo de cache"""
        safe_key = hashlib.md5(cache_key.encode()).hexdigest()
        return self.cache_dir / f"graph_{safe_key}.pkl"
    
    async def get_city_graph(self, city_name: str = None, 
                           bbox: Tuple[float, float, float, float] = None,
                           network_type: str = 'drive_service') -> Optional[nx.MultiGraph]:
        """
        🗺️ Obtener o crear grafo de ciudad
        
        Args:
            city_name: Nombre de ciudad predefinida ('santiago', 'valparaiso', etc.)
            bbox: Bounding box (north, south, east, west) 
            network_type: Tipo de red ('drive_service', 'walk', 'bike')
        """
        
        # Determinar bbox
        if city_name and city_name.lower() in self.chile_cities:
            bbox = self.chile_cities[city_name.lower()]['bbox']
            self.logger.info(f"📍 Usando bbox predefinido para {city_name}")
        elif not bbox:
            raise ValueError("Debe proporcionar city_name o bbox")
        
        cache_key = self._get_cache_key(bbox, network_type)
        
        # Verificar cache en memoria
        if cache_key in self.graphs_cache:
            self.logger.info(f"🚀 Cache hit en memoria: {cache_key}")
            return self.graphs_cache[cache_key]
        
        # Verificar cache en disco
        cache_file = self._get_cache_file(cache_key)
        if cache_file.exists():
            try:
                self.logger.info(f"💾 Cargando desde cache: {cache_file}")
                with open(cache_file, 'rb') as f:
                    graph = pickle.load(f)
                    self.graphs_cache[cache_key] = graph
                    return graph
            except Exception as e:
                self.logger.warning(f"⚠️ Error cargando cache: {e}")
        
        # Crear nuevo grafo
        self.logger.info(f"🏗️ Creando nuevo grafo para bbox {bbox}")
        start_time = time.time()
        
        try:
            # Descargar grafo desde OSM
            north, south, east, west = bbox
            graph = ox.graph_from_bbox(
                bbox=(north, south, east, west),
                network_type=network_type,
                simplify=True
            )
            
            # Proyectar a sistema de coordenadas local para cálculos precisos
            graph = ox.project_graph(graph)
            
            creation_time = time.time() - start_time
            
            self.logger.info(f"✅ Grafo creado: {len(graph.nodes)} nodos, {len(graph.edges)} aristas")
            self.logger.info(f"⏱️ Tiempo creación: {creation_time:.2f}s")
            
            # Guardar en cache
            self.graphs_cache[cache_key] = graph
            
            try:
                with open(cache_file, 'wb') as f:
                    pickle.dump(graph, f)
                self.logger.info(f"💾 Grafo guardado en cache: {cache_file}")
            except Exception as e:
                self.logger.warning(f"⚠️ Error guardando cache: {e}")
            
            return graph
            
        except Exception as e:
            self.logger.error(f"❌ Error creando grafo: {e}")
            return None
    
    def get_route_distance(self, origin: Tuple[float, float], 
                          destination: Tuple[float, float],
                          graph: nx.MultiGraph,
                          mode: str = 'drive') -> Optional[Dict]:
        """
        🛣️ Calcular ruta usando grafo preexistente
        
        Args:
            origin: (lat, lon) origen
            destination: (lat, lon) destino
            graph: Grafo de la ciudad
            mode: Modo de transporte
        """
        try:
            start_time = time.time()
            
            # Encontrar nodos más cercanos
            orig_node = ox.distance.nearest_nodes(graph, origin[1], origin[0])
            dest_node = ox.distance.nearest_nodes(graph, destination[1], destination[0])
            
            if orig_node == dest_node:
                return {
                    'distance_km': 0.0,
                    'duration_minutes': 0.0,
                    'route_found': True,
                    'source': 'city2graph',
                    'processing_time_ms': 0
                }
            
            # Calcular ruta más corta
            try:
                route = nx.shortest_path(graph, orig_node, dest_node, weight='length')
            except nx.NetworkXNoPath:
                self.logger.warning(f"⚠️ No se encontró ruta entre nodos")
                return None
            
            # Calcular distancia total
            distance_m = sum(graph[route[i]][route[i+1]][0]['length'] 
                           for i in range(len(route)-1))
            
            # Estimar duración basada en modo
            duration_minutes = self._estimate_duration(distance_m, mode)
            
            processing_time = (time.time() - start_time) * 1000  # ms
            
            return {
                'distance_km': round(distance_m / 1000, 2),
                'duration_minutes': round(duration_minutes, 1),
                'route_found': True,
                'source': 'city2graph',
                'processing_time_ms': round(processing_time, 1),
                'nodes_in_route': len(route)
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error calculando ruta: {e}")
            return None
    
    def _estimate_duration(self, distance_m: float, mode: str) -> float:
        """⏱️ Estimar duración basada en distancia y modo"""
        
        # Velocidades promedio urbanas (km/h)
        speeds = {
            'walk': 5,
            'drive': 25,  # Velocidad urbana conservadora
            'transit': 20,
            'bike': 15
        }
        
        speed_kmh = speeds.get(mode, 25)
        distance_km = distance_m / 1000
        duration_hours = distance_km / speed_kmh
        
        return duration_hours * 60  # minutos
    
    def get_city_stats(self, graph: nx.MultiGraph) -> Dict:
        """📊 Obtener estadísticas del grafo de ciudad"""
        if not graph:
            return {}
            
        return {
            'nodes': len(graph.nodes),
            'edges': len(graph.edges),
            'is_connected': nx.is_connected(graph.to_undirected()),
            'avg_degree': sum(dict(graph.degree()).values()) / len(graph.nodes),
            'coverage_area_km2': self._estimate_coverage_area(graph)
        }
    
    def _estimate_coverage_area(self, graph: nx.MultiGraph) -> float:
        """🗺️ Estimar área de cobertura del grafo"""
        try:
            # Obtener bounding box del grafo
            nodes_gdf = ox.graph_to_gdfs(graph, edges=False)
            bounds = nodes_gdf.total_bounds  # minx, miny, maxx, maxy
            
            # Calcular área aproximada (muy básico)
            width_deg = bounds[2] - bounds[0]
            height_deg = bounds[3] - bounds[1]
            
            # Conversión muy aproximada a km² (válida para Chile)
            area_km2 = width_deg * height_deg * 111 * 111 * 0.7  # Factor Chile
            
            return round(area_km2, 1)
        except:
            return 0.0
    
    async def preload_chile_cities(self):
        """🇨🇱 Precargar ciudades principales de Chile"""
        self.logger.info("🇨🇱 Precargando ciudades principales de Chile...")
        
        for city_name, config in self.chile_cities.items():
            if config['priority'] == 'high':
                self.logger.info(f"📍 Precargando {city_name}...")
                
                try:
                    graph = await self.get_city_graph(city_name=city_name)
                    if graph:
                        stats = self.get_city_stats(graph)
                        self.logger.info(f"✅ {city_name}: {stats['nodes']} nodos, {stats['coverage_area_km2']} km²")
                    else:
                        self.logger.warning(f"⚠️ No se pudo cargar {city_name}")
                        
                except Exception as e:
                    self.logger.error(f"❌ Error precargando {city_name}: {e}")
        
        self.logger.info("🎉 Precarga completada")

# Test básico
async def test_city2graph_basic():
    """🧪 Test básico del servicio"""
    print("🧪 TESTING CITY2GRAPH SERVICE - BÁSICO")
    print("="*50)
    
    service = City2GraphService()
    
    # Test Santiago
    print("📍 Cargando grafo Santiago...")
    start_time = time.time()
    
    santiago_graph = await service.get_city_graph('santiago')
    
    load_time = time.time() - start_time
    print(f"⏱️ Tiempo carga: {load_time:.2f}s")
    
    if santiago_graph:
        stats = service.get_city_stats(santiago_graph)
        print(f"📊 Estadísticas Santiago:")
        print(f"   Nodos: {stats['nodes']}")
        print(f"   Aristas: {stats['edges']}")
        print(f"   Conectado: {stats['is_connected']}")
        print(f"   Área: {stats['coverage_area_km2']} km²")
        
        # Test routing
        print(f"\n🛣️ Test routing...")
        origin = (-33.4489, -70.6693)  # Centro Santiago  
        destination = (-33.4372, -70.6506)  # Plaza de Armas
        
        route_result = service.get_route_distance(origin, destination, santiago_graph)
        
        if route_result:
            print(f"✅ Ruta encontrada:")
            print(f"   Distancia: {route_result['distance_km']} km")
            print(f"   Duración: {route_result['duration_minutes']} min")
            print(f"   Tiempo cálculo: {route_result['processing_time_ms']} ms")
        else:
            print(f"❌ No se pudo calcular ruta")
    else:
        print("❌ No se pudo cargar grafo Santiago")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_city2graph_basic())
