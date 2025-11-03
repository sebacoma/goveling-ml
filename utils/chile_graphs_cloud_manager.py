#!/usr/bin/env python3
"""
🌥️ CHILE GRAPHS CLOUD MANAGER
Gestor de grafos de Chile en storage cloud gratuito
"""

import os
import requests
import gzip
import logging
from typing import Dict, Optional, List
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)

class ChileGraphsCloudManager:
    """
    Gestor para subir/descargar grafos de Chile desde storage cloud gratuito
    """
    
    def __init__(self):
        self.cache_dir = "cache"
        self.temp_dir = "temp_graphs"
        
        # URLs de storage gratuito (GitHub Releases como CDN)
        self.base_url = "https://github.com/sebacoma/goveling-ml-graphs/releases/download"
        self.version = "v1.0.0"
        
        # Grafos esenciales para Chile
        self.essential_graphs = {
            'chile_graph_cache.pkl': {
                'size_gb': 1.8,
                'description': 'Grafo principal de Chile (drive)',
                'priority': 'critical'
            },
            'chile_nodes_dict.pkl': {
                'size_gb': 0.488,
                'description': 'Diccionario de nodos Chile',
                'priority': 'critical' 
            },
            'santiago_metro_walking_cache.pkl': {
                'size_gb': 0.365,
                'description': 'Red peatonal Santiago',
                'priority': 'high'
            },
            'santiago_metro_cycling_cache.pkl': {
                'size_gb': 0.323,
                'description': 'Red ciclista Santiago',  
                'priority': 'medium'
            }
        }
        
        os.makedirs(self.temp_dir, exist_ok=True)
        logger.info("🌥️ ChileGraphsCloudManager inicializado")
    
    def compress_graph(self, graph_file: str) -> str:
        """Comprimir grafo para reducir tamaño de upload"""
        input_path = os.path.join(self.cache_dir, graph_file)
        output_path = os.path.join(self.temp_dir, f"{graph_file}.gz")
        
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Grafo no encontrado: {input_path}")
        
        logger.info(f"🗜️ Comprimiendo {graph_file}...")
        start_time = datetime.now()
        
        with open(input_path, 'rb') as f_in:
            with gzip.open(output_path, 'wb') as f_out:
                f_out.write(f_in.read())
        
        # Estadísticas de compresión
        original_size = os.path.getsize(input_path) / (1024**3)
        compressed_size = os.path.getsize(output_path) / (1024**3)
        compression_ratio = (1 - compressed_size/original_size) * 100
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(
            f"✅ Compresión completada: {original_size:.2f}GB → {compressed_size:.2f}GB "
            f"({compression_ratio:.1f}% reducción) en {duration:.1f}s"
        )
        
        return output_path
    
    def generate_upload_script(self) -> str:
        """Generar script para subir grafos a GitHub Releases"""
        script_content = f'''#!/bin/bash
# 🚀 UPLOAD CHILE GRAPHS TO GITHUB RELEASES
# Script generado automáticamente - {datetime.now().isoformat()}

echo "🌥️ SUBIENDO GRAFOS DE CHILE A GITHUB RELEASES"
echo "=============================================="

# Verificar GitHub CLI
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI no instalado. Instalar con: brew install gh"
    exit 1
fi

# Crear release si no existe
gh release create {self.version} --title "Chile Graphs v1.0.0" --notes "Grafos multimodales de Chile para Goveling ML" || true

echo "📦 Comprimiendo y subiendo grafos..."
'''
        
        for graph_file, info in self.essential_graphs.items():
            script_content += f'''
# {graph_file} - {info['description']} ({info['size_gb']:.2f}GB)
if [ -f "cache/{graph_file}" ]; then
    echo "🗜️ Comprimiendo {graph_file}..."
    gzip -c cache/{graph_file} > temp_graphs/{graph_file}.gz
    
    echo "🚀 Subiendo {graph_file}.gz..."
    gh release upload {self.version} temp_graphs/{graph_file}.gz --clobber
    
    echo "✅ {graph_file} subido exitosamente"
else
    echo "⚠️ {graph_file} no encontrado - saltando"
fi
'''
        
        script_content += '''
echo ""
echo "✅ TODOS LOS GRAFOS SUBIDOS A GITHUB RELEASES"
echo "🔗 Disponibles en: https://github.com/sebacoma/goveling-ml-graphs/releases"
echo ""
echo "📋 SIGUIENTE PASO:"
echo "   Actualizar código para descargar automáticamente en deploy"
'''
        
        return script_content
    
    def download_graph(self, graph_file: str, force: bool = False) -> bool:
        """Descargar grafo desde cloud storage"""
        local_path = os.path.join(self.cache_dir, graph_file)
        compressed_url = f"{self.base_url}/{self.version}/{graph_file}.gz"
        
        # Skip si ya existe y no es forzado
        if os.path.exists(local_path) and not force:
            logger.info(f"✅ {graph_file} ya existe localmente")
            return True
        
        try:
            logger.info(f"📥 Descargando {graph_file} desde cloud...")
            
            # Descargar archivo comprimido
            response = requests.get(compressed_url, stream=True)
            response.raise_for_status()
            
            # Descomprimir directamente
            import gzip
            decompressed_data = gzip.decompress(response.content)
            
            # Guardar archivo descomprimido
            with open(local_path, 'wb') as f:
                f.write(decompressed_data)
            
            size_mb = len(decompressed_data) / (1024**2)
            logger.info(f"✅ {graph_file} descargado: {size_mb:.1f}MB")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error descargando {graph_file}: {e}")
            return False
    
    def download_all_graphs(self, priority_only: bool = False) -> Dict[str, bool]:
        """Descargar todos los grafos o solo los críticos"""
        results = {}
        
        for graph_file, info in self.essential_graphs.items():
            if priority_only and info['priority'] != 'critical':
                continue
                
            results[graph_file] = self.download_graph(graph_file)
        
        successful = sum(results.values())
        total = len(results)
        logger.info(f"📊 Descarga completada: {successful}/{total} grafos")
        
        return results
    
    def get_cloud_status(self) -> Dict[str, any]:
        """Verificar estado de grafos en cloud vs local"""
        status = {
            'cloud_available': [],
            'local_available': [],
            'missing': [],
            'total_size_gb': 0
        }
        
        for graph_file, info in self.essential_graphs.items():
            local_path = os.path.join(self.cache_dir, graph_file)
            cloud_url = f"{self.base_url}/{self.version}/{graph_file}.gz"
            
            # Verificar local
            if os.path.exists(local_path):
                status['local_available'].append(graph_file)
            else:
                status['missing'].append(graph_file)
            
            # Verificar cloud (head request)
            try:
                response = requests.head(cloud_url, timeout=5)
                if response.status_code == 200:
                    status['cloud_available'].append(graph_file)
            except:
                pass
            
            status['total_size_gb'] += info['size_gb']
        
        return status


