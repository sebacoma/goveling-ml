"""
🌍 OPTIMIZACIÓN DEL SISTEMA CITY2GRAPH REAL
Sistema optimizado con manejo de timeouts y reintentos
"""

import logging
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import os
import json
import time

# Configurar logging
logger = logging.getLogger(__name__)

try:
    import osmnx as ox
    import networkx as nx
    from shapely.geometry import Point, Polygon
    from sklearn.cluster import DBSCAN
    import aiohttp
    
    # Configuración optimizada para evitar timeouts
    ox.settings.timeout = 600  # 10 minutos
    ox.settings.max_query_area_size = 2500000000  # Área máxima más grande
    ox.settings.requests_timeout = 600
    
    # Configuración optimizada para OSMnx
    
    OSMNX_AVAILABLE = True
    logger.info("✅ OSMnx optimizado disponible")
    
except ImportError as e:
    logger.warning(f"⚠️ OSMnx no disponible: {e}")
    OSMNX_AVAILABLE = False

class OptimizedRealCity2GraphService:
    """
    🌍 Servicio optimizado de City2Graph REAL con manejo inteligente de timeouts
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.poi_data = {}
        self.street_networks = {}
        self.transport_networks = {}
        self.districts = {}
        self.processing_status = {}
        
        if OSMNX_AVAILABLE:
            self.logger.info("🌍 OptimizedRealCity2GraphService inicializado")
        else:
            self.logger.warning("🔴 OSMnx no disponible - funcionalidad limitada")
    
    async def initialize_city_optimized(self, city_name: str, bbox: Tuple[float, float, float, float]) -> bool:
        """
        🏙️ Inicialización optimizada con estrategia progresiva
        """
        if not OSMNX_AVAILABLE:
            return False
        
        try:
            self.logger.info(f"🌍 Iniciando descarga OPTIMIZADA para {city_name}")
            start_time = time.time()
            
            # Estrategia 1: Área más pequeña primero
            small_bbox = self._create_smaller_bbox(bbox, 0.5)  # 50% del área original
            
            success = False
            
            # Intentar con área pequeña primero
            self.logger.info("📦 Estrategia 1: Área reducida")
            success = await self._download_with_retries(city_name, small_bbox, max_retries=2)
            
            if not success:
                # Estrategia 2: Área por fragmentos
                self.logger.info("📦 Estrategia 2: Descarga por fragmentos")
                success = await self._download_by_fragments(city_name, bbox)
            
            if not success:
                # Estrategia 3: Solo POIs críticos
                self.logger.info("📦 Estrategia 3: Solo POIs críticos")
                success = await self._download_critical_pois_only(city_name, small_bbox)
            
            elapsed = time.time() - start_time
            
            if success:
                self.logger.info(f"✅ {city_name} inicializada OPTIMIZADA en {elapsed:.1f}s")
                self._create_optimized_districts(city_name)
                return True
            else:
                self.logger.warning(f"⚠️ {city_name} inicialización parcial en {elapsed:.1f}s")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error en inicialización optimizada: {e}")
            return False
    
    def _create_smaller_bbox(self, bbox: Tuple[float, float, float, float], factor: float) -> Tuple[float, float, float, float]:
        """
        📦 Crear bounding box más pequeño centrado
        """
        min_lat, max_lat, min_lon, max_lon = bbox
        
        center_lat = (min_lat + max_lat) / 2
        center_lon = (min_lon + max_lon) / 2
        
        lat_range = (max_lat - min_lat) * factor / 2
        lon_range = (max_lon - min_lon) * factor / 2
        
        return (
            center_lat - lat_range,
            center_lat + lat_range,
            center_lon - lon_range,
            center_lon + lon_range
        )
    
    async def _download_with_retries(self, city_name: str, bbox: Tuple[float, float, float, float], max_retries: int = 3) -> bool:
        """
        🔄 Descarga con reintentos inteligentes
        """
        for attempt in range(max_retries):
            try:
                self.logger.info(f"🔄 Intento {attempt + 1}/{max_retries}")
                
                # Intentar descargar red de calles básica
                success_streets = await self._download_basic_streets(city_name, bbox)
                
                # Intentar descargar POIs básicos
                success_pois = await self._download_basic_pois(city_name, bbox)
                
                # Intentar transporte básico
                success_transport = await self._download_basic_transport(city_name, bbox)
                
                if success_streets or success_pois or success_transport:
                    self.logger.info(f"✅ Descarga parcial exitosa en intento {attempt + 1}")
                    return True
                    
            except Exception as e:
                self.logger.warning(f"⚠️ Intento {attempt + 1} falló: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(10)  # Esperar antes del siguiente intento
        
        return False
    
    async def _download_basic_streets(self, city_name: str, bbox: Tuple[float, float, float, float]) -> bool:
        """
        🛣️ Descarga básica de calles con timeout optimizado
        """
        try:
            min_lat, max_lat, min_lon, max_lon = bbox
            
            self.logger.info("🚗 Descargando red básica...")
            
            # Solo red de conducción para empezar
            # Configurar timeout temporalmente
            original_timeout = ox.settings.timeout
            ox.settings.timeout = 300  # 5 minutos máximo
            
            G = ox.graph_from_bbox(bbox=(max_lat, min_lat, max_lon, min_lon), network_type='drive')
            
            # Restaurar timeout original
            ox.settings.timeout = original_timeout
            
            self.street_networks[city_name] = G
            
            # Guardar en cache
            cache_file = f"city2graph_real_cache/{city_name}_streets_basic.graphml"
            os.makedirs("city2graph_real_cache", exist_ok=True)
            ox.save_graphml(G, cache_file)
            
            nodes_count = len(G.nodes())
            self.logger.info(f"✅ Red básica: {nodes_count} nodos")
            
            return True
            
        except Exception as e:
            self.logger.warning(f"⚠️ Error en red básica: {e}")
            return False
    
    async def _download_basic_pois(self, city_name: str, bbox: Tuple[float, float, float, float]) -> bool:
        """
        🏛️ Descarga básica de POIs críticos
        """
        try:
            min_lat, max_lat, min_lon, max_lon = bbox
            
            # Solo categorías críticas
            critical_categories = {
                'tourism': ['attraction', 'museum'],
                'amenity': ['restaurant', 'cafe'],
                'shop': ['mall']
            }
            
            pois_data = []
            
            for category, values in critical_categories.items():
                try:
                    self.logger.info(f"📍 Descargando {category} críticos...")
                    
                    tags = {category: values}
                    
                    # Configurar timeout para POIs
                    original_timeout = ox.settings.timeout
                    ox.settings.timeout = 120  # 2 minutos por categoría
                    
                    pois = ox.features_from_bbox(bbox=(max_lat, min_lat, max_lon, min_lon), tags=tags)
                    
                    # Restaurar timeout
                    ox.settings.timeout = original_timeout
                    
                    if not pois.empty:
                        for idx, poi in pois.iterrows():
                            try:
                                if hasattr(poi.geometry, 'centroid'):
                                    centroid = poi.geometry.centroid
                                    lat, lon = centroid.y, centroid.x
                                else:
                                    lat, lon = poi.geometry.y, poi.geometry.x
                                
                                poi_data = {
                                    'name': poi.get('name', f'{category}_poi'),
                                    'lat': lat,
                                    'lon': lon,
                                    'category': category,
                                    'osm_type': poi.get('tourism') or poi.get('amenity') or poi.get('shop'),
                                    'confidence': 0.8
                                }
                                
                                pois_data.append(poi_data)
                                
                            except Exception as poi_error:
                                continue
                                
                except Exception as cat_error:
                    self.logger.warning(f"⚠️ Error en {category}: {cat_error}")
                    continue
            
            self.poi_data[city_name] = pois_data
            
            # Guardar en cache
            cache_file = f"city2graph_real_cache/{city_name}_pois_basic.json"
            with open(cache_file, 'w') as f:
                json.dump(pois_data, f, indent=2)
            
            self.logger.info(f"✅ POIs básicos: {len(pois_data)} lugares")
            return len(pois_data) > 0
            
        except Exception as e:
            self.logger.warning(f"⚠️ Error en POIs básicos: {e}")
            return False
    
    async def _download_basic_transport(self, city_name: str, bbox: Tuple[float, float, float, float]) -> bool:
        """
        🚌 Descarga básica de transporte público
        """
        try:
            min_lat, max_lat, min_lon, max_lon = bbox
            
            transport_data = {'stations': [], 'stops': []}
            
            # Solo estaciones de metro/tren
            try:
                self.logger.info("🚇 Descargando estaciones básicas...")
                
                metro_tags = {'public_transport': 'station'}
                
                # Configurar timeout para transporte
                original_timeout = ox.settings.timeout
                ox.settings.timeout = 60  # 1 minuto
                
                metros = ox.features_from_bbox(bbox=(max_lat, min_lat, max_lon, min_lon), tags=metro_tags)
                
                # Restaurar timeout
                ox.settings.timeout = original_timeout
                
                if not metros.empty:
                    for idx, station in metros.iterrows():
                        try:
                            if hasattr(station.geometry, 'centroid'):
                                centroid = station.geometry.centroid
                                lat, lon = centroid.y, centroid.x
                            else:
                                lat, lon = station.geometry.y, station.geometry.x
                            
                            station_data = {
                                'name': station.get('name', 'Estación'),
                                'lat': lat,
                                'lon': lon,
                                'type': 'station'
                            }
                            
                            transport_data['stations'].append(station_data)
                            
                        except Exception:
                            continue
                            
            except Exception as e:
                self.logger.warning(f"⚠️ Error en transporte: {e}")
            
            self.transport_networks[city_name] = transport_data
            
            # Guardar en cache
            cache_file = f"city2graph_real_cache/{city_name}_transport_basic.json"
            with open(cache_file, 'w') as f:
                json.dump(transport_data, f, indent=2)
            
            total_transport = len(transport_data['stations']) + len(transport_data['stops'])
            self.logger.info(f"✅ Transporte básico: {total_transport} puntos")
            
            return total_transport > 0
            
        except Exception as e:
            self.logger.warning(f"⚠️ Error en transporte básico: {e}")
            return False
    
    async def _download_by_fragments(self, city_name: str, bbox: Tuple[float, float, float, float]) -> bool:
        """
        🧩 Descarga por fragmentos del área
        """
        try:
            self.logger.info("🧩 Dividiendo área en fragmentos...")
            
            fragments = self._create_bbox_fragments(bbox, 4)  # 4 fragmentos
            
            success_count = 0
            all_pois = []
            
            for i, fragment_bbox in enumerate(fragments):
                self.logger.info(f"📦 Procesando fragmento {i+1}/4")
                
                try:
                    # Descargar POIs del fragmento
                    fragment_success = await self._download_basic_pois(f"{city_name}_fragment_{i}", fragment_bbox)
                    
                    if fragment_success:
                        # Agregar POIs del fragmento
                        fragment_pois = self.poi_data.get(f"{city_name}_fragment_{i}", [])
                        all_pois.extend(fragment_pois)
                        success_count += 1
                        
                except Exception as e:
                    self.logger.warning(f"⚠️ Fragmento {i+1} falló: {e}")
                    continue
            
            # Combinar todos los POIs
            if all_pois:
                self.poi_data[city_name] = all_pois
                self.logger.info(f"✅ Fragmentos: {len(all_pois)} POIs de {success_count}/4 fragmentos")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Error en fragmentación: {e}")
            return False
    
    def _create_bbox_fragments(self, bbox: Tuple[float, float, float, float], count: int) -> List[Tuple[float, float, float, float]]:
        """
        🧩 Crear fragmentos del bounding box
        """
        min_lat, max_lat, min_lon, max_lon = bbox
        
        fragments = []
        
        if count == 4:
            # Dividir en 4 cuadrantes
            mid_lat = (min_lat + max_lat) / 2
            mid_lon = (min_lon + max_lon) / 2
            
            fragments = [
                (min_lat, mid_lat, min_lon, mid_lon),  # SO
                (min_lat, mid_lat, mid_lon, max_lon),  # SE
                (mid_lat, max_lat, min_lon, mid_lon),  # NO
                (mid_lat, max_lat, mid_lon, max_lon),  # NE
            ]
        
        return fragments
    
    async def _download_critical_pois_only(self, city_name: str, bbox: Tuple[float, float, float, float]) -> bool:
        """
        🎯 Descarga solo POIs críticos mínimos
        """
        try:
            self.logger.info("🎯 Descarga mínima de POIs críticos...")
            
            min_lat, max_lat, min_lon, max_lon = bbox
            minimal_pois = []
            
            # Solo atracciones turísticas
            try:
                # Configurar timeout para atracciones
                original_timeout = ox.settings.timeout
                ox.settings.timeout = 30  # 30 segundos
                
                attractions = ox.features_from_bbox(
                    bbox=(max_lat, min_lat, max_lon, min_lon), 
                    tags={'tourism': 'attraction'}
                )
                
                # Restaurar timeout
                ox.settings.timeout = original_timeout
                
                if not attractions.empty:
                    for idx, attraction in attractions.iterrows():
                        try:
                            if hasattr(attraction.geometry, 'centroid'):
                                centroid = attraction.geometry.centroid
                                lat, lon = centroid.y, centroid.x
                            else:
                                lat, lon = attraction.geometry.y, attraction.geometry.x
                            
                            poi_data = {
                                'name': attraction.get('name', 'Atracción'),
                                'lat': lat,
                                'lon': lon,
                                'category': 'tourism',
                                'osm_type': 'attraction',
                                'confidence': 0.9
                            }
                            
                            minimal_pois.append(poi_data)
                            
                        except Exception:
                            continue
                            
            except Exception as e:
                self.logger.warning(f"⚠️ Error en atracciones mínimas: {e}")
            
            if minimal_pois:
                self.poi_data[city_name] = minimal_pois
                self.logger.info(f"✅ POIs mínimos: {len(minimal_pois)} lugares")
                return True
            
            return False
            
        except Exception as e:
            self.logger.warning(f"⚠️ Error en POIs mínimos: {e}")
            return False
    
    def _create_optimized_districts(self, city_name: str):
        """
        🧠 Crear distritos semánticos optimizados
        """
        try:
            pois = self.poi_data.get(city_name, [])
            
            if len(pois) < 3:
                self.logger.warning("⚠️ Pocos POIs para clustering optimizado")
                return
            
            # Clustering simple pero efectivo
            coordinates = [[poi['lat'], poi['lon']] for poi in pois]
            
            clustering = DBSCAN(eps=0.01, min_samples=2).fit(coordinates)
            labels = clustering.labels_
            
            districts = []
            
            for cluster_id in set(labels):
                if cluster_id == -1:  # Ruido
                    continue
                
                cluster_pois = [pois[i] for i, label in enumerate(labels) if label == cluster_id]
                
                if len(cluster_pois) >= 2:
                    # Crear distrito simple
                    center_lat = sum(poi['lat'] for poi in cluster_pois) / len(cluster_pois)
                    center_lon = sum(poi['lon'] for poi in cluster_pois) / len(cluster_pois)
                    
                    # Determinar tipo dominante
                    categories = [poi['category'] for poi in cluster_pois]
                    dominant_category = max(set(categories), key=categories.count)
                    
                    district_type = {
                        'tourism': 'tourist',
                        'amenity': 'commercial',
                        'shop': 'commercial'
                    }.get(dominant_category, 'mixed')
                    
                    district = {
                        'name': f'Distrito {district_type.title()} {len(districts) + 1}',
                        'district_type': district_type,
                        'center_lat': center_lat,
                        'center_lon': center_lon,
                        'pois_count': len(cluster_pois),
                        'real_pois': cluster_pois,
                        'walkability_score': 0.7,  # Estimación
                        'confidence_score': 0.8,
                        'osm_data_quality': 'basic'
                    }
                    
                    districts.append(district)
            
            self.districts[city_name] = districts
            self.logger.info(f"✅ Distritos optimizados: {len(districts)} creados")
            
        except Exception as e:
            self.logger.error(f"❌ Error creando distritos optimizados: {e}")
    
    def get_optimized_summary(self, city_name: str) -> Dict:
        """
        📊 Resumen optimizado de la ciudad
        """
        if city_name not in self.poi_data and city_name not in self.street_networks:
            return {'status': 'not_initialized'}
        
        pois = self.poi_data.get(city_name, [])
        districts = self.districts.get(city_name, [])
        streets = self.street_networks.get(city_name)
        transport = self.transport_networks.get(city_name, {})
        
        return {
            'status': 'active_optimized',
            'city': city_name,
            'districts': districts,
            'total_pois': len(pois),
            'total_districts': len(districts),
            'street_network_nodes': len(streets.nodes()) if streets else 0,
            'transport_stations': len(transport.get('stations', [])),
            'transport_stops': len(transport.get('stops', [])),
            'data_source': 'openstreetmap_optimized',
            'processing_mode': 'optimized_with_fallbacks'
        }

# Instancia global optimizada
optimized_real_service = OptimizedRealCity2GraphService()

async def test_optimized_system():
    """
    🧪 Test del sistema optimizado
    """
    print("🧪 Probando sistema optimizado...")
    
    # Área más pequeña para Santiago centro
    small_bbox = (-33.45, -33.43, -70.66, -70.64)
    
    success = await optimized_real_service.initialize_city_optimized('santiago_test', small_bbox)
    
    if success:
        summary = optimized_real_service.get_optimized_summary('santiago_test')
        print(f"✅ Sistema optimizado funcionando: {summary}")
        return True
    else:
        print("❌ Sistema optimizado falló")
        return False

if __name__ == "__main__":
    asyncio.run(test_optimized_system())