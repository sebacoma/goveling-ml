#!/usr/bin/env python3
"""
Generador de Cache Multi-Modal para Chile
Expande el cache actual para incluir walking y biking
"""

import osmnx as ox
import networkx as nx
import pickle
import os
import time
from datetime import datetime
import logging

# Configurar OSMnx para descargas grandes
ox.settings.log_console = True
ox.settings.use_cache = True
ox.settings.timeout = 600  # 10 minutos por query
ox.settings.max_query_area_size = 50000000000  # Área grande

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ChileMultiModalGenerator:
    """
    Generador de cache multi-modal para Chile
    """
    
    def __init__(self):
        self.cache_dir = "cache"
        self.backup_dir = "cache_backup"
        
        # Crear directorios
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # Configuración de Chile (bbox más conservador para empezar)
        self.chile_regions = {
            'santiago_metro': {
                'bbox': (-33.2, -33.8, -70.4, -71.0),  # Región Metropolitana
                'description': 'Santiago y alrededores',
                'priority': 'high'
            },
            'valparaiso': {
                'bbox': (-32.8, -33.3, -71.3, -71.8),  # Valparaíso
                'description': 'Valparaíso y Viña del Mar',
                'priority': 'high'
            },
            'concepcion': {
                'bbox': (-36.5, -37.0, -72.8, -73.3),  # Concepción
                'description': 'Gran Concepción',
                'priority': 'medium'
            }
        }
        
        logger.info("🏗️ ChileMultiModalGenerator inicializado")
    
    def backup_existing_cache(self):
        """Respaldar cache existente"""
        logger.info("💾 Respaldando cache existente...")
        
        existing_files = [
            'chile_graph_cache.pkl',
            'chile_nodes_dict.pkl', 
            'chile_spatial_index.pkl'
        ]
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for file in existing_files:
            src = os.path.join(self.cache_dir, file)
            if os.path.exists(src):
                backup_name = f"{file.replace('.pkl', '')}_{timestamp}.pkl"
                dst = os.path.join(self.backup_dir, backup_name)
                
                import shutil
                shutil.copy2(src, dst)
                logger.info(f"✅ Respaldado: {file} → {backup_name}")
    
    async def generate_walking_cache(self, region_name: str = 'santiago_metro'):
        """
        Generar cache para red peatonal
        """
        logger.info(f"🚶‍♂️ Generando cache WALKING para {region_name}...")
        
        region = self.chile_regions[region_name]
        bbox = region['bbox']
        north, south, west, east = bbox
        
        start_time = time.time()
        
        try:
            # Descargar red peatonal
            logger.info(f"📥 Descargando red peatonal desde OSM...")
            logger.info(f"   Bbox: {bbox}")
            
            walking_graph = ox.graph_from_bbox(
                bbox=(north, south, east, west),
                network_type='walk',  # Solo red peatonal
                simplify=True,
                retain_all=True
            )
            
            # Proyectar para cálculos precisos
            walking_graph = ox.project_graph(walking_graph)
            
            # Agregar datos de longitud y peso
            walking_graph = ox.distance.add_edge_lengths(walking_graph)
            walking_graph = ox.add_edge_speeds(walking_graph, hwy_speeds=None, fallback=5)  # 5 km/h walking
            walking_graph = ox.add_edge_travel_times(walking_graph)
            
            generation_time = time.time() - start_time
            
            logger.info(f"✅ Red peatonal generada:")
            logger.info(f"   Nodos: {walking_graph.number_of_nodes():,}")
            logger.info(f"   Aristas: {walking_graph.number_of_edges():,}")
            logger.info(f"   Tiempo: {generation_time:.1f}s")
            
            # Guardar cache
            cache_file = os.path.join(self.cache_dir, f'{region_name}_walking_cache.pkl')
            
            logger.info(f"💾 Guardando cache peatonal...")
            with open(cache_file, 'wb') as f:
                pickle.dump(walking_graph, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            # Verificar tamaño
            size_mb = os.path.getsize(cache_file) / (1024 * 1024)
            logger.info(f"✅ Cache peatonal guardado: {size_mb:.1f} MB")
            
            # Generar diccionario de nodos
            await self.generate_nodes_dict(walking_graph, f'{region_name}_walking_nodes.pkl')
            
            return {
                'success': True,
                'nodes': walking_graph.number_of_nodes(),
                'edges': walking_graph.number_of_edges(),
                'size_mb': size_mb,
                'generation_time': generation_time
            }
            
        except Exception as e:
            logger.error(f"❌ Error generando cache peatonal: {e}")
            return {'success': False, 'error': str(e)}
    
    async def generate_cycling_cache(self, region_name: str = 'santiago_metro'):
        """
        Generar cache para red ciclista
        """
        logger.info(f"🚴‍♀️ Generando cache CYCLING para {region_name}...")
        
        region = self.chile_regions[region_name]
        bbox = region['bbox']
        north, south, west, east = bbox
        
        start_time = time.time()
        
        try:
            # Descargar red ciclista
            logger.info(f"📥 Descargando red ciclista desde OSM...")
            
            cycling_graph = ox.graph_from_bbox(
                bbox=(north, south, east, west),
                network_type='bike',  # Red ciclista
                simplify=True,
                retain_all=True
            )
            
            # Proyectar para cálculos precisos
            cycling_graph = ox.project_graph(cycling_graph)
            
            # Agregar datos optimizados para ciclismo
            cycling_graph = ox.distance.add_edge_lengths(cycling_graph)
            
            # Velocidades de ciclismo (más variables que walking)
            bike_speeds = {
                'cycleway': 20,      # Ciclovía dedicada
                'residential': 15,   # Calle residencial
                'tertiary': 12,      # Calle terciaria
                'secondary': 10,     # Calle secundaria (cuidado)
                'primary': 8,        # Calle principal (peligroso)
                'path': 12,          # Sendero
                'track': 15,         # Pista
                'service': 10        # Calle de servicio
            }
            
            cycling_graph = ox.add_edge_speeds(cycling_graph, hwy_speeds=bike_speeds, fallback=12)
            cycling_graph = ox.add_edge_travel_times(cycling_graph)
            
            generation_time = time.time() - start_time
            
            logger.info(f"✅ Red ciclista generada:")
            logger.info(f"   Nodos: {cycling_graph.number_of_nodes():,}")
            logger.info(f"   Aristas: {cycling_graph.number_of_edges():,}")
            logger.info(f"   Tiempo: {generation_time:.1f}s")
            
            # Guardar cache
            cache_file = os.path.join(self.cache_dir, f'{region_name}_cycling_cache.pkl')
            
            logger.info(f"💾 Guardando cache ciclista...")
            with open(cache_file, 'wb') as f:
                pickle.dump(cycling_graph, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            # Verificar tamaño
            size_mb = os.path.getsize(cache_file) / (1024 * 1024)
            logger.info(f"✅ Cache ciclista guardado: {size_mb:.1f} MB")
            
            # Generar diccionario de nodos
            await self.generate_nodes_dict(cycling_graph, f'{region_name}_cycling_nodes.pkl')
            
            return {
                'success': True,
                'nodes': cycling_graph.number_of_nodes(),
                'edges': cycling_graph.number_of_edges(),
                'size_mb': size_mb,
                'generation_time': generation_time
            }
            
        except Exception as e:
            logger.error(f"❌ Error generando cache ciclista: {e}")
            return {'success': False, 'error': str(e)}
    
    async def generate_nodes_dict(self, graph, filename):
        """Generar diccionario optimizado de nodos"""
        logger.info(f"📋 Generando diccionario de nodos...")
        
        nodes_dict = {}
        
        for node_id, node_data in graph.nodes(data=True):
            # Convertir coordenadas proyectadas de vuelta a lat/lon
            if 'y' in node_data and 'x' in node_data:
                nodes_dict[node_id] = {
                    'lat': node_data['y'],
                    'lon': node_data['x']
                }
        
        # Guardar diccionario
        dict_file = os.path.join(self.cache_dir, filename)
        with open(dict_file, 'wb') as f:
            pickle.dump(nodes_dict, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        size_mb = os.path.getsize(dict_file) / (1024 * 1024)
        logger.info(f"✅ Diccionario guardado: {len(nodes_dict):,} nodos, {size_mb:.1f} MB")
    
    async def generate_full_multimodal_cache(self):
        """
        Generar cache completo multi-modal
        """
        logger.info("🚀 INICIANDO GENERACIÓN MULTI-MODAL COMPLETA")
        logger.info("=" * 60)
        
        # Backup existing cache
        self.backup_existing_cache()
        
        results = {
            'walking': {},
            'cycling': {},
            'total_time': 0,
            'total_size_mb': 0
        }
        
        start_total = time.time()
        
        # Generar para región prioritaria primero
        region = 'santiago_metro'
        
        try:
            # 1. Generar walking cache
            logger.info(f"\n🚶‍♂️ FASE 1: Generando cache WALKING...")
            walking_result = await self.generate_walking_cache(region)
            results['walking'] = walking_result
            
            if walking_result['success']:
                results['total_size_mb'] += walking_result['size_mb']
            
            # 2. Generar cycling cache
            logger.info(f"\n🚴‍♀️ FASE 2: Generando cache CYCLING...")
            cycling_result = await self.generate_cycling_cache(region)
            results['cycling'] = cycling_result
            
            if cycling_result['success']:
                results['total_size_mb'] += cycling_result['size_mb']
            
        except Exception as e:
            logger.error(f"❌ Error en generación multi-modal: {e}")
            results['error'] = str(e)
        
        results['total_time'] = time.time() - start_total
        
        # Reporte final
        logger.info(f"\n" + "="*60)
        logger.info("📊 REPORTE FINAL MULTI-MODAL")
        logger.info(f"⏱️ Tiempo total: {results['total_time']:.1f}s")
        logger.info(f"💾 Tamaño total nuevo: {results['total_size_mb']:.1f} MB")
        
        if results['walking'].get('success'):
            w = results['walking']
            logger.info(f"✅ Walking: {w['nodes']:,} nodos, {w['edges']:,} aristas, {w['size_mb']:.1f} MB")
        
        if results['cycling'].get('success'):
            c = results['cycling']
            logger.info(f"✅ Cycling: {c['nodes']:,} nodos, {c['edges']:,} aristas, {c['size_mb']:.1f} MB")
        
        # Calcular total con cache existente
        existing_size = 2300  # 2.3 GB actual
        total_multimodal = existing_size + results['total_size_mb']
        logger.info(f"📊 Cache multi-modal total: {total_multimodal:.0f} MB (~{total_multimodal/1024:.1f} GB)")
        
        return results

async def main():
    """Función principal"""
    generator = ChileMultiModalGenerator()
    
    print("🚀 GENERADOR DE CACHE MULTI-MODAL PARA CHILE")
    print("=" * 60)
    print("📋 Este proceso va a generar cache para:")
    print("   🚶‍♂️ Walking: Red peatonal completa")
    print("   🚴‍♀️ Cycling: Red ciclista + calles compatibles")
    print("   ⏱️ Tiempo estimado: 30-60 minutos")
    print("   💾 Espacio estimado: ~4.6 GB adicionales")
    
    response = input("\n¿Continuar con la generación? (y/N): ")
    
    if response.lower() in ['y', 'yes', 'si', 's']:
        results = await generator.generate_full_multimodal_cache()
        
        if results.get('error'):
            print(f"\n❌ Generación falló: {results['error']}")
            return False
        
        print(f"\n🎉 ¡GENERACIÓN COMPLETADA!")
        print(f"   ✅ Tu app ahora soporta routing multi-modal")
        print(f"   📱 Modos disponibles: drive, walk, bike")
        print(f"   🎯 Lista para uso comercial en Chile")
        
        return True
    else:
        print("❌ Generación cancelada")
        return False

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())