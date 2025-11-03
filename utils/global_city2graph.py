"""
🌍 GLOBAL CITY2GRAPH INTEGRATION
Integración global del sistema semántico City2Graph en todo el stack de optimización
"""

import logging
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import os
import sys

# Configurar logging
logger = logging.getLogger(__name__)

# Importar el servicio semántico
try:
    from services.semantic_city2graph_demo import SemanticCity2GraphService
    SEMANTIC_AVAILABLE = True
    logger.info("✅ City2Graph semántico disponible")
except ImportError as e:
    logger.warning(f"⚠️ City2Graph semántico no disponible: {e}")
    SEMANTIC_AVAILABLE = False

class GlobalCity2GraphManager:
    """
    🌍 Gestor global de City2Graph para todo el sistema
    """
    
    def __init__(self):
        self.semantic_service = None
        self.initialized_cities = set()
        self.is_enabled = SEMANTIC_AVAILABLE
        
        if self.is_enabled:
            self.semantic_service = SemanticCity2GraphService()
            logger.info("🧠 GlobalCity2GraphManager inicializado con capacidades semánticas")
        else:
            logger.warning("🔴 GlobalCity2GraphManager inicializado SIN capacidades semánticas")
    
    async def initialize_city_if_needed(self, places: List[Dict], city_name: str = None) -> bool:
        """
        🏙️ Inicializar análisis semántico de ciudad automáticamente
        """
        if not self.is_enabled:
            return False
        
        try:
            # Detectar ciudad automáticamente si no se proporciona
            if not city_name:
                city_name = self._detect_city_from_places(places)
            
            if city_name and city_name not in self.initialized_cities:
                # Calcular bbox de los lugares
                bbox = self._calculate_bbox_from_places(places)
                
                logger.info(f"🏗️ Inicializando análisis semántico para {city_name}")
                success = await self.semantic_service.initialize_city(city_name, bbox)
                
                if success:
                    self.initialized_cities.add(city_name)
                    logger.info(f"✅ {city_name} inicializada exitosamente")
                    return True
                else:
                    logger.warning(f"⚠️ No se pudo inicializar {city_name}")
                    return False
            
            return city_name in self.initialized_cities
            
        except Exception as e:
            logger.error(f"❌ Error inicializando ciudad {city_name}: {e}")
            return False
    
    def _detect_city_from_places(self, places: List[Dict]) -> Optional[str]:
        """
        🔍 Detectar ciudad automáticamente basado en coordenadas
        """
        if not places:
            return None
        
        # Calcular centro de los lugares
        lats = [p.get('lat', 0) for p in places if p.get('lat')]
        lons = [p.get('lon', 0) for p in places if p.get('lon')]
        
        if not lats or not lons:
            return None
        
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
        
        # Detectar ciudades conocidas por región
        if -33.6 <= center_lat <= -33.3 and -70.8 <= center_lon <= -70.4:
            return 'santiago'
        elif -23.7 <= center_lat <= -23.4 and -70.5 <= center_lon <= -70.2:
            return 'antofagasta'
        elif -27.4 <= center_lat <= -27.2 and -70.4 <= center_lon <= -70.2:
            return 'copiapo'
        elif -29.3 <= center_lat <= -29.8 and -71.3 <= center_lon <= -71.1:
            return 'la_serena'
        
        # Para otras ubicaciones, usar nombre genérico
        return 'ciudad_desconocida'
    
    def _calculate_bbox_from_places(self, places: List[Dict]) -> Tuple[float, float, float, float]:
        """
        📦 Calcular bounding box de los lugares
        """
        lats = [p.get('lat', 0) for p in places if p.get('lat')]
        lons = [p.get('lon', 0) for p in places if p.get('lon')]
        
        if not lats or not lons:
            return (-33.5, -33.3, -70.8, -70.5)  # Santiago por defecto
        
        min_lat = min(lats) - 0.05  # Margin
        max_lat = max(lats) + 0.05
        min_lon = min(lons) - 0.05
        max_lon = max(lons) + 0.05
        
        return (min_lat, max_lat, min_lon, max_lon)
    
    async def get_semantic_clustering(self, places: List[Dict], city_name: str = None) -> Dict:
        """
        🧠 Obtener clustering semántico inteligente
        """
        if not self.is_enabled:
            return {
                'strategy': 'geographic_fallback',
                'reason': 'semantic_service_not_available',
                'recommendations': [],
                'optimization_insights': ['Sistema en modo geográfico básico']
            }
        
        try:
            # Inicializar ciudad si es necesario
            await self.initialize_city_if_needed(places, city_name)
            
            # Obtener clustering semántico
            if not city_name:
                city_name = self._detect_city_from_places(places)
            
            if city_name:
                clustering_result = await self.semantic_service.get_smart_clustering_suggestions(places, city_name)
                logger.info(f"🎯 Clustering semántico obtenido: {clustering_result['strategy']}")
                return clustering_result
            else:
                return {
                    'strategy': 'geographic_fallback',
                    'reason': 'city_not_detected',
                    'recommendations': [],
                    'optimization_insights': ['Ciudad no detectada - usando clustering geográfico']
                }
                
        except Exception as e:
            logger.error(f"❌ Error en clustering semántico: {e}")
            return {
                'strategy': 'geographic_fallback',
                'reason': f'error: {str(e)}',
                'recommendations': [],
                'optimization_insights': ['Error en análisis semántico - fallback a clustering geográfico']
            }
    
    async def enhance_place_with_semantic_context(self, place: Dict, city_name: str = None) -> Dict:
        """
        ✨ Enriquecer lugar con contexto semántico
        """
        if not self.is_enabled:
            return place
        
        try:
            if not city_name:
                city_name = self._detect_city_from_places([place])
            
            if city_name and city_name in self.initialized_cities:
                lat = place.get('lat', 0)
                lon = place.get('lon', 0)
                
                if lat and lon:
                    context = await self.semantic_service.get_semantic_context(lat, lon, city_name)
                    
                    # Enriquecer lugar con información semántica
                    enhanced_place = place.copy()
                    enhanced_place.update({
                        'semantic_district': context.get('district', 'Unknown'),
                        'district_type': context.get('district_type', 'general'),
                        'walkability_score': context.get('walkability_score', 0.5),
                        'transit_accessibility': context.get('transit_accessibility', 0.5),
                        'cultural_context': context.get('cultural_context', {}),
                        'peak_hours': context.get('peak_hours', {}),
                        'semantic_confidence': context.get('confidence', 0.1)
                    })
                    
                    logger.debug(f"✨ Lugar enriquecido: {place.get('name')} → {context.get('district')}")
                    return enhanced_place
            
            return place
            
        except Exception as e:
            logger.error(f"❌ Error enriqueciendo lugar {place.get('name', 'unknown')}: {e}")
            return place
    
    async def get_city_summary(self, city_name: str = None) -> Dict:
        """
        📊 Obtener resumen completo de la ciudad
        """
        if not self.is_enabled or not city_name:
            return {'status': 'not_available'}
        
        try:
            if city_name in self.initialized_cities:
                return self.semantic_service.get_city_summary(city_name)
            else:
                return {'status': 'not_initialized', 'city': city_name}
        except Exception as e:
            logger.error(f"❌ Error obteniendo resumen de {city_name}: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def is_semantic_enabled(self) -> bool:
        """
        ✅ Verificar si las capacidades semánticas están habilitadas
        """
        return self.is_enabled
    
    def get_semantic_features_summary(self) -> Dict:
        """
        📋 Resumen de capacidades semánticas disponibles
        """
        if self.is_enabled:
            return {
                'semantic_clustering': True,
                'walkability_scoring': True,
                'poi_discovery': True,
                'cultural_context': True,
                'district_analysis': True,
                'initialized_cities': list(self.initialized_cities),
                'total_cities': len(self.initialized_cities)
            }
        else:
            return {
                'semantic_clustering': False,
                'walkability_scoring': False,
                'poi_discovery': False,
                'cultural_context': False,
                'district_analysis': False,
                'initialized_cities': [],
                'total_cities': 0,
                'reason': 'semantic_service_not_available'
            }

# Instancia global del manager
global_city2graph = GlobalCity2GraphManager()

async def get_global_semantic_clustering(places: List[Dict], city_name: str = None) -> Dict:
    """
    🌍 Función global para obtener clustering semántico
    """
    return await global_city2graph.get_semantic_clustering(places, city_name)

async def enhance_places_with_semantic_context(places: List[Dict], city_name: str = None) -> List[Dict]:
    """
    ✨ Función global para enriquecer lugares con contexto semántico
    """
    enhanced_places = []
    
    for place in places:
        enhanced_place = await global_city2graph.enhance_place_with_semantic_context(place, city_name)
        enhanced_places.append(enhanced_place)
    
    return enhanced_places

def get_semantic_status() -> Dict:
    """
    📊 Estado global del sistema semántico
    """
    return {
        'enabled': global_city2graph.is_semantic_enabled(),
        'features': global_city2graph.get_semantic_features_summary(),
        'service_status': 'active' if global_city2graph.is_enabled else 'disabled'
    }