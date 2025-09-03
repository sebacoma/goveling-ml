import time
from typing import Dict
from collections import defaultdict

class RateLimiter:
    """Rate limiter simple basado en sliding window"""
    
    def __init__(self, max_requests: int = 100, time_window: int = 3600):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = defaultdict(list)
    
    def is_allowed(self, client_id: str) -> bool:
        """Verificar si una request está permitida"""
        now = time.time()
        
        # Limpiar requests antiguas
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if now - req_time < self.time_window
        ]
        
        # Verificar límite
        if len(self.requests[client_id]) >= self.max_requests:
            return False
        
        # Registrar nueva request
        self.requests[client_id].append(now)
        return True
    
    def get_remaining_requests(self, client_id: str) -> int:
        """Obtener requests restantes"""
        now = time.time()
        
        # Limpiar requests antiguas
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if now - req_time < self.time_window
        ]
        
        return max(0, self.max_requests - len(self.requests[client_id]))
    
    def reset_client(self, client_id: str):
        """Resetear contador para un cliente"""
        if client_id in self.requests:
            del self.requests[client_id]
