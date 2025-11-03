#!/usr/bin/env python3
"""
🚀 Optimized City2Graph Service v2.0
Lazy loading + H3 partitions + R-tree spatial     def _load_metadata(self):
        """Carga metadatos de optimización"""
        metadata_file = self.optimized_dir / "metadata.json"
        
        if not metadata_file.exists():
            raise FileNotFoundError(f"No se encontraron metadatos en {metadata_file}")
        
        with open(metadata_file, 'r') as f:
            self.metadata = json.load(f)
        
        # Obtener lista de particiones disponibles
        self.available_partitions = set()
        partition_files = list(self.optimized_dir.glob("*.pkl.zst"))
        for pfile in partition_files:
            h3_cell = pfile.stem.replace('.pkl', '')
            self.available_partitions.add(h3_cell)
        
        logger.info(f"📊 Metadatos cargados: {len(self.available_partitions):,} particiones H3 disponibles")import h3
import pandas as pd
import networkx as nx
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from rtree import index
import math
from functools import lru_cache
import pickle

# Configurar logging
logging.basicConfig(level=logging.INFO)
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
    distance_m: float
    lat: float
    lon: float

class SpeedProfileManager:
    """Maneja perfiles de velocidad por tipo de highway"""
    
    SPEED_PROFILES = {
        # Autopistas y rutas principales
        'motorway': 120, 'motorway_link': 80,
        'trunk': 100, 'trunk_link': 60,
        'primary': 80, 'primary_link': 50,
        
        # Rutas secundarias
        'secondary': 60, 'secondary_link': 40,
        'tertiary': 50, 'tertiary_link': 30,
        
        # Rutas urbanas
        'residential': 30, 'living_street': 20,
        'unclassified': 40, 'service': 20,
        
        # Default
        'road': 40
    }
    
    @classmethod
    def get_speed(cls, highway_type: str, maxspeed: Optional[str] = None) -> float:
        """Obtiene velocidad en km/h para un tipo de highway"""
        if maxspeed:
            try:
                speed_str = maxspeed.replace('mph', '').replace('km/h', '').strip()
                speed = float(speed_str)
                if 'mph' in maxspeed.lower():
                    speed *= 1.60934
                return min(speed, 150)
            except:
                pass
        return cls.SPEED_PROFILES.get(highway_type, cls.SPEED_PROFILES['road'])
    
    @classmethod
    def calculate_travel_time(cls, distance_m: float, highway_type: str, 
                            maxspeed: Optional[str] = None) -> float:
        """Calcula tiempo de viaje en segundos"""
        speed_kmh = cls.get_speed(highway_type, maxspeed)
        speed_ms = speed_kmh / 3.6
        return distance_m / speed_ms

class OptimizedCity2GraphService:
    """Servicio optimizado con lazy loading y particiones H3"""
    
    def __init__(self, data_dir: str = "data/graphs", region: str = "chile"):
        self.data_dir = Path(data_dir)
        self.region = region
        self.optimized_dir = self.data_dir / region / "optimized"
        
        # Estado
        self.metadata: Optional[Dict] = None
        self.loaded_partitions: Set[str] = set()
        self.graph: nx.DiGraph = nx.DiGraph()
        self.node_coords: Dict[int, Tuple[float, float]] = {}
        self.spatial_index: Optional[index.Index] = None
        
        # Cache
        self.partition_cache: Dict[str, Tuple[pd.DataFrame, pd.DataFrame]] = {}
        
        logger.info(f"🚀 OptimizedCity2GraphService v2.0 ({region})")
        
        # Cargar metadatos
        self._load_metadata()
        
        # Crear índice espacial global (rápido)
        self._build_spatial_index()
    
    def _load_metadata(self):
        """Carga metadatos del grafo optimizado"""
        metadata_file = self.optimized_dir / "metadata.json"
        
        if not metadata_file.exists():
            raise FileNotFoundError(f"Metadatos no encontrados: {metadata_file}")
        
        with open(metadata_file, 'r') as f:
            self.metadata = json.load(f)
        
        logger.info(f"📊 Metadatos cargados: {self.metadata['partitions_count']:,} particiones H3")
    
    def _build_spatial_index(self):
        """Construye índice espacial R-tree de todas las particiones"""
        start_time = time.time()
        
        # Intentar cargar índice persistente + coordenadas
        index_file = self.optimized_dir / "spatial_index"
        coords_file = self.optimized_dir / "node_coords.pkl"
        
        if index_file.with_suffix('.idx').exists() and coords_file.exists():
            try:
                self.spatial_index = index.Rtree(str(index_file))
                with open(coords_file, 'rb') as f:
                    self.node_coords = pickle.load(f)
                elapsed = time.time() - start_time
                logger.info(f"✅ Índice espacial cargado desde disco en {elapsed:.2f}s ({len(self.node_coords):,} nodos)")
                return
            except Exception as e:
                logger.warning(f"⚠️ Error cargando índice: {e}, reconstruyendo...")
        
        # Construir índice desde particiones
        logger.info("🗺️ Construyendo índice espacial global...")
        
        # Crear índice en memoria (evitar problemas con archivos)
        self.spatial_index = index.Index()
        
        nodes_dir = self.optimized_dir / f"nodes_h3_{self.metadata['h3_level']}"
        nodes_indexed = 0
        
        # Procesar cada partición (solo samplear para índice inicial)
        partition_files = list(nodes_dir.glob("*.parquet"))
        logger.info(f"   Procesando {len(partition_files):,} particiones...")
        
        for i, partition_file in enumerate(partition_files):
            nodes_df = pd.read_parquet(partition_file)
            
            # Samplear nodos para construir índice más rápido
            sample_size = min(len(nodes_df), 1000)  # Max 1000 nodos por partición
            nodes_sample = nodes_df.sample(n=sample_size) if len(nodes_df) > sample_size else nodes_df
            
            for _, row in nodes_sample.iterrows():
                node_id = row['id']
                lat, lon = row['lat'], row['lon']
                
                # Insertar en índice
                self.spatial_index.insert(node_id, (lon, lat, lon, lat))
                self.node_coords[node_id] = (lat, lon)
                nodes_indexed += 1
            
            # Log progreso
            if (i + 1) % 500 == 0:
                logger.info(f"   Procesadas {i+1:,}/{len(partition_files):,} particiones...")
        
        # Guardar coordenadas para próxima vez
        with open(coords_file, 'wb') as f:
            pickle.dump(self.node_coords, f)
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Índice espacial construido: {nodes_indexed:,} nodos (sample) en {elapsed:.1f}s")
    
    def _get_h3_cells_for_route(self, origin_lat: float, origin_lon: float,
                               dest_lat: float, dest_lon: float, 
                               buffer_km: float = 50.0) -> Set[str]:
        """Obtiene celdas H3 necesarias para una ruta con mejor conectividad"""
        h3_level = self.metadata['h3_level']
        h3_cells = set()
        
        # 1. Celdas de origen y destino
        origin_cell = h3.latlng_to_cell(origin_lat, origin_lon, h3_level)
        dest_cell = h3.latlng_to_cell(dest_lat, dest_lon, h3_level)
        h3_cells.update([origin_cell, dest_cell])
        
        # 2. Calcular línea recta entre origen y destino
        # Crear puntos intermedios para rutas largas
        distance = self._haversine_distance(origin_lat, origin_lon, dest_lat, dest_lon)
        
        if distance > 50000:  # >50km: ruta larga, necesita más puntos
            num_points = max(10, min(50, int(distance / 10000)))  # 1 punto cada 10km
        else:
            num_points = 5
        
        # Interpolar puntos a lo largo de la línea recta
        for i in range(num_points + 1):
            t = i / num_points
            lat = origin_lat + t * (dest_lat - origin_lat)
            lon = origin_lon + t * (dest_lon - origin_lon)
            cell = h3.latlng_to_cell(lat, lon, h3_level)
            h3_cells.add(cell)
        
        # 3. Agregar buffer con celdas vecinas (2-ring para mejor conectividad)
        extended_cells = set(h3_cells)
        for cell in h3_cells:
            try:
                # 1-ring neighbors
                neighbors_1 = h3.grid_ring(cell, 1)
                extended_cells.update(neighbors_1)
                
                # Para rutas largas, agregar 2-ring en celdas clave
                if distance > 100000:  # >100km
                    neighbors_2 = h3.grid_ring(cell, 2)
                    extended_cells.update(neighbors_2)
            except Exception:
                # Skip si hay error con vecinos (celdas en bordes)
                pass
        
        # 4. Verificar disponibilidad de particiones
        available_cells = [cell for cell in extended_cells if cell in self.available_partitions]
        
        logger.info(f"🗺️ Ruta {distance/1000:.0f}km: {len(extended_cells)} celdas calculadas, {len(available_cells)} disponibles")
        
        if len(available_cells) < len(extended_cells) * 0.3:  # <30% disponibles
            logger.warning(f"⚠️ Pocas particiones disponibles: {len(available_cells)}/{len(extended_cells)}")
        
        return extended_cells
    
    def _load_partitions(self, h3_cells: Set[str]) -> Tuple[int, int]:
        """Carga particiones H3 específicas en memoria"""
        h3_level = self.metadata['h3_level']
        nodes_dir = self.optimized_dir / f"nodes_h3_{h3_level}"
        edges_dir = self.optimized_dir / f"edges_h3_{h3_level}"
        
        nodes_loaded = 0
        edges_loaded = 0
        
        for h3_cell in h3_cells:
            if h3_cell in self.loaded_partitions:
                continue  # Ya cargada
            
            # Cargar nodos de la partición
            nodes_file = nodes_dir / f"h3_{h3_cell}.parquet"
            if nodes_file.exists():
                nodes_df = pd.read_parquet(nodes_file)
                
                # Agregar nodos al grafo
                for _, row in nodes_df.iterrows():
                    node_id = row['id']
                    lat, lon = row['lat'], row['lon']
                    self.graph.add_node(node_id, lat=lat, lon=lon)
                    self.node_coords[node_id] = (lat, lon)
                    nodes_loaded += 1
            
            # Cargar aristas de la partición
            edges_file = edges_dir / f"h3_{h3_cell}.parquet"
            if edges_file.exists():
                edges_df = pd.read_parquet(edges_file)
                
                # Agregar aristas al grafo
                for _, row in edges_df.iterrows():
                    from_id = row['from_id']
                    to_id = row['to_id']
                    distance = row['distance_m']
                    highway_type = row['highway_type']
                    maxspeed = row.get('maxspeed')
                    oneway = row.get('oneway', False)
                    
                    # Calcular tiempo de viaje 
                    travel_time = SpeedProfileManager.calculate_travel_time(
                        distance, highway_type, maxspeed
                    )
                    
                    self.graph.add_edge(
                        from_id, to_id,
                        distance=distance,
                        travel_time=travel_time,
                        highway_type=highway_type,
                        maxspeed=maxspeed,
                        weight=travel_time
                    )
                    
                    # Agregar arista reversa si no es oneway
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
            
            # Marcar partición como cargada
            self.loaded_partitions.add(h3_cell)
        
        return nodes_loaded, edges_loaded
    
    @lru_cache(maxsize=10000)
    def find_nearest_node(self, lat: float, lon: float, 
                         max_distance_m: float = 1000) -> Optional[NearestNodeResult]:
        """Encuentra el nodo más cercano usando R-tree"""
        if not self.spatial_index:
            return None
        
        # Convertir distancia a grados
        deg_distance = max_distance_m / 111000
        
        # Buscar candidatos
        candidates = list(self.spatial_index.intersection((
            lon - deg_distance, lat - deg_distance,
            lon + deg_distance, lat + deg_distance
        )))
        
        if not candidates:
            return None
        
        # Encontrar el más cercano
        min_distance = float('inf')
        nearest_node = None
        
        for node_id in candidates:
            if node_id in self.node_coords:
                node_lat, node_lon = self.node_coords[node_id]
                distance = self._haversine_distance(lat, lon, node_lat, node_lon)
                
                if distance < min_distance:
                    min_distance = distance
                    nearest_node = node_id
        
        if nearest_node and min_distance <= max_distance_m:
            node_lat, node_lon = self.node_coords[nearest_node]
            return NearestNodeResult(
                node_id=nearest_node,
                distance_m=min_distance,
                lat=node_lat,
                lon=node_lon
            )
        
        return None
    
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
        nodes_loaded, edges_loaded = self._load_partitions(h3_cells)
        if nodes_loaded > 0 or edges_loaded > 0:
            logger.info(f"🔄 Cargadas particiones: +{nodes_loaded} nodos, +{edges_loaded} aristas")
        
        logger.info(f"📊 Estado actual: {self.graph.number_of_nodes()} nodos, {self.graph.number_of_edges()} aristas")
        
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
        
        try:
            # 4. Calcular ruta
            path = nx.shortest_path(
                self.graph,
                origin_node.node_id,
                dest_node.node_id,
                weight=weight
            )
            
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
            logger.info(f"✅ Ruta calculada en {elapsed*1000:.1f}ms: {total_distance/1000:.1f}km, {total_travel_time/60:.1f}min")
            
            return RouteResult(
                path=path,
                distance_m=total_distance,
                travel_time_s=total_travel_time,
                highway_types=highway_types,
                estimated_speed_kmh=avg_speed_kmh
            )
            
        except nx.NetworkXNoPath:
            logger.warning("❌ No hay ruta disponible")
            return None
        except Exception as e:
            logger.error(f"❌ Error calculando ruta: {e}")
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
        return {
            "status": "ready",
            "region": self.region,
            "total_partitions": self.metadata['partitions_count'] if self.metadata else 0,
            "loaded_partitions": len(self.loaded_partitions),
            "nodes_in_memory": self.graph.number_of_nodes(),
            "edges_in_memory": self.graph.number_of_edges(),
            "spatial_index": self.spatial_index is not None,
            "cache_size": self.find_nearest_node.cache_info().currsize if hasattr(self.find_nearest_node, 'cache_info') else 0
        }

# Singleton global
_optimized_service = None

def get_optimized_service() -> OptimizedCity2GraphService:
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
    
    print(f"\n📊 Stats finales: {service.get_stats()}")