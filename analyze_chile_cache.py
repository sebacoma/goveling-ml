#!/usr/bin/env python3
"""
Analizador del cache actual de Chile para determinar el modo de transporte
y planificar la expansión multi-modal
"""

import pickle
import os
import networkx as nx
from collections import Counter

def analyze_current_cache():
    print("🔍 ANALIZANDO CACHE ACTUAL DE CHILE")
    print("=" * 60)
    
    cache_file = "cache/chile_graph_cache.pkl"
    
    if not os.path.exists(cache_file):
        print(f"❌ Cache no encontrado: {cache_file}")
        return
    
    print("📊 Cargando grafo actual...")
    start_time = time.time()
    
    with open(cache_file, 'rb') as f:
        chile_graph = pickle.load(f)
    
    load_time = time.time() - start_time
    print(f"✅ Grafo cargado en {load_time:.2f}s")
    
    # Análisis básico
    print(f"\n📈 ESTADÍSTICAS BÁSICAS:")
    print(f"   Nodos: {chile_graph.number_of_nodes():,}")
    print(f"   Aristas: {chile_graph.number_of_edges():,}")
    print(f"   Tipo: {type(chile_graph).__name__}")
    
    # Análisis de atributos de aristas
    print(f"\n🛣️ ANÁLISIS DE ARISTAS:")
    
    # Tomar muestra de aristas para análisis
    sample_edges = list(chile_graph.edges(data=True))[:1000]
    
    # Recolectar todos los atributos únicos
    all_attributes = set()
    for _, _, data in sample_edges:
        all_attributes.update(data.keys())
    
    print(f"   Atributos encontrados: {sorted(list(all_attributes))}")
    
    # Análisis específico por atributo clave
    key_attributes = ['highway', 'maxspeed', 'oneway', 'surface', 'access', 'lanes']
    
    for attr in key_attributes:
        if attr in all_attributes:
            values = []
            for _, _, data in sample_edges:
                if attr in data:
                    values.append(data[attr])
            
            if values:
                counter = Counter(values)
                top_values = counter.most_common(5)
                print(f"   {attr}: {top_values}")
    
    # Determinar tipo de red probable
    print(f"\n🎯 DETERMINANDO TIPO DE RED:")
    
    highway_types = []
    for _, _, data in sample_edges:
        if 'highway' in data:
            highway_types.append(data['highway'])
    
    highway_counter = Counter(highway_types)
    top_highways = highway_counter.most_common(10)
    
    print(f"   Tipos de carretera más comunes:")
    for highway_type, count in top_highways:
        percentage = (count / len(highway_types)) * 100
        print(f"      {highway_type}: {count} ({percentage:.1f}%)")
    
    # Clasificar el tipo de red
    network_type = classify_network_type(top_highways)
    print(f"\n🏷️ TIPO DE RED DETECTADO: {network_type}")
    
    # Recomendaciones para expansión
    print(f"\n💡 RECOMENDACIONES PARA EXPANSIÓN:")
    
    missing_modes = get_missing_modes(network_type)
    for mode in missing_modes:
        size_estimate = estimate_cache_size(mode, chile_graph.number_of_nodes())
        print(f"   📱 {mode}: ~{size_estimate} GB estimado")
    
    return {
        'current_type': network_type,
        'missing_modes': missing_modes,
        'nodes_count': chile_graph.number_of_nodes(),
        'edges_count': chile_graph.number_of_edges()
    }

def classify_network_type(top_highways):
    """Clasificar el tipo de red basado en los highways más comunes"""
    
    # Convertir a dict para fácil acceso
    highway_dict = dict(top_highways)
    
    # Detectar si incluye peatonal
    pedestrian_types = ['footway', 'pedestrian', 'steps', 'path']
    has_pedestrian = any(hw in highway_dict for hw in pedestrian_types)
    
    # Detectar si incluye ciclismo
    cycling_types = ['cycleway', 'track']
    has_cycling = any(hw in highway_dict for hw in cycling_types)
    
    # Detectar si incluye vehículos
    vehicle_types = ['primary', 'secondary', 'tertiary', 'residential', 'trunk', 'motorway']
    has_vehicle = any(hw in highway_dict for hw in vehicle_types)
    
    # Detectar nivel de detalle
    detail_types = ['service', 'unclassified', 'living_street']
    has_detail = any(hw in highway_dict for hw in detail_types)
    
    if has_vehicle and has_pedestrian and has_cycling:
        return "all" if has_detail else "drive_service"
    elif has_vehicle and has_detail:
        return "drive_service"
    elif has_vehicle:
        return "drive"
    elif has_pedestrian:
        return "walk"
    else:
        return "unknown"

def get_missing_modes(current_type):
    """Determinar qué modos faltan generar"""
    
    all_modes = {
        'walk': 'Red peatonal completa',
        'bike': 'Red ciclista + calles compatibles', 
        'drive': 'Red vehicular básica',
        'drive_service': 'Red vehicular + calles de servicio',
        'all': 'Red completa multi-modal'
    }
    
    if current_type == 'drive_service':
        return ['walk', 'bike']  # Faltan peatonal y ciclista
    elif current_type == 'drive':
        return ['walk', 'bike', 'drive_service']
    elif current_type == 'walk':
        return ['bike', 'drive', 'drive_service']
    elif current_type == 'all':
        return []  # Ya tiene todo
    else:
        return ['walk', 'bike', 'drive', 'drive_service']

def estimate_cache_size(mode, current_nodes):
    """Estimar tamaño del cache para cada modo"""
    
    # Factores basados en densidad de red típica
    size_factors = {
        'walk': 1.2,      # Más nodos (senderos, escaleras, etc.)
        'bike': 0.8,      # Menos que drive_service, más que drive
        'drive': 0.6,     # Solo carreteras principales
        'drive_service': 1.0,  # Baseline (tu cache actual)
    }
    
    current_size_gb = 2.3  # Tu cache actual
    factor = size_factors.get(mode, 1.0)
    
    return round(current_size_gb * factor, 1)

if __name__ == "__main__":
    import time
    
    try:
        result = analyze_current_cache()
        
        print(f"\n" + "="*60)
        print("📋 RESUMEN EJECUTIVO:")
        print(f"   Red actual: {result['current_type']}")
        print(f"   Modos faltantes: {len(result['missing_modes'])}")
        print(f"   Expansión total estimada: ~{sum(estimate_cache_size(mode, result['nodes_count']) for mode in result['missing_modes']):.1f} GB adicionales")
        
        if result['missing_modes']:
            print(f"\n🚀 PRÓXIMOS PASOS:")
            print(f"   1. Generar cache para: {', '.join(result['missing_modes'])}")
            print(f"   2. Implementar selector de modo en routing")
            print(f"   3. Testing multi-modal")
        else:
            print(f"\n🎉 ¡Tu cache ya incluye todos los modos!")
            
    except Exception as e:
        print(f"❌ Error en análisis: {e}")
        import traceback
        traceback.print_exc()