"""
⚡ Google API Cache - Optimización para Render
Caché inteligente para reducir llamadas a Google APIs
"""

import hashlib
import json
import time
from typing import Dict, Any, Optional, List
from functools import wraps
import asyncio

class GoogleAPICache:
    """Caché en memoria para APIs de Google con TTL"""
    
    def __init__(self, default_ttl: int = 1800):  # 30 minutos
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl
    
    def _hash_key(self, *args, **kwargs) -> str:
        """Generar hash único para parámetros"""
        key_data = str(args) + str(sorted(kwargs.items()))
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _is_expired(self, cache_entry: Dict[str, Any]) -> bool:
        """Verificar si entrada está expirada"""
        return time.time() > cache_entry['expires_at']
    
    def get(self, key: str) -> Optional[Any]:
        """Obtener valor del caché"""
        if key in self.cache:
            entry = self.cache[key]
            if not self._is_expired(entry):
                return entry['data']
            else:
                del self.cache[key]
        return None
    
    def set(self, key: str, data: Any, ttl: Optional[int] = None) -> None:
        """Guardar valor en caché"""
        ttl = ttl or self.default_ttl
        self.cache[key] = {
            'data': data,
            'expires_at': time.time() + ttl,
            'created_at': time.time()
        }
    
    def clear_expired(self) -> int:
        """Limpiar entradas expiradas"""
        expired_keys = [
            key for key, entry in self.cache.items()
            if self._is_expired(entry)
        ]
        for key in expired_keys:
            del self.cache[key]
        return len(expired_keys)
    
    def stats(self) -> Dict[str, Any]:
        """Estadísticas del caché"""
        return {
            'total_entries': len(self.cache),
            'expired_entries': len([
                k for k, v in self.cache.items() 
                if self._is_expired(v)
            ])
        }

# Instancia global del caché
google_cache = GoogleAPICache()

def cache_google_api(ttl: int = 1800):
    """Decorador para cachear llamadas a Google APIs"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generar clave de caché
            cache_key = google_cache._hash_key(func.__name__, *args, **kwargs)
            
            # Intentar obtener del caché
            cached_result = google_cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Ejecutar función y cachear resultado
            result = await func(*args, **kwargs)
            google_cache.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator

def batch_google_requests(requests: List[Dict[str, Any]], max_batch_size: int = 5) -> List[List[Dict[str, Any]]]:
    """Agrupar requests para optimizar llamadas batch"""
    batches = []
    for i in range(0, len(requests), max_batch_size):
        batches.append(requests[i:i + max_batch_size])
    return batches

async def parallel_google_calls(calls: List[Any], max_concurrent: int = 3) -> List[Any]:
    """Ejecutar llamadas a Google APIs en paralelo controlado"""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def limited_call(call):
        async with semaphore:
            return await call
    
    tasks = [limited_call(call) for call in calls]
    return await asyncio.gather(*tasks, return_exceptions=True)