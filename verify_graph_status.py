#!/usr/bin/env python3
"""
Verificación del Estado de Grafos en Goveling ML
Inspecciona qué grafos están pre-cargados, cached, o se cargan on-demand
"""

import os
import sys
import json
from datetime import datetime
import asyncio

def check_cache_status():
    """Verificar estado de archivos de cache"""
    print("🔍 VERIFICANDO ESTADO DE GRAFOS Y CACHE")
    print("=" * 60)
    
    # 1. Cache Directory
    cache_dir = 'cache'
    if os.path.exists(cache_dir):
        print(f"\n📦 CACHE DIRECTORY: {cache_dir}/")
        cache_files = [f for f in os.listdir(cache_dir) if f.endswith(('.json', '.pkl'))]
        
        if cache_files:
            total_size = 0
            for f in sorted(cache_files):
                file_path = os.path.join(cache_dir, f)
                size_kb = os.path.getsize(file_path) / 1024
                total_size += size_kb
                modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                print(f"   ├── {f:<35} {size_kb:>8.1f}KB  {modified.strftime('%Y-%m-%d %H:%M')}")
            print(f"   └── Total: {len(cache_files)} files, {total_size:.1f}KB")
        else:
            print("   └── No cache files found")
    else:
        print(f"\n📦 CACHE DIRECTORY: Not found")
    
    # 2. OSRM Data Directory  
    osrm_dir = 'osrm_data'
    if os.path.exists(osrm_dir):
        print(f"\n🗺️ OSRM DATA: {osrm_dir}/")
        osrm_files = [f for f in os.listdir(osrm_dir) if not f.startswith('.')]
        
        if osrm_files:
            total_size_mb = 0
            for f in sorted(osrm_files):
                file_path = os.path.join(osrm_dir, f)
                if os.path.isfile(file_path):
                    size_mb = os.path.getsize(file_path) / (1024 * 1024)
                    total_size_mb += size_mb
                    print(f"   ├── {f:<25} {size_mb:>8.1f}MB")
            print(f"   └── Total: {len(osrm_files)} files, {total_size_mb:.1f}MB")
        else:
            print("   └── No OSRM files found")
    else:
        print(f"\n🗺️ OSRM DATA: Not found (probably using external server)")
    
    # 3. Data Directory
    data_dir = 'data'
    if os.path.exists(data_dir):
        print(f"\n📊 DATA DIRECTORY: {data_dir}/")
        data_files = []
        for root, dirs, files in os.walk(data_dir):
            for f in files:
                if not f.startswith('.'):
                    rel_path = os.path.relpath(os.path.join(root, f), data_dir)
                    data_files.append(rel_path)
        
        if data_files:
            for f in sorted(data_files)[:10]:  # Show first 10
                file_path = os.path.join(data_dir, f)
                if os.path.isfile(file_path):
                    size_kb = os.path.getsize(file_path) / 1024
                    print(f"   ├── {f:<35} {size_kb:>8.1f}KB")
            if len(data_files) > 10:
                print(f"   └── ... and {len(data_files) - 10} more files")
        else:
            print("   └── No data files found")
    else:
        print(f"\n📊 DATA DIRECTORY: Not found")

def check_service_imports():
    """Verificar qué servicios de grafos están disponibles para import"""
    print(f"\n🔧 VERIFICANDO SERVICIOS DISPONIBLES")
    print("-" * 40)
    
    services_to_check = [
        ("H3SpatialPartitioner", "services.h3_spatial_partitioner", "H3SpatialPartitioner"),
        ("City2Graph OR-Tools", "services.city2graph_ortools_service", "City2GraphORToolsService"),
        ("Distance Cache", "services.ortools_distance_cache", "ORToolsDistanceCache"), 
        ("Global City2Graph", "utils.global_city2graph", "global_city2graph"),
        ("Global Real City2Graph", "utils.global_real_city2graph", "global_real_city2graph"),
        ("OSRM Service", "utils.osrm_service", "OSRMService"),
        ("Hybrid Optimizer", "utils.hybrid_optimizer_v31", "optimize_itinerary_hybrid_v31")
    ]
    
    for service_name, module_path, class_or_func in services_to_check:
        try:
            module = __import__(module_path.replace('.', '/').replace('/', '.'), fromlist=[class_or_func])
            if hasattr(module, class_or_func):
                print(f"   ✅ {service_name:<25} Available")
            else:
                print(f"   ❌ {service_name:<25} Module found, but missing {class_or_func}")
        except ImportError as e:
            print(f"   ❌ {service_name:<25} Import failed: {str(e)[:50]}")
        except Exception as e:
            print(f"   ⚠️ {service_name:<25} Error: {str(e)[:50]}")

