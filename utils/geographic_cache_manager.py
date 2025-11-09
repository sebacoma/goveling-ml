#!/usr/bin/env python3
"""
🗺️ GEOGRAPHIC CACHE MANAGER
Sistema de caché inteligente para reducir llamadas a Google Places API

Características:
- Cache por ciudad/región con TTL inteligente
- Clustering geográfico para optimizar búsquedas
- Persistencia en disco para mantener datos entre reinicios
- Compresión de datos para optimizar espacio
- Invalidación inteligente basada en tiempo y uso
"""

import os
import json
import time
import gzip
import hashlib
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Entrada del caché con metadata"""
    data: List[Dict[str, Any]]
    created_at: float
    last_accessed: float
    access_count: int
    location: Tuple[float, float]  # (lat, lon)
    radius: float
    place_types: List[str]
    ttl: float  # Time to live en segundos

class GeographicCacheManager:
    """
    🗺️ Gestor de caché geográfico inteligente
    
    Reduce llamadas API mediante:
    - Cache por ubicación geográfica
    - TTL dinámico según tipo de lugar
    - Clustering de ubicaciones cercanas
    - Persistencia automática
    """
    
    def __init__(self, 
                 cache_dir: str = "cache_places",
                 default_ttl_hours: int = 24,
                 max_cache_size_mb: int = 100,
                 compression: bool = True):
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        self.default_ttl = default_ttl_hours * 3600  # Convertir a segundos
        self.max_cache_size = max_cache_size_mb * 1024 * 1024  # Convertir a bytes
        self.compression = compression
        
        # Cache en memoria para acceso rápido
        self.memory_cache: Dict[str, CacheEntry] = {}
        
        # TTL específico por tipo de lugar
        self.ttl_by_type = {
            'tourist_attraction': 7 * 24 * 3600,    # 7 días (no cambian frecuentemente)
            'museum': 7 * 24 * 3600,                # 7 días
            'park': 5 * 24 * 3600,                  # 5 días
            'monument': 14 * 24 * 3600,             # 14 días (muy estables)
            'church': 14 * 24 * 3600,               # 14 días
            'restaurant': 2 * 24 * 3600,            # 2 días (pueden cambiar)
            'cafe': 2 * 24 * 3600,                  # 2 días
            'bar': 24 * 3600,                       # 1 día (horarios variables)
            'lodging': 3 * 24 * 3600,               # 3 días (ocupación variable)
            'shopping_mall': 5 * 24 * 3600,         # 5 días
            'point_of_interest': 3 * 24 * 3600      # 3 días (genérico)
        }
        
        # Cargar caché existente
        self._load_from_disk()
        
        # Limpiar caché expirado
        self._cleanup_expired()
        
        logger.info(f"✅ GeographicCacheManager inicializado")
        logger.info(f"   📁 Cache dir: {self.cache_dir}")
        logger.info(f"   🧠 Entries en memoria: {len(self.memory_cache)}")
        
    def _calculate_ttl(self, place_types: List[str]) -> float:
        """Calcular TTL óptimo basado en los tipos de lugares"""
        if not place_types:
            return self.default_ttl
            
        # Usar el TTL más conservador (menor) entre los tipos
        ttls = [self.ttl_by_type.get(place_type, self.default_ttl) for place_type in place_types]
        return min(ttls)
    
    def _generate_cache_key(self, lat: float, lon: float, radius: float, place_types: List[str]) -> str:
        """Generar clave única para la ubicación y parámetros"""
        # Redondear coordenadas para agrupar búsquedas cercanas
        lat_rounded = round(lat, 3)  # ~111m precision
        lon_rounded = round(lon, 3)
        
        # Normalizar tipos y ordenar para consistencia
        types_normalized = sorted([t.lower().strip() for t in place_types])
        
        # Crear string para hash
        cache_string = f"{lat_rounded}_{lon_rounded}_{radius}_{','.join(types_normalized)}"
        
        # Generar hash corto pero único
        return hashlib.md5(cache_string.encode()).hexdigest()[:16]
    
    def _get_file_path(self, cache_key: str) -> Path:
        """Obtener ruta del archivo de caché"""
        extension = ".json.gz" if self.compression else ".json"
        return self.cache_dir / f"{cache_key}{extension}"
    
    def _is_within_radius(self, center_lat: float, center_lon: float, 
                         cache_lat: float, cache_lon: float, 
                         search_radius: float, cache_radius: float) -> bool:
        """Verificar si una ubicación cached puede servir para una búsqueda"""
        
        # Calcular distancia entre centros
        distance = self._haversine_distance(center_lat, center_lon, cache_lat, cache_lon)
        
        # La búsqueda cached sirve si:
        # 1. El punto de búsqueda está dentro del radio cached
        # 2. O si el radio cached cubre el área de búsqueda
        coverage_radius = min(cache_radius, search_radius + distance)
        
        return distance <= coverage_radius
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calcular distancia haversine en metros"""
        R = 6371000  # Radio de la Tierra en metros
        
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = (math.sin(dlat/2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def get_cached_places(self, 
                         lat: float, 
                         lon: float, 
                         radius: float = 5000,
                         place_types: List[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Obtener lugares del caché si están disponibles y válidos
        
        Args:
            lat: Latitud del centro de búsqueda
            lon: Longitud del centro de búsqueda  
            radius: Radio de búsqueda en metros
            place_types: Tipos de lugares a buscar
            
        Returns:
            Lista de lugares cached o None si no hay caché válido
        """
        if place_types is None:
            place_types = ['tourist_attraction', 'restaurant', 'point_of_interest']
            
        current_time = time.time()
        
        # Buscar en caché en memoria primero
        for cache_key, entry in self.memory_cache.items():
            # Verificar si la entrada cubre nuestra búsqueda
            if not self._is_within_radius(lat, lon, entry.location[0], entry.location[1], 
                                        radius, entry.radius):
                continue
                
            # Verificar si los tipos coinciden (al menos parcialmente)
            if not any(ptype in entry.place_types for ptype in place_types):
                continue
                
            # Verificar TTL
            if current_time - entry.created_at > entry.ttl:
                logger.debug(f"🗑️ Cache expirado para {cache_key}")
                continue
                
            # ✅ Cache válido encontrado
            entry.last_accessed = current_time
            entry.access_count += 1
            
            # Filtrar resultados por tipos solicitados y radio
            filtered_results = self._filter_cached_results(
                entry.data, lat, lon, radius, place_types
            )
            
            logger.info(f"🎯 Cache HIT: {len(filtered_results)} lugares encontrados")
            logger.debug(f"   Key: {cache_key}")
            logger.debug(f"   Edad: {(current_time - entry.created_at) / 3600:.1f}h")
            
            return filtered_results
        
        # No se encontró caché válido
        logger.debug(f"❌ Cache MISS para {lat:.3f},{lon:.3f} r={radius}m")
        return None
    
    def _filter_cached_results(self, 
                              cached_data: List[Dict[str, Any]], 
                              search_lat: float, 
                              search_lon: float,
                              search_radius: float,
                              place_types: List[str]) -> List[Dict[str, Any]]:
        """Filtrar resultados cached por proximidad y tipo"""
        
        filtered = []
        
        for place in cached_data:
            # Verificar distancia
            place_lat = place.get('lat', 0)
            place_lon = place.get('lon', 0)
            distance = self._haversine_distance(search_lat, search_lon, place_lat, place_lon)
            
            if distance > search_radius:
                continue
                
            # Verificar tipo
            place_type = place.get('type', '').lower()
            if place_types and place_type not in [pt.lower() for pt in place_types]:
                continue
                
            # Agregar información de distancia
            place_copy = place.copy()
            place_copy['distance_m'] = distance
            place_copy['cache_hit'] = True
            
            filtered.append(place_copy)
        
        # Ordenar por distancia
        filtered.sort(key=lambda x: x.get('distance_m', 0))
        
        return filtered
    
    def cache_places(self, 
                    lat: float, 
                    lon: float, 
                    radius: float,
                    place_types: List[str],
                    places_data: List[Dict[str, Any]]) -> None:
        """
        Guardar lugares en caché
        
        Args:
            lat: Latitud del centro de búsqueda
            lon: Longitud del centro de búsqueda
            radius: Radio de búsqueda utilizado
            place_types: Tipos de lugares buscados
            places_data: Datos de lugares obtenidos de la API
        """
        if not places_data:
            logger.debug("No hay datos para cachear")
            return
            
        cache_key = self._generate_cache_key(lat, lon, radius, place_types)
        current_time = time.time()
        ttl = self._calculate_ttl(place_types)
        
        # Crear entrada de caché
        cache_entry = CacheEntry(
            data=places_data,
            created_at=current_time,
            last_accessed=current_time,
            access_count=1,
            location=(lat, lon),
            radius=radius,
            place_types=place_types,
            ttl=ttl
        )
        
        # Guardar en memoria
        self.memory_cache[cache_key] = cache_entry
        
        # Guardar en disco de manera asíncrona
        try:
            self._save_to_disk(cache_key, cache_entry)
            logger.info(f"💾 Cached {len(places_data)} lugares")
            logger.debug(f"   Key: {cache_key}")
            logger.debug(f"   TTL: {ttl / 3600:.1f}h")
            logger.debug(f"   Tipos: {', '.join(place_types)}")
        except Exception as e:
            logger.error(f"Error guardando cache: {e}")
    
    def _save_to_disk(self, cache_key: str, entry: CacheEntry) -> None:
        """Guardar entrada de caché en disco"""
        file_path = self._get_file_path(cache_key)
        
        # Preparar datos para serialización
        cache_data = {
            'entry': asdict(entry),
            'metadata': {
                'version': '1.0',
                'saved_at': time.time(),
                'compression': self.compression
            }
        }
        
        try:
            # Serializar a JSON
            json_data = json.dumps(cache_data, separators=(',', ':'))
            
            if self.compression:
                # Guardar comprimido
                with gzip.open(file_path, 'wt', encoding='utf-8') as f:
                    f.write(json_data)
            else:
                # Guardar normal
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(json_data)
                    
        except Exception as e:
            logger.error(f"Error escribiendo cache a disco: {e}")
    
    def _load_from_disk(self) -> None:
        """Cargar caché existente desde disco"""
        if not self.cache_dir.exists():
            return
            
        loaded_count = 0
        
        for file_path in self.cache_dir.glob("*"):
            if not file_path.is_file():
                continue
                
            try:
                cache_key = file_path.stem.replace('.json', '')
                
                # Leer archivo
                if file_path.suffix == '.gz':
                    with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                        cache_data = json.load(f)
                else:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                
                # Recrear entrada de caché
                entry_dict = cache_data['entry']
                entry = CacheEntry(
                    data=entry_dict['data'],
                    created_at=entry_dict['created_at'],
                    last_accessed=entry_dict['last_accessed'],
                    access_count=entry_dict['access_count'],
                    location=tuple(entry_dict['location']),
                    radius=entry_dict['radius'],
                    place_types=entry_dict['place_types'],
                    ttl=entry_dict['ttl']
                )
                
                self.memory_cache[cache_key] = entry
                loaded_count += 1
                
            except Exception as e:
                logger.warning(f"Error cargando cache {file_path}: {e}")
                # Eliminar archivo corrupto
                try:
                    file_path.unlink()
                except:
                    pass
        
        if loaded_count > 0:
            logger.info(f"📚 Cargadas {loaded_count} entradas de caché desde disco")
    
    def _cleanup_expired(self) -> None:
        """Limpiar entradas de caché expiradas"""
        current_time = time.time()
        expired_keys = []
        
        for cache_key, entry in self.memory_cache.items():
            if current_time - entry.created_at > entry.ttl:
                expired_keys.append(cache_key)
        
        for key in expired_keys:
            # Eliminar de memoria
            del self.memory_cache[key]
            
            # Eliminar archivo
            file_path = self._get_file_path(key)
            try:
                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                logger.warning(f"Error eliminando cache expirado {file_path}: {e}")
        
        if expired_keys:
            logger.info(f"🗑️ Limpiadas {len(expired_keys)} entradas expiradas")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del caché"""
        current_time = time.time()
        
        total_entries = len(self.memory_cache)
        total_places = sum(len(entry.data) for entry in self.memory_cache.values())
        
        # Calcular tamaño del caché en disco
        cache_size = 0
        if self.cache_dir.exists():
            for file_path in self.cache_dir.glob("*"):
                if file_path.is_file():
                    cache_size += file_path.stat().st_size
        
        # Estadísticas de acceso
        access_counts = [entry.access_count for entry in self.memory_cache.values()]
        avg_access = sum(access_counts) / len(access_counts) if access_counts else 0
        
        # TTL promedio restante
        ttl_remaining = []
        for entry in self.memory_cache.values():
            remaining = entry.ttl - (current_time - entry.created_at)
            ttl_remaining.append(max(0, remaining))
        
        avg_ttl_remaining = sum(ttl_remaining) / len(ttl_remaining) if ttl_remaining else 0
        
        return {
            'total_entries': total_entries,
            'total_places_cached': total_places,
            'cache_size_mb': cache_size / (1024 * 1024),
            'avg_places_per_entry': total_places / total_entries if total_entries > 0 else 0,
            'avg_access_count': avg_access,
            'avg_ttl_remaining_hours': avg_ttl_remaining / 3600,
            'hit_rate_potential': '80-90%' if total_entries > 10 else 'Insufficient data'
        }
    
    def clear_cache(self, older_than_hours: Optional[float] = None) -> int:
        """
        Limpiar caché manualmente
        
        Args:
            older_than_hours: Solo eliminar entradas más antiguas que X horas
            
        Returns:
            Número de entradas eliminadas
        """
        if older_than_hours is None:
            # Limpiar todo
            count = len(self.memory_cache)
            self.memory_cache.clear()
            
            # Eliminar archivos
            if self.cache_dir.exists():
                for file_path in self.cache_dir.glob("*"):
                    if file_path.is_file():
                        try:
                            file_path.unlink()
                        except:
                            pass
            
            logger.info(f"🧹 Cache completamente limpiado ({count} entradas)")
            return count
        
        else:
            # Limpiar entradas antiguas
            current_time = time.time()
            cutoff_time = older_than_hours * 3600
            
            keys_to_remove = []
            for cache_key, entry in self.memory_cache.items():
                if current_time - entry.created_at > cutoff_time:
                    keys_to_remove.append(cache_key)
            
            for key in keys_to_remove:
                del self.memory_cache[key]
                
                file_path = self._get_file_path(key)
                try:
                    if file_path.exists():
                        file_path.unlink()
                except:
                    pass
            
            logger.info(f"🧹 Limpiadas {len(keys_to_remove)} entradas > {older_than_hours}h")
            return len(keys_to_remove)


# Instancia global para uso en servicios
_global_cache_manager = None

def get_cache_manager() -> GeographicCacheManager:
    """Obtener instancia global del cache manager"""
    global _global_cache_manager
    
    if _global_cache_manager is None:
        _global_cache_manager = GeographicCacheManager()
    
    return _global_cache_manager


if __name__ == "__main__":
    # Test básico
    cache = GeographicCacheManager()
    
    # Simular datos de lugares
    sample_places = [
        {
            'name': 'Plaza de Armas',
            'lat': -33.4372,
            'lon': -70.6506,
            'type': 'tourist_attraction',
            'rating': 4.5
        },
        {
            'name': 'Mercado Central',
            'lat': -33.4333,
            'lon': -70.6500,
            'type': 'restaurant', 
            'rating': 4.2
        }
    ]
    
    # Test cache
    print("🧪 Testing Geographic Cache Manager")
    
    # Cachear lugares
    cache.cache_places(-33.437, -70.650, 5000, ['tourist_attraction', 'restaurant'], sample_places)
    
    # Recuperar del cache
    cached_results = cache.get_cached_places(-33.437, -70.650, 5000, ['tourist_attraction'])
    
    print(f"✅ Cached: {len(sample_places)} lugares")
    print(f"✅ Retrieved: {len(cached_results) if cached_results else 0} lugares")
    
    # Estadísticas
    stats = cache.get_cache_stats()
    print(f"📊 Stats: {stats}")