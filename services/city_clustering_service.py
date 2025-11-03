#!/usr/bin/env python3
"""
🏙️ City Clustering Service - Clustering inteligente de POIs por ciudades
Versión especializada para arquitectura multi-ciudad con detección automática
Usa H3, geocoding y machine learning para clustering preciso
"""

import logging
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import math
import json
from pathlib import Path
import numpy as np
from geopy.distance import geodesic
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler

from .h3_spatial_partitioner import H3SpatialPartitioner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CityCluster:
    """Representa un cluster de ciudad detectado"""
    cluster_id: str
    name: str
    country: str
    center_lat: float
    center_lon: float
    pois: List[Dict] = field(default_factory=list)
    confidence: float = 0.0
    
    @property
    def coordinates(self) -> Tuple[float, float]:
        """Retorna (lat, lon) del centro"""
        return (self.center_lat, self.center_lon)
    
    @property
    def poi_count(self) -> int:
        """Número de POIs en este cluster"""
        return len(self.pois)
    
    def add_poi(self, poi: Dict):
        """Añade POI al cluster"""
        self.pois.append(poi)
    
    def calculate_radius_km(self) -> float:
        """Calcula radio del cluster en km"""
        if len(self.pois) < 2:
            return 0.0
        
        distances = []
        for poi in self.pois:
            poi_coord = (poi['lat'], poi['lon'])
            distance = geodesic(self.coordinates, poi_coord).kilometers
            distances.append(distance)
        
        return max(distances) if distances else 0.0
    
    def get_poi_density(self) -> float:
        """Calcula densidad POIs/km²"""
        radius = self.calculate_radius_km()
        if radius == 0:
            return float('inf')
        
        area = math.pi * (radius ** 2)
        return len(self.pois) / area if area > 0 else 0

@dataclass
class ClusteringConfig:
    """Configuración para clustering de ciudades"""
    # H3 parameters
    h3_resolution: int = 7  # ~5km hexágonos
    
    # DBSCAN parameters  
    eps_km: float = 25.0  # Radio máximo para cluster (25km)
    min_samples: int = 2  # Mínimo POIs por cluster
    
    # Filtering
    min_city_radius_km: float = 0.1   # Radio mínimo ciudad (100m)
    max_city_radius_km: float = 50.0  # Radio máximo ciudad
    min_pois_per_city: int = 1        # Mínimo POIs por ciudad
    
    # Confidence thresholds
    high_confidence_threshold: float = 0.8
    medium_confidence_threshold: float = 0.6

