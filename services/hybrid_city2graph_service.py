#!/usr/bin/env python3
"""
🚀 Hybrid City2Graph Service
Combina NetworkX optimizado con análisis semántico para máximo rendimiento
"""

import time
import logging
from typing import Dict, List, Tuple, Optional
import pandas as pd
import networkx as nx
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from rtree import index
import math
import asyncio
from functools import lru_cache

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
        'motorway': 120,
        'motorway_link': 80,
        'trunk': 100,
        'trunk_link': 60,
        'primary': 80,
        'primary_link': 50,
        
        # Rutas secundarias
        'secondary': 60,
        'secondary_link': 40,
        'tertiary': 50,
        'tertiary_link': 30,
        
        # Rutas urbanas
        'residential': 30,
        'living_street': 20,
        'unclassified': 40,
        'service': 20,
        
        # Rutas especiales
        'track': 15,
        'path': 10,
        'footway': 5,
        'cycleway': 15,
        'steps': 3,
        
        # Default
        'road': 40
    }
    
    @classmethod
    def get_speed(cls, highway_type: str, maxspeed: Optional[str] = None) -> float:
        """Obtiene velocidad en km/h para un tipo de highway"""
        # Prioridad 1: maxspeed explícito
        if maxspeed:
            try:
                # Extraer números de strings como "50 mph", "80", "50 km/h"
                speed_str = maxspeed.replace('mph', '').replace('km/h', '').strip()
                speed = float(speed_str)
                # Convertir mph a km/h si es necesario
                if 'mph' in maxspeed.lower():
                    speed *= 1.60934
                return min(speed, 150)  # Cap máximo 150 km/h
            except:
                pass
        
        # Prioridad 2: perfil por highway type
        return cls.SPEED_PROFILES.get(highway_type, cls.SPEED_PROFILES['road'])
    
    @classmethod
    def calculate_travel_time(cls, distance_m: float, highway_type: str, 
                            maxspeed: Optional[str] = None) -> float:
        """Calcula tiempo de viaje en segundos"""
        speed_kmh = cls.get_speed(highway_type, maxspeed)
        speed_ms = speed_kmh / 3.6  # km/h a m/s
        return distance_m / speed_ms

