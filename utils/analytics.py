import time
import logging
from typing import Dict, Any
from datetime import datetime

class AnalyticsLogger:
    """Logger para analytics de uso"""
    
    def __init__(self):
        self.logger = logging.getLogger('goveling.analytics')
    
    def track_request(self, event_name: str, data: Dict[str, Any]):
        """Track request events"""
        self.log_event(event_name, data)
    
    def track_error(self, error_type: str, error_message: str, context: Dict = None):
        """Track error events"""
        self.log_error(error_type, error_message, context)
    
    def log_event(self, event_name: str, data: Dict[str, Any]):
        """Log general events"""
        analytics_data = {
            'event': event_name,
            'timestamp': datetime.now().isoformat(),
            **data
        }
        self.logger.info("ANALYTICS", extra=analytics_data)
    
    def log_itinerary_generation(self, request: Dict, response: Dict, duration: float):
        """Log generación de itinerario"""
        analytics_data = {
            'event': 'itinerary_generated',
            'timestamp': datetime.now().isoformat(),
            'places_count': len(request.get('places', [])),
            'days_count': len(response.get('days', [])),
            'transport_mode': request.get('transport_mode'),
            'generation_time_seconds': duration,
            'success': len(response.get('unassigned', [])) == 0,
            'unassigned_count': len(response.get('unassigned', [])),
            'daily_start_hour': request.get('daily_start_hour'),
            'daily_end_hour': request.get('daily_end_hour')
        }
        
        self.logger.info("ANALYTICS", extra=analytics_data)
    
    def log_ml_prediction(self, place_type: str, predicted_duration: float, 
                         actual_duration: float = None):
        """Log predicción de ML"""
        analytics_data = {
            'event': 'ml_prediction',
            'timestamp': datetime.now().isoformat(),
            'place_type': place_type,
            'predicted_duration': predicted_duration,
            'actual_duration': actual_duration
        }
        
        if actual_duration:
            analytics_data['prediction_error'] = abs(predicted_duration - actual_duration)
        
        self.logger.info("ANALYTICS", extra=analytics_data)
    
    def log_error(self, error_type: str, error_message: str, context: Dict = None):
        """Log errores del sistema"""
        analytics_data = {
            'event': 'system_error',
            'timestamp': datetime.now().isoformat(),
            'error_type': error_type,
            'error_message': error_message,
            'context': context or {}
        }
        
        self.logger.error("ANALYTICS", extra=analytics_data)

# Crear instancia global
analytics = AnalyticsLogger()

# Configurar logging para analytics
def setup_analytics_logging():
    """Configurar logging específico para analytics"""
    import os
    
    # Crear directorio logs si no existe
    os.makedirs('logs', exist_ok=True)
    
    analytics_logger = logging.getLogger('goveling.analytics')
    analytics_logger.setLevel(logging.INFO)
    
    # Handler para archivo de analytics
    handler = logging.FileHandler('logs/analytics.log')
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    analytics_logger.addHandler(handler)
    
    return analytics_logger
