"""
🏙️ CITY2GRAPH COMPLETE SERVICE - ANÁLISIS SEMÁNTICO URBANO COMPLETO
Servicio completo para análisis semántico de ciudades con OSM y NetworkX
"""

import osmnx as ox
import networkx as nx
import geopandas as gpd
from shapely.geometry import Point, Polygon
import pandas as pd
from typing import Dict, List, Tuple, Optional
import logging
import asyncio
from dataclasses import dataclass
import json
import pickle
import os
import numpy as np
import time
from sklearn.cluster import DBSCAN
from scipy.spatial import ConvexHull
import requests

# Configuración OSMnx
try:
    ox.settings.log_console = True
    ox.settings.use_cache = True
except AttributeError:
    # Para versiones más recientes de OSMnx
    pass

logger = logging.getLogger(__name__)

@dataclass
class SemanticDistrict:
    """Distrito urbano con análisis semántico completo"""
    name: str
    center: Tuple[float, float]
    polygon: Polygon
    district_type: str  # 'financial', 'tourist', 'residential', 'commercial', 'cultural', 'nightlife'
    walkability_score: float
    transit_accessibility: float
    cultural_context: Dict
    peak_hours: Dict
    poi_density: Dict
    confidence_score: float

@dataclass
class WalkabilityMetrics:
    """Métricas detalladas de walkability"""
    sidewalk_coverage: float
    intersection_density: float
    slope_difficulty: float
    safety_score: float
    accessibility_score: float
    overall_score: float

@dataclass
class TransitAccessibility:
    """Accesibilidad del transporte público"""
    metro_stations_nearby: int
    bus_stops_nearby: int
    accessibility_score: float
    average_wait_time: float
    transit_types: List[str]