def main():
    """Función principal para gestión de grafos"""
    manager = ChileGraphsCloudManager()
    
    print("🌥️ GESTOR DE GRAFOS CHILE EN CLOUD")
    print("=" * 50)
    
    # Mostrar estado actual
    status = manager.get_cloud_status()
    print(f"📊 Grafos locales: {len(status['local_available'])}/4")
    print(f"☁️ Grafos en cloud: {len(status['cloud_available'])}/4") 
    print(f"💾 Tamaño total: {status['total_size_gb']:.2f}GB")
    
    print("\\n📋 OPCIONES:")
    print("1. Generar script de upload")
    print("2. Descargar grafos críticos")
    print("3. Descargar todos los grafos")
    print("4. Verificar estado")
    
    choice = input("\\nSeleccionar opción (1-4): ")
    
    if choice == "1":
        script = manager.generate_upload_script()
        with open("upload_graphs.sh", "w") as f:
            f.write(script)
        os.chmod("upload_graphs.sh", 0o755)
        print("✅ Script 'upload_graphs.sh' generado")
        print("🚀 Ejecutar: ./upload_graphs.sh")
        
    elif choice == "2":
        print("📥 Descargando grafos críticos...")
        manager.download_all_graphs(priority_only=True)
        
    elif choice == "3":
        print("📥 Descargando todos los grafos...")
        manager.download_all_graphs()
        
    elif choice == "4":
        print("🔍 Estado actual:", status)


if __name__ == "__main__":
    main()