#!/usr/bin/env python3
"""
🚗 OSRM Service - Motor de ruteo profesional
Implementación según recomendaciones de stack de producción
"""

import requests
import subprocess
import time
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OSRMService:
    """
    Servicio OSRM para routing profesional con <0.1s por consulta
    Reemplaza NetworkX para routing de producción
    """
    
    def __init__(self, profile: str = "car", port: int = 5555):
        """
        Inicializa servicio OSRM
        
        Args:
            profile: Perfil de transporte (car, foot, bike)
            port: Puerto del servidor OSRM
        """
        self.profile = profile
        self.port = port
        self.base_url = f"http://localhost:{port}"
        self.container_name = f"osrm_{profile}"
        self.data_dir = Path(__file__).parent.parent / "osrm_data"
        self.processed_dir = self.data_dir / f"processed_{profile}"
        
        logger.info(f"🚗 OSRMService iniciado - Perfil: {profile}, Puerto: {port}")
    
    def setup_osrm_data(self) -> bool:
        """
        Prepara datos OSM para OSRM
        
        Returns:
            True si el setup fue exitoso
        """
        logger.info(f"🔧 Configurando datos OSRM para perfil {self.profile}...")
        
        # Verificar archivo PBF
        pbf_file = self.data_dir / "chile-latest.osm.pbf"
        if not pbf_file.exists():
            logger.error(f"❌ Archivo PBF no encontrado: {pbf_file}")
            return False
        
        # Crear directorio procesado
        self.processed_dir.mkdir(exist_ok=True)
        
        # Archivos de salida OSRM
        osrm_file = self.processed_dir / "chile-latest.osrm"
        
        if osrm_file.exists():
            logger.info(f"✅ Datos OSRM ya procesados: {osrm_file}")
            return True
        
        try:
            # Comando de extracción OSRM
            extract_cmd = [
                "docker", "run", "-t", "--rm", "--platform", "linux/amd64",
                "-v", f"{self.data_dir}:/data",
                "-v", f"{self.processed_dir}:/processed",
                "osrm/osrm-backend:latest",
                "osrm-extract", "-p", f"/opt/car.lua", 
                "/data/chile-latest.osm.pbf"
            ]
            
            logger.info(f"🔄 Ejecutando extracción OSRM...")
            result = subprocess.run(extract_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"❌ Error en extracción: {result.stderr}")
                return False
            
            # Comando de partición OSRM
            partition_cmd = [
                "docker", "run", "-t", "--rm", "--platform", "linux/amd64",
                "-v", f"{self.data_dir}:/data",
                "osrm/osrm-backend:latest",
                "osrm-partition", "/data/chile-latest.osrm"
            ]
            
            logger.info(f"🔄 Ejecutando partición OSRM...")
            result = subprocess.run(partition_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"❌ Error en partición: {result.stderr}")
                return False
            
            # Comando de customización OSRM
            customize_cmd = [
                "docker", "run", "-t", "--rm", "--platform", "linux/amd64",
                "-v", f"{self.data_dir}:/data",
                "osrm/osrm-backend:latest",
                "osrm-customize", "/data/chile-latest.osrm"
            ]
            
            logger.info(f"🔄 Ejecutando customización OSRM...")
            result = subprocess.run(customize_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"❌ Error en customización: {result.stderr}")
                return False
            
            logger.info(f"✅ Datos OSRM procesados exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en setup OSRM: {e}")
            return False
    
    def start_server(self) -> bool:
        """
        Inicia servidor OSRM en Docker
        
        Returns:
            True si el servidor inició correctamente
        """
        try:
            # Detener container existente
            subprocess.run([
                "docker", "stop", self.container_name
            ], capture_output=True)
            
            subprocess.run([
                "docker", "rm", self.container_name
            ], capture_output=True)
            
            # Iniciar nuevo container
            run_cmd = [
                "docker", "run", "-d", "--platform", "linux/amd64",
                "--name", self.container_name,
                "-p", f"{self.port}:5000",
                "-v", f"{self.data_dir}:/data",
                "osrm/osrm-backend:latest",
                "osrm-routed", "--algorithm", "mld", "/data/chile-latest.osrm"
            ]
            
            logger.info(f"🚀 Iniciando servidor OSRM en puerto {self.port}...")
            result = subprocess.run(run_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"❌ Error al iniciar servidor: {result.stderr}")
                return False
            
            # Esperar que el servidor esté listo
            for i in range(30):  # 30 segundos máximo
                try:
                    response = requests.get(f"{self.base_url}/health", timeout=1)
                    if response.status_code == 200:
                        logger.info(f"✅ Servidor OSRM listo en {self.base_url}")
                        return True
                except:
                    time.sleep(1)
            
            logger.error(f"❌ Servidor OSRM no respondió en 30s")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error iniciando servidor: {e}")
            return False
    
    def route(self, origin: Tuple[float, float], destination: Tuple[float, float]) -> Optional[Dict]:
        """
        Calcula ruta entre dos puntos
        
        Args:
            origin: (lat, lon) del origen
            destination: (lat, lon) del destino
            
        Returns:
            Diccionario con información de la ruta o None si falla
        """
        try:
            # Coordenadas en formato OSRM (lon, lat)
            origin_str = f"{origin[1]},{origin[0]}"
            destination_str = f"{destination[1]},{destination[0]}"
            
            # Construir URL
            url = f"{self.base_url}/route/v1/{self.profile}/{origin_str};{destination_str}"
            params = {
                "overview": "full",
                "geometries": "geojson",
                "steps": "true"
            }
            
            # Realizar consulta
            start_time = time.time()
            response = requests.get(url, params=params, timeout=5)
            query_time = time.time() - start_time
            
            if response.status_code != 200:
                logger.error(f"❌ Error OSRM: {response.status_code}")
                return None
            
            data = response.json()
            
            if data.get("code") != "Ok":
                logger.error(f"❌ Error ruta: {data.get('message')}")
                return None
            
            route = data["routes"][0]
            
            return {
                "distance_m": route["distance"],
                "duration_s": route["duration"],
                "geometry": route["geometry"],
                "query_time_s": query_time,
                "legs": route.get("legs", []),
                "waypoints": data.get("waypoints", [])
            }
            
        except Exception as e:
            logger.error(f"❌ Error en route: {e}")
            return None
    
    def distance_matrix(self, coordinates: List[Tuple[float, float]]) -> Optional[Dict]:
        """
        Calcula matriz de distancias origen-destino
        
        Args:
            coordinates: Lista de (lat, lon)
            
        Returns:
            Matriz de distancias y tiempos
        """
        try:
            # Convertir coordenadas a formato OSRM
            coords_str = ";".join([f"{lon},{lat}" for lat, lon in coordinates])
            
            url = f"{self.base_url}/table/v1/{self.profile}/{coords_str}"
            params = {
                "annotations": "distance,duration"
            }
            
            start_time = time.time()
            response = requests.get(url, params=params, timeout=10)
            query_time = time.time() - start_time
            
            if response.status_code != 200:
                logger.error(f"❌ Error matriz: {response.status_code}")
                return None
            
            data = response.json()
            
            if data.get("code") != "Ok":
                logger.error(f"❌ Error matriz: {data.get('message')}")
                return None
            
            return {
                "distances": data["distances"],  # Matriz NxN en metros
                "durations": data["durations"],  # Matriz NxN en segundos
                "query_time_s": query_time,
                "sources": data.get("sources", []),
                "destinations": data.get("destinations", [])
            }
            
        except Exception as e:
            logger.error(f"❌ Error en distance_matrix: {e}")
            return None
    
    def health_check(self) -> bool:
        """
        Verifica que el servidor OSRM esté funcionando
        
        Returns:
            True si el servidor responde correctamente
        """
        try:
            # Usar ruta de prueba simple en lugar de /health
            test_url = f"{self.base_url}/route/v1/{self.profile}/-70.6693,-33.4489;-71.6127,-33.0472"
            response = requests.get(test_url, timeout=2)
            return response.status_code == 200 and "Ok" in response.text
        except:
            return False
    
    def stop_server(self):
        """Detiene el servidor OSRM"""
        try:
            subprocess.run([
                "docker", "stop", self.container_name
            ], capture_output=True)
            
            subprocess.run([
                "docker", "rm", self.container_name
            ], capture_output=True)
            
            logger.info(f"🛑 Servidor OSRM detenido: {self.container_name}")
            
        except Exception as e:
            logger.error(f"❌ Error deteniendo servidor: {e}")

