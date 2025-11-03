#!/usr/bin/env python3
"""
🧭 City2Graph PBF Implementation
Convierte archivos OSM .pbf en grafos optimizados usando pyosmium y parquet
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import math
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import networkx as nx
from dataclasses import dataclass
import requests
from urllib.parse import urlparse
import subprocess
import json
import xml.etree.ElementTree as ET
import gzip
import tempfile

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class OSMNode:
    """Representa un nodo OSM con coordenadas y tags"""
    id: int
    lat: float
    lon: float
    tags: Dict[str, str]

@dataclass
class OSMEdge:
    """Representa una arista del grafo (conexión entre nodos)"""
    id_from: int
    id_to: int
    distance_m: float
    highway_type: str
    max_speed: Optional[int]
    oneway: bool
    surface: Optional[str]
    name: Optional[str]

class City2GraphPBF:
    """
    Conversor principal de archivos PBF a grafos optimizados
    """
    
    def __init__(self, data_dir: str = "data/graphs"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Highway types con velocidades por defecto (km/h)
        self.highway_speeds = {
            'motorway': 120,
            'trunk': 100,
            'primary': 90,
            'secondary': 70,
            'tertiary': 50,
            'residential': 30,
            'living_street': 20,
            'service': 20,
            'unclassified': 50,
            'motorway_link': 80,
            'trunk_link': 70,
            'primary_link': 60,
            'secondary_link': 50,
            'tertiary_link': 40
        }
        
        # Tipos de highway relevantes para routing
        self.valid_highways = set(self.highway_speeds.keys())
    
    def download_chile_pbf(self, output_path: str = None) -> str:
        """
        Descarga el archivo PBF de Chile desde Geofabrik
        """
        if output_path is None:
            output_path = self.data_dir / "chile-latest.osm.pbf"
        
        url = "https://download.geofabrik.de/south-america/chile-latest.osm.pbf"
        
        if os.path.exists(output_path):
            logger.info(f"Archivo PBF ya existe: {output_path}")
            return str(output_path)
        
        logger.info(f"Descargando Chile PBF desde {url}")
        start_time = time.time()
        
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\rDescarga: {progress:.1f}% ({downloaded // 1024 // 1024}MB)", end='')
        
        duration = time.time() - start_time
        logger.info(f"\n✅ PBF descargado en {duration:.1f}s: {output_path}")
        return str(output_path)
    
    def haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calcula distancia en metros entre dos puntos usando fórmula haversine
        """
        R = 6371000  # Radio de la Tierra en metros
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c

