#!/usr/bin/env python3
"""
🔍 RENDER DEPLOYMENT DIAGNOSTIC TOOL
Verifica dependencias y configuración antes del deployment
"""

import sys
import importlib
import logging
from typing import List, Dict, Tuple

def check_import(module_name: str, package_name: str = None) -> Tuple[bool, str]:
    """
    Verificar si un módulo se puede importar
    
    Args:
        module_name: Nombre del módulo a importar
        package_name: Nombre del paquete en pip (si es diferente)
    
    Returns:
        Tuple[bool, str]: (éxito, mensaje)
    """
    try:
        importlib.import_module(module_name)
        return True, f"✅ {module_name} - OK"
    except ImportError as e:
        package = package_name or module_name
        return False, f"❌ {module_name} - FALTA (pip install {package})"
    except Exception as e:
        return False, f"⚠️ {module_name} - ERROR: {e}"

def check_critical_dependencies() -> Dict[str, bool]:
    """Verificar dependencias críticas para el sistema"""
    
    print("🔍 VERIFICANDO DEPENDENCIAS CRÍTICAS")
    print("=" * 50)
    
    # Dependencias críticas con nombres de paquete
    critical_deps = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("pydantic", "pydantic"),
        ("pandas", "pandas"),
        ("numpy", "numpy"),
        ("requests", "requests"),
        ("h3", "h3"),  # ← Esta era la que faltaba
        ("ortools", "ortools"),  # ← Esta también
        ("geopy", "geopy"),
        ("networkx", "networkx"),
        ("shapely", "shapely"),
        ("scipy", "scipy"),
        ("sklearn", "scikit-learn"),
        ("rtree", "rtree"),
    ]
    
    results = {}
    failed = []
    
    for module, package in critical_deps:
        success, message = check_import(module, package)
        results[module] = success
        print(f"   {message}")
        
        if not success:
            failed.append((module, package))
    
    if failed:
        print("\n🚨 DEPENDENCIAS FALTANTES:")
        print("pip install " + " ".join([pkg for _, pkg in failed]))
    else:
        print("\n✅ Todas las dependencias críticas están disponibles")
    
    return results

def check_optional_dependencies():
    """Verificar dependencias opcionales"""
    
    print("\n🔍 VERIFICANDO DEPENDENCIAS OPCIONALES")
    print("=" * 50)
    
    optional_deps = [
        ("osmnx", "osmnx"),
        ("geopandas", "geopandas"), 
        ("matplotlib", "matplotlib"),
        ("folium", "folium"),
        ("boto3", "boto3"),
    ]
    
    for module, package in optional_deps:
        success, message = check_import(module, package)
        print(f"   {message}")

def check_settings_import():
    """Verificar que settings.py se puede importar"""
    
    print("\n🔍 VERIFICANDO CONFIGURACIÓN")
    print("=" * 50)
    
    try:
        from settings import settings
        print("   ✅ settings.py - OK")
        
        # Verificar algunas configuraciones críticas
        if hasattr(settings, 'GOOGLE_MAPS_API_KEY'):
            key_status = "Configurada" if settings.GOOGLE_MAPS_API_KEY else "Vacía"
            print(f"   🗝️ GOOGLE_MAPS_API_KEY - {key_status}")
        
        if hasattr(settings, 'DEBUG'):
            print(f"   🔧 DEBUG - {settings.DEBUG}")
            
        return True
        
    except Exception as e:
        print(f"   ❌ settings.py - ERROR: {e}")
        return False

def check_api_import():
    """Verificar que api.py se puede importar"""
    
    print("\n🔍 VERIFICANDO API PRINCIPAL")
    print("=" * 50)
    
    try:
        # Intentar importar solo el módulo, no ejecutar
        import api
        print("   ✅ api.py - OK")
        
        # Verificar que FastAPI app existe
        if hasattr(api, 'app'):
            print("   ✅ FastAPI app - OK")
        else:
            print("   ❌ FastAPI app - NO ENCONTRADA")
            
        return True
        
    except ImportError as e:
        print(f"   ❌ api.py - IMPORT ERROR: {e}")
        
        # Analizar el error específico
        error_str = str(e)
        if "No module named" in error_str:
            missing_module = error_str.split("'")[1]
            print(f"   💡 Módulo faltante detectado: {missing_module}")
            
        return False
        
    except Exception as e:
        print(f"   ❌ api.py - ERROR: {e}")
        return False