class CityClusteringService:
    """
    Servicio avanzado de clustering de POIs por ciudades
    
    Combina múltiples técnicas:
    - H3 spatial indexing para primera aproximación
    - DBSCAN clustering para refinamiento
    - Geocoding reverso para validación de nombres
    - ML features para scoring de confianza
    """
    
    def __init__(self, config: Optional[ClusteringConfig] = None):
        """
        Inicializa el servicio de clustering
        
        Args:
            config: Configuración personalizada (opcional)
        """
        self.config = config or ClusteringConfig()
        self.h3_partitioner = H3SpatialPartitioner()
        
        # Cache de resultados
        self.clustering_cache: Dict[str, List[CityCluster]] = {}
        
        logger.info("🏙️ CityClusteringService inicializado")
    
    def cluster_pois_advanced(self, pois: List[Dict]) -> List[CityCluster]:
        """
        Clustering avanzado de POIs por ciudades
        
        Args:
            pois: Lista de POIs con lat, lon, name, etc.
            
        Returns:
            Lista de clusters de ciudades detectados
        """
        logger.info(f"🔍 Clustering avanzado de {len(pois)} POIs...")
        
        if not pois:
            return []
        
        # Generar cache key
        cache_key = self._generate_cache_key(pois)
        if cache_key in self.clustering_cache:
            logger.info("💾 Resultado obtenido desde cache")
            return self.clustering_cache[cache_key]
        
        # Paso 1: Clustering inicial con H3
        h3_clusters = self._h3_initial_clustering(pois)
        logger.info(f"📐 H3 clustering: {len(h3_clusters)} clusters iniciales")
        
        # Paso 2: Refinamiento con DBSCAN
        refined_clusters = self._dbscan_refinement(h3_clusters)
        logger.info(f"🎯 DBSCAN refinement: {len(refined_clusters)} clusters refinados")
        
        # Paso 3: Validación y naming
        validated_clusters = self._validate_and_name_clusters(refined_clusters)
        logger.info(f"✅ Validación completada: {len(validated_clusters)} ciudades finales")
        
        # Paso 4: Scoring de confianza
        final_clusters = self._calculate_confidence_scores(validated_clusters)
        
        # Filtrar clusters de baja calidad
        quality_clusters = [
            cluster for cluster in final_clusters
            if cluster.confidence >= 0.3 and cluster.poi_count >= self.config.min_pois_per_city
        ]
        
        logger.info(f"🏆 Clustering completado: {len(quality_clusters)} ciudades de calidad")
        
        # Cache resultado
        self.clustering_cache[cache_key] = quality_clusters
        
        return quality_clusters
    
    def _generate_cache_key(self, pois: List[Dict]) -> str:
        """Genera clave de cache para POIs"""
        import hashlib
        
        # Crear string único basado en coordenadas
        coords_str = ";".join([
            f"{poi['lat']:.4f},{poi['lon']:.4f}" 
            for poi in sorted(pois, key=lambda x: (x['lat'], x['lon']))
        ])
        
        return hashlib.md5(coords_str.encode()).hexdigest()[:16]
    
    def _h3_initial_clustering(self, pois: List[Dict]) -> Dict[str, List[Dict]]:
        """Clustering inicial usando H3 spatial indexing"""
        clusters = defaultdict(list)
        
        for poi in pois:
            h3_id = self.h3_partitioner.coordinate_to_h3(
                poi['lat'], poi['lon']
            )
            clusters[h3_id].append(poi)
        
        return dict(clusters)
    
    def _dbscan_refinement(self, h3_clusters: Dict[str, List[Dict]]) -> List[List[Dict]]:
        """Refinamiento con DBSCAN para detectar sub-clusters"""
        refined_clusters = []
        
        for h3_id, cluster_pois in h3_clusters.items():
            if len(cluster_pois) < 2:
                # Clusters pequeños pasan directo
                refined_clusters.append(cluster_pois)
                continue
            
            # Preparar datos para DBSCAN
            coordinates = np.array([[poi['lat'], poi['lon']] for poi in cluster_pois])
            
            # Convertir eps de km a grados (aproximado)
            eps_degrees = self.config.eps_km / 111.0  # 1 grado ≈ 111km
            
            # DBSCAN clustering
            dbscan = DBSCAN(
                eps=eps_degrees,
                min_samples=self.config.min_samples,
                metric='euclidean'
            )
            
            cluster_labels = dbscan.fit_predict(coordinates)
            
            # Agrupar por labels
            dbscan_groups = defaultdict(list)
            for i, label in enumerate(cluster_labels):
                if label != -1:  # No es ruido
                    dbscan_groups[label].append(cluster_pois[i])
                else:
                    # POIs de ruido van como clusters individuales
                    refined_clusters.append([cluster_pois[i]])
            
            # Añadir grupos válidos
            for group_pois in dbscan_groups.values():
                if len(group_pois) >= self.config.min_pois_per_city:
                    refined_clusters.append(group_pois)
        
        return refined_clusters
    
    def _validate_and_name_clusters(self, clusters: List[List[Dict]]) -> List[CityCluster]:
        """Valida clusters y asigna nombres de ciudad"""
        validated_clusters = []
        
        logger.info(f"🔍 Validando {len(clusters)} clusters de entrada:")
        for i, cluster_pois in enumerate(clusters):
            logger.info(f"   Cluster {i}: {len(cluster_pois)} POIs - {[poi.get('name', 'Unknown') for poi in cluster_pois]}")
        
        for i, cluster_pois in enumerate(clusters):
            if not cluster_pois:
                continue
            
            # Calcular centro del cluster
            center_lat = sum(poi['lat'] for poi in cluster_pois) / len(cluster_pois)
            center_lon = sum(poi['lon'] for poi in cluster_pois) / len(cluster_pois)
            
            # Calcular radio del cluster
            radius_km = self._calculate_cluster_radius(cluster_pois, center_lat, center_lon)
            
            # Validar tamaño del cluster (permitir clusters de 1 POI)
            if len(cluster_pois) == 1:
                # Clusters de 1 POI siempre son válidos
                logger.info(f"✅ Cluster {i} validado - 1 POI: {cluster_pois[0].get('name', 'Unknown')}")
            elif not (self.config.min_city_radius_km <= radius_km <= self.config.max_city_radius_km):
                logger.warning(f"❌ Cluster {i} descartado - radio inválido: {radius_km:.4f}km (min: {self.config.min_city_radius_km}, max: {self.config.max_city_radius_km})")
                logger.warning(f"   Condición: {self.config.min_city_radius_km} <= {radius_km} <= {self.config.max_city_radius_km} = {self.config.min_city_radius_km <= radius_km <= self.config.max_city_radius_km}")
                continue
            else:
                logger.info(f"✅ Cluster {i} validado - {len(cluster_pois)} POIs, radio: {radius_km:.1f}km")
            
            # Determinar nombre y país
            city_name = self._determine_cluster_name(cluster_pois)
            country = self._determine_cluster_country(cluster_pois)
            
            logger.info(f"🏙️ Cluster {i}: '{city_name}', {country} - Centro: ({center_lat:.4f}, {center_lon:.4f})")
            
            # Crear cluster validado
            city_cluster = CityCluster(
                cluster_id=f"cluster_{i}",
                name=city_name,
                country=country,
                center_lat=center_lat,
                center_lon=center_lon,
                pois=cluster_pois
            )
            
            validated_clusters.append(city_cluster)
            logger.info(f"✅ Cluster {i} añadido a clusters validados")
        
        return validated_clusters
    
    def _calculate_cluster_radius(self, pois: List[Dict], 
                                center_lat: float, center_lon: float) -> float:
        """Calcula radio máximo del cluster en km"""
        if not pois:
            return 0.0
        
        center = (center_lat, center_lon)
        max_distance = 0.0
        
        for poi in pois:
            poi_coord = (poi['lat'], poi['lon'])
            distance = geodesic(center, poi_coord).kilometers
            max_distance = max(max_distance, distance)
        
        return max_distance
    
    def _determine_cluster_name(self, pois: List[Dict]) -> str:
        """Determina el nombre más representativo del cluster"""
        
        # Buscar nombres de ciudades explícitos
        city_names = []
        for poi in pois:
            # Campos posibles para ciudad
            city_fields = ['city', 'locality', 'municipality']
            for field in city_fields:
                if field in poi and poi[field]:
                    city_names.append(poi[field])
            
            # Buscar en address nested
            if 'address' in poi and isinstance(poi['address'], dict):
                for field in city_fields:
                    if field in poi['address'] and poi['address'][field]:
                        city_names.append(poi['address'][field])
            
            # NUEVA LÓGICA: Extraer ciudad desde address string
            if 'address' in poi and isinstance(poi['address'], str):
                city_from_address = self._extract_city_from_address_string(poi['address'])
                if city_from_address:
                    city_names.append(city_from_address)
        
        if city_names:
            # Usar la ciudad más frecuente
            most_common = Counter(city_names).most_common(1)
            return most_common[0][0]
        
        # Fallback: usar el POI más representativo
        # Priorizar POIs con nombres de lugares conocidos
        landmark_keywords = ['tower', 'museum', 'cathedral', 'palace', 'bridge', 'square']
        
        for poi in pois:
            poi_name = poi.get('name', '').lower()
            for keyword in landmark_keywords:
                if keyword in poi_name:
                    # Extraer ciudad del nombre del landmark
                    parts = poi['name'].split()
                    if len(parts) > 1:
                        return parts[-1]  # Última palabra suele ser la ciudad
        
        # Último fallback: usar primer POI
        return pois[0].get('name', f"City_{len(pois)}_pois")
    
    def _extract_city_from_address_string(self, address: str) -> Optional[str]:
        """
        Extrae nombre de ciudad desde string de dirección
        Formatos soportados:
        - "Antofagasta, Chile"
        - "Paris, France"  
        - "123 Main St, New York, USA"
        """
        if not address or not isinstance(address, str):
            return None
        
        # Limpiar address
        address = address.strip()
        
        # Patrones comunes de dirección
        parts = address.split(',')
        
        if len(parts) >= 2:
            # Formato: "Ciudad, País" o "Calle, Ciudad, País"
            if len(parts) == 2:
                # "Antofagasta, Chile"
                city_candidate = parts[0].strip()
                # Validar que no sea una calle (no debe contener números)
                if not any(char.isdigit() for char in city_candidate):
                    return city_candidate
            elif len(parts) >= 3:
                # "123 Main St, New York, USA" -> segunda parte es ciudad
                city_candidate = parts[-2].strip()  # Penúltima parte
                return city_candidate
        
        # Fallback: buscar palabras conocidas de ciudad
        city_keywords = ['santiago', 'valparaiso', 'antofagasta', 'calama', 
                        'iquique', 'temuco', 'concepcion', 'valdivia',
                        'paris', 'london', 'madrid', 'barcelona', 'rome',
                        'amsterdam', 'berlin', 'prague', 'vienna']
        
        address_lower = address.lower()
        for keyword in city_keywords:
            if keyword in address_lower:
                # Extraer la palabra completa que contiene el keyword
                words = address.split()
                for word in words:
                    if keyword in word.lower():
                        # Limpiar punctuación
                        clean_word = word.strip('.,;:')
                        return clean_word.title()
        
        return None
    
    def _determine_cluster_country(self, pois: List[Dict]) -> str:
        """Determina el país del cluster"""
        countries = []
        
        for poi in pois:
            if 'country' in poi and poi['country']:
                countries.append(poi['country'])
            elif 'address' in poi and isinstance(poi['address'], dict):
                if 'country' in poi['address'] and poi['address']['country']:
                    countries.append(poi['address']['country'])
            
            # NUEVA LÓGICA: Extraer país desde address string  
            elif 'address' in poi and isinstance(poi['address'], str):
                country_from_address = self._extract_country_from_address_string(poi['address'])
                if country_from_address:
                    countries.append(country_from_address)
        
        if countries:
            # País más frecuente
            most_common = Counter(countries).most_common(1)
            return most_common[0][0]
        
        return "Unknown"
    
    def _extract_country_from_address_string(self, address: str) -> Optional[str]:
        """Extrae país desde string de dirección"""
        if not address or not isinstance(address, str):
            return None
            
        address = address.strip().lower()
        
        # Mapeo de países comunes
        country_mapping = {
            'chile': 'Chile',
            'argentina': 'Argentina', 
            'peru': 'Peru',
            'bolivia': 'Bolivia',
            'brazil': 'Brazil',
            'france': 'France',
            'spain': 'Spain', 
            'italy': 'Italy',
            'germany': 'Germany',
            'netherlands': 'Netherlands',
            'uk': 'United Kingdom',
            'usa': 'United States',
            'canada': 'Canada'
        }
        
        for country_key, country_name in country_mapping.items():
            if country_key in address:
                return country_name
        
        return None
        
        # Fallback geográfico básico
        center_lat = sum(poi['lat'] for poi in pois) / len(pois)
        
        # Rangos aproximados de países
        if -56 <= center_lat <= -17:
            return "Chile"
        elif 35 <= center_lat <= 71:
            return "Europe"
        elif 24 <= center_lat <= 49:
            return "United States"
        
        return "Unknown"
    
    def _calculate_confidence_scores(self, clusters: List[CityCluster]) -> List[CityCluster]:
        """Calcula scores de confianza para cada cluster"""
        
        for cluster in clusters:
            confidence_factors = []
            
            # Factor 1: Número de POIs (más POIs = más confianza)
            poi_factor = min(1.0, cluster.poi_count / 5.0)
            confidence_factors.append(poi_factor)
            
            # Factor 2: Densidad del cluster (más denso = más confianza)
            radius = cluster.calculate_radius_km()
            if radius > 0:
                density_factor = min(1.0, cluster.poi_count / radius)
                confidence_factors.append(density_factor)
            else:
                confidence_factors.append(1.0)
            
            # Factor 3: Calidad del nombre (nombre reconocible = más confianza)
            name_quality = self._assess_name_quality(cluster.name)
            confidence_factors.append(name_quality)
            
            # Factor 4: Consistencia geográfica
            geo_consistency = self._assess_geographic_consistency(cluster)
            confidence_factors.append(geo_consistency)
            
            # Calcular confianza final (promedio ponderado)
            cluster.confidence = sum(confidence_factors) / len(confidence_factors)
        
        return clusters
    
    def _assess_name_quality(self, name: str) -> float:
        """Evalúa la calidad del nombre de ciudad (0.0 - 1.0)"""
        if not name or name == "Unknown":
            return 0.1
        
        # Nombres genéricos tienen baja calidad
        generic_names = ["city", "cluster", "location", "place", "area"]
        if any(generic in name.lower() for generic in generic_names):
            return 0.3
        
        # Nombres con números tienen calidad media
        if any(char.isdigit() for char in name):
            return 0.5
        
        # Nombres reconocibles tienen alta calidad
        known_cities = [
            "paris", "london", "berlin", "madrid", "rome", "amsterdam",
            "santiago", "valparaiso", "antofagasta", "calama"
        ]
        if name.lower() in known_cities:
            return 1.0
        
        # Nombres normales tienen buena calidad
        return 0.7
    
    def _assess_geographic_consistency(self, cluster: CityCluster) -> float:
        """Evalúa consistencia geográfica del cluster (0.0 - 1.0)"""
        if cluster.poi_count < 2:
            return 1.0
        
        # Calcular varianza de distancias al centro
        distances = []
        for poi in cluster.pois:
            poi_coord = (poi['lat'], poi['lon'])
            distance = geodesic(cluster.coordinates, poi_coord).kilometers
            distances.append(distance)
        
        if not distances:
            return 1.0
        
        # Consistencia basada en desviación estándar
        mean_distance = sum(distances) / len(distances)
        variance = sum((d - mean_distance) ** 2 for d in distances) / len(distances)
        std_dev = math.sqrt(variance)
        
        # Normalizar: std_dev pequeño = alta consistencia
        consistency = max(0.1, 1.0 - (std_dev / 50.0))  # 50km como referencia
        return min(1.0, consistency)
    
    def get_clustering_stats(self, clusters: List[CityCluster]) -> Dict:
        """Genera estadísticas del clustering"""
        if not clusters:
            return {"total_clusters": 0}
        
        total_pois = sum(cluster.poi_count for cluster in clusters)
        confidences = [cluster.confidence for cluster in clusters]
        radii = [cluster.calculate_radius_km() for cluster in clusters]
        
        # Categorizar por confianza
        high_conf = sum(1 for c in confidences if c >= self.config.high_confidence_threshold)
        medium_conf = sum(1 for c in confidences 
                         if self.config.medium_confidence_threshold <= c < self.config.high_confidence_threshold)
        low_conf = len(clusters) - high_conf - medium_conf
        
        return {
            "total_clusters": len(clusters),
            "total_pois": total_pois,
            "avg_pois_per_cluster": total_pois / len(clusters),
            "avg_confidence": sum(confidences) / len(confidences),
            "avg_radius_km": sum(radii) / len(radii),
            "confidence_distribution": {
                "high": high_conf,
                "medium": medium_conf,
                "low": low_conf
            },
            "countries": list(set(cluster.country for cluster in clusters))
        }

