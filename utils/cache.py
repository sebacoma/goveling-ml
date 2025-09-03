import time
import logging
from typing import Dict, Any, Callable
from functools import wraps
import json

class SimpleCache:
    """Cache simple en memoria"""
    
    def __init__(self):
        self._cache = {}
        self._timestamps = {}
    
    def get(self, key: str, ttl: int = 3600):
        """Obtener valor del cache"""
        if key not in self._cache:
            return None
        
        # Verificar TTL
        if time.time() - self._timestamps[key] > ttl:
            del self._cache[key]
            del self._timestamps[key]
            return None
        
        return self._cache[key]
    
    def set(self, key: str, value: Any):
        """Guardar valor en cache"""
        self._cache[key] = value
        self._timestamps[key] = time.time()
    
    def clear(self):
        """Limpiar cache"""
        self._cache.clear()
        self._timestamps.clear()

# Instancia global del cache
_cache = SimpleCache()

def cache_result(ttl: int = 3600):
    """Decorator para cachear resultados de funciones"""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Crear clave de cache
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Intentar obtener del cache
            cached = _cache.get(cache_key, ttl)
            if cached is not None:
                return cached
            
            # Ejecutar función y cachear resultado
            result = await func(*args, **kwargs)
            _cache.set(cache_key, result)
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Crear clave de cache
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Intentar obtener del cache
            cached = _cache.get(cache_key, ttl)
            if cached is not None:
                return cached
            
            # Ejecutar función y cachear resultado
            result = func(*args, **kwargs)
            _cache.set(cache_key, result)
            return result
        
        # Retornar wrapper apropiado
        if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
