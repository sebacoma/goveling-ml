#!/usr/bin/env python3
"""
📦 AMAZON S3 GRAPHS MANAGER FOR CHILE
Gestor profesional de grafos usando Amazon S3 (escalable, seguro, rápido)
"""

import os
import pickle
import gzip
import logging
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from typing import Dict, Optional, List
import json
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

class S3GraphsManager:
    """
    Gestor profesional para subir/descargar grafos de Chile usando Amazon S3
    
    Ventajas vs Google Drive:
    - ✅ Más rápido (CDN global)  
    - ✅ Más confiable (99.999999999% durabilidad)
    - ✅ Mejor integración con aplicaciones
    - ✅ Versionado automático
    - ✅ Escalabilidad profesional
    """
    
    def __init__(self, config_file: str = "s3_config.json"):
        """
        Inicializar el manager de S3
        
        Args:
            config_file (str): Archivo JSON con configuración S3
        """
        self.cache_dir = "cache"
        self.config_file = config_file
        
        # Crear directorio cache si no existe
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Cargar configuración
        self.config = self._load_config()
        
        # Inicializar cliente S3
        self.s3_client = None
        self._init_s3_client()
        
        logger.info(f"S3GraphsManager inicializado con {len(self.config.get('files', {}))} archivos")
    
    def _load_config(self) -> Dict:
        """Cargar configuración desde archivo JSON"""
        try:
            if not os.path.exists(self.config_file):
                logger.warning(f"No existe {self.config_file}, usando configuración vacía")
                return {}
            
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            # Validar estructura requerida
            required_keys = ['bucket_name', 'region', 'files']
            for key in required_keys:
                if key not in config:
                    logger.error(f"Configuración S3 inválida: falta '{key}'")
                    return {}
            
            logger.info(f"Configuración S3 cargada: bucket={config['bucket_name']}, region={config['region']}")
            return config
            
        except Exception as e:
            logger.error(f"Error cargando configuración S3: {e}")
            return {}
    
    def _init_s3_client(self):
        """Inicializar cliente de S3 con credenciales"""
        if not self.config:
            return
        
        try:
            # Método 1: Credenciales desde archivo de configuración
            if 'aws_access_key_id' in self.config and 'aws_secret_access_key' in self.config:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=self.config['aws_access_key_id'],
                    aws_secret_access_key=self.config['aws_secret_access_key'],
                    region_name=self.config['region']
                )
                logger.info("✅ Cliente S3 inicializado con credenciales del archivo config")
            
            # Método 2: Credenciales desde variables de entorno
            elif os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY'):
                self.s3_client = boto3.client(
                    's3',
                    region_name=self.config['region']
                )
                logger.info("✅ Cliente S3 inicializado con variables de entorno")
            
            # Método 3: IAM Role (recomendado para producción)
            else:
                self.s3_client = boto3.client(
                    's3',
                    region_name=self.config['region']
                )
                logger.info("✅ Cliente S3 inicializado con IAM Role")
                
        except Exception as e:
            logger.error(f"❌ Error inicializando cliente S3: {e}")
            self.s3_client = None
    
    def _get_s3_key(self, filename: str) -> str:
        """
        Obtener la clave S3 para un archivo
        
        Args:
            filename (str): Nombre del archivo local
            
        Returns:
            str: Clave S3 (path en el bucket)
        """
        # Usar prefijo para organizar archivos
        prefix = self.config.get('prefix', 'goveling-ml/graphs')
        return f"{prefix}/{filename}.gz"
    
    def download_graph(self, filename: str, force_redownload: bool = False) -> bool:
        """
        Descargar un grafo específico desde S3
        
        Args:
            filename (str): Nombre del archivo a descargar (ej: 'chile_graph_cache.pkl')
            force_redownload (bool): Forzar re-descarga si el archivo ya existe
        
        Returns:
            bool: True si se descargó exitosamente
        """
        if not self.s3_client:
            logger.error("❌ Cliente S3 no inicializado")
            return False
        
        local_path = os.path.join(self.cache_dir, filename)
        
        # Verificar si ya existe y no forzar re-descarga
        if os.path.exists(local_path) and not force_redownload:
            logger.info(f"✅ {filename} ya existe localmente")
            return True
        
        try:
            bucket_name = self.config['bucket_name']
            s3_key = self._get_s3_key(filename)
            
            logger.info(f"⬇️ Descargando {filename} desde S3: s3://{bucket_name}/{s3_key}")
            
            # Descargar archivo comprimido a temporal
            compressed_path = local_path + '.gz'
            
            # Verificar que el objeto existe en S3
            try:
                self.s3_client.head_object(Bucket=bucket_name, Key=s3_key)
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    logger.error(f"❌ Archivo no encontrado en S3: {s3_key}")
                    return False
                raise
            
            # Descargar archivo
            self.s3_client.download_file(bucket_name, s3_key, compressed_path)
            
            # Descomprimir archivo
            logger.info(f"📦 Descomprimiendo {filename}...")
            with gzip.open(compressed_path, 'rb') as f_gz:
                with open(local_path, 'wb') as f_out:
                    f_out.write(f_gz.read())
            
            # Obtener tamaños para logging
            compressed_size = os.path.getsize(compressed_path)
            uncompressed_size = os.path.getsize(local_path)
            
            logger.info(f"✅ {filename} descargado exitosamente")
            logger.info(f"   📊 Tamaño: {compressed_size/1024/1024:.1f}MB → {uncompressed_size/1024/1024:.1f}MB")
            
            # Limpiar archivo comprimido temporal (opcional)
            # os.remove(compressed_path)
            
            return True
            
        except NoCredentialsError:
            logger.error("❌ Credenciales AWS no encontradas")
            return False
        except ClientError as e:
            logger.error(f"❌ Error S3: {e}")
            return False
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
    
    def upload_graph(self, filename: str, compress: bool = True) -> bool:
        """
        Subir un grafo local a S3
        
        Args:
            filename (str): Nombre del archivo a subir
            compress (bool): Comprimir antes de subir
            
        Returns:
            bool: True si se subió exitosamente
        """
        if not self.s3_client:
            logger.error("❌ Cliente S3 no inicializado")
            return False
        
        local_path = os.path.join(self.cache_dir, filename)
        
        if not os.path.exists(local_path):
            logger.error(f"❌ Archivo local no existe: {local_path}")
            return False
        
        try:
            bucket_name = self.config['bucket_name']
            s3_key = self._get_s3_key(filename)
            
            if compress:
                # Comprimir antes de subir
                compressed_path = local_path + '.gz'
                if not os.path.exists(compressed_path):
                    logger.info(f"🗜️ Comprimiendo {filename}...")
                    with open(local_path, 'rb') as f_in:
                        with gzip.open(compressed_path, 'wb') as f_out:
                            f_out.write(f_in.read())
                
                upload_path = compressed_path
                original_size = os.path.getsize(local_path)
                compressed_size = os.path.getsize(compressed_path)
                compression_ratio = (1 - compressed_size/original_size) * 100
                
                logger.info(f"📦 Compresión: {original_size/1024/1024:.1f}MB → {compressed_size/1024/1024:.1f}MB ({compression_ratio:.1f}% reducción)")
            else:
                upload_path = local_path
            
            # Subir a S3
            logger.info(f"⬆️ Subiendo a S3: s3://{bucket_name}/{s3_key}")
            
            # Subir con metadata
            extra_args = {
                'Metadata': {
                    'original-filename': filename,
                    'upload-timestamp': str(int(os.path.getmtime(local_path))),
                    'goveling-version': '1.0'
                }
            }
            
            self.s3_client.upload_file(upload_path, bucket_name, s3_key, ExtraArgs=extra_args)
            
            logger.info(f"✅ {filename} subido exitosamente a S3")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error subiendo {filename}: {e}")
            return False
    
    def check_cache_status(self) -> Dict:
        """
        Verifica el estado de todos los archivos de caché (local y S3)
        
        Returns:
            dict: Estado de cada archivo
        """
        status = {}
        
        if not self.config.get('files'):
            return status
        
        for filename in self.config['files'].keys():
            local_path = os.path.join(self.cache_dir, filename)
            compressed_path = local_path + '.gz'
            
            file_info = {
                'exists_local': os.path.exists(local_path),
                'exists_compressed': os.path.exists(compressed_path),
                'exists_s3': False,
                'size_local': None,
                'size_compressed': None,
                'size_s3': None
            }
            
            # Información local
            if file_info['exists_local']:
                file_info['size_local'] = os.path.getsize(local_path)
            
            if file_info['exists_compressed']:
                file_info['size_compressed'] = os.path.getsize(compressed_path)
            
            # Información S3
            if self.s3_client:
                try:
                    s3_key = self._get_s3_key(filename)
                    response = self.s3_client.head_object(
                        Bucket=self.config['bucket_name'], 
                        Key=s3_key
                    )
                    file_info['exists_s3'] = True
                    file_info['size_s3'] = response['ContentLength']
                except ClientError:
                    file_info['exists_s3'] = False
            
            status[filename] = file_info
        
        return status
    
    def download_all_graphs(self, force_redownload: bool = False) -> Dict:
        """
        Descarga todos los grafos desde S3 si no existen localmente
        
        Args:
            force_redownload (bool): Forzar re-descarga incluso si los archivos existen
        
        Returns:
            dict: Estado de descarga para cada archivo
        """
        if not self.config.get('files'):
            logger.error("No hay archivos configurados en S3")
            return {}
        
        download_status = {}
        
        for filename in self.config['files'].keys():
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
        
        logger.info(f"📊 Descarga desde S3 completada: {successful}/{total} archivos")
        
        return download_status
    
    def ensure_critical_graphs(self) -> bool:
        """
        Asegurar que los grafos críticos estén disponibles
        
        Returns:
            bool: True si todos los grafos críticos están disponibles
        """
        if not self.config.get('files'):
            logger.warning("No hay archivos definidos en configuración S3")
            return True
        
        critical_files = [
            filename for filename, info in self.config['files'].items()
            if info.get('priority') == 'critical'
        ]
        
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
        
        logger.info(f"⬇️ Descargando {len(missing_files)} grafos críticos desde S3...")
        
        # Descargar archivos críticos faltantes
        download_status = {}
        for filename in missing_files:
            success = self.download_graph(filename)
            download_status[filename] = success
        
        # Verificar si todos se descargaron exitosamente
        all_downloaded = all(download_status.values())
        
        if all_downloaded:
            logger.info("✅ Todos los grafos críticos descargados desde S3")
        else:
            failed = [f for f, success in download_status.items() if not success]
            logger.error(f"❌ Falló descarga de grafos críticos desde S3: {failed}")
        
        return all_downloaded