if __name__ == "__main__":
    """Test del City Clustering Service"""
    
    print("🏙️ TESTING CITY CLUSTERING SERVICE")
    print("=" * 50)
    
    # POIs de prueba - Multiple ciudades
    test_pois = [
        # París
        {"name": "Eiffel Tower", "lat": 48.8584, "lon": 2.2945, "city": "Paris", "country": "France"},
        {"name": "Louvre Museum", "lat": 48.8606, "lon": 2.3376, "city": "Paris", "country": "France"},
        {"name": "Notre Dame", "lat": 48.8530, "lon": 2.3499, "city": "Paris", "country": "France"},
        
        # Amsterdam
        {"name": "Van Gogh Museum", "lat": 52.3584, "lon": 4.8811, "city": "Amsterdam", "country": "Netherlands"},
        {"name": "Anne Frank House", "lat": 52.3752, "lon": 4.8840, "city": "Amsterdam", "country": "Netherlands"},
        
        # Berlin
        {"name": "Brandenburg Gate", "lat": 52.5163, "lon": 13.3777, "city": "Berlin", "country": "Germany"},
        {"name": "Museum Island", "lat": 52.5170, "lon": 13.4019, "city": "Berlin", "country": "Germany"},
        
        # Santiago (lejos)
        {"name": "La Moneda", "lat": -33.4428, "lon": -70.6540, "city": "Santiago", "country": "Chile"}
    ]
    
    # Crear servicio
    service = CityClusteringService()
    
    # Test clustering avanzado
    clusters = service.cluster_pois_advanced(test_pois)
    
    print(f"✅ Clusters detectados: {len(clusters)}")
    for cluster in clusters:
        print(f"   🏙️ {cluster.name} ({cluster.country})")
        print(f"      POIs: {cluster.poi_count}, Confianza: {cluster.confidence:.2f}")
        print(f"      Radio: {cluster.calculate_radius_km():.1f}km")
    
    # Estadísticas
    stats = service.get_clustering_stats(clusters)
    print(f"\n📊 ESTADÍSTICAS:")
    for key, value in stats.items():
        print(f"   {key}: {value}")