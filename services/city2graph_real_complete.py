"""
🌍 CITY2GRAPH REAL - IMPLEMENTACIÓN COMPLETA CON OSM
Sistema completo con descarga de datos reales de OpenStreetMap
Configurado para esperar el tiempo que sea necesario (sin timeouts)
"""

import logging
import asyncio
import aiohttp
import requests
import osmnx as ox
import networkx as nx
import geopandas as gpd
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field
from shapely.geometry import Point, Polygon, MultiPolygon
import numpy as np
from sklearn.cluster import DBSCAN
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
import warnings

# Configurar para evitar warnings y timeouts
warnings.filterwarnings('ignore')
ox.settings.timeout = 300  # 5 minutos por request
ox.settings.max_query_area_size = 50000000000  # Área máxima grande

logger = logging.getLogger(__name__)

@dataclass
class RealSemanticDistrict:
    name: str
    center: Tuple[float, float]
    polygon: Polygon
    district_type: str
    walkability_score: float
    transit_accessibility: float
    cultural_context: Dict
    peak_hours: Dict
    real_pois: List[Dict]
    street_network_density: float
    public_transport_nodes: int
    confidence_score: float
    osm_data_quality: str

class RealCity2GraphService:
    """
    🏙️ Servicio City2Graph REAL con datos completos de OSM
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.districts = {}
        self.street_networks = {}
        self.poi_data = {}
        self.transport_networks = {}
        
        # Configuraciones para descarga masiva sin timeout
        self.session_timeout = aiohttp.ClientTimeout(total=None)  # Sin timeout
        self.request_timeout = 600  # 10 minutos por request individual
        
        # Cache para evitar re-descargas
        self.cache_dir = "city2graph_real_cache"
        os.makedirs(self.cache_dir, exist_ok=True)
        
        self.logger.info("🌍 RealCity2GraphService inicializado con timeouts extendidos")
    
    async def initialize_city_real(self, city_name: str, bbox: Tuple[float, float, float, float]) -> bool:
        """
        🏗️ Inicialización REAL con descarga completa de datos OSM
        bbox: (south, north, west, east)
        """
        try:
            self.logger.info(f"🌍 Iniciando descarga COMPLETA de datos OSM para {city_name}")
            self.logger.info(f"📦 Bounding box: {bbox}")
            
            start_time = time.time()
            
            # PASO 1: Descargar red de calles
            await self._download_street_network(city_name, bbox)
            
            # PASO 2: Descargar POIs masivamente
            await self._download_real_pois(city_name, bbox)
            
            # PASO 3: Descargar red de transporte público
            await self._download_transport_network(city_name, bbox)
            
            # PASO 4: Crear distritos semánticos reales
            await self._create_real_semantic_districts(city_name, bbox)
            
            # PASO 5: Calcular métricas reales
            await self._calculate_real_metrics(city_name)
            
            total_time = time.time() - start_time
            self.logger.info(f"✅ {city_name} inicializada COMPLETAMENTE en {total_time:.1f}s")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error inicializando {city_name} REAL: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _download_street_network(self, city_name: str, bbox: Tuple) -> bool:
        """
        🛣️ Descargar red completa de calles usando OSMnx
        """
        try:
            cache_file = os.path.join(self.cache_dir, f"{city_name}_streets.graphml")
            
            if os.path.exists(cache_file):
                self.logger.info(f"📂 Cargando red de calles desde cache: {cache_file}")
                G = ox.load_graphml(cache_file)
            else:
                self.logger.info(f"🌐 Descargando red de calles de OSM para {city_name}...")
                self.logger.info("⏳ Esto puede tomar varios minutos - SIN TIMEOUT")
                
                # Usar coordenadas del bbox para OSMnx
                south, north, west, east = bbox
                
                # Descargar red completa (drive + walk)
                self.logger.info("🚗 Descargando red de conducción...")
                G_drive = ox.graph_from_bbox(bbox=(north, south, east, west), network_type='drive')
                
                self.logger.info("🚶‍♂️ Descargando red peatonal...")
                G_walk = ox.graph_from_bbox(bbox=(north, south, east, west), network_type='walk')
                
                # Combinar ambas redes
                self.logger.info("🔗 Combinando redes de transporte...")
                G = nx.compose(G_drive, G_walk)
                
                # Guardar en cache
                ox.save_graphml(G, cache_file)
                self.logger.info(f"💾 Red guardada en cache: {cache_file}")
            
            # Almacenar en memoria
            self.street_networks[city_name] = G
            
            # Estadísticas de la red
            nodes = len(G.nodes())
            edges = len(G.edges())
            self.logger.info(f"📊 Red de {city_name}: {nodes:,} nodos, {edges:,} aristas")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error descargando red de calles: {e}")
            return False
    
    async def _download_real_pois(self, city_name: str, bbox: Tuple) -> bool:
        """
        🏛️ Descarga masiva de POIs reales desde OSM
        """
        try:
            cache_file = os.path.join(self.cache_dir, f"{city_name}_pois.json")
            
            if os.path.exists(cache_file):
                self.logger.info(f"📂 Cargando POIs desde cache: {cache_file}")
                with open(cache_file, 'r', encoding='utf-8') as f:
                    self.poi_data[city_name] = json.load(f)
            else:
                self.logger.info(f"🏛️ Descargando POIs masivamente de OSM para {city_name}...")
                self.logger.info("⏳ Descarga masiva - SIN TIMEOUT")
                
                south, north, west, east = bbox
                all_pois = []
                
                # Categorías principales de POIs
                poi_categories = {
                    'tourism': ['attraction', 'museum', 'monument', 'viewpoint', 'artwork'],
                    'amenity': ['restaurant', 'cafe', 'bar', 'pub', 'bank', 'hospital', 'school', 'university'],
                    'shop': ['mall', 'supermarket', 'department_store', 'clothes', 'electronics'],
                    'leisure': ['park', 'garden', 'sports_centre', 'stadium'],
                    'public_transport': ['station', 'stop_position', 'platform'],
                    'office': ['government', 'company', 'financial'],
                    'accommodation': ['hotel', 'hostel', 'guest_house']
                }
                
                for category, tags in poi_categories.items():
                    self.logger.info(f"📍 Descargando {category} POIs...")
                    
                    try:
                        # Construir tags dict para OSMnx
                        tags_dict = {category: tags}
                        
                        # Descargar con timeout extendido
                        pois = ox.features_from_bbox(bbox=(north, south, east, west), tags=tags_dict)
                        
                        if not pois.empty:
                            # Procesar POIs
                            for idx, poi in pois.iterrows():
                                try:
                                    # Obtener coordenadas del centroide
                                    if hasattr(poi.geometry, 'centroid'):
                                        centroid = poi.geometry.centroid
                                        lat, lon = centroid.y, centroid.x
                                    else:
                                        lat, lon = poi.geometry.y, poi.geometry.x
                                    
                                    poi_data = {
                                        'name': poi.get('name', f'{category} place'),
                                        'category': category,
                                        'subcategory': poi.get(category, 'unknown'),
                                        'lat': float(lat),
                                        'lon': float(lon),
                                        'osm_id': str(idx),
                                        'amenity': poi.get('amenity', ''),
                                        'tourism': poi.get('tourism', ''),
                                        'shop': poi.get('shop', ''),
                                        'leisure': poi.get('leisure', ''),
                                        'address': poi.get('addr:full', ''),
                                        'opening_hours': poi.get('opening_hours', ''),
                                        'website': poi.get('website', ''),
                                        'phone': poi.get('phone', ''),
                                        'source': 'osm_real'
                                    }
                                    
                                    all_pois.append(poi_data)
                                    
                                except Exception as e:
                                    self.logger.debug(f"Error procesando POI: {e}")
                                    continue
                        
                        self.logger.info(f"✅ {category}: {len(pois) if not pois.empty else 0} POIs descargados")
                        
                        # Pequeña pausa entre categorías
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        self.logger.warning(f"⚠️ Error descargando {category} POIs: {e}")
                        continue
                
                # Guardar en cache
                self.poi_data[city_name] = all_pois
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(all_pois, f, ensure_ascii=False, indent=2)
                
                self.logger.info(f"💾 {len(all_pois)} POIs guardados en cache: {cache_file}")
            
            self.logger.info(f"📊 POIs reales de {city_name}: {len(self.poi_data[city_name]):,} lugares")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error descargando POIs reales: {e}")
            return False
    
    async def _download_transport_network(self, city_name: str, bbox: Tuple) -> bool:
        """
        🚌 Descargar red de transporte público real
        """
        try:
            cache_file = os.path.join(self.cache_dir, f"{city_name}_transport.json")
            
            if os.path.exists(cache_file):
                self.logger.info(f"📂 Cargando transporte desde cache: {cache_file}")
                with open(cache_file, 'r', encoding='utf-8') as f:
                    self.transport_networks[city_name] = json.load(f)
            else:
                self.logger.info(f"🚌 Descargando red de transporte público para {city_name}...")
                
                south, north, west, east = bbox
                transport_data = {
                    'stations': [],
                    'routes': [],
                    'stops': []
                }
                
                # Descargar estaciones de metro/tren
                try:
                    self.logger.info("🚇 Descargando estaciones de metro...")
                    metro_tags = {'railway': ['station', 'subway_entrance'], 'public_transport': ['station']}
                    metros = ox.features_from_bbox(bbox=(north, south, east, west), tags=metro_tags)
                    
                    if not metros.empty:
                        for idx, metro in metros.iterrows():
                            try:
                                if hasattr(metro.geometry, 'centroid'):
                                    centroid = metro.geometry.centroid
                                    lat, lon = centroid.y, centroid.x
                                else:
                                    lat, lon = metro.geometry.y, metro.geometry.x
                                
                                station = {
                                    'name': metro.get('name', 'Metro Station'),
                                    'type': 'metro',
                                    'lat': float(lat),
                                    'lon': float(lon),
                                    'railway': metro.get('railway', ''),
                                    'public_transport': metro.get('public_transport', ''),
                                    'osm_id': str(idx)
                                }
                                transport_data['stations'].append(station)
                            except:
                                continue
                        
                        self.logger.info(f"✅ Metro: {len(transport_data['stations'])} estaciones")
                
                except Exception as e:
                    self.logger.warning(f"⚠️ Error descargando metro: {e}")
                
                # Descargar paradas de bus
                try:
                    self.logger.info("🚌 Descargando paradas de bus...")
                    bus_tags = {'highway': 'bus_stop', 'public_transport': ['stop_position', 'platform']}
                    buses = ox.features_from_bbox(bbox=(north, south, east, west), tags=bus_tags)
                    
                    if not buses.empty:
                        for idx, bus in buses.iterrows():
                            try:
                                if hasattr(bus.geometry, 'centroid'):
                                    centroid = bus.geometry.centroid
                                    lat, lon = centroid.y, centroid.x
                                else:
                                    lat, lon = bus.geometry.y, bus.geometry.x
                                
                                stop = {
                                    'name': bus.get('name', 'Bus Stop'),
                                    'type': 'bus',
                                    'lat': float(lat),
                                    'lon': float(lon),
                                    'highway': bus.get('highway', ''),
                                    'public_transport': bus.get('public_transport', ''),
                                    'osm_id': str(idx)
                                }
                                transport_data['stops'].append(stop)
                            except:
                                continue
                        
                        self.logger.info(f"✅ Bus: {len(transport_data['stops'])} paradas")
                
                except Exception as e:
                    self.logger.warning(f"⚠️ Error descargando buses: {e}")
                
                # Guardar en cache
                self.transport_networks[city_name] = transport_data
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(transport_data, f, ensure_ascii=False, indent=2)
                
                self.logger.info(f"💾 Transporte guardado en cache: {cache_file}")
            
            transport = self.transport_networks[city_name]
            total_transport = len(transport['stations']) + len(transport['stops'])
            self.logger.info(f"📊 Transporte público de {city_name}: {total_transport} puntos")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error descargando transporte: {e}")
            return False
    
    async def _create_real_semantic_districts(self, city_name: str, bbox: Tuple) -> bool:
        """
        🏛️ Crear distritos semánticos REALES basados en datos OSM
        """
        try:
            self.logger.info(f"🧠 Creando distritos semánticos REALES para {city_name}")
            
            pois = self.poi_data.get(city_name, [])
            if not pois:
                self.logger.warning("⚠️ No hay POIs disponibles para crear distritos")
                return False
            
            # Agrupar POIs por categoría
            poi_by_category = {}
            for poi in pois:
                category = poi.get('category', 'unknown')
                if category not in poi_by_category:
                    poi_by_category[category] = []
                poi_by_category[category].append(poi)
            
            self.logger.info(f"📊 Categorías encontradas: {list(poi_by_category.keys())}")
            
            districts = []
            
            # Crear distritos por clustering de POIs similares
            for category, category_pois in poi_by_category.items():
                if len(category_pois) < 3:  # Necesitamos al menos 3 POIs para clustering
                    continue
                
                self.logger.info(f"🗂️ Procesando {category}: {len(category_pois)} POIs")
                
                # Coordenadas para clustering
                coords = np.array([[poi['lat'], poi['lon']] for poi in category_pois])
                
                # DBSCAN clustering
                eps = 0.01 if len(category_pois) > 50 else 0.02  # Más estricto para muchos POIs
                clustering = DBSCAN(eps=eps, min_samples=min(3, len(category_pois)//3)).fit(coords)
                
                # Crear distritos por cluster
                unique_labels = set(clustering.labels_)
                unique_labels.discard(-1)  # Remover noise
                
                for cluster_id in unique_labels:
                    cluster_pois = [category_pois[i] for i, label in enumerate(clustering.labels_) 
                                  if label == cluster_id]
                    
                    if len(cluster_pois) >= 2:
                        # Centro del distrito
                        center_lat = sum(poi['lat'] for poi in cluster_pois) / len(cluster_pois)
                        center_lon = sum(poi['lon'] for poi in cluster_pois) / len(cluster_pois)
                        
                        # Crear polígono del distrito (convex hull de los POIs)
                        if len(cluster_pois) >= 3:
                            points = [Point(poi['lon'], poi['lat']) for poi in cluster_pois]
                            polygon = MultiPolygon([Point(p.x, p.y).buffer(0.008) for p in points]).convex_hull
                        else:
                            polygon = Point(center_lon, center_lat).buffer(0.01)
                        
                        # Calcular métricas reales
                        walkability = await self._calculate_real_walkability(
                            center_lat, center_lon, city_name
                        )
                        transit = await self._calculate_real_transit_access(
                            center_lat, center_lon, city_name
                        )
                        
                        # Crear distrito
                        district = RealSemanticDistrict(
                            name=f"{category.title()} District {cluster_id + 1}",
                            center=(center_lat, center_lon),
                            polygon=polygon,
                            district_type=self._map_category_to_district_type(category),
                            walkability_score=walkability,
                            transit_accessibility=transit,
                            cultural_context=self._get_cultural_context_for_category(category),
                            peak_hours=self._get_peak_hours_for_category(category),
                            real_pois=cluster_pois,
                            street_network_density=await self._calculate_street_density(
                                center_lat, center_lon, city_name
                            ),
                            public_transport_nodes=await self._count_nearby_transport(
                                center_lat, center_lon, city_name
                            ),
                            confidence_score=min(1.0, len(cluster_pois) * 0.1 + 0.3),
                            osm_data_quality='high'
                        )
                        
                        districts.append(district)
                        self.logger.info(f"✅ Distrito REAL: {district.name} con {len(cluster_pois)} POIs")
            
            self.districts[city_name] = districts
            self.logger.info(f"🎯 Total distritos REALES creados para {city_name}: {len(districts)}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error creando distritos reales: {e}")
            return False
    
    def _map_category_to_district_type(self, category: str) -> str:
        """Mapear categorías OSM a tipos de distrito"""
        mapping = {
            'tourism': 'tourist',
            'amenity': 'mixed',
            'shop': 'commercial',
            'leisure': 'recreational',
            'office': 'business',
            'accommodation': 'hospitality',
            'public_transport': 'transport_hub'
        }
        return mapping.get(category, 'general')
    
    async def _calculate_real_walkability(self, lat: float, lon: float, city_name: str) -> float:
        """
        🚶‍♂️ Calcular walkability REAL basado en red de calles OSM
        """
        try:
            G = self.street_networks.get(city_name)
            if not G:
                return 0.6  # Fallback
            
            # Encontrar nodo más cercano
            nearest_node = ox.distance.nearest_nodes(G, lon, lat)
            
            # Obtener subgrafo en radio de 500m
            subgraph = nx.ego_graph(G, nearest_node, radius=500, distance='length')
            
            if len(subgraph.nodes()) < 5:
                return 0.3  # Área con muy pocos nodos
            
            # Métricas de walkability
            node_density = len(subgraph.nodes()) / 0.785  # Área de 500m radio en km²
            edge_density = len(subgraph.edges()) / 0.785
            
            # Análisis de conectividad
            avg_degree = sum(dict(subgraph.degree()).values()) / len(subgraph.nodes())
            
            # Score basado en densidad y conectividad
            density_score = min(1.0, node_density / 100)  # Normalizar
            connectivity_score = min(1.0, avg_degree / 4)  # 4 conexiones = muy bueno
            
            walkability = (density_score * 0.6 + connectivity_score * 0.4)
            
            return round(min(1.0, walkability), 2)
            
        except Exception as e:
            self.logger.debug(f"Error calculando walkability real: {e}")
            return 0.5  # Fallback neutral
    
    async def _calculate_real_transit_access(self, lat: float, lon: float, city_name: str) -> float:
        """
        🚌 Calcular acceso real a transporte público
        """
        try:
            transport = self.transport_networks.get(city_name, {})
            stations = transport.get('stations', [])
            stops = transport.get('stops', [])
            
            all_transport = stations + stops
            if not all_transport:
                return 0.4  # Sin datos de transporte
            
            # Calcular distancia a transporte más cercano
            user_point = Point(lon, lat)
            min_distance = float('inf')
            
            for transport_point in all_transport:
                t_point = Point(transport_point['lon'], transport_point['lat'])
                distance = user_point.distance(t_point)  # En grados
                distance_km = distance * 111.32  # Aproximación a km
                min_distance = min(min_distance, distance_km)
            
            # Score basado en distancia
            if min_distance <= 0.2:  # Menos de 200m
                return 0.95
            elif min_distance <= 0.5:  # Menos de 500m
                return 0.85
            elif min_distance <= 1.0:  # Menos de 1km
                return 0.70
            elif min_distance <= 2.0:  # Menos de 2km
                return 0.50
            else:
                return 0.25
            
        except Exception as e:
            self.logger.debug(f"Error calculando acceso transporte: {e}")
            return 0.5
    
    async def _calculate_street_density(self, lat: float, lon: float, city_name: str) -> float:
        """
        🛣️ Calcular densidad real de calles
        """
        try:
            G = self.street_networks.get(city_name)
            if not G:
                return 0.0
            
            nearest_node = ox.distance.nearest_nodes(G, lon, lat)
            subgraph = nx.ego_graph(G, nearest_node, radius=300, distance='length')
            
            # Calcular longitud total de calles en área
            total_length = 0
            for u, v, data in subgraph.edges(data=True):
                total_length += data.get('length', 0)
            
            # Densidad en km de calle por km²
            area_km2 = 0.283  # Área de círculo de 300m radio
            density = (total_length / 1000) / area_km2  # km de calle por km²
            
            return round(density, 2)
            
        except Exception as e:
            self.logger.debug(f"Error calculando densidad calles: {e}")
            return 0.0
    
    async def _count_nearby_transport(self, lat: float, lon: float, city_name: str) -> int:
        """
        🚌 Contar nodos de transporte público cercanos
        """
        try:
            transport = self.transport_networks.get(city_name, {})
            stations = transport.get('stations', [])
            stops = transport.get('stops', [])
            
            user_point = Point(lon, lat)
            nearby_count = 0
            
            for transport_point in stations + stops:
                t_point = Point(transport_point['lon'], transport_point['lat'])
                distance_km = user_point.distance(t_point) * 111.32
                
                if distance_km <= 1.0:  # Dentro de 1km
                    nearby_count += 1
            
            return nearby_count
            
        except Exception as e:
            self.logger.debug(f"Error contando transporte cercano: {e}")
            return 0
    
    def _get_cultural_context_for_category(self, category: str) -> Dict:
        """
        🎭 Contexto cultural específico por categoría
        """
        contexts = {
            'tourism': {
                'business_hours': '09:00-19:00',
                'dress_code': 'casual',
                'pace': 'relaxed',
                'noise_level': 'moderate',
                'photo_opportunities': 'excellent',
                'language': 'tourist_friendly'
            },
            'amenity': {
                'business_hours': '08:00-20:00',
                'dress_code': 'casual',
                'pace': 'normal',
                'noise_level': 'moderate',
                'language': 'local'
            },
            'shop': {
                'business_hours': '10:00-22:00',
                'dress_code': 'casual',
                'pace': 'busy',
                'noise_level': 'high',
                'language': 'commercial'
            },
            'office': {
                'business_hours': '09:00-18:00',
                'dress_code': 'formal',
                'pace': 'fast',
                'noise_level': 'low',
                'language': 'business'
            }
        }
        
        return contexts.get(category, contexts['amenity'])
    
    def _get_peak_hours_for_category(self, category: str) -> Dict:
        """
        ⏰ Horarios pico por categoría
        """
        schedules = {
            'tourism': {
                'morning_optimal': (9, 11),
                'afternoon_peak': (14, 17),
                'avoid_times': [(12, 14)]
            },
            'shop': {
                'morning_start': (10, 12),
                'afternoon_peak': (15, 18),
                'weekend_peak': (11, 20),
                'avoid_times': [(22, 10)]
            },
            'office': {
                'morning_rush': (8, 10),
                'lunch_peak': (12, 14),
                'evening_rush': (17, 19),
                'optimal_visit': (10, 12)
            },
            'amenity': {
                'general_hours': (8, 20),
                'peak_hours': (12, 14),
                'optimal_visit': (15, 17)
            }
        }
        
        return schedules.get(category, schedules['amenity'])
    
    async def _calculate_real_metrics(self, city_name: str) -> Dict:
        """
        📊 Calcular métricas reales de la ciudad
        """
        try:
            districts = self.districts.get(city_name, [])
            pois = self.poi_data.get(city_name, [])
            transport = self.transport_networks.get(city_name, {})
            
            metrics = {
                'total_districts': len(districts),
                'total_real_pois': len(pois),
                'total_transport_nodes': len(transport.get('stations', [])) + len(transport.get('stops', [])),
                'avg_walkability': sum(d.walkability_score for d in districts) / len(districts) if districts else 0,
                'avg_transit_access': sum(d.transit_accessibility for d in districts) / len(districts) if districts else 0,
                'street_network_nodes': len(self.street_networks.get(city_name, {}).nodes()) if city_name in self.street_networks else 0,
                'street_network_edges': len(self.street_networks.get(city_name, {}).edges()) if city_name in self.street_networks else 0,
                'data_quality': 'high_osm_real',
                'analysis_timestamp': datetime.now().isoformat()
            }
            
            self.logger.info(f"📊 Métricas REALES de {city_name}:")
            self.logger.info(f"   🏛️ Distritos: {metrics['total_districts']}")
            self.logger.info(f"   📍 POIs reales: {metrics['total_real_pois']:,}")
            self.logger.info(f"   🚌 Transporte: {metrics['total_transport_nodes']:,}")
            self.logger.info(f"   🛣️ Red vial: {metrics['street_network_nodes']:,} nodos")
            self.logger.info(f"   🚶‍♂️ Walkability promedio: {metrics['avg_walkability']:.2f}")
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"❌ Error calculando métricas reales: {e}")
            return {}
    
    async def get_real_semantic_context(self, lat: float, lon: float, city_name: str) -> Dict:
        """
        🎯 Obtener contexto semántico REAL de una ubicación
        """
        try:
            districts = self.districts.get(city_name, [])
            if not districts:
                return {
                    'district': 'Unknown',
                    'district_type': 'general',
                    'walkability_score': 0.5,
                    'real_data': False,
                    'recommendation': 'Initialize city with real OSM data first'
                }
            
            point = Point(lon, lat)
            
            # Buscar distrito que contenga el punto
            for district in districts:
                try:
                    if district.polygon.contains(point):
                        return {
                            'district': district.name,
                            'district_type': district.district_type,
                            'walkability_score': district.walkability_score,
                            'transit_accessibility': district.transit_accessibility,
                            'street_density': district.street_network_density,
                            'transport_nodes_nearby': district.public_transport_nodes,
                            'real_pois_count': len(district.real_pois),
                            'cultural_context': district.cultural_context,
                            'peak_hours': district.peak_hours,
                            'confidence': district.confidence_score,
                            'data_quality': district.osm_data_quality,
                            'real_data': True,
                            'inside_district': True
                        }
                except Exception as e:
                    self.logger.debug(f"Error verificando contención: {e}")
                    continue
            
            # Buscar distrito más cercano
            if districts:
                closest_district = min(
                    districts,
                    key=lambda d: Point(d.center[1], d.center[0]).distance(point)
                )
                
                distance = Point(closest_district.center[1], closest_district.center[0]).distance(point)
                
                return {
                    'district': f"Near {closest_district.name}",
                    'district_type': closest_district.district_type,
                    'walkability_score': closest_district.walkability_score * 0.8,
                    'transit_accessibility': closest_district.transit_accessibility * 0.8,
                    'street_density': closest_district.street_network_density,
                    'distance_to_center_km': distance * 111.32,
                    'real_pois_count': len(closest_district.real_pois),
                    'confidence': closest_district.confidence_score * 0.7,
                    'data_quality': closest_district.osm_data_quality,
                    'real_data': True,
                    'inside_district': False
                }
            
            return {
                'district': 'Unknown Area',
                'district_type': 'general',
                'walkability_score': 0.5,
                'real_data': False
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo contexto real: {e}")
            return {
                'district': 'Error',
                'district_type': 'general',
                'walkability_score': 0.5,
                'real_data': False,
                'error': str(e)
            }
    
    def get_city_real_summary(self, city_name: str) -> Dict:
        """
        📊 Resumen REAL completo de la ciudad
        """
        if city_name not in self.districts:
            return {'status': 'not_initialized_real', 'city': city_name}
        
        try:
            districts = self.districts[city_name]
            pois = self.poi_data.get(city_name, [])
            transport = self.transport_networks.get(city_name, {})
            
            # Estadísticas por tipo de distrito
            district_stats = {}
            for district in districts:
                dtype = district.district_type
                if dtype not in district_stats:
                    district_stats[dtype] = {
                        'count': 0,
                        'total_pois': 0,
                        'avg_walkability': 0,
                        'avg_transit': 0,
                        'avg_street_density': 0
                    }
                
                district_stats[dtype]['count'] += 1
                district_stats[dtype]['total_pois'] += len(district.real_pois)
                district_stats[dtype]['avg_walkability'] += district.walkability_score
                district_stats[dtype]['avg_transit'] += district.transit_accessibility
                district_stats[dtype]['avg_street_density'] += district.street_network_density
            
            # Promediar métricas
            for dtype in district_stats:
                count = district_stats[dtype]['count']
                if count > 0:
                    district_stats[dtype]['avg_walkability'] = round(district_stats[dtype]['avg_walkability'] / count, 2)
                    district_stats[dtype]['avg_transit'] = round(district_stats[dtype]['avg_transit'] / count, 2)
                    district_stats[dtype]['avg_street_density'] = round(district_stats[dtype]['avg_street_density'] / count, 2)
            
            return {
                'status': 'initialized_real',
                'city': city_name,
                'data_source': 'openstreetmap_real',
                'total_districts': len(districts),
                'district_types': list(district_stats.keys()),
                'district_stats': district_stats,
                'real_metrics': {
                    'total_osm_pois': len(pois),
                    'transport_stations': len(transport.get('stations', [])),
                    'transport_stops': len(transport.get('stops', [])),
                    'street_network_size': len(self.street_networks.get(city_name, {}).nodes()) if city_name in self.street_networks else 0,
                    'avg_walkability': round(sum(d.walkability_score for d in districts) / len(districts), 2) if districts else 0,
                    'avg_transit_accessibility': round(sum(d.transit_accessibility for d in districts) / len(districts), 2) if districts else 0
                },
                'analysis_quality': 'high_real_osm_data',
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error generando resumen real: {e}")
            return {'status': 'error', 'city': city_name, 'error': str(e)}