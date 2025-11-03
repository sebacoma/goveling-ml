#!/usr/bin/env python3
"""
📂 GOOGLE DRIVE MANAGER FOR CHILE GRAPHS
Gestor automático de grafos de Chile usando Google Drive (15GB gratis)
"""

import os
import pickle
import gzip
import logging
import requests
from typing import Dict, Optional, List
import json
import tempfile

logger = logging.getLogger(__name__)

class GoogleDriveGraphsManager:
    """
    Gestor para subir/descargar grafos de Chile usando Google Drive
    """
    
    def __init__(self, config_file="google_drive_config.json"):
        """
        Inicializar el manager de Google Drive
        
        Args:
            config_file (str): Archivo JSON con configuración de URLs
        """
        self.cache_dir = "cache"
        self.config_file = config_file
        
        # Crear directorio cache si no existe
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Cargar configuración
        self.config = self._load_config()
        
        logger.info(f"GoogleDriveGraphsManager inicializado con {len(self.config)} archivos")
    
    def _load_config(self) -> Dict:
        """Cargar configuración desde archivo JSON"""
        try:
            if not os.path.exists(self.config_file):
                logger.warning(f"No existe {self.config_file}, usando configuración vacía")
                return {}
            
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            logger.info(f"Configuración cargada: {len(config)} archivos")
            return config
            
        except Exception as e:
            logger.error(f"Error cargando configuración: {e}")
            return {}
    
    def _get_download_url(self, filename: str) -> Optional[str]:
        """
        Obtener URL de descarga directa para un archivo
        
        Args:
            filename (str): Nombre del archivo (ej: 'chile_graph_cache.pkl')
        
        Returns:
            str: URL de descarga directa o None si no está configurado
        """
        if filename not in self.config:
            logger.error(f"Archivo {filename} no encontrado en configuración")
            return None
        
        return self.config[filename].get('direct_url')
    
    def download_graph(self, filename: str, force_redownload: bool = False) -> bool:
        """
        Descargar un grafo específico desde Google Drive
        
        Args:
            filename (str): Nombre del archivo a descargar
            force_redownload (bool): Forzar re-descarga si el archivo ya existe
        
        Returns:
            bool: True si se descargó exitosamente
        """
        local_path = os.path.join(self.cache_dir, filename)
        
        # Verificar si ya existe y no forzar re-descarga
        if os.path.exists(local_path) and not force_redownload:
            logger.info(f"✅ {filename} ya existe localmente")
            return True
        
        # Obtener URL de descarga
        download_url = self._get_download_url(filename)
        if not download_url:
            logger.error(f"❌ No hay URL configurada para {filename}")
            return False
        
        try:
            logger.info(f"⬇️ Descargando {filename} desde Google Drive...")
            
            # Descargar archivo comprimido
            compressed_path = local_path + '.gz'
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            
            # Guardar archivo comprimido
            with open(compressed_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Descomprimir archivo
            logger.info(f"📦 Descomprimiendo {filename}...")
            with gzip.open(compressed_path, 'rb') as f_gz:
                with open(local_path, 'wb') as f_out:
                    f_out.write(f_gz.read())
            
            # Limpiar archivo comprimido temporal (opcional)
            # os.remove(compressed_path)  # Mantener por si acaso
            
            logger.info(f"✅ {filename} descargado y descomprimido exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error descargando {filename}: {e}")
            
            # Limpiar archivos parciales
            for path in [local_path, local_path + '.gz']:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except:
                        pass
            
            return False
    
    def check_cache_status(self) -> Dict:
        """
        Verifica el estado de todos los archivos de caché
        
        Returns:
            dict: Estado de cada archivo (exists, compressed_exists, size)
        """
        status = {}
        
        for filename in self.config.keys():
            local_path = os.path.join(self.cache_dir, filename)
            compressed_path = local_path + '.gz'
            
            file_info = {
                'exists': os.path.exists(local_path),
                'compressed_exists': os.path.exists(compressed_path),
                'size': None,
                'compressed_size': None
            }
            
            if file_info['exists']:
                file_info['size'] = os.path.getsize(local_path)
            
            if file_info['compressed_exists']:
                file_info['compressed_size'] = os.path.getsize(compressed_path)
            
            status[filename] = file_info
        
        return status
    
    def download_all_graphs(self, force_redownload: bool = False) -> Dict:
        """
        Descarga todos los grafos desde Google Drive si no existen localmente
        
        Args:
            force_redownload (bool): Forzar re-descarga incluso si los archivos existen
        
        Returns:
            dict: Estado de descarga para cada archivo
        """
        if not self.config:
            logger.error("No hay configuración de Google Drive disponible")
            return {}
        
        download_status = {}
        
        for filename in self.config.keys():
            try:
                success = self.download_graph(filename, force_redownload)
                download_status[filename] = success
                
                if success:
                    logger.info(f"✅ {filename} descargado y listo")
                else:
                    logger.warning(f"⚠️ {filename} no se pudo descargar")
                    
            except Exception as e:
                logger.error(f"❌ Error descargando {filename}: {e}")
                download_status[filename] = False
        
        # Resumen
        successful = sum(1 for status in download_status.values() if status)
        total = len(download_status)
        
        logger.info(f"📊 Descarga completada: {successful}/{total} archivos")
        
        return download_status
    
    def get_required_files(self, priority_filter: Optional[List[str]] = None) -> List[str]:
        """
        Obtener lista de archivos requeridos, filtrados por prioridad
        
        Args:
            priority_filter (list): Lista de prioridades ('critical', 'high', 'medium')
        
        Returns:
            list: Nombres de archivos que cumplen el filtro
        """
        if not priority_filter:
            return list(self.config.keys())
        
        required = []
        for filename, info in self.config.items():
            priority = info.get('priority', 'medium')
            if priority in priority_filter:
                required.append(filename)
        
        return required
    
    def ensure_critical_graphs(self) -> bool:
        """
        Asegurar que los grafos críticos estén disponibles
        
        Returns:
            bool: True si todos los grafos críticos están disponibles
        """
        critical_files = self.get_required_files(['critical'])
        
        if not critical_files:
            logger.warning("No hay archivos críticos definidos")
            return True
        
        missing_files = []
        for filename in critical_files:
            local_path = os.path.join(self.cache_dir, filename)
            if not os.path.exists(local_path):
                missing_files.append(filename)
        
        if not missing_files:
            logger.info("✅ Todos los grafos críticos están disponibles")
            return True
        
        logger.info(f"⬇️ Descargando {len(missing_files)} grafos críticos faltantes...")
        
        # Descargar archivos críticos faltantes
        download_status = {}
        for filename in missing_files:
            success = self.download_graph(filename)
            download_status[filename] = success
        
        # Verificar si todos se descargaron exitosamente
        all_downloaded = all(download_status.values())
        
        if all_downloaded:
            logger.info("✅ Todos los grafos críticos descargados exitosamente")
        else:
            failed = [f for f, success in download_status.items() if not success]
            logger.error(f"❌ Falló descarga de grafos críticos: {failed}")
        
        return all_downloaded


# Función de conveniencia para usar en el sistema principal
def get_chile_graphs_manager() -> GoogleDriveGraphsManager:
    """
    Obtener instancia del manager de grafos configurado
    
    Returns:
        GoogleDriveGraphsManager: Manager listo para usar
    """
    return GoogleDriveGraphsManager()


# CLI para pruebas manuales
if __name__ == "__main__":
    """
    Interfaz de línea de comandos para probar el sistema
    """
    import sys
    
    print("🚀 GOOGLE DRIVE GRAPHS MANAGER")
    print("=" * 50)
    
    # Crear manager
    manager = GoogleDriveGraphsManager()
    
    if not manager.config:
        print("❌ No hay configuración disponible")
        print("💡 Ejecuta: ./setup_google_drive.sh")
        sys.exit(1)
    
    # Menú interactivo
    while True:
        print("\n📋 OPCIONES:")
        print("1. Ver estado de archivos")
        print("2. Descargar todos los grafos")
        print("3. Asegurar grafos críticos")
        print("4. Descargar archivo específico")
        print("5. Salir")
        
        try:
            choice = input("\n🎯 Elige una opción (1-5): ").strip()
            
            if choice == "1":
                print("\n📊 ESTADO DE ARCHIVOS:")
                status = manager.check_cache_status()
                for filename, info in status.items():
                    exists_icon = "✅" if info['exists'] else "❌"
                    compressed_icon = "📦" if info['compressed_exists'] else "📭"
                    print(f"   {exists_icon} {filename}")
                    print(f"      {compressed_icon} Comprimido disponible: {info['compressed_exists']}")
                    if info['size']:
                        size_mb = info['size'] / (1024 * 1024)
                        print(f"      📏 Tamaño: {size_mb:.1f} MB")
            
            elif choice == "2":
                print("\n⬇️ DESCARGANDO TODOS LOS GRAFOS...")
                results = manager.download_all_graphs()
                
                print("\n📊 RESULTADOS:")
                for filename, success in results.items():
                    icon = "✅" if success else "❌"
                    print(f"   {icon} {filename}")
            
            elif choice == "3":
                print("\n🎯 ASEGURANDO GRAFOS CRÍTICOS...")
                success = manager.ensure_critical_graphs()
                
                if success:
                    print("✅ Grafos críticos listos")
                else:
                    print("❌ Error asegurando grafos críticos")
            
            elif choice == "4":
                print("\n📁 ARCHIVOS DISPONIBLES:")
                for i, filename in enumerate(manager.config.keys(), 1):
                    print(f"   {i}. {filename}")
                
                try:
                    file_choice = int(input("\n🎯 Número de archivo: ")) - 1
                    filenames = list(manager.config.keys())
                    
                    if 0 <= file_choice < len(filenames):
                        filename = filenames[file_choice]
                        print(f"\n⬇️ Descargando {filename}...")
                        success = manager.download_graph(filename, force_redownload=True)
                        
                        if success:
                            print(f"✅ {filename} descargado exitosamente")
                        else:
                            print(f"❌ Error descargando {filename}")
                    else:
                        print("❌ Número inválido")
                        
                except ValueError:
                    print("❌ Entrada inválida")
            
            elif choice == "5":
                print("👋 ¡Hasta luego!")
                break
                
            else:
                print("❌ Opción inválida")
                
        except KeyboardInterrupt:
            print("\n\n👋 ¡Hasta luego!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")