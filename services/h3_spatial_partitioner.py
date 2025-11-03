#!/usr/bin/env python3
"""
🗺️ H3 Spatial Partitioner - Indexación espacial profesional
Implementa clustering automático y bounding boxes según recomendaciones
"""

import h3
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Set, Optional
from dataclasses import dataclass
from collections import defaultdict
import logging
from pathlib import Path
import json
import pickle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class H3Cluster:
    """Representa un cluster H3 con metadatos"""
    h3_id: str
    center_lat: float
    center_lon: float
    bbox_north: float
    bbox_south: float
    bbox_east: float
    bbox_west: float
    poi_count: int
    city_name: Optional[str] = None
    region_name: Optional[str] = None
    area_km2: Optional[float] = None

@dataclass
class RoutingSession:
    """Sesión de routing con cluster automático"""
    session_id: str
    main_cluster: str
    clusters: List[str]
    pois: List[Dict]
    bbox: Tuple[float, float, float, float]  # north, south, east, west
    estimated_area_km2: float

class H3SpatialPartitioner:
    """
    Particionador espacial H3 profesional para routing eficiente
    Implementa recomendaciones de clustering automático por ciudades
    """
    
    def __init__(self, resolution: int = 5):
        """
        Inicializa particionador H3
        
        Args:
            resolution: Resolución H3 (5 = ~2.5km hexágonos, 6 = ~0.9km)
        """
        self.resolution = resolution
        self.clusters: Dict[str, H3Cluster] = {}
        self.city_mappings: Dict[str, str] = {}  # h3_id -> city_name
        self.cache_file = Path(__file__).parent.parent / "cache" / "h3_clusters_cache.pkl"
        
        logger.info(f"🗺️ H3Partitioner iniciado - Resolución: {resolution}")
        
        # Cargar cache si existe
        self._load_cache()
    
    def coordinate_to_h3(self, lat: float, lon: float) -> str:
        """
        Convierte coordenadas geográficas a ID H3
        
        Args:
            lat: Latitud
            lon: Longitud
            
        Returns:
            ID de celda H3
        """
        return h3.latlng_to_cell(lat, lon, self.resolution)
    
    def h3_to_coordinate(self, h3_id: str) -> Tuple[float, float]:
        """
        Convierte ID H3 a coordenadas del centro
        
        Args:
            h3_id: ID de celda H3
            
        Returns:
            (lat, lon) del centro de la celda
        """
        lat, lon = h3.cell_to_latlng(h3_id)
        return lat, lon
    
    def get_h3_bbox(self, h3_id: str) -> Tuple[float, float, float, float]:
        """
        Obtiene bounding box de una celda H3
        
        Args:
            h3_id: ID de celda H3
            
        Returns:
            (north, south, east, west) bounding box
        """
        boundary = h3.cell_to_boundary(h3_id)
        
        lats = [point[0] for point in boundary]
        lons = [point[1] for point in boundary]
        
        return (
            max(lats),  # north
            min(lats),  # south
            max(lons),  # east
            min(lons)   # west
        )
    
    def cluster_pois_auto(self, pois: List[Dict]) -> RoutingSession:
        """
        Clustering automático de POIs por proximidad geográfica
        
        Args:
            pois: Lista de POIs con lat/lon
            
        Returns:
            Sesión de routing con clusters automáticos
        """
        if not pois:
            raise ValueError("Lista de POIs vacía")
        
        logger.info(f"🔍 Clustering automático de {len(pois)} POIs...")
        
        # Convertir POIs a H3
        poi_h3_map = {}
        h3_counter = defaultdict(list)
        
        for i, poi in enumerate(pois):
            h3_id = self.coordinate_to_h3(poi['lat'], poi['lon'])
            poi_h3_map[i] = h3_id
            h3_counter[h3_id].append(i)
        
        # Encontrar cluster principal (más POIs)
        main_cluster = max(h3_counter.keys(), key=lambda x: len(h3_counter[x]))
        main_cluster_pois = len(h3_counter[main_cluster])
        
        logger.info(f"🎯 Cluster principal: {main_cluster} ({main_cluster_pois} POIs)")
        
        # Obtener clusters vecinos si es necesario
        all_clusters = set(h3_counter.keys())
        
        if len(all_clusters) > 1:
            # Expandir con vecinos del cluster principal
            neighbors = set(h3.grid_ring(main_cluster, 1))
            relevant_clusters = all_clusters.intersection(neighbors)
            relevant_clusters.add(main_cluster)
        else:
            relevant_clusters = all_clusters
        
        # Calcular bounding box total
        all_lats = [poi['lat'] for poi in pois]
        all_lons = [poi['lon'] for poi in pois]
        
        bbox = (
            max(all_lats),  # north
            min(all_lats),  # south
            max(all_lons),  # east
            min(all_lons)   # west
        )
        
        # Estimar área
        lat_diff = bbox[0] - bbox[1]
        lon_diff = bbox[2] - bbox[3]
        estimated_area = lat_diff * lon_diff * 111.32 * 111.32  # km²
        
        session = RoutingSession(
            session_id=f"session_{len(pois)}_{str(hash(str(sorted(all_clusters))))[:8]}",
            main_cluster=main_cluster,
            clusters=list(relevant_clusters),
            pois=pois,
            bbox=bbox,
            estimated_area_km2=estimated_area
        )
        
        logger.info(f"✅ Clustering completado:")
        logger.info(f"   Clusters: {len(relevant_clusters)}")
        logger.info(f"   Área estimada: {estimated_area:.1f}km²")
        logger.info(f"   Bbox: {bbox}")
        
        return session
    
    def detect_cities_from_pois(self, pois: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Detecta ciudades automáticamente basándose en clustering de POIs
        
        Args:
            pois: Lista de POIs con lat/lon
            
        Returns:
            Diccionario {ciudad_estimada: [pois_en_ciudad]}
        """
        logger.info(f"🏙️ Detectando ciudades desde {len(pois)} POIs...")
        
        # Agrupar por H3
        h3_groups = defaultdict(list)
        for poi in pois:
            h3_id = self.coordinate_to_h3(poi['lat'], poi['lon'])
            h3_groups[h3_id].append(poi)
        
        # Detectar ciudades principales (>= 3 POIs por cluster)
        cities = {}
        city_counter = 1
        
        for h3_id, poi_group in h3_groups.items():
            if len(poi_group) >= 3:  # Mínimo POIs para considerar "ciudad"
                # Estimar nombre de ciudad basándose en coordenadas
                center_lat, center_lon = self.h3_to_coordinate(h3_id)
                city_name = self._estimate_city_name(center_lat, center_lon)
                
                if not city_name:
                    city_name = f"Cluster_{city_counter}"
                    city_counter += 1
                
                cities[city_name] = poi_group
                
                logger.info(f"   📍 {city_name}: {len(poi_group)} POIs ({center_lat:.4f}, {center_lon:.4f})")
        
        # POIs restantes van a "Other"
        remaining_pois = []
        for h3_id, poi_group in h3_groups.items():
            if len(poi_group) < 3:
                remaining_pois.extend(poi_group)
        
        if remaining_pois:
            cities["Other"] = remaining_pois
            logger.info(f"   📍 Other: {len(remaining_pois)} POIs")
        
        return cities
    
    def _estimate_city_name(self, lat: float, lon: float) -> Optional[str]:
        """
        Estima nombre de ciudad basándose en coordenadas (mapping básico Chile)
        
        Args:
            lat: Latitud
            lon: Longitud
            
        Returns:
            Nombre estimado de ciudad o None
        """
        # Mapping básico de ciudades principales de Chile
        chile_cities = [
            ("Santiago", -33.4489, -70.6693, 0.5),
            ("Valparaíso", -33.0472, -71.6127, 0.3),
            ("Concepción", -36.8201, -73.0444, 0.3),
            ("La Serena", -29.9027, -71.2519, 0.2),
            ("Antofagasta", -23.6509, -70.3975, 0.2),
            ("Temuco", -38.7359, -72.5904, 0.2),
            ("Valdivia", -39.8142, -73.2459, 0.2),
            ("Puerto Montt", -41.4693, -72.9424, 0.2),
            ("Punta Arenas", -53.1638, -70.9171, 0.3),
            ("Iquique", -20.2307, -70.1355, 0.2),
            ("Calama", -22.4667, -68.9167, 0.2),
            ("Copiapó", -27.3668, -70.3323, 0.2),
        ]
        
        for city_name, city_lat, city_lon, radius in chile_cities:
            distance = ((lat - city_lat) ** 2 + (lon - city_lon) ** 2) ** 0.5
            if distance <= radius:
                return city_name
        
        return None
    
    def create_cluster_metadata(self, h3_id: str, pois: List[Dict]) -> H3Cluster:
        """
        Crea metadatos completos para un cluster H3
        
        Args:
            h3_id: ID de celda H3
            pois: POIs en este cluster
            
        Returns:
            Objeto H3Cluster con metadatos
        """
        center_lat, center_lon = self.h3_to_coordinate(h3_id)
        bbox = self.get_h3_bbox(h3_id)
        
        # Calcular área aproximada
        area_km2 = h3.average_hexagon_area(self.resolution, unit='km^2')
        
        # Estimar ciudad
        city_name = self._estimate_city_name(center_lat, center_lon)
        
        cluster = H3Cluster(
            h3_id=h3_id,
            center_lat=center_lat,
            center_lon=center_lon,
            bbox_north=bbox[0],
            bbox_south=bbox[1],
            bbox_east=bbox[2],
            bbox_west=bbox[3],
            poi_count=len(pois),
            city_name=city_name,
            area_km2=area_km2
        )
        
        self.clusters[h3_id] = cluster
        return cluster
    
    def get_clusters_for_bbox(self, bbox: Tuple[float, float, float, float]) -> List[str]:
        """
        Obtiene todas las celdas H3 que intersectan con un bounding box
        
        Args:
            bbox: (north, south, east, west)
            
        Returns:
            Lista de IDs H3 que intersectan el área
        """
        north, south, east, west = bbox
        
        # Crear polígono del bbox
        bbox_polygon = [
            [north, west],  # noroeste
            [north, east],  # noreste
            [south, east],  # sureste
            [south, west],  # suroeste
        ]
        
        # Obtener celdas H3 que cubren el polígono
        h3_cells = h3.polygon_to_cells(bbox_polygon, self.resolution)
        
        return list(h3_cells)
    
    def _save_cache(self):
        """Guarda clusters en cache para reutilización"""
        try:
            self.cache_file.parent.mkdir(exist_ok=True)
            with open(self.cache_file, 'wb') as f:
                pickle.dump({
                    'clusters': self.clusters,
                    'city_mappings': self.city_mappings,
                    'resolution': self.resolution
                }, f)
            logger.info(f"💾 Cache H3 guardado: {len(self.clusters)} clusters")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo guardar cache H3: {e}")
    
    def _load_cache(self):
        """Carga clusters desde cache si existe"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'rb') as f:
                    cache_data = pickle.load(f)
                
                if cache_data.get('resolution') == self.resolution:
                    self.clusters = cache_data.get('clusters', {})
                    self.city_mappings = cache_data.get('city_mappings', {})
                    logger.info(f"💾 Cache H3 cargado: {len(self.clusters)} clusters")
                else:
                    logger.warning("⚠️ Cache H3 con resolución diferente, ignorando")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo cargar cache H3: {e}")

if __name__ == "__main__":
    """Test del particionador H3"""
    
    print("🗺️ TESTING H3 SPATIAL PARTITIONER")
    print("=" * 50)
    
    # Crear particionador
    partitioner = H3SpatialPartitioner(resolution=5)
    
    # POIs de prueba (tour gastronómico norte)
    test_pois = [
        {"name": "BLACK ANTOFAGASTA", "lat": -23.6509, "lon": -70.3975},
        {"name": "La Franchuteria", "lat": -23.6400, "lon": -70.4100},
        {"name": "McDonald's Antofagasta", "lat": -23.6600, "lon": -70.3800},
        {"name": "Restaurant La Serena", "lat": -29.9027, "lon": -71.2519},
        {"name": "Café Copiapó", "lat": -27.3668, "lon": -70.3323}
    ]
    
    print(f"📍 Testing con {len(test_pois)} POIs")
    
    # Test clustering automático
    session = partitioner.cluster_pois_auto(test_pois)
    
    print(f"\n✅ Sesión creada:")
    print(f"   ID: {session.session_id}")
    print(f"   Cluster principal: {session.main_cluster}")
    print(f"   Total clusters: {len(session.clusters)}")
    print(f"   Área estimada: {session.estimated_area_km2:.1f}km²")
    print(f"   Bbox: {session.bbox}")
    
    # Test detección de ciudades
    cities = partitioner.detect_cities_from_pois(test_pois)
    
    print(f"\n🏙️ Ciudades detectadas:")
    for city, city_pois in cities.items():
        print(f"   {city}: {len(city_pois)} POIs")
    
    # Test conversiones H3
    santiago_h3 = partitioner.coordinate_to_h3(-33.4489, -70.6693)
    santiago_coords = partitioner.h3_to_coordinate(santiago_h3)
    santiago_bbox = partitioner.get_h3_bbox(santiago_h3)
    
    print(f"\n🎯 Test Santiago:")
    print(f"   H3 ID: {santiago_h3}")
    print(f"   Centro: {santiago_coords}")
    print(f"   Bbox: {santiago_bbox}")
    
    # Guardar cache
    partitioner._save_cache()
    
    print(f"\n✅ Test H3 Partitioner completado")