def check_file_structure():
    """Verificar estructura de archivos esencial"""
    
    print("\n🔍 VERIFICANDO ESTRUCTURA DE ARCHIVOS")
    print("=" * 50)
    
    essential_files = [
        "api.py",
        "settings.py", 
        "requirements.txt",
    ]
    
    essential_dirs = [
        "services",
        "utils", 
        "models",
    ]
    
    import os
    
    # Verificar archivos
    for file in essential_files:
        if os.path.exists(file):
            print(f"   ✅ {file} - OK")
        else:
            print(f"   ❌ {file} - FALTA")
    
    # Verificar directorios  
    for directory in essential_dirs:
        if os.path.isdir(directory):
            file_count = len(os.listdir(directory))
            print(f"   ✅ {directory}/ - OK ({file_count} archivos)")
        else:
            print(f"   ❌ {directory}/ - FALTA")

def generate_render_commands():
    """Generar comandos específicos para Render.com"""
    
    print("\n🚀 COMANDOS PARA RENDER.COM")
    print("=" * 50)
    
    print("📦 Build Command:")
    print("   pip install --no-cache-dir -r requirements.txt")
    print()
    
    print("🚀 Start Command:")  
    print("   uvicorn api:app --host 0.0.0.0 --port $PORT")
    print()
    
    print("⚙️ Environment Variables recomendadas:")
    env_vars = [
        ("GOOGLE_MAPS_API_KEY", "tu_google_maps_api_key"),
        ("GOOGLE_PLACES_API_KEY", "tu_google_places_api_key"),
        ("DEBUG", "false"),
        ("ENABLE_CACHE", "true"),
        ("CACHE_TTL_SECONDS", "300"),
        ("MAX_CONCURRENT_REQUESTS", "3"),
        ("ENABLE_ORTOOLS", "true"),
    ]
    
    for var_name, example_value in env_vars:
        print(f"   {var_name}={example_value}")

def main():
    """Ejecutar diagnóstico completo"""
    
    print("🩺 DIAGNÓSTICO RENDER DEPLOYMENT - GOVELING ML")
    print("=" * 60)
    print()
    
    # Verificaciones paso a paso
    deps_ok = check_critical_dependencies()
    check_optional_dependencies()
    settings_ok = check_settings_import()
    api_ok = check_api_import()
    check_file_structure()
    
    # Generar comandos para Render
    generate_render_commands()
    
    # Resumen final
    print("\n📊 RESUMEN DEL DIAGNÓSTICO")
    print("=" * 50)
    
    critical_deps_passed = sum(deps_ok.values())
    total_critical = len(deps_ok)
    
    print(f"   📦 Dependencias críticas: {critical_deps_passed}/{total_critical}")
    print(f"   ⚙️ Settings: {'✅ OK' if settings_ok else '❌ ERROR'}")
    print(f"   🚀 API: {'✅ OK' if api_ok else '❌ ERROR'}")
    
    if critical_deps_passed == total_critical and settings_ok and api_ok:
        print("\n🎉 ¡SISTEMA LISTO PARA DEPLOYMENT!")
        print("   Puedes proceder con el deploy a Render.com")
    else:
        print("\n🔧 SISTEMA NECESITA CORRECCIONES")
        print("   Resuelve los errores mostrados arriba antes de hacer deploy")
        
        if not api_ok:
            print("\n💡 TIPS PARA RESOLVER PROBLEMAS DE API:")
            print("   • Verifica que todas las dependencias estén instaladas")
            print("   • Revisa imports en api.py que puedan estar fallando")
            print("   • Asegúrate que services/ y utils/ tengan archivos __init__.py")

if __name__ == "__main__":
    main()