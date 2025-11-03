"""
🌍 GLOBAL CITY2GRAPH REAL INTEGRATION
Integración global del sistema City2Graph REAL con datos completos de OSM
Configurado sin timeouts para descargas masivas
"""

import logging
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import os
import sys

# Configurar logging
logger = logging.getLogger(__name__)

# Importar el servicio REAL
try:
    from services.city2graph_real_complete import RealCity2GraphService
    REAL_SEMANTIC_AVAILABLE = True
    logger.info("✅ City2Graph REAL disponible")
except ImportError as e:
    logger.warning(f"⚠️ City2Graph REAL no disponible: {e}")
    REAL_SEMANTIC_AVAILABLE = False

class GlobalRealCity2GraphManager:
    """
    🌍 Gestor global de City2Graph REAL para todo el sistema
    """
    
    def __init__(self):
        self.real_service = None
        self.initialized_cities = set()
        self.is_enabled = REAL_SEMANTIC_AVAILABLE
        self.initialization_status = {}
        
        if self.is_enabled:
            self.real_service = RealCity2GraphService()
            logger.info("🧠 GlobalRealCity2GraphManager inicializado con capacidades REALES")
        else:
            logger.warning("🔴 GlobalRealCity2GraphManager inicializado SIN capacidades REALES")
    
    async def initialize_city_real_if_needed(self, places: List[Dict], city_name: str = None) -> bool:
        """
        🏙️ Inicializar análisis REAL de ciudad automáticamente (SIN TIMEOUT)
        """
        if not self.is_enabled:
            return False
        
        try:
            # Detectar ciudad automáticamente si no se proporciona
            if not city_name:
                city_name = self._detect_city_from_places(places)
            
            if city_name and city_name not in self.initialized_cities:
                # Verificar si ya se está inicializando
                if city_name in self.initialization_status:
                    status = self.initialization_status[city_name]
                    if status == 'in_progress':
                        logger.info(f"⏳ {city_name} ya se está inicializando...")
                        return False
                    elif status == 'completed':
                        self.initialized_cities.add(city_name)
                        return True
                
                # Marcar como en progreso
                self.initialization_status[city_name] = 'in_progress'
                
                # Calcular bbox de los lugares
                bbox = self._calculate_bbox_from_places(places)
                
                logger.info(f"🌍 Iniciando descarga MASIVA de datos OSM para {city_name}")
                logger.info(f"📦 Bbox: {bbox}")
                logger.info("⏳ ESTO PUEDE TOMAR VARIOS MINUTOS - SIN TIMEOUT")
                
                success = await self.real_service.initialize_city_real(city_name, bbox)
                
                if success:
                    self.initialized_cities.add(city_name)
                    self.initialization_status[city_name] = 'completed'
                    logger.info(f"✅ {city_name} inicializada COMPLETAMENTE con datos OSM reales")
                    return True
                else:
                    self.initialization_status[city_name] = 'failed'
                    logger.warning(f"⚠️ No se pudo inicializar {city_name} con datos reales")
                    return False
            
            return city_name in self.initialized_cities
            
        except Exception as e:
            logger.error(f"❌ Error inicializando ciudad REAL {city_name}: {e}")
            self.initialization_status[city_name] = 'failed'
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
        elif -33.1 <= center_lat <= -32.8 and -71.6 <= center_lon <= -71.4:
            return 'valparaiso'
        
        # Para otras ubicaciones, usar nombre genérico basado en coordenadas
        return f'city_{abs(center_lat):.1f}_{abs(center_lon):.1f}'
    
    def _calculate_bbox_from_places(self, places: List[Dict]) -> Tuple[float, float, float, float]:
        """
        📦 Calcular bounding box de los lugares
        """
        lats = [p.get('lat', 0) for p in places if p.get('lat')]
        lons = [p.get('lon', 0) for p in places if p.get('lon')]
        
        if not lats or not lons:
            return (-33.5, -33.3, -70.8, -70.5)  # Santiago por defecto
        
        min_lat = min(lats) - 0.02  # Margin más amplio para más datos
        max_lat = max(lats) + 0.02
        min_lon = min(lons) - 0.02
        max_lon = max(lons) + 0.02
        
        return (min_lat, max_lat, min_lon, max_lon)
    
    async def get_real_semantic_clustering(self, places: List[Dict], city_name: str = None) -> Dict:
        """
        🧠 Obtener clustering semántico REAL con datos OSM
        """
        if not self.is_enabled:
            return {
                'strategy': 'basic_fallback',
                'reason': 'real_semantic_service_not_available',
                'recommendations': [],
                'optimization_insights': ['Sistema en modo básico - sin datos OSM reales']
            }
        
        try:
            # Inicializar ciudad si es necesario (puede tomar tiempo)
            city_initialized = await self.initialize_city_real_if_needed(places, city_name)
            
            if not city_initialized:
                return {
                    'strategy': 'initialization_pending',
                    'reason': 'city_initialization_in_progress_or_failed',
                    'recommendations': [],
                    'optimization_insights': ['Inicialización de datos OSM en progreso o falló']
                }
            
            # Detectar ciudad si no se especifica
            if not city_name:
                city_name = self._detect_city_from_places(places)
            
            if city_name and city_name in self.initialized_cities:
                # Análisis semántico REAL con datos OSM
                real_districts = self.real_service.districts.get(city_name, [])
                
                if not real_districts:
                    return {
                        'strategy': 'no_districts_found',
                        'reason': 'no_semantic_districts_created',
                        'recommendations': [],
                        'optimization_insights': ['No se pudieron crear distritos semánticos con datos OSM']
                    }
                
                # Crear recomendaciones basadas en distritos REALES
                recommendations = []
                
                for district in real_districts:
                    # Filtrar lugares que estén en este distrito
                    district_places = []
                    for place in places:
                        try:
                            from shapely.geometry import Point
                            point = Point(place.get('lon', 0), place.get('lat', 0))
                            if district.polygon.contains(point):
                                district_places.append(place)
                        except:
                            continue
                    
                    if district_places:
                        recommendation = {
                            'district': district.name,
                            'district_type': district.district_type,
                            'places_count': len(district_places),
                            'place_names': [p.get('name', 'Unknown') for p in district_places],
                            'walkability': district.walkability_score,
                            'transit_accessibility': district.transit_accessibility,
                            'street_density': district.street_network_density,
                            'transport_nodes': district.public_transport_nodes,
                            'real_pois_in_district': len(district.real_pois),
                            'cultural_context': district.cultural_context,
                            'peak_hours': district.peak_hours,
                            'confidence': district.confidence_score,
                            'data_quality': district.osm_data_quality,
                            'clustering_reason': f"REAL OSM semantic grouping in {district.district_type} district",
                            'optimization_tips': self._generate_real_optimization_tips(district)
                        }
                        
                        recommendations.append(recommendation)
                
                return {
                    'strategy': 'real_osm_semantic',
                    'city': city_name,
                    'data_source': 'openstreetmap_complete',
                    'recommendations': recommendations,
                    'total_real_pois_analyzed': len(self.real_service.poi_data.get(city_name, [])),
                    'street_network_size': len(self.real_service.street_networks.get(city_name, {}).nodes()) if city_name in self.real_service.street_networks else 0,
                    'transport_network_size': len(self.real_service.transport_networks.get(city_name, {}).get('stations', [])) + len(self.real_service.transport_networks.get(city_name, {}).get('stops', [])),
                    'optimization_insights': self._generate_real_global_insights(recommendations, city_name)
                }
            else:
                return {
                    'strategy': 'city_not_detected_or_initialized',
                    'reason': f'city_detection_failed_or_not_initialized: {city_name}',
                    'recommendations': [],
                    'optimization_insights': ['No se pudo detectar la ciudad o no está inicializada con datos OSM']
                }
                
        except Exception as e:
            logger.error(f"❌ Error en clustering semántico REAL: {e}")
            return {
                'strategy': 'error_fallback',
                'reason': f'error: {str(e)}',
                'recommendations': [],
                'optimization_insights': ['Error en análisis semántico REAL - fallback a clustering básico']
            }
    
    def _generate_real_optimization_tips(self, district) -> List[str]:
        """
        💡 Generar tips de optimización basados en datos REALES
        """
        tips = []
        
        # Tips basados en walkability REAL
        if district.walkability_score >= 0.8:
            tips.append("🚶‍♂️ Excelente walkability REAL - rutas peatonales optimizadas disponibles")
        elif district.walkability_score >= 0.6:
            tips.append("👟 Buena walkability REAL - cómodo para caminar distancias cortas")
        else:
            tips.append("🚗 Walkability limitada - considerar transporte para distancias largas")
        
        # Tips basados en transporte REAL
        if district.transit_accessibility >= 0.8:
            tips.append(f"🚌 Excelente acceso transporte público - {district.public_transport_nodes} nodos cercanos")
        elif district.public_transport_nodes > 0:
            tips.append(f"🚌 Transporte disponible - {district.public_transport_nodes} nodos de transporte público")
        
        # Tips basados en densidad de calles REAL
        if district.street_network_density > 10:
            tips.append("🛣️ Red de calles densa - múltiples rutas alternativas disponibles")
        elif district.street_network_density > 5:
            tips.append("🛣️ Red de calles moderada - buenas opciones de routing")
        
        # Tips basados en POIs REALES
        if len(district.real_pois) > 20:
            tips.append(f"🏛️ Zona muy rica en POIs - {len(district.real_pois)} lugares de interés reales identificados")
        elif len(district.real_pois) > 10:
            tips.append(f"📍 Buena densidad de POIs - {len(district.real_pois)} lugares disponibles")
        
        # Tips por tipo de distrito
        district_tips = {
            'tourist': ["📸 Zona turística identificada con datos OSM", "🗺️ Múltiples atracciones cercanas"],
            'commercial': ["🛍️ Distrito comercial REAL - horarios comerciales aplicables", "💳 Infraestructura comercial desarrollada"],
            'business': ["💼 Distrito de negocios - horarios y códigos profesionales", "🏢 Área de oficinas y servicios empresariales"],
            'mixed': ["🏙️ Distrito mixto - variedad de servicios y actividades", "⚖️ Balance entre comercial y residencial"],
            'transport_hub': ["🚌 Hub de transporte identificado", "⚡ Excelente conectividad de transporte público"]
        }
        
        if district.district_type in district_tips:
            tips.extend(district_tips[district.district_type])
        
        return tips
    
    def _generate_real_global_insights(self, recommendations: List[Dict], city_name: str) -> List[str]:
        """
        📊 Insights globales basados en datos OSM REALES
        """
        insights = []
        
        if not recommendations:
            return ["No se encontraron distritos semánticos en datos OSM reales"]
        
        # Análisis de diversidad
        district_types = set(rec['district_type'] for rec in recommendations)
        if len(district_types) >= 3:
            insights.append(f"🎯 EXCELENTE diversidad REAL: {len(district_types)} tipos de distrito diferentes identificados con OSM")
        
        # Análisis de walkability promedio
        avg_walkability = sum(rec['walkability'] for rec in recommendations) / len(recommendations)
        if avg_walkability >= 0.8:
            insights.append("🚶‍♂️ Ciudad MUY walkable según análisis OSM real - optimizar para rutas peatonales")
        elif avg_walkability >= 0.6:
            insights.append("👟 Ciudad moderadamente walkable - balance peatonal/transporte recomendado")
        else:
            insights.append("🚗 Walkability limitada según OSM - priorizar optimización de transporte")
        
        # Análisis de transporte
        total_transport = sum(rec['transport_nodes'] for rec in recommendations)
        if total_transport > 20:
            insights.append("🚌 Red de transporte público MUY DESARROLLADA según datos OSM")
        elif total_transport > 10:
            insights.append("🚌 Buena cobertura de transporte público identificada")
        
        # Análisis de POIs reales
        total_real_pois = sum(rec['real_pois_in_district'] for rec in recommendations)
        if total_real_pois > 100:
            insights.append(f"🏛️ Ciudad MUY RICA en POIs: {total_real_pois} lugares reales de OSM analizados")
        elif total_real_pois > 50:
            insights.append(f"📍 Buena densidad de POIs: {total_real_pois} lugares reales identificados")
        
        # Calidad de datos
        high_confidence = [r for r in recommendations if r['confidence'] >= 0.7]
        if len(high_confidence) == len(recommendations):
            insights.append("✅ ALTA confianza en análisis - datos OSM completos y consistentes")
        elif len(high_confidence) >= len(recommendations) // 2:
            insights.append("⚖️ Buena confianza en análisis - datos OSM mayormente completos")
        
        # Información específica de la ciudad
        if city_name == 'santiago':
            insights.append("🇨🇱 Análisis específico de Santiago con datos OSM completos")
        
        return insights
    
    async def enhance_place_with_real_semantic_context(self, place: Dict, city_name: str = None) -> Dict:
        """
        ✨ Enriquecer lugar con contexto semántico REAL
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
                    context = await self.real_service.get_real_semantic_context(lat, lon, city_name)
                    
                    # Enriquecer lugar con información semántica REAL
                    enhanced_place = place.copy()
                    enhanced_place.update({
                        'semantic_district': context.get('district', 'Unknown'),
                        'district_type': context.get('district_type', 'general'),
                        'walkability_score_real': context.get('walkability_score', 0.5),
                        'transit_accessibility_real': context.get('transit_accessibility', 0.5),
                        'street_density_real': context.get('street_density', 0.0),
                        'transport_nodes_nearby': context.get('transport_nodes_nearby', 0),
                        'real_pois_in_area': context.get('real_pois_count', 0),
                        'cultural_context': context.get('cultural_context', {}),
                        'peak_hours': context.get('peak_hours', {}),
                        'semantic_confidence': context.get('confidence', 0.1),
                        'data_quality': context.get('data_quality', 'unknown'),
                        'real_osm_data': context.get('real_data', False)
                    })
                    
                    logger.debug(f"✨ Lugar enriquecido con datos REALES: {place.get('name')} → {context.get('district')}")
                    return enhanced_place
            
            return place
            
        except Exception as e:
            logger.error(f"❌ Error enriqueciendo lugar REAL {place.get('name', 'unknown')}: {e}")
            return place
    
    async def get_real_city_summary(self, city_name: str = None) -> Dict:
        """
        📊 Obtener resumen REAL completo de la ciudad
        """
        if not self.is_enabled or not city_name:
            return {'status': 'real_service_not_available'}
        
        try:
            if city_name in self.initialized_cities:
                return self.real_service.get_city_real_summary(city_name)
            else:
                return {'status': 'not_initialized_real', 'city': city_name}
        except Exception as e:
            logger.error(f"❌ Error obteniendo resumen REAL de {city_name}: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def is_real_semantic_enabled(self) -> bool:
        """
        ✅ Verificar si las capacidades semánticas REALES están habilitadas
        """
        return self.is_enabled
    
    def get_real_semantic_features_summary(self) -> Dict:
        """
        📋 Resumen de capacidades semánticas REALES disponibles
        """
        if self.is_enabled:
            return {
                'real_osm_data_download': True,
                'real_street_network_analysis': True,
                'real_poi_discovery': True,
                'real_transport_network': True,
                'real_walkability_calculation': True,
                'real_semantic_districts': True,
                'initialized_cities': list(self.initialized_cities),
                'total_cities': len(self.initialized_cities),
                'data_source': 'openstreetmap_complete'
            }
        else:
            return {
                'real_osm_data_download': False,
                'real_street_network_analysis': False,
                'real_poi_discovery': False,
                'real_transport_network': False,
                'real_walkability_calculation': False,
                'real_semantic_districts': False,
                'initialized_cities': [],
                'total_cities': 0,
                'reason': 'real_semantic_service_not_available'
            }

# Instancia global del manager REAL
global_real_city2graph = GlobalRealCity2GraphManager()

async def get_global_real_semantic_clustering(places: List[Dict], city_name: str = None) -> Dict:
    """
    🌍 Función global para obtener clustering semántico REAL
    """
    return await global_real_city2graph.get_real_semantic_clustering(places, city_name)

async def enhance_places_with_real_semantic_context(places: List[Dict], city_name: str = None) -> List[Dict]:
    """
    ✨ Función global para enriquecer lugares con contexto semántico REAL
    """
    enhanced_places = []
    
    for place in places:
        enhanced_place = await global_real_city2graph.enhance_place_with_real_semantic_context(place, city_name)
        enhanced_places.append(enhanced_place)
    
    return enhanced_places

def get_real_semantic_status() -> Dict:
    """
    📊 Estado global del sistema semántico REAL
    """
    return {
        'enabled': global_real_city2graph.is_real_semantic_enabled(),
        'features': global_real_city2graph.get_real_semantic_features_summary(),
        'service_status': 'active_real' if global_real_city2graph.is_enabled else 'disabled'
    }