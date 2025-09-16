"""
⚡ Configuración de Logging Optimizada para Render
"""

import logging
import sys
from settings import settings

def setup_production_logging():
    """Configurar logging optimizado para producción"""
    
    # Nivel de logging basado en DEBUG
    log_level = logging.DEBUG if settings.DEBUG else logging.WARNING
    
    # Configurar formato simple para producción
    formatter = logging.Formatter(
        '%(levelname)s:%(name)s:%(message)s' if not settings.DEBUG 
        else '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Handler para stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    # Configurar root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    
    # Silenciar logs verbosos de librerías en producción
    if not settings.DEBUG:
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("aiohttp").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.WARNING)
        logging.getLogger("sklearn").setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)