# Factory para múltiples perfiles
class OSRMFactory:
    """Factory para crear servicios OSRM con diferentes perfiles"""
    
    @staticmethod
    def create_car_service() -> OSRMService:
        """Crea servicio para automóviles"""
        return OSRMService(profile="car", port=5555)
    
    @staticmethod
    def create_foot_service() -> OSRMService:
        """Crea servicio para peatones"""
        return OSRMService(profile="foot", port=5556)
    
    @staticmethod
    def create_bike_service() -> OSRMService:
        """Crea servicio para bicicletas"""
        return OSRMService(profile="bike", port=5002)

if __name__ == "__main__":
    """Test básico del servicio OSRM"""
    
    print("🚗 TESTING OSRM SERVICE")
    print("=" * 50)
    
    # Crear servicio
    osrm = OSRMFactory.create_car_service()
    
    # Setup inicial
    if osrm.setup_osrm_data():
        print("✅ Setup completado")
        
        # Iniciar servidor
        if osrm.start_server():
            print("✅ Servidor iniciado")
            
            # Test de ruta
            santiago = (-33.4489, -70.6693)
            valparaiso = (-33.0472, -71.6127)
            
            route = osrm.route(santiago, valparaiso)
            
            if route:
                print(f"✅ Ruta exitosa:")
                print(f"   Distancia: {route['distance_m']/1000:.1f}km")
                print(f"   Tiempo: {route['duration_s']/60:.1f}min")
                print(f"   Query: {route['query_time_s']:.3f}s")
            else:
                print("❌ Error en ruta")
            
            # Detener servidor
            osrm.stop_server()
        else:
            print("❌ Error iniciando servidor")
    else:
        print("❌ Error en setup")