class OSMPBFParser:
    """
    Parser para procesar archivo PBF usando osmium-tool y procesamiento XML
    """
    
    def __init__(self, city2graph: City2GraphPBF):
        self.city2graph = city2graph
        self.nodes: Dict[int, OSMNode] = {}
        self.edges: List[OSMEdge] = []
        self.processed_ways = 0
        self.processed_nodes = 0
    
    def check_osmium_tool(self) -> bool:
        """Verifica si osmium-tool está disponible"""
        try:
            result = subprocess.run(['osmium', '--version'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def install_osmium_tool(self):
        """Instala osmium-tool usando brew en macOS"""
        logger.info("📦 Instalando osmium-tool...")
        try:
            subprocess.run(['brew', 'install', 'osmium-tool'], check=True)
            logger.info("✅ osmium-tool instalado exitosamente")
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Error instalando osmium-tool: {e}")
            raise
    
    def convert_pbf_to_xml(self, pbf_path: str, xml_path: str):
        """Convierte PBF a XML usando osmium-tool"""
        logger.info(f"🔄 Convirtiendo PBF a XML: {pbf_path} -> {xml_path}")
        
        cmd = [
            'osmium', 'export', pbf_path,
            '--output-format', 'xml',
            '--output', xml_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Error convirtiendo PBF: {result.stderr}")
        
        logger.info("✅ Conversión PBF->XML completada")
    
    def parse_osm_xml(self, xml_path: str):
        """Parsea archivo XML OSM y extrae nodos y ways"""
        logger.info(f"📊 Parseando XML OSM: {xml_path}")
        
        # Primer paso: extraer todos los nodos
        self._extract_nodes_from_xml(xml_path)
        
        # Segundo paso: procesar ways y crear edges
        self._process_ways_from_xml(xml_path)
        
        logger.info(f"✅ Parsing completado: {len(self.nodes)} nodos, {len(self.edges)} edges")
    
    def _extract_nodes_from_xml(self, xml_path: str):
        """Extrae nodos del XML OSM"""
        logger.info("📍 Extrayendo nodos...")
        
        # Usar iterparse para manejar archivos grandes
        context = ET.iterparse(xml_path, events=('start', 'end'))
        context = iter(context)
        event, root = next(context)
        
        node_count = 0
        for event, elem in context:
            if event == 'end' and elem.tag == 'node':
                node_id = int(elem.get('id'))
                lat = float(elem.get('lat'))
                lon = float(elem.get('lon'))
                
                # Extraer tags
                tags = {}
                for tag_elem in elem.findall('tag'):
                    key = tag_elem.get('k')
                    value = tag_elem.get('v')
                    tags[key] = value
                
                self.nodes[node_id] = OSMNode(
                    id=node_id,
                    lat=lat,
                    lon=lon,
                    tags=tags
                )
                
                node_count += 1
                if node_count % 50000 == 0:
                    logger.info(f"  Procesados {node_count} nodos...")
                
                # Limpiar memoria
                elem.clear()
                root.clear()
    
    def _process_ways_from_xml(self, xml_path: str):
        """Procesa ways del XML OSM y crea edges"""
        logger.info("🛣️  Procesando ways...")
        
        context = ET.iterparse(xml_path, events=('start', 'end'))
        context = iter(context)
        event, root = next(context)
        
        way_count = 0
        for event, elem in context:
            if event == 'end' and elem.tag == 'way':
                # Extraer tags del way
                tags = {}
                for tag_elem in elem.findall('tag'):
                    key = tag_elem.get('k')
                    value = tag_elem.get('v')
                    tags[key] = value
                
                highway_type = tags.get('highway')
                if not highway_type or highway_type not in self.city2graph.valid_highways:
                    elem.clear()
                    continue
                
                # Extraer información del way
                max_speed = self._extract_maxspeed(tags.get('maxspeed'))
                oneway = tags.get('oneway') in ['yes', '1', 'true']
                surface = tags.get('surface')
                name = tags.get('name')
                
                # Extraer nodos del way
                node_refs = []
                for nd_elem in elem.findall('nd'):
                    node_id = int(nd_elem.get('ref'))
                    if node_id in self.nodes:
                        node_refs.append(node_id)
                
                # Crear edges entre nodos consecutivos
                for i in range(len(node_refs) - 1):
                    node_from_id = node_refs[i]
                    node_to_id = node_refs[i + 1]
                    
                    node_from = self.nodes[node_from_id]
                    node_to = self.nodes[node_to_id]
                    
                    # Calcular distancia
                    distance = self.city2graph.haversine_distance(
                        node_from.lat, node_from.lon,
                        node_to.lat, node_to.lon
                    )
                    
                    # Crear edge
                    edge = OSMEdge(
                        id_from=node_from_id,
                        id_to=node_to_id,
                        distance_m=distance,
                        highway_type=highway_type,
                        max_speed=max_speed or self.city2graph.highway_speeds.get(highway_type, 50),
                        oneway=oneway,
                        surface=surface,
                        name=name
                    )
                    self.edges.append(edge)
                    
                    # Si no es one-way, agregar edge inverso
                    if not oneway:
                        reverse_edge = OSMEdge(
                            id_from=node_to_id,
                            id_to=node_from_id,
                            distance_m=distance,
                            highway_type=highway_type,
                            max_speed=max_speed or self.city2graph.highway_speeds.get(highway_type, 50),
                            oneway=False,
                            surface=surface,
                            name=name
                        )
                        self.edges.append(reverse_edge)
                
                way_count += 1
                if way_count % 10000 == 0:
                    logger.info(f"  Procesados {way_count} ways, {len(self.edges)} edges")
                
                # Limpiar memoria
                elem.clear()
                root.clear()
    
    def _extract_maxspeed(self, maxspeed_str: Optional[str]) -> Optional[int]:
        """Extrae velocidad máxima de string OSM"""
        if not maxspeed_str:
            return None
        
        try:
            # Remover unidades y convertir
            speed_str = maxspeed_str.replace('km/h', '').replace('mph', '').strip()
            speed = int(speed_str)
            
            # Convertir mph a km/h si es necesario
            if 'mph' in maxspeed_str:
                speed = int(speed * 1.60934)
            
            return speed
        except (ValueError, AttributeError):
            return None

class City2GraphProcessor:
    """
    Procesador principal que coordina la conversión PBF -> Parquet
    """
    
    def __init__(self, data_dir: str = "data/graphs"):
        self.city2graph = City2GraphPBF(data_dir)
        self.data_dir = Path(data_dir)
    
    def process_chile(self, force_download: bool = False) -> Tuple[str, str]:
        """
        Proceso completo: descargar PBF, convertir a grafo, guardar parquet
        """
        logger.info("🚀 Iniciando procesamiento de Chile con city2graph")
        
        # 1. Descargar PBF
        pbf_path = self.data_dir / "chile-latest.osm.pbf"
        if force_download or not pbf_path.exists():
            pbf_path = self.city2graph.download_chile_pbf(str(pbf_path))
        else:
            logger.info(f"Usando PBF existente: {pbf_path}")
        
        # 2. Inicializar parser
        parser = OSMPBFParser(self.city2graph)
        
        # 3. Verificar/instalar osmium-tool
        if not parser.check_osmium_tool():
            logger.info("🔧 osmium-tool no encontrado, instalando...")
            parser.install_osmium_tool()
        
        # 4. Convertir PBF a XML temporal
        logger.info("📊 Procesando archivo PBF...")
        start_time = time.time()
        
        with tempfile.NamedTemporaryFile(suffix='.xml', delete=False) as temp_xml:
            xml_path = temp_xml.name
        
        try:
            parser.convert_pbf_to_xml(str(pbf_path), xml_path)
            parser.parse_osm_xml(xml_path)
        finally:
            # Limpiar archivo temporal
            if os.path.exists(xml_path):
                os.unlink(xml_path)
        
        processing_time = time.time() - start_time
        logger.info(f"✅ PBF procesado en {processing_time:.1f}s")
        logger.info(f"📍 Nodos: {len(parser.nodes):,}")
        logger.info(f"🛣️  Edges: {len(parser.edges):,}")
        
        # 5. Guardar como Parquet
        chile_dir = self.data_dir / "chile"
        chile_dir.mkdir(exist_ok=True)
        
        nodes_path = self._save_nodes_parquet(parser.nodes, chile_dir / "nodes.parquet")
        edges_path = self._save_edges_parquet(parser.edges, chile_dir / "edges.parquet")
        
        return nodes_path, edges_path
    
    def _save_nodes_parquet(self, nodes: Dict[int, OSMNode], output_path: Path) -> str:
        """Guarda nodos en formato Parquet optimizado"""
        logger.info(f"💾 Guardando {len(nodes):,} nodos en {output_path}")
        
        # Convertir a DataFrame
        nodes_data = []
        for node in nodes.values():
            nodes_data.append({
                'node_id': node.id,
                'lat': node.lat,
                'lon': node.lon,
                'tags': str(node.tags) if node.tags else ''
            })
        
        df = pd.DataFrame(nodes_data)
        
        # Guardar con compresión
        table = pa.Table.from_pandas(df)
        pq.write_table(table, output_path, compression='snappy')
        
        size_mb = output_path.stat().st_size / 1024 / 1024
        logger.info(f"✅ Nodos guardados: {size_mb:.1f}MB")
        return str(output_path)
    
    def _save_edges_parquet(self, edges: List[OSMEdge], output_path: Path) -> str:
        """Guarda aristas en formato Parquet optimizado"""
        logger.info(f"💾 Guardando {len(edges):,} edges en {output_path}")
        
        # Convertir a DataFrame
        edges_data = []
        for edge in edges:
            edges_data.append({
                'id_from': edge.id_from,
                'id_to': edge.id_to,
                'distance_m': edge.distance_m,
                'highway_type': edge.highway_type,
                'max_speed': edge.max_speed,
                'oneway': edge.oneway,
                'surface': edge.surface or '',
                'name': edge.name or ''
            })
        
        df = pd.DataFrame(edges_data)
        
        # Guardar con compresión
        table = pa.Table.from_pandas(df)
        pq.write_table(table, output_path, compression='snappy')
        
        size_mb = output_path.stat().st_size / 1024 / 1024
        logger.info(f"✅ Edges guardados: {size_mb:.1f}MB")
        return str(output_path)
    
    def load_graph(self, country: str = "chile") -> nx.DiGraph:
        """
        Carga grafo desde archivos Parquet para uso en memoria
        """
        logger.info(f"🔄 Cargando grafo de {country}")
        start_time = time.time()
        
        country_dir = self.data_dir / country
        nodes_path = country_dir / "nodes.parquet"
        edges_path = country_dir / "edges.parquet"
        
        if not nodes_path.exists() or not edges_path.exists():
            raise FileNotFoundError(f"Grafos no encontrados en {country_dir}")
        
        # Cargar DataFrames
        nodes_df = pd.read_parquet(nodes_path)
        edges_df = pd.read_parquet(edges_path)
        
        # Crear grafo NetworkX
        G = nx.DiGraph()
        
        # Agregar nodos
        for _, row in nodes_df.iterrows():
            G.add_node(row['node_id'], 
                      lat=row['lat'], 
                      lon=row['lon'],
                      tags=eval(row['tags']) if row['tags'] else {})
        
        # Agregar aristas
        for _, row in edges_df.iterrows():
            G.add_edge(row['id_from'], row['id_to'],
                      distance=row['distance_m'],
                      highway_type=row['highway_type'],
                      max_speed=row['max_speed'],
                      oneway=row['oneway'],
                      surface=row['surface'],
                      name=row['name'])
        
        load_time = time.time() - start_time
        logger.info(f"✅ Grafo cargado en {load_time:.1f}s")
        logger.info(f"📊 Nodos: {G.number_of_nodes():,}, Aristas: {G.number_of_edges():,}")
        
        return G

def main():
    """Función principal para ejecutar city2graph"""
    processor = City2GraphProcessor()
    
    try:
        # Procesar Chile completo
        nodes_path, edges_path = processor.process_chile()
        
        print(f"\n🎉 ¡Proceso completado exitosamente!")
        print(f"📍 Nodos: {nodes_path}")
        print(f"🛣️  Edges: {edges_path}")
        print(f"\n💡 Para usar el grafo:")
        print(f"   processor = City2GraphProcessor()")
        print(f"   G = processor.load_graph('chile')")
        
    except Exception as e:
        logger.error(f"❌ Error en procesamiento: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()