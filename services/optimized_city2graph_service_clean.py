#!/usr/bin/env python3
"""
🚀 Optimized City2Graph Service v2.0  
Lazy loading + H3 partitions + R-tree spatial indexing
"""

import json
import math
import pickle
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import h3
import networkx as nx
import pandas as pd
from rtree import index

# Logging
import logging
logger = logging.getLogger(__name__)

@dataclass
class RouteResult:
    """Resultado de routing optimizado"""
    path: List[int]
    distance_m: float
    travel_time_s: float
    highway_types: List[str]
    estimated_speed_kmh: float

@dataclass  
class NearestNodeResult:
    """Resultado de snap-to-road"""
    node_id: int
    lat: float
    lon: float
    distance_m: float

class SpeedProfileManager:
    """Maneja perfiles de velocidad por tipo de highway"""
    
    SPEED_PROFILES = {
        'motorway': 120,
        'motorway_link': 80,
        'trunk': 100,
        'trunk_link': 70,
        'primary': 80,
        'primary_link': 60,
        'secondary': 70,
        'secondary_link': 50,
        'tertiary': 60,
        'tertiary_link': 40,
        'unclassified': 50,
        'residential': 30,
        'service': 20,
        'living_street': 10,
        'pedestrian': 5,
        'track': 30,
        'bus_guideway': 50,
        'raceway': 200,
        'road': 50,
        'busway': 50,
        'footway': 5,
        'bridleway': 10,
        'steps': 3,
        'path': 5,
        'cycleway': 15
    }
    
    @classmethod
    def get_speed(cls, highway_type: str, maxspeed: Optional[str] = None) -> float:
        """Obtiene velocidad en km/h para un tipo de highway"""
        if maxspeed:
            try:
                # Normalizar maxspeed: "50 mph" -> 80, "60" -> 60
                if 'mph' in str(maxspeed).lower():
                    return float(str(maxspeed).lower().replace('mph', '').strip()) * 1.60934
                else:
                    return float(str(maxspeed).replace('km/h', '').strip())
            except (ValueError, AttributeError):
                pass
        
        return cls.SPEED_PROFILES.get(highway_type, 50)
    
    @classmethod
    def calculate_travel_time(cls, distance_m: float, highway_type: str, 
                            maxspeed: Optional[str] = None) -> float:
        """Calcula tiempo de viaje en segundos"""
        speed_kmh = cls.get_speed(highway_type, maxspeed)
        speed_ms = speed_kmh / 3.6  # km/h to m/s
        return distance_m / speed_ms

