"""
🚀 Performance Optimizations for Render Deployment
"""
import asyncio
import functools
import hashlib
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

# Simple in-memory cache
_cache = {}
_cache_expiry = {}

def cache_result(expiry_minutes: int = 30):
    """Simple async cache decorator for API responses"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Check if cached result exists and is not expired
            if cache_key in _cache:
                expiry_time = _cache_expiry.get(cache_key)
                if expiry_time and datetime.now() < expiry_time:
                    return _cache[cache_key]
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            _cache[cache_key] = result
            _cache_expiry[cache_key] = datetime.now() + timedelta(minutes=expiry_minutes)
            
            return result
        return wrapper
    return decorator

def hash_places(places: list) -> str:
    """Create hash for places list for caching"""
    places_str = json.dumps([
        {
            'name': p.get('name', ''),
            'lat': round(p.get('lat', 0), 4),
            'lon': round(p.get('lon', 0), 4),
            'type': p.get('type', '')
        } for p in places
    ], sort_keys=True)
    return hashlib.md5(places_str.encode()).hexdigest()

def clear_cache():
    """Clear all cached data"""
    global _cache, _cache_expiry
    _cache.clear()
    _cache_expiry.clear()

# Background cache cleanup
async def cleanup_expired_cache():
    """Remove expired cache entries"""
    now = datetime.now()
    expired_keys = [
        key for key, expiry in _cache_expiry.items()
        if expiry < now
    ]
    
    for key in expired_keys:
        _cache.pop(key, None)
        _cache_expiry.pop(key, None)