class City2GraphCompleteService:
    """
    🧠 Servicio completo City2graph con análisis semántico profundo
    Proporciona clustering inteligente, walkability scoring y contexto cultural
    """
    
    def __init__(self, cache_dir: str = "city2graph_cache"):
        self.logger = logging.getLogger(__name__)
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
        # Cache de grafos y análisis por ciudad
        self.city_graphs = {}
        self.semantic_districts = {}
        self.walkability_cache = {}
        self.cultural_contexts = {}
        
        # Configuración de análisis semántico
        self.semantic_tags = {
            'financial': {
                'amenity': ['bank', 'atm'],
                'office': ['financial', 'insurance', 'company'],
                'shop': ['insurance']
            },
            'tourist': {
                'tourism': ['attraction', 'museum', 'gallery', 'viewpoint', 'artwork'],
                'historic': ['monument', 'memorial', 'castle', 'ruins'],
                'leisure': ['park', 'garden']
            },
            'commercial': {
                'shop': True,  # Todos los tipos de tiendas
                'amenity': ['restaurant', 'cafe', 'fast_food', 'bar', 'pub', 'marketplace']
            },
            'residential': {
                'building': ['residential', 'apartments', 'house'],
                'landuse': ['residential']
            },
            'cultural': {
                'amenity': ['theatre', 'cinema', 'library', 'arts_centre', 'community_centre'],
                'building': ['theatre', 'library'],
                'tourism': ['theatre']
            },
            'nightlife': {
                'amenity': ['bar', 'nightclub', 'pub', 'biergarten'],
                'leisure': ['adult_gaming_centre']
            },
            'transport': {
                'amenity': ['bus_station', 'taxi'],
                'railway': ['station', 'subway_entrance'],
                'aeroway': ['terminal'],
                'public_transport': ['station', 'stop_position']
            },
            'educational': {
                'amenity': ['school', 'university', 'college', 'kindergarten'],
                'building': ['school', 'university']
            },
            'healthcare': {
                'amenity': ['hospital', 'clinic', 'pharmacy', 'dentist', 'doctors'],
                'building': ['hospital']
            }
        }
        
    async def initialize_city(self, city_name: str, bbox: Tuple[float, float, float, float]) -> bool:
        """
        🏗️ Inicializar análisis completo de una ciudad
        Args:
            city_name: Nombre de la ciudad
            bbox: (north, south, east, west) - Límites de la ciudad
        """
        try:
            self.logger.info(f"🏙️ Inicializando análisis completo para {city_name}")
            start_time = time.time()
            
            # 1. Crear grafos multimodales
            await self._create_multimodal_graph(city_name, bbox)
            
            # 2. Análisis semántico de distritos
            await self._analyze_semantic_districts(city_name, bbox)
            
            # 3. Análisis de walkability
            await self._analyze_walkability(city_name)
            
            # 4. Análisis de transporte público
            await self._analyze_transit_network(city_name, bbox)
            
            # 5. Contexto cultural y horarios
            await self._analyze_cultural_context(city_name, bbox)
            
            total_time = time.time() - start_time
            self.logger.info(f"✅ {city_name} inicializada completamente en {total_time:.2f}s")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error inicializando {city_name}: {e}")
            return False
    
    async def _create_multimodal_graph(self, city_name: str, bbox: Tuple):
        """
        🚶‍♂️🚗🚌 Crear grafo multimodal (peatonal + vehicular + transporte)
        """
        cache_file = f"{self.cache_dir}/{city_name}_multimodal_graph.pkl"
        
        if os.path.exists(cache_file):
            self.logger.info(f"📂 Cargando grafo desde cache: {cache_file}")
            try:
                with open(cache_file, 'rb') as f:
                    self.city_graphs[city_name] = pickle.load(f)
                return
            except Exception as e:
                self.logger.warning(f"Error cargando cache, regenerando: {e}")
        
        self.logger.info(f"🔄 Creando grafo multimodal para {city_name}")
        
        graphs = {}
        
        try:
                        # 1. Grafo peatonal (con detalles de aceras, cruces, pendientes)
            self.logger.info("🚶‍♂️ Descargando grafo peatonal...")
            graphs['walk'] = ox.graph_from_bbox(
                north=bbox[0], south=bbox[1], east=bbox[2], west=bbox[3],
                network_type='walk',
                simplify=True,
                retain_all=True
            )
            
            # 2. Grafo vehicular
            self.logger.info("🚗 Descargando grafo vehicular...")
            graphs['drive'] = ox.graph_from_bbox(
                north=bbox[0], south=bbox[1], east=bbox[2], west=bbox[3],
                network_type='drive',
                simplify=True
            )
            
            # 3. Grafo de transporte público
            self.logger.info("🚌 Descargando red de transporte público...")
            try:
                graphs['transit'] = ox.graph_from_bbox(
                    north=bbox[0], south=bbox[1], east=bbox[2], west=bbox[3],
                    custom_filter='["highway"~"bus_guideway|busway"]|["railway"~"subway|light_rail|tram"]',
                    simplify=True
                )
            except Exception as e:
                self.logger.warning(f"No se pudo descargar red de transporte público: {e}")
                graphs['transit'] = None
            
            # Enriquecer grafos con datos adicionales
            for mode, graph in graphs.items():
                if graph and len(graph.nodes()) > 0:
                    self.logger.info(f"📊 Enriqueciendo grafo {mode}: {len(graph.nodes())} nodos, {len(graph.edges())} edges")
                    
                    # Calcular métricas específicas por modo
                    if mode == 'walk':
                        self._calculate_walkability_metrics(graph)
                    elif mode == 'drive':
                        self._calculate_driving_metrics(graph)
            
            self.city_graphs[city_name] = graphs
            
            # Guardar en cache
            try:
                with open(cache_file, 'wb') as f:
                    pickle.dump(graphs, f)
                self.logger.info(f"💾 Grafo guardado en cache: {cache_file}")
            except Exception as e:
                self.logger.warning(f"Error guardando cache: {e}")
                
        except Exception as e:
            self.logger.error(f"Error creando grafos: {e}")
            self.city_graphs[city_name] = {}
    
    def _calculate_walkability_metrics(self, graph):
        """
        🚶‍♂️ Calcular métricas de walkability para cada edge
        """
        try:
            # Agregar métricas de walkability a cada edge
            for u, v, data in graph.edges(data=True):
                # Métricas básicas
                length = data.get('length', 0)
                
                # Score de walkability basado en tipo de vía
                highway_type = data.get('highway', 'unclassified')
                walkability_score = self._get_walkability_score_by_highway_type(highway_type)
                
                # Agregar métricas al edge
                data['walkability_score'] = walkability_score
                data['pedestrian_friendly'] = walkability_score > 0.6
                
        except Exception as e:
            self.logger.warning(f"Error calculando walkability metrics: {e}")
    
    def _get_walkability_score_by_highway_type(self, highway_type: str) -> float:
        """
        🎯 Score de walkability por tipo de vía
        """
        walkability_scores = {
            'pedestrian': 1.0,
            'footway': 1.0,
            'path': 0.9,
            'steps': 0.8,
            'residential': 0.7,
            'living_street': 0.8,
            'unclassified': 0.6,
            'tertiary': 0.5,
            'secondary': 0.3,
            'primary': 0.2,
            'trunk': 0.1,
            'motorway': 0.0
        }
        
        if isinstance(highway_type, list):
            highway_type = highway_type[0]
            
        return walkability_scores.get(highway_type, 0.5)
    
    def _calculate_driving_metrics(self, graph):
        """
        🚗 Calcular métricas de conducción
        """
        try:
            for u, v, data in graph.edges(data=True):
                # Velocidad estimada por tipo de vía
                highway_type = data.get('highway', 'unclassified')
                max_speed = data.get('maxspeed', None)
                
                if max_speed:
                    try:
                        speed_kmh = int(max_speed) if isinstance(max_speed, str) and max_speed.isdigit() else 30
                    except:
                        speed_kmh = self._get_default_speed_by_highway_type(highway_type)
                else:
                    speed_kmh = self._get_default_speed_by_highway_type(highway_type)
                
                data['speed_kmh'] = speed_kmh
                
        except Exception as e:
            self.logger.warning(f"Error calculando driving metrics: {e}")
    
    def _get_default_speed_by_highway_type(self, highway_type: str) -> int:
        """
        🚗 Velocidad por defecto por tipo de vía
        """
        speeds = {
            'motorway': 100,
            'trunk': 80,
            'primary': 60,
            'secondary': 50,
            'tertiary': 40,
            'residential': 30,
            'living_street': 20,
            'unclassified': 30
        }
        
        if isinstance(highway_type, list):
            highway_type = highway_type[0]
            
        return speeds.get(highway_type, 30)
    
    async def _analyze_semantic_districts(self, city_name: str, bbox: Tuple):
        """
        🏛️ Análisis semántico de distritos urbanos
        """
        cache_file = f"{self.cache_dir}/{city_name}_semantic_districts.json"
        
        if os.path.exists(cache_file):
            self.logger.info(f"📂 Cargando distritos semánticos desde cache")
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    districts_data = json.load(f)
                    self.semantic_districts[city_name] = self._deserialize_districts(districts_data)
                return
            except Exception as e:
                self.logger.warning(f"Error cargando cache de distritos: {e}")
        
        self.logger.info(f"🧠 Analizando distritos semánticos de {city_name}")
        
        # Descargar POIs por categorías semánticas
        district_pois = {}
        
        for district_type, tags in self.semantic_tags.items():
            self.logger.info(f"📍 Descargando POIs para distrito: {district_type}")
            pois = []
            
            for key, values in tags.items():
                try:
                    if values is True:
                        # Descargar todos los valores para esta key
                        geometries = ox.features_from_bbox(
                            north=bbox[0], south=bbox[1], east=bbox[2], west=bbox[3],
                            tags=tag_dict
                        )
                    elif isinstance(values, list):
                        # Descargar valores específicos
                        for value in values:
                            try:
                                geometries = ox.geometries_from_bbox(
                                    bbox[0], bbox[1], bbox[2], bbox[3],
                                    tags={key: value}
                                )
                                
                                if not geometries.empty:
                                    points = self._geometries_to_points(geometries, district_type)
                                    pois.extend(points)
                                    
                            except Exception as e:
                                self.logger.debug(f"No se encontraron POIs para {key}={value}: {e}")
                                continue
                    
                except Exception as e:
                    self.logger.warning(f"Error descargando {key}: {e}")
                    continue
            
            district_pois[district_type] = pois
            self.logger.info(f"✅ {district_type}: {len(pois)} POIs encontrados")
        
        # Crear clusters semánticos
        districts = self._create_semantic_clusters(district_pois, city_name)
        self.semantic_districts[city_name] = districts
        
        # Guardar en cache
        try:
            districts_data = self._serialize_districts(districts)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(districts_data, f, ensure_ascii=False, indent=2)
            self.logger.info(f"💾 Distritos semánticos guardados en cache")
        except Exception as e:
            self.logger.warning(f"Error guardando cache de distritos: {e}")
    
    def _geometries_to_points(self, geometries, district_type: str) -> List[Dict]:
        """
        📍 Convertir geometrías OSM a puntos con metadatos
        """
        points = []
        
        for idx, geom in geometries.iterrows():
            try:
                # Obtener punto central
                if hasattr(geom.geometry, 'centroid'):
                    point = geom.geometry.centroid
                elif hasattr(geom.geometry, 'representative_point'):
                    point = geom.geometry.representative_point()
                else:
                    point = geom.geometry
                
                if point and hasattr(point, 'x') and hasattr(point, 'y'):
                    # Validar coordenadas
                    if -90 <= point.y <= 90 and -180 <= point.x <= 180:
                        poi_data = {
                            'lat': point.y,
                            'lon': point.x,
                            'name': geom.get('name', f'{district_type}_poi_{len(points)}'),
                            'type': district_type,
                            'osm_id': idx[1] if isinstance(idx, tuple) else str(idx),
                            'tags': {k: v for k, v in geom.items() if k not in ['geometry']}
                        }
                        points.append(poi_data)
                        
            except Exception as e:
                self.logger.debug(f"Error procesando geometría: {e}")
                continue
        
        return points
    
    def _create_semantic_clusters(self, district_pois: Dict, city_name: str) -> List[SemanticDistrict]:
        """
        🎯 Crear clusters semánticos de distritos
        """
        districts = []
        
        for district_type, pois in district_pois.items():
            if len(pois) < 3:  # Necesitamos mínimo 3 POIs para clustering significativo
                self.logger.info(f"⚠️ {district_type}: Solo {len(pois)} POIs, saltando clustering")
                continue
            
            self.logger.info(f"🔄 Clustering {len(pois)} POIs para {district_type}")
            
            try:
                # Preparar datos para clustering
                coords = np.array([[poi['lat'], poi['lon']] for poi in pois])
                
                # DBSCAN clustering (eps=0.01 ≈ 1km radius)
                clustering = DBSCAN(eps=0.01, min_samples=3).fit(coords)
                
                # Crear distritos por cluster
                unique_labels = set(clustering.labels_)
                if -1 in unique_labels:
                    unique_labels.remove(-1)  # Remover noise
                
                for cluster_id in unique_labels:
                    cluster_indices = [i for i, label in enumerate(clustering.labels_) if label == cluster_id]
                    cluster_pois = [pois[i] for i in cluster_indices]
                    
                    if len(cluster_pois) >= 3:
                        district = self._create_district_from_cluster(
                            cluster_pois, district_type, cluster_id, city_name
                        )
                        if district:
                            districts.append(district)
                            
            except Exception as e:
                self.logger.error(f"Error en clustering para {district_type}: {e}")
                continue
        
        self.logger.info(f"✅ Creados {len(districts)} distritos semánticos para {city_name}")
        return districts
    
    def _create_district_from_cluster(self, cluster_pois: List[Dict], district_type: str, 
                                    cluster_id: int, city_name: str) -> Optional[SemanticDistrict]:
        """
        🏗️ Crear distrito semántico desde un cluster de POIs
        """
        try:
            # Calcular centro del distrito
            center_lat = sum(poi['lat'] for poi in cluster_pois) / len(cluster_pois)
            center_lon = sum(poi['lon'] for poi in cluster_pois) / len(cluster_pois)
            
            # Crear polígono del distrito
            polygon = self._create_district_polygon(cluster_pois)
            
            # Calcular métricas del distrito
            confidence_score = min(1.0, len(cluster_pois) / 10.0)  # Más POIs = mayor confianza
            
            district = SemanticDistrict(
                name=f"{district_type.title()} District {cluster_id + 1}",
                center=(center_lat, center_lon),
                polygon=polygon,
                district_type=district_type,
                walkability_score=0.0,  # Se calculará después
                transit_accessibility=0.0,  # Se calculará después
                cultural_context=self._get_cultural_context(district_type),
                peak_hours=self._get_peak_hours(district_type),
                poi_density={
                    'total': len(cluster_pois), 
                    district_type: len(cluster_pois),
                    'density_per_km2': len(cluster_pois) / max(0.01, polygon.area * 111 * 111)  # Rough km2 conversion
                },
                confidence_score=confidence_score
            )
            
            return district
            
        except Exception as e:
            self.logger.error(f"Error creando distrito: {e}")
            return None
    
    def _create_district_polygon(self, cluster_pois: List[Dict]) -> Polygon:
        """
        🔷 Crear polígono que representa el distrito
        """
        try:
            if len(cluster_pois) >= 3:
                points = [(poi['lon'], poi['lat']) for poi in cluster_pois]
                
                # Intentar crear convex hull
                if len(points) >= 3:
                    hull = ConvexHull(points)
                    hull_points = [points[i] for i in hull.vertices]
                    return Polygon(hull_points)
            
            # Fallback: círculo alrededor del centro
            center_lat = sum(poi['lat'] for poi in cluster_pois) / len(cluster_pois)
            center_lon = sum(poi['lon'] for poi in cluster_pois) / len(cluster_pois)
            
            # Radio basado en dispersión de POIs
            max_distance = 0
            for poi in cluster_pois:
                dist = ((poi['lat'] - center_lat) ** 2 + (poi['lon'] - center_lon) ** 2) ** 0.5
                max_distance = max(max_distance, dist)
            
            radius = max(0.005, max_distance * 1.2)  # Mínimo 500m, o 120% de la dispersión
            return Point(center_lon, center_lat).buffer(radius)
            
        except Exception as e:
            self.logger.warning(f"Error creando polígono, usando círculo por defecto: {e}")
            center_lat = sum(poi['lat'] for poi in cluster_pois) / len(cluster_pois)
            center_lon = sum(poi['lon'] for poi in cluster_pois) / len(cluster_pois)
            return Point(center_lon, center_lat).buffer(0.005)  # 500m radius por defecto
    
    def _get_cultural_context(self, district_type: str) -> Dict:
        """
        🌍 Contexto cultural por tipo de distrito
        """
        cultural_contexts = {
            'financial': {
                'business_hours': '9:00-18:00',
                'busy_days': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
                'quiet_days': ['saturday', 'sunday'],
                'dress_code': 'formal',
                'pace': 'fast',
                'noise_level': 'moderate'
            },
            'commercial': {
                'business_hours': '10:00-22:00',
                'busy_days': ['friday', 'saturday', 'sunday'],
                'quiet_days': ['monday', 'tuesday'],
                'dress_code': 'casual',
                'pace': 'moderate',
                'noise_level': 'high'
            },
            'tourist': {
                'business_hours': '9:00-18:00',
                'busy_days': ['friday', 'saturday', 'sunday'],
                'quiet_days': ['monday', 'tuesday'],
                'dress_code': 'casual',
                'pace': 'slow',
                'noise_level': 'moderate',
                'photo_opportunities': 'high'
            },
            'nightlife': {
                'business_hours': '20:00-03:00',
                'busy_days': ['friday', 'saturday'],
                'quiet_days': ['sunday', 'monday', 'tuesday'],
                'dress_code': 'trendy',
                'pace': 'slow',
                'noise_level': 'very_high'
            },
            'cultural': {
                'business_hours': '10:00-18:00',
                'busy_days': ['saturday', 'sunday'],
                'quiet_days': ['monday'],
                'dress_code': 'smart_casual',
                'pace': 'slow',
                'noise_level': 'low'
            },
            'residential': {
                'business_hours': '24/7',
                'busy_days': ['saturday', 'sunday'],
                'quiet_days': ['weekdays'],
                'dress_code': 'casual',
                'pace': 'slow',
                'noise_level': 'low'
            }
        }
        
        return cultural_contexts.get(district_type, {
            'business_hours': '9:00-18:00',
            'busy_days': ['friday', 'saturday', 'sunday'],
            'dress_code': 'casual',
            'pace': 'moderate',
            'noise_level': 'moderate'
        })
    
    def _get_peak_hours(self, district_type: str) -> Dict:
        """
        ⏰ Horarios pico por tipo de distrito
        """
        peak_schedules = {
            'financial': {
                'morning_rush': (8, 10),
                'lunch_peak': (12, 14),
                'evening_rush': (17, 19),
                'quiet_hours': [(19, 24), (0, 8)]
            },
            'commercial': {
                'morning_start': (10, 12),
                'afternoon_peak': (14, 18),
                'evening_peak': (19, 21),
                'quiet_hours': [(21, 24), (0, 10)]
            },
            'tourist': {
                'morning_peak': (9, 11),
                'afternoon_peak': (14, 17),
                'evening_moderate': (18, 20),
                'quiet_hours': [(20, 24), (0, 9)]
            },
            'nightlife': {
                'evening_start': (20, 22),
                'night_peak': (22, 2),
                'late_night': (2, 4),
                'quiet_hours': [(4, 20)]
            },
            'residential': {
                'morning_activity': (7, 9),
                'evening_activity': (17, 20),
                'quiet_hours': [(22, 7)]
            },
            'cultural': {
                'afternoon_peak': (14, 17),
                'evening_events': (19, 22),
                'quiet_hours': [(22, 10)]
            }
        }
        
        return peak_schedules.get(district_type, {
            'general_hours': (9, 18),
            'quiet_hours': [(18, 9)]
        })
    
    async def _analyze_walkability(self, city_name: str):
        """
        🚶‍♂️ Análisis de walkability para cada distrito
        """
        if city_name not in self.semantic_districts or city_name not in self.city_graphs:
            self.logger.warning(f"No hay datos para analizar walkability de {city_name}")
            return
        
        walk_graph = self.city_graphs[city_name].get('walk')
        if not walk_graph:
            self.logger.warning(f"No hay grafo peatonal para {city_name}")
            return
        
        self.logger.info(f"🚶‍♂️ Analizando walkability para {len(self.semantic_districts[city_name])} distritos")
        
        for district in self.semantic_districts[city_name]:
            try:
                # Obtener nodos dentro del distrito
                district_nodes = []
                
                for node_id, node_data in walk_graph.nodes(data=True):
                    node_point = Point(node_data['x'], node_data['y'])
                    if district.polygon.contains(node_point):
                        district_nodes.append(node_id)
                
                if len(district_nodes) > 0:
                    # Calcular métricas de walkability
                    walkability_score = self._calculate_district_walkability(walk_graph, district_nodes)
                    district.walkability_score = walkability_score
                    
                    self.logger.debug(f"🎯 {district.name}: walkability {walkability_score:.2f}")
                else:
                    district.walkability_score = 0.5  # Score neutral si no hay datos
                    
            except Exception as e:
                self.logger.warning(f"Error calculando walkability para {district.name}: {e}")
                district.walkability_score = 0.5
    
    def _calculate_district_walkability(self, graph, district_nodes: List) -> float:
        """
        📊 Calcular score de walkability para un distrito
        """
        try:
            if len(district_nodes) == 0:
                return 0.5
            
            # Métricas de walkability
            total_walkability = 0
            edge_count = 0
            
            # Analizar edges dentro del distrito
            for u, v, data in graph.edges(data=True):
                if u in district_nodes or v in district_nodes:
                    walkability = data.get('walkability_score', 0.5)
                    total_walkability += walkability
                    edge_count += 1
            
            if edge_count > 0:
                avg_walkability = total_walkability / edge_count
            else:
                avg_walkability = 0.5
            
            # Factores adicionales
            connectivity_bonus = min(0.2, len(district_nodes) / 100)  # Más nodos = mejor conectividad
            
            final_score = min(1.0, avg_walkability + connectivity_bonus)
            return round(final_score, 2)
            
        except Exception as e:
            self.logger.warning(f"Error en cálculo de walkability: {e}")
            return 0.5
    
    async def _analyze_transit_network(self, city_name: str, bbox: Tuple):
        """
        🚌 Análisis de red de transporte público
        """
        self.logger.info(f"🚌 Analizando red de transporte público para {city_name}")
        
        try:
            # Descargar paradas de transporte público
            transit_stops = ox.features_from_bbox(
                north=bbox[0], south=bbox[1], east=bbox[2], west=bbox[3],
                tags={'public_transport': ['stop_position', 'platform'], 'highway': 'bus_stop', 'railway': ['station', 'halt']}
            )
            
            # Convertir a puntos
            stop_points = []
            if not transit_stops.empty:
                for idx, stop in transit_stops.iterrows():
                    try:
                        if hasattr(stop.geometry, 'centroid'):
                            point = stop.geometry.centroid
                        else:
                            point = stop.geometry
                        
                        if point and hasattr(point, 'x') and hasattr(point, 'y'):
                            stop_points.append({
                                'lat': point.y,
                                'lon': point.x,
                                'name': stop.get('name', 'Transit Stop'),
                                'type': stop.get('public_transport', 'stop')
                            })
                    except:
                        continue
            
            # Calcular accesibilidad de transporte para cada distrito
            if city_name in self.semantic_districts:
                for district in self.semantic_districts[city_name]:
                    accessibility = self._calculate_transit_accessibility(district, stop_points)
                    district.transit_accessibility = accessibility
                    
        except Exception as e:
            self.logger.warning(f"Error analizando transporte público: {e}")
    
    def _calculate_transit_accessibility(self, district: SemanticDistrict, stop_points: List[Dict]) -> float:
        """
        🎯 Calcular accesibilidad de transporte público para un distrito
        """
        try:
            district_center = Point(district.center[1], district.center[0])
            
            # Contar paradas dentro de diferentes radios
            nearby_stops_500m = 0
            nearby_stops_1km = 0
            
            for stop in stop_points:
                stop_point = Point(stop['lon'], stop['lat'])
                distance = district_center.distance(stop_point)
                
                if distance <= 0.005:  # ~500m
                    nearby_stops_500m += 1
                elif distance <= 0.01:  # ~1km
                    nearby_stops_1km += 1
            
            # Score basado en proximidad a paradas
            if nearby_stops_500m >= 3:
                score = 1.0
            elif nearby_stops_500m >= 1:
                score = 0.8
            elif nearby_stops_1km >= 2:
                score = 0.6
            elif nearby_stops_1km >= 1:
                score = 0.4
            else:
                score = 0.2
            
            return round(score, 2)
            
        except Exception as e:
            self.logger.warning(f"Error calculando accesibilidad de transporte: {e}")
            return 0.5
    
    async def _analyze_cultural_context(self, city_name: str, bbox: Tuple):
        """
        🌍 Análisis de contexto cultural
        """
        self.logger.info(f"🌍 Analizando contexto cultural para {city_name}")
        
        # Por ahora, usar contextos predefinidos
        # En el futuro se podrían obtener de APIs externas o análisis de reviews
        self.cultural_contexts[city_name] = {
            'timezone': 'America/Santiago',  # Será dinámico según ubicación
            'language': 'es',
            'currency': 'CLP',
            'business_culture': 'latin_american',
            'meal_times': {
                'breakfast': (7, 10),
                'lunch': (13, 15),
                'dinner': (20, 22)
            },
            'siesta_culture': False,
            'weekend_days': ['saturday', 'sunday']
        }
    
    def _serialize_districts(self, districts: List[SemanticDistrict]) -> List[Dict]:
        """
        💾 Serializar distritos para cache JSON
        """
        serialized = []
        
        for district in districts:
            try:
                # Convertir polígono a coordenadas
                if hasattr(district.polygon, 'exterior'):
                    coords = list(district.polygon.exterior.coords)
                else:
                    coords = [(district.center[1], district.center[0])]  # Fallback al centro
                
                district_dict = {
                    'name': district.name,
                    'center': district.center,
                    'polygon_coords': coords,
                    'district_type': district.district_type,
                    'walkability_score': district.walkability_score,
                    'transit_accessibility': district.transit_accessibility,
                    'cultural_context': district.cultural_context,
                    'peak_hours': district.peak_hours,
                    'poi_density': district.poi_density,
                    'confidence_score': district.confidence_score
                }
                
                serialized.append(district_dict)
                
            except Exception as e:
                self.logger.warning(f"Error serializando distrito {district.name}: {e}")
                continue
        
        return serialized
    
    def _deserialize_districts(self, districts_data: List[Dict]) -> List[SemanticDistrict]:
        """
        📂 Deserializar distritos desde cache JSON
        """
        districts = []
        
        for district_dict in districts_data:
            try:
                # Recrear polígono desde coordenadas
                coords = district_dict.get('polygon_coords', [])
                if len(coords) >= 3:
                    polygon = Polygon(coords)
                else:
                    center = district_dict['center']
                    polygon = Point(center[1], center[0]).buffer(0.005)
                
                district = SemanticDistrict(
                    name=district_dict['name'],
                    center=tuple(district_dict['center']),
                    polygon=polygon,
                    district_type=district_dict['district_type'],
                    walkability_score=district_dict.get('walkability_score', 0.5),
                    transit_accessibility=district_dict.get('transit_accessibility', 0.5),
                    cultural_context=district_dict.get('cultural_context', {}),
                    peak_hours=district_dict.get('peak_hours', {}),
                    poi_density=district_dict.get('poi_density', {}),
                    confidence_score=district_dict.get('confidence_score', 0.5)
                )
                
                districts.append(district)
                
            except Exception as e:
                self.logger.warning(f"Error deserializando distrito: {e}")
                continue
        
        return districts
    
    async def get_semantic_context(self, lat: float, lon: float, city_name: str) -> Dict:
        """
        🎯 Obtener contexto semántico de una ubicación específica
        """
        if city_name not in self.semantic_districts or not self.semantic_districts[city_name]:
            return {
                'district': 'Unknown',
                'district_type': 'general',
                'walkability_score': 0.5,
                'transit_accessibility': 0.5,
                'cultural_context': self._get_cultural_context('general'),
                'peak_hours': self._get_peak_hours('general'),
                'poi_density': {'total': 0},
                'confidence': 0.0,
                'recommendation': 'Initialize city analysis first'
            }
        
        point = Point(lon, lat)
        
        # Buscar distrito que contenga el punto
        for district in self.semantic_districts[city_name]:
            if district.polygon.contains(point):
                return {
                    'district': district.name,
                    'district_type': district.district_type,
                    'walkability_score': district.walkability_score,
                    'transit_accessibility': district.transit_accessibility,
                    'peak_hours': district.peak_hours,
                    'poi_density': district.poi_density,
                    'cultural_context': district.cultural_context,
                    'center': district.center,
                    'confidence': district.confidence_score,
                    'inside_district': True
                }
        
        # Si no está dentro de ningún distrito, buscar el más cercano
        if self.semantic_districts[city_name]:
            closest_district = min(
                self.semantic_districts[city_name],
                key=lambda d: Point(d.center[1], d.center[0]).distance(point)
            )
            
            distance_to_center = Point(closest_district.center[1], closest_district.center[0]).distance(point)
            
            return {
                'district': f"Near {closest_district.name}",
                'district_type': closest_district.district_type,
                'walkability_score': closest_district.walkability_score * 0.7,  # Penalizar por distancia
                'transit_accessibility': closest_district.transit_accessibility * 0.7,
                'peak_hours': closest_district.peak_hours,
                'poi_density': closest_district.poi_density,
                'cultural_context': closest_district.cultural_context,
                'center': closest_district.center,
                'distance_to_center_degrees': distance_to_center,
                'confidence': closest_district.confidence_score * 0.6,
                'inside_district': False
            }
        
        # Fallback si no hay distritos
        return {
            'district': 'Unanalyzed Area',
            'district_type': 'general',
            'walkability_score': 0.5,
            'transit_accessibility': 0.5,
            'cultural_context': self._get_cultural_context('general'),
            'peak_hours': self._get_peak_hours('general'),
            'poi_density': {'total': 0},
            'confidence': 0.1,
            'inside_district': False
        }
    
    async def get_smart_clustering_suggestions(self, places: List[Dict], city_name: str) -> Dict:
        """
        🧠 Sugerencias de clustering inteligente basado en análisis semántico
        """
        if city_name not in self.semantic_districts:
            return {
                'strategy': 'geographic',
                'reason': 'semantic_data_unavailable',
                'recommendation': f'Initialize {city_name} first with initialize_city()'
            }
        
        self.logger.info(f"🧠 Generando sugerencias de clustering semántico para {len(places)} lugares")
        
        # Analizar contexto semántico de cada lugar
        place_contexts = []
        for place in places:
            context = await self.get_semantic_context(place['lat'], place['lon'], city_name)
            place_contexts.append({
                'place': place,
                'context': context
            })
        
        # Agrupar por distritos semánticos
        district_groups = {}
        for pc in place_contexts:
            district = pc['context']['district']
            if district not in district_groups:
                district_groups[district] = []
            district_groups[district].append(pc)
        
        # Generar estrategias de clustering semántico
        suggestions = {
            'strategy': 'semantic',
            'city': city_name,
            'total_places': len(places),
            'district_groups': district_groups,
            'recommendations': [],
            'optimization_insights': []
        }
        
        for district, places_in_district in district_groups.items():
            if len(places_in_district) >= 2:
                first_context = places_in_district[0]['context']
                district_type = first_context['district_type']
                peak_hours = first_context['peak_hours']
                walkability = first_context['walkability_score']
                
                # Generar recomendación específica
                recommendation = {
                    'district': district,
                    'district_type': district_type,
                    'places_count': len(places_in_district),
                    'recommended_time_slots': peak_hours,
                    'walkability': walkability,
                    'transit_accessibility': first_context['transit_accessibility'],
                    'clustering_reason': f"Semantic grouping: {district_type} district",
                    'confidence': first_context['confidence'],
                    'optimization_tips': self._get_optimization_tips(district_type, walkability)
                }
                
                suggestions['recommendations'].append(recommendation)
        
        # Insights de optimización general
        suggestions['optimization_insights'] = self._generate_optimization_insights(suggestions)
        
        return suggestions
    
    def _get_optimization_tips(self, district_type: str, walkability: float) -> List[str]:
        """
        💡 Tips de optimización por tipo de distrito
        """
        tips = []
        
        # Tips por tipo de distrito
        district_tips = {
            'financial': [
                "Visit during business hours (9-18) for full experience",
                "Avoid lunch rush (12-14) for better restaurant availability"
            ],
            'tourist': [
                "Best visited in morning (9-11) or late afternoon (15-17)",
                "Allow extra time for photos and exploration"
            ],
            'commercial': [
                "Shopping centers busiest on weekends",
                "Restaurant lunch deals typically 12-15"
            ],
            'nightlife': [
                "Plan for evening visits (20:00+)",
                "Consider area may be quiet during daytime"
            ],
            'cultural': [
                "Check opening hours - many closed Mondays",
                "Allow 2-3 hours per major cultural site"
            ]
        }
        
        tips.extend(district_tips.get(district_type, ["Standard urban area - plan accordingly"]))
        
        # Tips por walkability
        if walkability >= 0.8:
            tips.append("Excellent walkability - consider walking between venues")
        elif walkability >= 0.6:
            tips.append("Good walkability - short walks between nearby places")
        elif walkability >= 0.4:
            tips.append("Moderate walkability - consider transportation for longer distances")
        else:
            tips.append("Limited walkability - transportation recommended between venues")
        
        return tips
    
    def _generate_optimization_insights(self, suggestions: Dict) -> List[str]:
        """
        📊 Generar insights de optimización general
        """
        insights = []
        
        total_districts = len(suggestions['district_groups'])
        clusterable_districts = len(suggestions['recommendations'])
        
        if clusterable_districts >= 2:
            insights.append(f"✅ Great semantic clustering potential: {clusterable_districts} distinct districts identified")
        
        # Análisis de tipos de distrito
        district_types = [rec['district_type'] for rec in suggestions['recommendations']]
        type_counts = {}
        for dt in district_types:
            type_counts[dt] = type_counts.get(dt, 0) + 1
        
        if len(type_counts) >= 3:
            insights.append("🎯 Diverse experience: Multiple district types for varied itinerary")
        
        # Análisis de walkability
        walkabilities = [rec['walkability'] for rec in suggestions['recommendations']]
        if walkabilities:
            avg_walkability = sum(walkabilities) / len(walkabilities)
            if avg_walkability >= 0.7:
                insights.append("🚶‍♂️ High walkability areas - optimize for pedestrian routes")
            elif avg_walkability <= 0.4:
                insights.append("🚗 Low walkability - transportation optimization priority")
        
        return insights
    
    def get_city_summary(self, city_name: str) -> Dict:
        """
        📊 Resumen completo del análisis de la ciudad
        """
        if city_name not in self.semantic_districts:
            return {
                'city': city_name,
                'status': 'not_initialized',
                'districts': 0
            }
        
        districts = self.semantic_districts[city_name]
        
        # Estadísticas por tipo de distrito
        district_types = {}
        total_walkability = 0
        total_transit = 0
        
        for district in districts:
            dt = district.district_type
            district_types[dt] = district_types.get(dt, 0) + 1
            total_walkability += district.walkability_score
            total_transit += district.transit_accessibility
        
        avg_walkability = total_walkability / len(districts) if districts else 0
        avg_transit = total_transit / len(districts) if districts else 0
        
        return {
            'city': city_name,
            'status': 'initialized',
            'total_districts': len(districts),
            'district_types': district_types,
            'average_walkability': round(avg_walkability, 2),
            'average_transit_accessibility': round(avg_transit, 2),
            'graphs_available': list(self.city_graphs.get(city_name, {}).keys()),
            'cultural_context': self.cultural_contexts.get(city_name, {})
        }