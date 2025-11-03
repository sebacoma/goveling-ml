#!/usr/bin/env python3
"""
💾 Redis Cache Service - Cache profesional para matriz OD
Implementa cache persistente según recomendaciones de stack profesional
"""

import json
import time
import hashlib
import logging
from typing import Dict, List, Optional, Any, Tuple
import redis
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RedisODMatrixCache:
    """
    Cache Redis profesional para matrices Origen-Destino
    Implementa TTL, keys estructurados y fallback automático
    """
    
    def __init__(self, 
                 host: str = 'localhost', 
                 port: int = 6379, 
                 db: int = 0,
                 default_ttl: int = 3600):
        """
        Inicializa cache Redis para matrices OD
        
        Args:
            host: Redis server host
            port: Redis server port  
            db: Redis database number
            default_ttl: TTL por defecto en segundos (1 hora)
        """
        self.host = host
        self.port = port
        self.db = db
        self.default_ttl = default_ttl
        
        # Conectar a Redis
        try:
            self.redis_client = redis.Redis(
                host=host, port=port, db=db,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            
            # Test conexión
            self.redis_client.ping()
            logger.info(f"💾 Redis conectado: {host}:{port}/{db}")
            
        except Exception as e:
            logger.error(f"❌ Error conectando Redis: {e}")
            self.redis_client = None
    
    def _generate_cache_key(self, 
                           coordinates: List[Tuple[float, float]], 
                           mode: str,
                           h3_cluster: Optional[str] = None) -> str:
        """
        Genera key de cache estructurado para matriz OD
        
        Args:
            coordinates: Lista de (lat, lon)
            mode: Modo de transporte (car, foot, bike)
            h3_cluster: Cluster H3 principal (opcional)
            
        Returns:
            Key de cache único
        """
        # Crear hash de coordenadas para key único pero corto
        coords_str = json.dumps(sorted(coordinates), sort_keys=True)
        coords_hash = hashlib.sha256(coords_str.encode()).hexdigest()[:12]
        
        # Key estructurado: goveling:od:{mode}:{cluster}:{coords_hash}:{count}
        cluster_part = f"{h3_cluster}" if h3_cluster else "global"
        key = f"goveling:od:{mode}:{cluster_part}:{coords_hash}:{len(coordinates)}"
        
        return key
    
    def get_od_matrix(self, 
                     coordinates: List[Tuple[float, float]], 
                     mode: str,
                     h3_cluster: Optional[str] = None) -> Optional[Dict]:
        """
        Obtiene matriz OD desde cache Redis
        
        Args:
            coordinates: Lista de coordenadas
            mode: Modo de transporte
            h3_cluster: Cluster H3 (opcional)
            
        Returns:
            Matriz OD desde cache o None si no existe
        """
        if not self.redis_client:
            return None
        
        try:
            cache_key = self._generate_cache_key(coordinates, mode, h3_cluster)
            
            # Obtener desde Redis
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                matrix_data = json.loads(cached_data)
                
                # Añadir metadatos de cache
                matrix_data['cache_hit'] = True
                matrix_data['cached_at'] = matrix_data.get('cached_at')
                matrix_data['cache_key'] = cache_key
                
                logger.info(f"💾 Cache HIT: {cache_key} ({len(coordinates)} coords)")
                return matrix_data
            else:
                logger.info(f"💾 Cache MISS: {cache_key}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error leyendo cache: {e}")
            return None
    
    def set_od_matrix(self, 
                     coordinates: List[Tuple[float, float]], 
                     mode: str,
                     matrix_data: Dict,
                     h3_cluster: Optional[str] = None,
                     ttl: Optional[int] = None) -> bool:
        """
        Guarda matriz OD en cache Redis
        
        Args:
            coordinates: Lista de coordenadas
            mode: Modo de transporte
            matrix_data: Datos de la matriz a cachear
            h3_cluster: Cluster H3 (opcional)
            ttl: TTL en segundos (usa default si None)
            
        Returns:
            True si se guardó exitosamente
        """
        if not self.redis_client:
            return False
        
        try:
            cache_key = self._generate_cache_key(coordinates, mode, h3_cluster)
            ttl = ttl or self.default_ttl
            
            # Preparar datos para cache
            cache_data = matrix_data.copy()
            cache_data['cached_at'] = datetime.now().isoformat()
            cache_data['cache_ttl'] = ttl
            cache_data['cache_key'] = cache_key
            
            # Guardar en Redis con TTL
            success = self.redis_client.setex(
                cache_key, 
                ttl, 
                json.dumps(cache_data)
            )
            
            if success:
                logger.info(f"💾 Cache SET: {cache_key} (TTL: {ttl}s)")
                return True
            else:
                logger.warning(f"⚠️ Error guardando en cache: {cache_key}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error guardando cache: {e}")
            return False
    
    def invalidate_cluster_cache(self, h3_cluster: str) -> int:
        """
        Invalida todo el cache de un cluster H3 específico
        
        Args:
            h3_cluster: ID del cluster H3
            
        Returns:
            Número de keys eliminados
        """
        if not self.redis_client:
            return 0
        
        try:
            # Buscar todas las keys del cluster
            pattern = f"goveling:od:*:{h3_cluster}:*"
            keys = self.redis_client.keys(pattern)
            
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"💾 Cache invalidado: {deleted} keys del cluster {h3_cluster}")
                return deleted
            else:
                logger.info(f"💾 No hay cache para cluster {h3_cluster}")
                return 0
                
        except Exception as e:
            logger.error(f"❌ Error invalidando cache: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict:
        """
        Obtiene estadísticas del cache Redis
        
        Returns:
            Diccionario con estadísticas
        """
        if not self.redis_client:
            return {'connected': False}
        
        try:
            info = self.redis_client.info()
            
            # Contar keys de Goveling
            goveling_keys = len(self.redis_client.keys("goveling:*"))
            
            return {
                'connected': True,
                'redis_version': info.get('redis_version'),
                'used_memory_human': info.get('used_memory_human'),
                'connected_clients': info.get('connected_clients'),
                'total_commands_processed': info.get('total_commands_processed'),
                'goveling_keys_count': goveling_keys,
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'hit_rate': self._calculate_hit_rate(
                    info.get('keyspace_hits', 0),
                    info.get('keyspace_misses', 0)
                )
            }
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo stats: {e}")
            return {'connected': False, 'error': str(e)}
    
    def _calculate_hit_rate(self, hits: int, misses: int) -> float:
        """Calcula tasa de acierto del cache"""
        total = hits + misses
        if total == 0:
            return 0.0
        return (hits / total) * 100
    
    def cleanup_expired_keys(self) -> int:
        """
        Limpia keys expirados manualmente (Redis lo hace automáticamente)
        
        Returns:
            Número de keys limpiados
        """
        if not self.redis_client:
            return 0
        
        try:
            # Redis maneja TTL automáticamente, pero podemos forzar limpieza
            deleted = 0
            pattern = "goveling:*"
            
            for key in self.redis_client.scan_iter(match=pattern, count=100):
                ttl = self.redis_client.ttl(key)
                if ttl == -2:  # Key expirado
                    self.redis_client.delete(key)
                    deleted += 1
            
            if deleted > 0:
                logger.info(f"💾 Limpieza manual: {deleted} keys expirados")
            
            return deleted
            
        except Exception as e:
            logger.error(f"❌ Error en limpieza: {e}")
            return 0
    
    def health_check(self) -> bool:
        """
        Verifica que Redis esté funcionando correctamente
        
        Returns:
            True si Redis responde
        """
        try:
            if self.redis_client:
                response = self.redis_client.ping()
                return response == True
            return False
        except:
            return False

class RedisODMatrixManager:
    """
    Manager de alto nivel para cache Redis de matrices OD
    Integra con la arquitectura híbrida
    """
    
    def __init__(self):
        """Inicializa manager de cache Redis"""
        self.cache = RedisODMatrixCache()
        logger.info("🏗️ Redis OD Matrix Manager iniciado")
    
    def get_or_calculate_matrix(self,
                              coordinates: List[Tuple[float, float]],
                              mode: str,
                              h3_cluster: Optional[str],
                              calculation_func: callable,
                              force_refresh: bool = False) -> Dict:
        """
        Obtiene matriz del cache o la calcula si no existe
        
        Args:
            coordinates: Lista de coordenadas
            mode: Modo de transporte
            h3_cluster: Cluster H3
            calculation_func: Función para calcular matriz si no está en cache
            force_refresh: Forzar recálculo aunque exista en cache
            
        Returns:
            Matriz OD con metadatos de cache
        """
        # Intentar obtener desde cache
        if not force_refresh:
            cached_matrix = self.cache.get_od_matrix(coordinates, mode, h3_cluster)
            if cached_matrix:
                return cached_matrix
        
        # Calcular nueva matriz
        logger.info(f"🔄 Calculando nueva matriz OD: {len(coordinates)} coords")
        start_time = time.time()
        
        matrix_data = calculation_func(coordinates)
        calculation_time = time.time() - start_time
        
        if matrix_data:
            # Añadir metadatos
            matrix_data['calculation_time_s'] = calculation_time
            matrix_data['cache_hit'] = False
            
            # Guardar en cache
            self.cache.set_od_matrix(coordinates, mode, matrix_data, h3_cluster)
            
            logger.info(f"✅ Matriz calculada y cacheada en {calculation_time:.3f}s")
        
        return matrix_data
    
    def is_healthy(self) -> bool:
        """Verifica que el cache esté funcionando"""
        return self.cache.health_check()
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas del cache"""
        return self.cache.get_cache_stats()

if __name__ == "__main__":
    """Test del cache Redis profesional"""
    
    print("💾 TESTING REDIS OD MATRIX CACHE")
    print("=" * 50)
    
    # Crear manager de cache
    cache_manager = RedisODMatrixManager()
    
    # Verificar conexión
    if cache_manager.is_healthy():
        print("✅ Redis conectado y funcionando")
    else:
        print("❌ Redis no disponible")
        exit(1)
    
    # Test data
    test_coordinates = [
        (-23.6509, -70.3975),  # Antofagasta
        (-23.6400, -70.4100),  # La Franchuteria
        (-23.6600, -70.3800)   # McDonald's
    ]
    
    # Función simulada de cálculo
    def mock_calculation(coords):
        time.sleep(0.1)  # Simular trabajo
        n = len(coords)
        return {
            'distances': [[i*1000 + j*500 for j in range(n)] for i in range(n)],
            'durations': [[i*60 + j*30 for j in range(n)] for i in range(n)],
            'query_time_s': 0.1
        }
    
    # Test 1: Calcular matriz (MISS)
    print("\n🧪 Test 1: Primera consulta (cache MISS)")
    start_time = time.time()
    
    matrix1 = cache_manager.get_or_calculate_matrix(
        coordinates=test_coordinates,
        mode="car", 
        h3_cluster="85b22607fffffff",
        calculation_func=mock_calculation
    )
    
    time1 = time.time() - start_time
    print(f"   Tiempo total: {time1:.3f}s")
    print(f"   Cache hit: {matrix1.get('cache_hit', False)}")
    
    # Test 2: Obtener desde cache (HIT)
    print("\n🧪 Test 2: Segunda consulta (cache HIT)")
    start_time = time.time()
    
    matrix2 = cache_manager.get_or_calculate_matrix(
        coordinates=test_coordinates,
        mode="car",
        h3_cluster="85b22607fffffff", 
        calculation_func=mock_calculation
    )
    
    time2 = time.time() - start_time
    print(f"   Tiempo total: {time2:.3f}s")
    print(f"   Cache hit: {matrix2.get('cache_hit', False)}")
    print(f"   Mejora velocidad: {time1/time2:.1f}x más rápido")
    
    # Test 3: Estadísticas
    print("\n📊 Estadísticas Redis:")
    stats = cache_manager.get_stats()
    if stats['connected']:
        print(f"   Redis version: {stats.get('redis_version')}")
        print(f"   Memoria usada: {stats.get('used_memory_human')}")
        print(f"   Keys Goveling: {stats.get('goveling_keys_count')}")
        print(f"   Hit rate: {stats.get('hit_rate', 0):.1f}%")
    
    print(f"\n✅ Cache Redis funcionando correctamente")
    print(f"🚀 Listo para integración con arquitectura híbrida")