class HybridCity2GraphService:
    """Servicio híbrido optimizado para routing y análisis semántico"""
    
    def __init__(self, data_dir: str = "data/graphs"):
        self.data_dir = Path(data_dir)
        self.graph: Optional[nx.DiGraph] = None
        self.spatial_index: Optional[index.Index] = None
        self.nodes_df: Optional[pd.DataFrame] = None
        self.edges_df: Optional[pd.DataFrame] = None
        self.node_coords: Dict[int, Tuple[float, float]] = {}
        
        logger.info("🚀 Inicializando HybridCity2GraphService...")
    
    def load_data(self, country: str = "chile") -> bool:
        """Carga datos desde Parquet con optimizaciones"""
        start_time = time.time()
        
        try:
            # Cargar datos
            country_dir = self.data_dir / country
            nodes_path = country_dir / "nodes.parquet"
            edges_path = country_dir / "edges.parquet"
            
            if not nodes_path.exists() or not edges_path.exists():
                logger.error(f"❌ Datos no encontrados en {country_dir}")
                return False
            
            logger.info(f"📊 Cargando datos de {country}...")
            self.nodes_df = pd.read_parquet(nodes_path)
            self.edges_df = pd.read_parquet(edges_path)
            
            logger.info(f"✅ Datos cargados: {len(self.nodes_df):,} nodos, {len(self.edges_df):,} aristas")
            
            # Crear grafo optimizado
            self._build_optimized_graph()
            
            # Crear índice espacial
            self._build_spatial_index()
            
            elapsed = time.time() - start_time
            logger.info(f"🎉 Sistema híbrido listo en {elapsed:.1f}s")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error cargando datos: {e}")
            return False
    
    def _build_optimized_graph(self):
        """Construye grafo NetworkX optimizado con travel times"""
        logger.info("🔧 Construyendo grafo optimizado...")
        start_time = time.time()
        
        self.graph = nx.DiGraph()
        
        # Agregar nodos con coordenadas
        for _, row in self.nodes_df.iterrows():
            node_id = row['id']
            lat, lon = row['lat'], row['lon']
            self.graph.add_node(node_id, lat=lat, lon=lon)
            self.node_coords[node_id] = (lat, lon)
        
        # Agregar aristas con travel times
        for _, row in self.edges_df.iterrows():
            from_id = row['from_id']
            to_id = row['to_id']
            distance = row['distance_m']
            highway_type = row['highway_type']
            maxspeed = row.get('maxspeed')
            
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
                weight=travel_time  # Usar travel_time como peso por defecto
            )
            
            # Agregar arista reversa si no es oneway
            oneway = row.get('oneway', False)
            if not oneway:
                self.graph.add_edge(
                    to_id, from_id,
                    distance=distance,
                    travel_time=travel_time,
                    highway_type=highway_type,
                    maxspeed=maxspeed,
                    weight=travel_time
                )
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Grafo construido en {elapsed:.1f}s: {self.graph.number_of_nodes():,} nodos, {self.graph.number_of_edges():,} aristas")
    
    def _build_spatial_index(self):
        """Construye R-tree para búsquedas espaciales rápidas"""
        logger.info("🗺️ Construyendo índice espacial...")
        start_time = time.time()
        
        # Crear índice R-tree
        self.spatial_index = index.Index()
        
        # Insertar nodos en el índice
        for node_id, (lat, lon) in self.node_coords.items():
            # R-tree usa (min_x, min_y, max_x, max_y)
            self.spatial_index.insert(node_id, (lon, lat, lon, lat))
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Índice espacial construido en {elapsed:.1f}s")
    
    @lru_cache(maxsize=10000)
    def find_nearest_node(self, lat: float, lon: float, max_distance_m: float = 1000) -> Optional[NearestNodeResult]:
        """Encuentra el nodo más cercano usando R-tree"""
        if not self.spatial_index:
            return None
        
        # Convertir distancia a grados aproximadamente
        deg_distance = max_distance_m / 111000  # ~111km por grado
        
        # Buscar nodos candidatos
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
        """Calcula ruta optimizada entre dos puntos"""
        start_time = time.time()
        
        # Snap to road
        origin_node = self.find_nearest_node(origin_lat, origin_lon)
        dest_node = self.find_nearest_node(dest_lat, dest_lon)
        
        if not origin_node or not dest_node:
            logger.warning("❌ No se pudo hacer snap-to-road")
            return None
        
        try:
            # Calcular ruta más corta
            path = nx.shortest_path(
                self.graph, 
                origin_node.node_id, 
                dest_node.node_id,
                weight=weight
            )
            
            # Calcular métricas de la ruta
            total_distance = 0
            total_travel_time = 0
            highway_types = []
            
            for i in range(len(path) - 1):
                edge_data = self.graph[path[i]][path[i+1]]
                total_distance += edge_data['distance']
                total_travel_time += edge_data['travel_time']
                highway_types.append(edge_data['highway_type'])
            
            # Velocidad promedio estimada
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
            logger.warning("❌ No hay ruta disponible entre los puntos")
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
            lat, lon = self.node_coords[node_id]
            coordinates.append((lat, lon))
        
        return coordinates
    
    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calcula distancia haversine en metros"""
        R = 6371000  # Radio de la Tierra en metros
        
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        
        a = (math.sin(dlat/2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2)
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas del sistema"""
        if not self.graph:
            return {"status": "not_loaded"}
        
        return {
            "status": "ready",
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "spatial_index": self.spatial_index is not None,
            "cache_size": self.find_nearest_node.cache_info().currsize if hasattr(self.find_nearest_node, 'cache_info') else 0
        }

# Singleton global
_hybrid_service = None

def get_hybrid_service() -> HybridCity2GraphService:
    """Obtiene instancia singleton del servicio híbrido"""
    global _hybrid_service
    if _hybrid_service is None:
        _hybrid_service = HybridCity2GraphService()
        _hybrid_service.load_data()
    return _hybrid_service

if __name__ == "__main__":
    # Test del sistema
    service = HybridCity2GraphService()
    
    if service.load_data():
        # Test de routing en Santiago
        origin_lat, origin_lon = -33.4378, -70.6504  # Plaza de Armas
        dest_lat, dest_lon = -33.4180, -70.6063      # Costanera Center
        
        result = service.route(origin_lat, origin_lon, dest_lat, dest_lon)
        
        if result:
            print(f"🎉 Ruta exitosa:")
            print(f"   📏 Distancia: {result.distance_m/1000:.1f}km")
            print(f"   ⏱️  Tiempo: {result.travel_time_s/60:.1f}min")
            print(f"   🚗 Velocidad promedio: {result.estimated_speed_kmh:.1f}km/h")
            print(f"   🛣️  Tipos de vía: {set(result.highway_types)}")
        
        print(f"📊 Stats: {service.get_stats()}")