#!/usr/bin/env python3
"""
📊 ANÁLISIS DE LLAMADAS A GOOGLE PLACES API
Analiza cuántas llamadas se hacen a Google Places API en un request típico
"""

import re
import os
from typing import Dict, List, Tuple

def analyze_google_places_calls():
    """Analizar llamadas a Google Places API en el codebase"""
    
    print("📊 ANÁLISIS DE LLAMADAS A GOOGLE PLACES API")
    print("=" * 60)
    
    # Archivos a analizar
    files_to_check = [
        "services/google_places_service.py",
        "utils/hybrid_optimizer_v31.py", 
        "api.py"
    ]
    
    call_patterns = {
        "search_nearby": r"search_nearby\s*\(",
        "search_nearby_real": r"search_nearby_real\s*\(",
        "_google_nearby_search": r"_google_nearby_search\s*\(",
        "Google API HTTP": r"session\.get.*googleapis\.com"
    }
    
    total_calls = {}
    file_details = {}
    
    for file_path in files_to_check:
        if not os.path.exists(file_path):
            print(f"❌ Archivo no encontrado: {file_path}")
            continue
            
        print(f"\n🔍 Analizando: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        file_calls = {}
        
        for pattern_name, pattern in call_patterns.items():
            matches = re.findall(pattern, content, re.IGNORECASE)
            count = len(matches)
            
            if count > 0:
                file_calls[pattern_name] = count
                total_calls[pattern_name] = total_calls.get(pattern_name, 0) + count
                print(f"   {pattern_name}: {count} ocurrencias")
        
        file_details[file_path] = file_calls
    
    # Análisis específico del flujo de un request típico
    print("\n🎯 ANÁLISIS DETALLADO DEL FLUJO")
    print("=" * 60)
    
    analyze_request_flow()
    
    # Resumen total
    print("\n📈 RESUMEN TOTAL")
    print("=" * 30)
    
    if total_calls:
        for call_type, count in total_calls.items():
            print(f"   {call_type}: {count} llamadas en el código")
    else:
        print("   No se encontraron patrones de llamadas explícitas")
    
    # Estimación por request
    estimate_calls_per_request()

def analyze_request_flow():
    """Analizar el flujo específico de un request multimodal"""
    
    print("🚀 Flujo típico de /itinerary/multimodal:")
    
    # Leer el optimizador híbrido para entender el flujo
    try:
        with open("utils/hybrid_optimizer_v31.py", 'r') as f:
            content = f.read()
        
        # Buscar funciones que hacen llamadas
        functions_with_calls = []
        
        # Patrón para encontrar funciones que llaman a Google Places
        lines = content.split('\n')
        current_function = ""
        
        for i, line in enumerate(lines):
            # Detectar definición de función
            if line.strip().startswith('def ') or line.strip().startswith('async def '):
                current_function = line.strip()
            
            # Detectar llamadas a Google Places
            if 'search_nearby' in line and 'places_service' in line:
                if current_function:
                    functions_with_calls.append({
                        'function': current_function,
                        'line': i + 1,
                        'call': line.strip()
                    })
        
        print("\n📋 Funciones que hacen llamadas a Google Places:")
        for func_call in functions_with_calls:
            print(f"   • {func_call['function'].split('(')[0].replace('async def ', '').replace('def ', '')}")
            print(f"     Línea {func_call['line']}: {func_call['call']}")
        
    except FileNotFoundError:
        print("   ❌ No se pudo leer hybrid_optimizer_v31.py")

def estimate_calls_per_request():
    """Estimar llamadas por request basado en el código"""
    
    print("\n💰 ESTIMACIÓN DE LLAMADAS POR REQUEST")
    print("=" * 50)
    
    # Análisis basado en el código del servicio
    print("📍 Escenario: Request con 2 lugares (como el que enviaste)")
    print()
    
    # Llamadas identificadas en el código
    scenarios = [
        {
            "name": "Sugerencias básicas (search_nearby)",
            "description": "Llamadas para sugerencias sintéticas/básicas",
            "calls_per_location": 0,  # search_nearby usa fallback sintético
            "total_calls": 0
        },
        {
            "name": "Sugerencias reales (search_nearby_real)", 
            "description": "Llamadas reales a Google Places API",
            "calls_per_location": 3,  # tourist_attraction + variedad por día
            "total_calls": 6  # 3 tipos × 2 ubicaciones
        },
        {
            "name": "Hoteles (si se solicitan)",
            "description": "Búsqueda de accommodations",
            "calls_per_location": 1,
            "total_calls": 0  # No se solicitaron en tu request
        }
    ]
    
    total_estimated = 0
    
    for scenario in scenarios:
        calls = scenario['total_calls']
        total_estimated += calls
        status = "✅ Activo" if calls > 0 else "⚠️ Inactivo"
        
        print(f"   {scenario['name']}")
        print(f"   {scenario['description']}")
        print(f"   Llamadas estimadas: {calls} {status}")
        print()
    
    print(f"🎯 TOTAL ESTIMADO POR REQUEST: {total_estimated} llamadas")
    print(f"💸 Costo estimado: ${total_estimated * 0.032:.3f} USD")
    print("   (Basado en $0.032 por llamada a Nearby Search)")
    
    # Análisis del comportamiento real observado
    print("\n🔍 COMPORTAMIENTO OBSERVADO EN TU REQUEST:")
    print("=" * 55)
    print("✅ El sistema respondió exitosamente (HTTP 200)")
    print("✅ Generó itinerario para 2 ubicaciones (Orlando + Miami)")
    print("⚠️ Usó optimizador LEGACY (no OR-Tools)")
    print("⚠️ Sin S3 configurado (sin grafos de Chile)")
    print(f"📍 Ubicaciones: Internacionales (Florida, USA)")
    print()
    print("💡 Recomendación:")
    print("   • Configurar ENABLE_ORTOOLS=true para mejor rendimiento")
    print("   • Las ubicaciones internacionales usan más llamadas a Google Places")
    print("   • Locations en Chile usan grafos cached (menos llamadas API)")

def check_api_key_usage():
    """Verificar si se está usando API key y cómo"""
    
    print("\n🔑 VERIFICACIÓN DE API KEY")
    print("=" * 35)
    
    try:
        with open("settings.py", 'r') as f:
            settings_content = f.read()
        
        if "GOOGLE_PLACES_API_KEY" in settings_content:
            print("✅ API Key configurada en settings")
        else:
            print("❌ API Key no encontrada en settings")
        
        # Verificar si hay validación de API key
        with open("services/google_places_service.py", 'r') as f:
            service_content = f.read()
        
        if "if not self.api_key:" in service_content:
            print("✅ Servicio valida existencia de API key")
            print("   • Sin API key → sugerencias sintéticas")
            print("   • Con API key → llamadas reales a Google Places")
        
    except FileNotFoundError as e:
        print(f"❌ Error leyendo archivos: {e}")

if __name__ == "__main__":
    analyze_google_places_calls()
    check_api_key_usage()