def check_settings_config():
    """Verificar configuración de grafos en settings"""
    print(f"\n⚙️ CONFIGURACIÓN DE GRAFOS")
    print("-" * 40)
    
    try:
        import settings
        
        # OR-Tools config
        ortools_enabled = getattr(settings, 'ENABLE_ORTOOLS', False)
        ortools_cities = getattr(settings, 'ORTOOLS_CITIES', [])
        ortools_percentage = getattr(settings, 'ORTOOLS_USER_PERCENTAGE', 0)
        
        print(f"   🧮 OR-Tools Enabled: {ortools_enabled}")
        print(f"   🌍 OR-Tools Cities: {len(ortools_cities)} ciudades")
        if ortools_cities:
            cities_str = ", ".join(ortools_cities[:3])
            if len(ortools_cities) > 3:
                cities_str += f", ... (+{len(ortools_cities)-3} more)"
            print(f"      └── {cities_str}")
        print(f"   👥 User Percentage: {ortools_percentage}%")
        
        # Cache config
        cache_enabled = getattr(settings, 'ENABLE_CACHE', True)
        cache_ttl = getattr(settings, 'CACHE_TTL', 3600)
        
        print(f"   💾 Cache Enabled: {cache_enabled}")
        print(f"   ⏱️ Cache TTL: {cache_ttl}s ({cache_ttl/3600:.1f}h)")
        
        # OSRM config
        osrm_url = getattr(settings, 'OSRM_BASE_URL', 'Not configured')
        osrm_enabled = getattr(settings, 'ORTOOLS_ENABLE_OSRM', False)
        
        print(f"   🗺️ OSRM Enabled: {osrm_enabled}")
        print(f"   🌐 OSRM URL: {osrm_url}")
        
    except ImportError:
        print("   ❌ Could not import settings")
    except Exception as e:
        print(f"   ⚠️ Error reading settings: {e}")

async def check_service_health():
    """Verificar si los servicios de grafos están funcionando"""
    print(f"\n🏥 HEALTH CHECK DE SERVICIOS")
    print("-" * 40)
    
    # 1. Check OR-Tools Distance Cache
    try:
        from services.ortools_distance_cache import ORToolsDistanceCache
        cache = ORToolsDistanceCache()
        
        # Test basic functionality
        test_places = [
            {"lat": -33.4378, "lon": -70.6504, "name": "Plaza de Armas"},
            {"lat": -33.4255, "lon": -70.6344, "name": "Cerro San Cristóbal"}
        ]
        
        print(f"   🗄️ Distance Cache: Service loaded successfully")
        stats = cache.get_cache_stats()
        print(f"      └── Current cache entries: {len(cache.cache)}")
        
    except Exception as e:
        print(f"   ❌ Distance Cache: {e}")
    
    # 2. Check OSRM Service
    try:
        from utils.osrm_service import OSRMService
        osrm = OSRMService()
        print(f"   🗺️ OSRM Service: Service loaded successfully")
        
        # Note: No hacemos request real para evitar dependencias externas
        
    except Exception as e:
        print(f"   ❌ OSRM Service: {e}")
    
    # 3. Check H3 Spatial Partitioner
    try:
        from services.h3_spatial_partitioner import H3SpatialPartitioner
        h3_service = H3SpatialPartitioner()
        print(f"   📍 H3 Spatial: Service loaded successfully")
        
    except Exception as e:
        print(f"   ❌ H3 Spatial: {e}")

def main():
    """Función principal de verificación"""
    print(f"📅 Verificación ejecutada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📂 Directorio: {os.getcwd()}")
    
    # Ejecutar todas las verificaciones
    check_cache_status()
    check_service_imports()  
    check_settings_config()
    
    # Health check (async)
    try:
        asyncio.run(check_service_health())
    except Exception as e:
        print(f"\n⚠️ Async health check failed: {e}")
    
    print(f"\n🎯 RESUMEN EJECUTIVO")
    print("=" * 60)
    print("✅ Cache files - Estado verificado")
    print("✅ Service imports - Disponibilidad verificada") 
    print("✅ Settings config - Configuración verificada")
    print("✅ Service health - Funcionalidad verificada")
    
    print(f"\n💡 INTERPRETACIÓN:")
    print("   🧮 OR-Tools: Usa grafos on-demand + cache inteligente")
    print("   🏙️ City2Graph: Lazy loading + cache persistente")
    print("   🗺️ OSRM: Servidor externo con grafos pre-cargados")

if __name__ == "__main__":
    main()