# Función de conveniencia
def get_s3_graphs_manager() -> S3GraphsManager:
    """
    Obtener instancia del manager S3 configurado
    
    Returns:
        S3GraphsManager: Manager listo para usar
    """
    return S3GraphsManager()


# CLI para gestión S3
if __name__ == "__main__":
    """
    Interfaz de línea de comandos para gestionar grafos en S3
    """
    import sys
    
    print("🚀 AMAZON S3 GRAPHS MANAGER")
    print("=" * 50)
    
    manager = S3GraphsManager()
    
    if not manager.config:
        print("❌ No hay configuración S3 disponible")
        print("💡 Crea: s3_config.json con bucket, región y credenciales")
        sys.exit(1)
    
    if not manager.s3_client:
        print("❌ Cliente S3 no inicializado")
        print("💡 Verifica credenciales AWS")
        sys.exit(1)
    
    # Menú interactivo
    while True:
        print("\n📋 OPCIONES S3:")
        print("1. Ver estado de archivos (local + S3)")
        print("2. Descargar todos los grafos desde S3")
        print("3. Subir todos los grafos a S3")  
        print("4. Asegurar grafos críticos")
        print("5. Descargar archivo específico")
        print("6. Subir archivo específico")
        print("7. Salir")
        
        try:
            choice = input("\n🎯 Elige una opción (1-7): ").strip()
            
            if choice == "1":
                print("\n📊 ESTADO DE ARCHIVOS:")
                status = manager.check_cache_status()
                for filename, info in status.items():
                    local_icon = "✅" if info['exists_local'] else "❌"
                    s3_icon = "☁️✅" if info['exists_s3'] else "☁️❌"
                    print(f"   {local_icon} Local: {filename}")
                    print(f"   {s3_icon} S3: {filename}")
                    
                    if info['size_local']:
                        print(f"      📏 Local: {info['size_local']/1024/1024:.1f} MB")
                    if info['size_s3']:
                        print(f"      ☁️ S3: {info['size_s3']/1024/1024:.1f} MB")
            
            elif choice == "2":
                print("\n⬇️ DESCARGANDO TODOS LOS GRAFOS DESDE S3...")
                results = manager.download_all_graphs()
                
                print("\n📊 RESULTADOS:")
                for filename, success in results.items():
                    icon = "✅" if success else "❌"
                    print(f"   {icon} {filename}")
            
            elif choice == "3":
                print("\n⬆️ SUBIENDO TODOS LOS GRAFOS A S3...")
                files = list(manager.config['files'].keys())
                
                for filename in files:
                    print(f"\n📤 Subiendo {filename}...")
                    success = manager.upload_graph(filename)
                    icon = "✅" if success else "❌"
                    print(f"   {icon} {filename}")
            
            elif choice == "4":
                print("\n🎯 ASEGURANDO GRAFOS CRÍTICOS...")
                success = manager.ensure_critical_graphs()
                
                if success:
                    print("✅ Grafos críticos listos")
                else:
                    print("❌ Error asegurando grafos críticos")
            
            elif choice in ["5", "6"]:
                print("\n📁 ARCHIVOS DISPONIBLES:")
                files = list(manager.config['files'].keys())
                for i, filename in enumerate(files, 1):
                    print(f"   {i}. {filename}")
                
                try:
                    file_choice = int(input("\n🎯 Número de archivo: ")) - 1
                    
                    if 0 <= file_choice < len(files):
                        filename = files[file_choice]
                        
                        if choice == "5":  # Descargar
                            print(f"\n⬇️ Descargando {filename}...")
                            success = manager.download_graph(filename, force_redownload=True)
                        else:  # Subir
                            print(f"\n⬆️ Subiendo {filename}...")
                            success = manager.upload_graph(filename)
                        
                        icon = "✅" if success else "❌"
                        action = "descargado" if choice == "5" else "subido"
                        print(f"   {icon} {filename} {action}")
                    else:
                        print("❌ Número inválido")
                        
                except ValueError:
                    print("❌ Entrada inválida")
            
            elif choice == "7":
                print("👋 ¡Hasta luego!")
                break
                
            else:
                print("❌ Opción inválida")
                
        except KeyboardInterrupt:
            print("\n\n👋 ¡Hasta luego!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")