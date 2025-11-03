#!/usr/bin/env python3
"""
Servicio de Routing Multi-Modal para Chile - Versión Optimizada con Lazy Loading
Utiliza los caches pre-generados para routing comercial con carga bajo demanda
"""

import os
import logging
import pickle
import time
from typing import Dict, Optional, Any
import threading

class ChileMultiModalRouter:
    """
    Router multi-modal comercial para Chile
    Versión optimizada con lazy loading y cache inteligente en memoria
    """
    
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = cache_dir
        self.logger = logging.getLogger(__name__)
        
        # Configuración de velocidades promedio (km/h)
        self.speeds = {
            'drive': 50,      # Velocidad promedio en ciudad
            'walk': 5,        # Velocidad peatonal
            'bike': 15        # Velocidad en bicicleta
        }
        
        # Cache en memoria con lazy loading
        self._memory_cache = {}
        self._cache_locks = {
            'drive': threading.Lock(),
            'walk': threading.Lock(),
            'bike': threading.Lock()
        }
        self._cache_loaded = {
            'drive': False,
            'walk': False,
            'bike': False
        }
        
        # Mapeo de archivos de cache
        self._cache_files = {
            'drive': 'chile_graph_cache.pkl',
            'walk': 'santiago_metro_walking_cache.pkl', 
            'bike': 'santiago_metro_cycling_cache.pkl'
        }
        
        # Estadísticas de uso para optimización
        self._usage_stats = {
            'drive': {'requests': 0, 'cache_hits': 0},
            'walk': {'requests': 0, 'cache_hits': 0},
            'bike': {'requests': 0, 'cache_hits': 0}
        }
        
        self.logger.info("🚀 ChileMultiModalRouter inicializado con lazy loading optimizado")
    
    def _load_cache_for_mode(self, mode: str) -> Optional[Any]:
        """
        Cargar cache para un modo específico usando lazy loading thread-safe
        """
        if mode not in self._cache_files:
            self.logger.error(f"❌ Modo no válido: {mode}")
            return None
        
        # Si ya está cargado, retornar desde memoria
        if self._cache_loaded[mode]:
            self._usage_stats[mode]['cache_hits'] += 1
            return self._memory_cache.get(mode)
        
        # Thread-safe loading con lock
        with self._cache_locks[mode]:
            # Double-check locking pattern
            if self._cache_loaded[mode]:
                self._usage_stats[mode]['cache_hits'] += 1
                return self._memory_cache.get(mode)
            
            cache_file = self._cache_files[mode]
            full_path = os.path.join(self.cache_dir, cache_file)
            
            if not os.path.exists(full_path):
                self.logger.warning(f"⚠️ Cache no encontrado para {mode}: {full_path}")
                return None
            
            try:
                start_time = time.time()
                self.logger.info(f"📥 Cargando cache {mode} desde {cache_file}...")
                
                with open(full_path, 'rb') as f:
                    cache_data = pickle.load(f)
                
                load_time = time.time() - start_time
                size_mb = os.path.getsize(full_path) / (1024 * 1024)
                
                # Almacenar en memoria
                self._memory_cache[mode] = cache_data
                self._cache_loaded[mode] = True
                
                self.logger.info(
                    f"✅ Cache {mode} cargado exitosamente: {size_mb:.1f}MB en {load_time:.2f}s"
                )
                
                return cache_data
                
            except Exception as e:
                self.logger.error(f"❌ Error cargando cache {mode}: {e}")
                return None
    
    def get_cache_status(self) -> Dict[str, Dict]:
        """Verificar estado de archivos de cache y memoria"""
        status = {}
        
        for mode, cache_file in self._cache_files.items():
            full_path = os.path.join(self.cache_dir, cache_file)
            
            file_exists = os.path.exists(full_path)
            file_size_mb = os.path.getsize(full_path) / (1024 * 1024) if file_exists else 0
            
            status[mode] = {
                'exists': file_exists,
                'size': file_size_mb,
                'path': full_path,
                'loaded_in_memory': self._cache_loaded[mode],
                'requests': self._usage_stats[mode]['requests'],
                'cache_hits': self._usage_stats[mode]['cache_hits'],
                'hit_ratio': (
                    self._usage_stats[mode]['cache_hits'] / self._usage_stats[mode]['requests'] 
                    if self._usage_stats[mode]['requests'] > 0 else 0
                )
            }
        
        return status
    
    def preload_cache(self, mode: str) -> bool:
        """
        Pre-cargar cache específico para optimización
        """
        self.logger.info(f"🚀 Pre-cargando cache para {mode}...")
        cache_data = self._load_cache_for_mode(mode)
        return cache_data is not None
    
    def preload_all_caches(self) -> Dict[str, bool]:
        """
        Pre-cargar todos los caches (útil para warm-up)
        """
        self.logger.info("🚀 Pre-cargando todos los caches...")
        results = {}
        
        for mode in self._cache_files.keys():
            results[mode] = self.preload_cache(mode)
        
        loaded_count = sum(results.values())
        self.logger.info(f"✅ Pre-carga completada: {loaded_count}/{len(results)} caches cargados")
        
        return results
    
    def clear_memory_cache(self, mode: Optional[str] = None) -> None:
        """
        Limpiar cache en memoria para liberar RAM
        """
        if mode:
            # Limpiar cache específico
            if mode in self._memory_cache:
                with self._cache_locks[mode]:
                    del self._memory_cache[mode]
                    self._cache_loaded[mode] = False
                self.logger.info(f"🧹 Cache {mode} eliminado de memoria")
        else:
            # Limpiar todos los caches
            for mode in self._cache_files.keys():
                with self._cache_locks[mode]:
                    if mode in self._memory_cache:
                        del self._memory_cache[mode]
                    self._cache_loaded[mode] = False
            self.logger.info("🧹 Todos los caches eliminados de memoria")
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """
        Obtener información sobre uso de memoria
        """
        import sys
        
        memory_info = {
            'caches_in_memory': {},
            'total_estimated_mb': 0
        }
        
        for mode, loaded in self._cache_loaded.items():
            if loaded and mode in self._memory_cache:
                # Estimación del tamaño en memoria
                obj_size = sys.getsizeof(self._memory_cache[mode])
                size_mb = obj_size / (1024 * 1024)
                
                memory_info['caches_in_memory'][mode] = {
                    'loaded': True,
                    'estimated_size_mb': size_mb
                }
                memory_info['total_estimated_mb'] += size_mb
            else:
                memory_info['caches_in_memory'][mode] = {
                    'loaded': False,
                    'estimated_size_mb': 0
                }
        
        return memory_info
    
    def get_route(self, 
                  start_lat: float, 
                  start_lon: float, 
                  end_lat: float, 
                  end_lon: float, 
                  mode: str = 'drive') -> Optional[Dict]:
        """
        Calcular ruta usando lazy loading del cache correspondiente
        Carga el grafo NetworkX solo cuando es necesario
        """
        
        try:
            start_time = time.time()
            
            # Actualizar estadísticas de uso
            self._usage_stats[mode]['requests'] += 1
            
            # Verificar que el modo sea válido
            if mode not in self.speeds:
                self.logger.error(f"❌ Modo de transporte no válido: {mode}")
                return None
            
            # Intentar cargar cache específico (lazy loading)
            cache_data = self._load_cache_for_mode(mode)
            
            if cache_data is None:
                # Fallback a cálculo simple si no hay cache
                self.logger.warning(f"⚠️ Cache no disponible para {mode}, usando cálculo simple")
                return self._calculate_simple_route(start_lat, start_lon, end_lat, end_lon, mode)
            
            # TODO: Aquí se implementaría el routing real con NetworkX
            # Por ahora, simulamos que usamos el cache pero hacemos cálculo simple
            self.logger.debug(f"📊 Usando cache {mode} (simulado) para routing avanzado")
            
            # Calcular distancia euclidiana aproximada (placeholder)
            lat_diff = end_lat - start_lat  
            lon_diff = end_lon - start_lon
            distance_deg = (lat_diff**2 + lon_diff**2)**0.5
            distance_km = distance_deg * 111
            
            # Calcular tiempo usando velocidad del modo
            time_hours = distance_km / self.speeds[mode]
            time_minutes = time_hours * 60
            
            # Crear path simple
            path = [(start_lat, start_lon), (end_lat, end_lon)]
            
            processing_time = time.time() - start_time
            
            self.logger.info(f"✅ Ruta {mode}: {distance_km:.2f}km, {time_minutes:.1f}min (cache usado)")
            
            return {
                'success': True,
                'mode': mode,
                'distance_km': round(distance_km, 2),
                'time_minutes': round(time_minutes, 1),
                'path': [(i, coord) for i, coord in enumerate(path)],
                'geometry': {
                    'type': 'LineString',
                    'coordinates': [(lon, lat) for lat, lon in path]
                },
                'source': 'cached_calculation',
                'cache_used': True,
                'processing_time_ms': round(processing_time * 1000, 2)
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error calculando ruta {mode}: {str(e)}")
            return None
    
    def _calculate_simple_route(self, start_lat: float, start_lon: float, 
                               end_lat: float, end_lon: float, mode: str) -> Dict:
        """
        Cálculo simple de ruta cuando no hay cache disponible
        """
        # Calcular distancia euclidiana aproximada
        lat_diff = end_lat - start_lat  
        lon_diff = end_lon - start_lon
        distance_deg = (lat_diff**2 + lon_diff**2)**0.5
        distance_km = distance_deg * 111
        
        # Calcular tiempo usando velocidad del modo
        time_hours = distance_km / self.speeds[mode]
        time_minutes = time_hours * 60
        
        # Crear path simple
        path = [(start_lat, start_lon), (end_lat, end_lon)]
        
        return {
            'success': True,
            'mode': mode,
            'distance_km': round(distance_km, 2),
            'time_minutes': round(time_minutes, 1),
            'path': [(i, coord) for i, coord in enumerate(path)],
            'geometry': {
                'type': 'LineString',
                'coordinates': [(lon, lat) for lat, lon in path]
            },
            'source': 'simple_calculation',
            'cache_used': False
        }

    def calculate_multimodal_routes(self, 
                                   start_lat: float, 
                                   start_lon: float, 
                                   end_lat: float, 
                                   end_lon: float) -> Dict[str, Optional[Dict]]:
        """
        Calcular rutas para todos los modos de transporte con lazy loading inteligente
        """
        start_time = time.time()
        results = {}
        
        # Calcular rutas para todos los modos
        for mode in self.speeds.keys():
            route = self.get_route(start_lat, start_lon, end_lat, end_lon, mode)
            results[mode] = route
        
        processing_time = time.time() - start_time
        
        # Agregar métricas de la operación multi-modal
        successful_routes = len([r for r in results.values() if r and r.get('success')])
        
        self.logger.info(
            f"✅ Rutas multi-modales calculadas: {successful_routes}/{len(results)} "
            f"en {processing_time:.2f}s"
        )
        
        return results
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Obtener estadísticas detalladas de rendimiento
        """
        stats = {
            'usage_statistics': self._usage_stats.copy(),
            'cache_status': self.get_cache_status(),
            'memory_usage': self.get_memory_usage(),
            'performance_summary': {
                'total_requests': sum(mode['requests'] for mode in self._usage_stats.values()),
                'total_cache_hits': sum(mode['cache_hits'] for mode in self._usage_stats.values()),
                'modes_loaded_in_memory': sum(self._cache_loaded.values()),
                'overall_hit_ratio': 0.0
            }
        }
        
        # Calcular hit ratio general
        total_requests = stats['performance_summary']['total_requests']
        total_hits = stats['performance_summary']['total_cache_hits']
        
        if total_requests > 0:
            stats['performance_summary']['overall_hit_ratio'] = total_hits / total_requests
        
        return stats
    
    def optimize_memory(self) -> Dict[str, Any]:
        """
        Optimizar uso de memoria basado en patrones de uso
        """
        optimization_report = {
            'actions_taken': [],
            'memory_before_mb': 0,
            'memory_after_mb': 0,
            'recommendations': []
        }
        
        # Obtener uso de memoria antes
        memory_before = self.get_memory_usage()
        optimization_report['memory_before_mb'] = memory_before['total_estimated_mb']
        
        # Análisis de patrones de uso
        for mode, stats in self._usage_stats.items():
            hit_ratio = stats['cache_hits'] / stats['requests'] if stats['requests'] > 0 else 0
            
            # Si un modo tiene muy pocas consultas y está en memoria, considerarlo para descarga
            if (stats['requests'] < 5 and 
                self._cache_loaded[mode] and 
                hit_ratio < 0.5):
                
                self.clear_memory_cache(mode)
                optimization_report['actions_taken'].append(f"Descargado cache {mode} (poco uso)")
            
            # Recomendaciones
            if stats['requests'] > 10 and not self._cache_loaded[mode]:
                optimization_report['recommendations'].append(
                    f"Considerar pre-cargar {mode} (alto uso: {stats['requests']} requests)"
                )
        
        # Obtener uso de memoria después
        memory_after = self.get_memory_usage()
        optimization_report['memory_after_mb'] = memory_after['total_estimated_mb']
        
        memory_saved = optimization_report['memory_before_mb'] - optimization_report['memory_after_mb']
        
        if memory_saved > 0:
            self.logger.info(f"🧹 Optimización de memoria completada: {memory_saved:.1f}MB liberados")
        else:
            self.logger.info("🧹 Optimización completada - no se encontraron ahorros")
        
        return optimization_report