class OptimizedCity2GraphService:
    """Servicio optimizado con lazy loading y particiones H3"""
    
    def __init__(self, data_dir: str = "data/graphs", region: str = "chile"):
        self.data_dir = Path(data_dir)
        self.region = region
        self.optimized_dir = self.data_dir / region / "optimized"
        
        # Estado
        self.metadata: Optional[Dict] = None
        self.available_partitions: Set[str] = set()
        self.loaded_partitions: Set[str] = set()
        self.graph: nx.DiGraph = nx.DiGraph()
        self.node_coords: Dict[int, Tuple[float, float]] = {}
        self.spatial_index: Optional[index.Index] = None
        
        # Cache
        self.partition_cache: Dict[str, Tuple[pd.DataFrame, pd.DataFrame]] = {}
        self.cells_cache: Dict[frozenset, Tuple[int, int]] = {}
        
        logger.info(f"🚀 OptimizedCity2GraphService v2.0 ({region})")
        
        # Cargar metadatos
        self._load_metadata()
        
        # Crear índice espacial global
        self._build_spatial_index()
    
    def _load_metadata(self):
        """Carga metadatos de optimización"""
        metadata_file = self.optimized_dir / "metadata.json"
        
        if not metadata_file.exists():
            raise FileNotFoundError(f"No se encontraron metadatos en {metadata_file}")
        
        with open(metadata_file, 'r') as f:
            self.metadata = json.load(f)
        
        # Obtener lista de particiones disponibles
        h3_level = self.metadata['h3_level']
        nodes_dir = self.optimized_dir / f"nodes_h3_{h3_level}"
        
        if nodes_dir.exists():
            partition_files = list(nodes_dir.glob("h3_*.parquet"))
            for pfile in partition_files:
                # Extraer H3 cell del nombre
                h3_cell = pfile.stem.replace('h3_', '')
                self.available_partitions.add(h3_cell)
        
        logger.info(f"📊 Metadatos cargados: {len(self.available_partitions):,} particiones H3 disponibles")
    
    def _build_spatial_index(self):
        """Construye índice espacial R-tree de todas las particiones"""
        start_time = time.time()
        
        # Intentar cargar índice persistente
        index_basename = str(self.optimized_dir / "spatial_index")
        coords_file = self.optimized_dir / "node_coords.pkl"
        
        idx_file = Path(f"{index_basename}.idx")
        dat_file = Path(f"{index_basename}.dat")
        
        if idx_file.exists() and dat_file.exists() and coords_file.exists():
            try:
                self.spatial_index = index.Index(index_basename)
                with open(coords_file, 'rb') as f:
                    self.node_coords = pickle.load(f)
                elapsed = time.time() - start_time
                logger.info(f"✅ Índice espacial cargado desde disco en {elapsed:.2f}s ({len(self.node_coords):,} nodos)")
                return
            except Exception as e:
                logger.warning(f"⚠️ Error cargando índice: {e}, reconstruyendo...")
        
        # Construir índice desde particiones
        logger.info("🗺️ Construyendo índice espacial global...")
        self.spatial_index = index.Index()
        
        h3_level = self.metadata['h3_level'] 
        nodes_dir = self.optimized_dir / f"nodes_h3_{h3_level}"
        nodes_indexed = 0
        
        partition_files = list(nodes_dir.glob("h3_*.parquet"))
        logger.info(f"   Procesando {len(partition_files):,} particiones...")
        
        for i, partition_file in enumerate(partition_files):
            nodes_df = pd.read_parquet(partition_file, columns=["id", "lat", "lon"])
            
            # Samplear para índice más rápido
            sample_size = min(len(nodes_df), 1000)
            nodes_sample = nodes_df.sample(n=sample_size) if len(nodes_df) > sample_size else nodes_df
            
            for _, row in nodes_sample.iterrows():
                node_id = int(row['id'])  # Asegurar tipo entero
                lat, lon = float(row['lat']), float(row['lon'])  # Asegurar tipo float
                
                self.spatial_index.insert(node_id, (lon, lat, lon, lat))
                self.node_coords[node_id] = (lat, lon)
                nodes_indexed += 1
            
            if (i + 1) % 500 == 0:
                logger.info(f"   Procesadas {i+1:,}/{len(partition_files):,} particiones...")
        
        # Guardar índice persistente
        try:
            temp_index = index.Index(index_basename)
            for node_id, (lat, lon) in self.node_coords.items():
                temp_index.insert(node_id, (lon, lat, lon, lat))
            temp_index.close()
            
            with open(coords_file, 'wb') as f:
                pickle.dump(self.node_coords, f)
                
            logger.debug("💾 Índice persistente guardado")
        except Exception as e:
            logger.warning(f"⚠️ Error guardando índice: {e}")
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Índice espacial construido: {nodes_indexed:,} nodos en {elapsed:.1f}s")
    
    def _get_h3_cells_for_route(self, origin_lat: float, origin_lon: float,
                               dest_lat: float, dest_lon: float, 
                               corridor_km: float = 8.0) -> Set[str]:
        """Obtiene celdas H3 del corredor origen-destino (optimizado)"""
        h3_level = self.metadata['h3_level']
        distance = self._haversine_distance(origin_lat, origin_lon, dest_lat, dest_lon)
        
        # Puntos del corredor cada ~5km
        n = max(2, int(distance / 5000))
        cells = set()
        
        # Corredor principal
        for i in range(n + 1):
            t = i / n
            lat = origin_lat + t * (dest_lat - origin_lat)
            lon = origin_lon + t * (dest_lon - origin_lon)
            cell = h3.latlng_to_cell(lat, lon, h3_level)
            
            # Buffer del corredor
            k = max(1, int(corridor_km // 3.5))
            try:
                cells.update(h3.grid_disk(cell, k))
            except Exception:
                cells.add(cell)
        
        # Refuerzo en extremos
        try:
            origin_cell = h3.latlng_to_cell(origin_lat, origin_lon, h3_level)
            dest_cell = h3.latlng_to_cell(dest_lat, dest_lon, h3_level)
            cells.update(h3.grid_disk(origin_cell, 1))
            cells.update(h3.grid_disk(dest_cell, 1))
        except Exception:
            pass
        
        # Verificar disponibilidad
        available_cells = [cell for cell in cells if cell in self.available_partitions]
        
        logger.info(f"🗺️ Corredor {distance/1000:.0f}km: {len(cells)} celdas H3, {len(available_cells)} disponibles")
        
        if len(available_cells) < len(cells) * 0.4:
            logger.warning(f"⚠️ Pocas particiones disponibles: {len(available_cells)}/{len(cells)}")
        
        return cells
    
    def _load_partitions(self, h3_cells: Set[str]) -> Tuple[int, int]:
        """Carga particiones H3 específicas en memoria con cache"""
        cells_key = frozenset(h3_cells)
        
        # Cache hit
        if cells_key in self.cells_cache:
            cached_nodes, cached_edges = self.cells_cache[cells_key]
            logger.debug(f"💨 Cache hit: {cached_nodes} nodos, {cached_edges} aristas")
            return cached_nodes, cached_edges
        
        h3_level = self.metadata['h3_level']
        nodes_dir = self.optimized_dir / f"nodes_h3_{h3_level}"
        edges_dir = self.optimized_dir / f"edges_h3_{h3_level}"
        
        nodes_loaded = 0
        edges_loaded = 0
        
        for h3_cell in h3_cells:
            if h3_cell in self.loaded_partitions:
                continue
            
            # Cargar nodos (lectura selectiva)
            nodes_file = nodes_dir / f"h3_{h3_cell}.parquet" 
            if nodes_file.exists():
                nodes_df = pd.read_parquet(nodes_file, columns=["id", "lat", "lon"])
                
                for _, row in nodes_df.iterrows():
                    node_id = row['id']
                    lat, lon = row['lat'], row['lon']
                    self.graph.add_node(node_id, lat=lat, lon=lon)
                    self.node_coords[node_id] = (lat, lon)
                    nodes_loaded += 1
            
            # Cargar aristas (lectura selectiva)
            edges_file = edges_dir / f"h3_{h3_cell}.parquet"
            if edges_file.exists():
                edges_df = pd.read_parquet(edges_file, columns=[
                    "from_id", "to_id", "distance_m", "highway_type", "maxspeed", "oneway"
                ])
                
                for _, row in edges_df.iterrows():
                    from_id = row['from_id']
                    to_id = row['to_id']
                    distance = row['distance_m']
                    highway_type = row['highway_type']
                    maxspeed = row.get('maxspeed')
                    oneway = row.get('oneway', False)
                    
                    travel_time = SpeedProfileManager.calculate_travel_time(
                        distance, highway_type, maxspeed
                    )
                    
                    # Arista principal
                    self.graph.add_edge(
                        from_id, to_id,
                        distance=distance,
                        travel_time=travel_time,
                        highway_type=highway_type,
                        maxspeed=maxspeed,
                        weight=travel_time
                    )
                    
                    # Arista reversa si no es oneway
                    if not oneway:
                        self.graph.add_edge(
                            to_id, from_id,
                            distance=distance,
                            travel_time=travel_time,
                            highway_type=highway_type,
                            maxspeed=maxspeed,
                            weight=travel_time
                        )
                    
                    edges_loaded += 1
            
            self.loaded_partitions.add(h3_cell)
        
        # Guardar en cache
        self.cells_cache[cells_key] = (nodes_loaded, edges_loaded)
        
        return nodes_loaded, edges_loaded
    
    @lru_cache(maxsize=10000)
    def find_nearest_node(self, lat: float, lon: float, 
                         max_distance_m: float = 1000) -> Optional[NearestNodeResult]:
        """Encuentra el nodo más cercano usando R-tree"""
        if not self.spatial_index:
            return None
        
        # Convertir a grados aproximados
        deg_buffer = max_distance_m / 111000
        
        # Buscar candidatos en R-tree
        candidates = list(self.spatial_index.nearest((lon, lat, lon, lat), 10))
        
        if not candidates:
            return None
        
        # Encontrar el más cercano por distancia haversine
        best_node = None
        best_distance = float('inf')
        
        for node_id in candidates:
            if node_id in self.node_coords:
                node_lat, node_lon = self.node_coords[node_id]
                distance = self._haversine_distance(lat, lon, node_lat, node_lon)
                
                if distance < best_distance and distance <= max_distance_m:
                    best_distance = distance
                    best_node = NearestNodeResult(
                        node_id=node_id,
                        lat=node_lat,
                        lon=node_lon,
                        distance_m=distance
                    )
        
        return best_node
    
    def route(self, origin_lat: float, origin_lon: float,
              dest_lat: float, dest_lon: float,
              weight: str = 'travel_time') -> Optional[RouteResult]:
        """Calcula ruta optimizada con lazy loading"""
        start_time = time.time()
        
        # 1. Determinar particiones necesarias
        route_distance = self._haversine_distance(origin_lat, origin_lon, dest_lat, dest_lon)
        h3_cells = self._get_h3_cells_for_route(origin_lat, origin_lon, dest_lat, dest_lon)
        
        logger.info(f"🎯 Ruta {route_distance/1000:.0f}km: {len(h3_cells)} celdas H3 calculadas")
        
        # 2. Cargar particiones (lazy loading)
        loading_start = time.time()
        nodes_loaded, edges_loaded = self._load_partitions(h3_cells)
        loading_time = time.time() - loading_start
        
        if nodes_loaded > 0 or edges_loaded > 0:
            logger.info(f"🔄 Cargadas en {loading_time*1000:.0f}ms: +{nodes_loaded} nodos, +{edges_loaded} aristas")
        else:
            logger.info(f"� Cache completo: datos ya en memoria ({loading_time*1000:.0f}ms)")
        
        # Eficiencia de particionado
        loaded_partitions = len([cell for cell in h3_cells if cell in self.loaded_partitions])
        partition_efficiency = (loaded_partitions / len(h3_cells)) * 100 if h3_cells else 0
        
        logger.info(f"📊 Grafo: {self.graph.number_of_nodes():,} nodos, {self.graph.number_of_edges():,} aristas")
        logger.info(f"🎯 Eficiencia particionado: {partition_efficiency:.1f}% ({loaded_partitions}/{len(h3_cells)} celdas)")
        
        # 3. Snap to road
        origin_node = self.find_nearest_node(origin_lat, origin_lon)
        dest_node = self.find_nearest_node(dest_lat, dest_lon)
        
        if not origin_node:
            logger.warning(f"❌ No se encontró nodo origen cerca de ({origin_lat:.6f}, {origin_lon:.6f})")
            return None
        if not dest_node:
            logger.warning(f"❌ No se encontró nodo destino cerca de ({dest_lat:.6f}, {dest_lon:.6f})")
            return None
        
        logger.info(f"📍 Snap-to-road: origen {origin_node.distance_m:.0f}m, destino {dest_node.distance_m:.0f}m")
        
        # Log estado del grafo antes de routing
        logger.info(f"📊 H3 corridor: nodos:{self.graph.number_of_nodes():,} aristas:{self.graph.number_of_edges():,}")
        
        try:
            # 4. Calcular ruta con A* (heurística geodésica corregida)
            dest_lat, dest_lon = self.node_coords[dest_node.node_id]
            
            def _heuristic(u, v):
                """Heurística haversine con velocidad máxima 120 km/h"""
                if u not in self.node_coords:
                    return 0  # Fallback seguro
                lat1, lon1 = self.node_coords[u]
                distance_m = self._haversine_distance(lat1, lon1, dest_lat, dest_lon)
                return distance_m / (120 / 3.6)  # 120 km/h to m/s
            
            # Usar A* para rutas largas, Dijkstra para cortas
            if route_distance > 50000:  # >50km
                path = nx.astar_path(self.graph, origin_node.node_id, dest_node.node_id,
                                   heuristic=_heuristic, weight=weight)
                algorithm = "A*"
            else:
                path = nx.shortest_path(self.graph, origin_node.node_id, dest_node.node_id,
                                      weight=weight)
                algorithm = "Dijkstra"
            
            # 5. Calcular métricas
            total_distance = 0
            total_travel_time = 0
            highway_types = []
            
            for i in range(len(path) - 1):
                edge_data = self.graph[path[i]][path[i+1]]
                total_distance += edge_data['distance']
                total_travel_time += edge_data['travel_time']
                highway_types.append(edge_data['highway_type'])
            
            avg_speed_kmh = (total_distance / 1000) / (total_travel_time / 3600) if total_travel_time > 0 else 0
            
            elapsed = time.time() - start_time
            logger.info(f"✅ {algorithm} ruta en {elapsed*1000:.0f}ms: {total_distance/1000:.1f}km, {total_travel_time/60:.1f}min, {len(path)} nodos")
            
            return RouteResult(
                path=path,
                distance_m=total_distance,
                travel_time_s=total_travel_time,
                highway_types=highway_types,
                estimated_speed_kmh=avg_speed_kmh
            )
            
        except nx.NetworkXNoPath:
            logger.warning("❌ No hay ruta disponible - verificar conectividad entre particiones")
            return None
        except Exception as e:
            # Fallback: intentar con Dijkstra si A* falla
            logger.warning(f"⚠️ A* falló ({e}), intentando Dijkstra...")
            try:
                path = nx.shortest_path(self.graph, origin_node.node_id, dest_node.node_id, weight=weight)
                algorithm = "Dijkstra (fallback)"
                
                # Calcular métricas igual que antes
                total_distance = 0
                total_travel_time = 0
                highway_types = []
                
                for i in range(len(path) - 1):
                    edge_data = self.graph[path[i]][path[i+1]]
                    total_distance += edge_data['distance']
                    total_travel_time += edge_data['travel_time']
                    highway_types.append(edge_data['highway_type'])
                
                avg_speed_kmh = (total_distance / 1000) / (total_travel_time / 3600) if total_travel_time > 0 else 0
                
                elapsed = time.time() - start_time
                logger.info(f"✅ {algorithm} ruta en {elapsed*1000:.0f}ms: {total_distance/1000:.1f}km, {total_travel_time/60:.1f}min, {len(path)} nodos")
                
                return RouteResult(
                    path=path,
                    distance_m=total_distance,
                    travel_time_s=total_travel_time,
                    highway_types=highway_types,
                    estimated_speed_kmh=avg_speed_kmh
                )
            except Exception as fallback_error:
                logger.error(f"❌ Dijkstra fallback también falló: {fallback_error}")
                return None
    
    def get_route_coordinates(self, route_result: RouteResult) -> List[Tuple[float, float]]:
        """Obtiene coordenadas de la ruta"""
        if not route_result:
            return []
        
        coordinates = []
        for node_id in route_result.path:
            if node_id in self.node_coords:
                lat, lon = self.node_coords[node_id]
                coordinates.append((lat, lon))
        
        return coordinates
    
    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calcula distancia haversine en metros"""
        R = 6371000
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        
        a = (math.sin(dlat/2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2)
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas del servicio"""
        # Cache stats del snap-to-road
        cache_info = None
        if hasattr(self.find_nearest_node, 'cache_info'):
            cache_info = self.find_nearest_node.cache_info()
        
        return {
            "status": "ready",
            "region": self.region,
            "total_partitions": len(self.available_partitions),
            "loaded_partitions": len(self.loaded_partitions),
            "partition_efficiency": f"{(len(self.loaded_partitions)/len(self.available_partitions)*100):.1f}%",
            "nodes_in_memory": self.graph.number_of_nodes(),
            "edges_in_memory": self.graph.number_of_edges(),
            "spatial_index": self.spatial_index is not None,
            "spatial_index_size": len(self.node_coords),
            "cache_size": cache_info.currsize if cache_info else 0,
            "cache_hit_rate": f"{(cache_info.hits/(cache_info.hits+cache_info.misses)*100):.1f}%" if cache_info and (cache_info.hits + cache_info.misses) > 0 else "0%",
            "partition_cache_entries": len(self.cells_cache)
        }

# Singleton global
_optimized_service = None

def get_optimized_service():
    """Obtiene instancia singleton del servicio optimizado"""
    global _optimized_service
    if _optimized_service is None:
        _optimized_service = OptimizedCity2GraphService()
    return _optimized_service

if __name__ == "__main__":
    # Test del servicio optimizado
    service = OptimizedCity2GraphService()
    
    print(f"📊 Stats iniciales: {service.get_stats()}")
    
    # Test routing: Antofagasta → San Pedro
    print(f"\n🧪 Test: Antofagasta → San Pedro de Atacama")
    result = service.route(-23.6509, -70.3975, -22.9083, -68.2000)
    
    if result:
        print(f"✅ Ruta exitosa:")
        print(f"   📏 Distancia: {result.distance_m/1000:.1f}km")
        print(f"   ⏱️  Tiempo: {result.travel_time_s/60:.1f}min")
        print(f"   🚗 Velocidad: {result.estimated_speed_kmh:.1f}km/h")
        print(f"   🛣️  Vías: {set(result.highway_types)}")
    else:
        print("❌ No se encontró ruta")
    
    print(f"\n📊 Stats finales: {service.get_stats()}")