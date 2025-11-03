"""
🧠 SEMANTIC HYBRID OPTIMIZER - OPTIMIZADOR HÍBRIDO CON ANÁLISIS SEMÁNTICO
Integra City2graph completo con el sistema de optimización existente
"""

import logging
import asyncio
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from services.city2graph_complete_service import City2GraphCompleteService
from utils.hybrid_optimizer_v31 import HybridOptimizerV31

logger = logging.getLogger(__name__)

class SemanticHybridOptimizer:
    """
    🔥 Optimizador híbrido con análisis semántico completo
    Combina routing híbrido con clustering semántico inteligente
    """
    
    def __init__(self):
        self.city2graph = City2GraphCompleteService()
        self.hybrid_optimizer = HybridOptimizerV31(use_hybrid_routing=True)
        self.logger = logging.getLogger(__name__)
        
    async def cluster_places_semantically(self, places: List[Dict], city_name: str) -> Dict:
        """
        🎯 Clustering semántico inteligente de lugares
        """
        try:
            self.logger.info(f"🧠 Iniciando clustering semántico para {city_name}")
            
            # Inicializar ciudad si no está lista
            if city_name not in self.city2graph.semantic_districts:
                # Determinar bbox basado en places
                lats = [p['lat'] for p in places]
                lons = [p['lon'] for p in places]
                
                # Expandir bbox con margen
                margin = 0.05  # ~5km margen
                bbox = (
                    max(lats) + margin,   # north
                    min(lats) - margin,   # south  
                    max(lons) + margin,   # east
                    min(lons) - margin    # west
                )
                
                self.logger.info(f"📍 Inicializando {city_name} con bbox: {bbox}")
                success = await self.city2graph.initialize_city(city_name, bbox)
                
                if not success:
                    self.logger.warning(f"⚠️ No se pudo inicializar {city_name}, usando clustering geográfico")
                    return {
                        'strategy': 'geographic_fallback',
                        'reason': 'city_initialization_failed',
                        'district_groups': {},
                        'recommendations': []
                    }
            
            # Obtener sugerencias de clustering semántico
            suggestions = await self.city2graph.get_smart_clustering_suggestions(places, city_name)
            
            self.logger.info(f"✅ Clustering semántico completado: {suggestions['strategy']}")
            return suggestions
            
        except Exception as e:
            self.logger.error(f"❌ Error en clustering semántico: {e}")
            return {
                'strategy': 'geographic_fallback',
                'reason': f'error: {str(e)}',
                'district_groups': {},
                'recommendations': []
            }
    
    async def get_place_semantic_context(self, place: Dict, city_name: str) -> Dict:
        """
        🏛️ Obtener contexto semántico detallado de un lugar específico
        """
        try:
            context = await self.city2graph.get_semantic_context(
                place['lat'], place['lon'], city_name
            )
            
            # Enriquecer con información del lugar
            enriched_context = {
                'place_name': place.get('name', 'Unknown'),
                'place_type': place.get('type', 'general'),
                'semantic_district': context['district'],
                'district_type': context['district_type'],
                'walkability_score': context['walkability_score'],
                'transit_accessibility': context['transit_accessibility'],
                'cultural_context': context['cultural_context'],
                'peak_hours': context['peak_hours'],
                'poi_density': context['poi_density'],
                'is_nearby_district': context.get('is_nearby', False),
                'distance_to_district_center': context.get('distance_to_center', 0)
            }
            
            return enriched_context
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo contexto semántico: {e}")
            return {
                'place_name': place.get('name', 'Unknown'),
                'semantic_district': 'Unknown',
                'district_type': 'general',
                'walkability_score': 0.5,
                'transit_accessibility': 0.5,
                'error': str(e)
            }
    
    async def optimize_with_semantic_clustering(
        self,
        places: List[Dict],
        start_date: datetime,
        end_date: datetime,
        city_name: str,
        daily_start_hour: int = 9,
        daily_end_hour: int = 18,
        transport_mode: str = 'walk',
        accommodations: Optional[List[Dict]] = None,
        packing_strategy: str = "balanced"
    ) -> Dict:
        """
        🚀 Optimización completa con clustering semántico inteligente
        """
        self.logger.info(f"🚀 Iniciando optimización semántica para {city_name}")
        
        try:
            # 1. Análisis semántico y clustering inteligente
            self.logger.info("🧠 Paso 1: Análisis semántico")
            semantic_analysis = await self.cluster_places_semantically(places, city_name)
            
            # 2. Contexto semántico de cada lugar
            self.logger.info("🏛️ Paso 2: Contexto semántico de lugares")
            places_with_context = []
            for place in places:
                context = await self.get_place_semantic_context(place, city_name)
                places_with_context.append({
                    **place,
                    'semantic_context': context
                })
            
            # 3. Optimización con el sistema híbrido existente
            self.logger.info("⚡ Paso 3: Optimización híbrida")
            optimization_result = await self._optimize_with_hybrid_system(
                places_with_context,
                start_date,
                end_date,
                daily_start_hour,
                daily_end_hour,
                transport_mode,
                accommodations,
                packing_strategy
            )
            
            # 4. Enriquecer resultado con análisis semántico
            self.logger.info("📊 Paso 4: Enriquecimiento semántico")
            enriched_result = await self._enrich_result_with_semantics(
                optimization_result,
                semantic_analysis,
                city_name
            )
            
            return enriched_result
            
        except Exception as e:
            self.logger.error(f"❌ Error en optimización semántica: {e}")
            # Fallback a optimización normal
            self.logger.info("🔄 Fallback a optimización híbrida normal")
            return await self._optimize_with_hybrid_system(
                places, start_date, end_date, daily_start_hour, daily_end_hour,
                transport_mode, accommodations, packing_strategy
            )
    
    async def _optimize_with_hybrid_system(
        self,
        places: List[Dict],
        start_date: datetime,
        end_date: datetime,
        daily_start_hour: int,
        daily_end_hour: int,
        transport_mode: str,
        accommodations: Optional[List[Dict]],
        packing_strategy: str
    ) -> Dict:
        """
        ⚡ Optimización usando el sistema híbrido existente
        """
        from utils.hybrid_optimizer_v31 import optimize_itinerary_hybrid_v31
        
        return await optimize_itinerary_hybrid_v31(
            places=places,
            start_date=start_date,
            end_date=end_date,
            daily_start_hour=daily_start_hour,
            daily_end_hour=daily_end_hour,
            transport_mode=transport_mode,
            accommodations=accommodations,
            packing_strategy=packing_strategy
        )
    
    async def _enrich_result_with_semantics(
        self,
        optimization_result: Dict,
        semantic_analysis: Dict,
        city_name: str
    ) -> Dict:
        """
        📊 Enriquecer resultado de optimización con análisis semántico
        """
        try:
            # Obtener resumen de la ciudad
            city_summary = self.city2graph.get_city_summary(city_name)
            
            # Enriquecer cada día con contexto semántico
            enriched_days = []
            
            for day_data in optimization_result.get('days', []):
                enriched_day = {**day_data}
                
                # Analizar lugares del día
                day_places = day_data.get('places', [])
                if day_places:
                    # Contexto semántico de los lugares del día
                    day_contexts = []
                    for place in day_places:
                        if 'lat' in place and 'lon' in place:
                            context = await self.city2graph.get_semantic_context(
                                place['lat'], place['lon'], city_name
                            )
                            day_contexts.append(context)
                    
                    # Análisis del día
                    if day_contexts:
                        # Tipos de distritos visitados
                        district_types = [ctx['district_type'] for ctx in day_contexts]
                        unique_districts = list(set(ctx['district'] for ctx in day_contexts))
                        
                        # Walkability promedio del día
                        avg_walkability = sum(ctx['walkability_score'] for ctx in day_contexts) / len(day_contexts)
                        
                        # Accesibilidad promedio
                        avg_transit = sum(ctx['transit_accessibility'] for ctx in day_contexts) / len(day_contexts)
                        
                        enriched_day['semantic_analysis'] = {
                            'districts_visited': unique_districts,
                            'district_types': district_types,
                            'avg_walkability': round(avg_walkability, 2),
                            'avg_transit_accessibility': round(avg_transit, 2),
                            'diversity_score': len(set(district_types)) / len(district_types) if district_types else 0
                        }
                
                enriched_days.append(enriched_day)
            
            # Resultado enriquecido
            enriched_result = {
                **optimization_result,
                'days': enriched_days,
                'semantic_metadata': {
                    'city_analysis': city_summary,
                    'clustering_strategy': semantic_analysis.get('strategy', 'unknown'),
                    'semantic_recommendations': semantic_analysis.get('recommendations', []),
                    'total_districts_available': len(city_summary.get('district_stats', {})),
                    'analysis_timestamp': datetime.now().isoformat()
                }
            }
            
            return enriched_result
            
        except Exception as e:
            self.logger.error(f"❌ Error enriqueciendo con semántica: {e}")
            # Retornar resultado original si falla el enriquecimiento
            return optimization_result
    
    async def get_city_insights(self, city_name: str) -> Dict:
        """
        📊 Obtener insights completos de una ciudad analizada
        """
        try:
            if city_name not in self.city2graph.semantic_districts:
                return {
                    'status': 'not_analyzed',
                    'city': city_name,
                    'message': 'City has not been analyzed yet'
                }
            
            summary = self.city2graph.get_city_summary(city_name)
            
            # Análisis adicional
            districts = self.city2graph.semantic_districts[city_name]
            
            # Top distritos por walkability
            top_walkable = sorted(
                districts,
                key=lambda d: d.walkability_score,
                reverse=True
            )[:5]
            
            # Top distritos por accesibilidad
            top_accessible = sorted(
                districts,
                key=lambda d: d.transit_accessibility,
                reverse=True
            )[:5]
            
            insights = {
                **summary,
                'insights': {
                    'most_walkable_districts': [
                        {
                            'name': d.name,
                            'type': d.district_type,
                            'walkability': d.walkability_score,
                            'center': d.center
                        } for d in top_walkable
                    ],
                    'most_accessible_districts': [
                        {
                            'name': d.name,
                            'type': d.district_type,
                            'accessibility': d.transit_accessibility,
                            'center': d.center
                        } for d in top_accessible
                    ],
                    'diversity_index': len(summary.get('district_types', [])),
                    'total_pois_analyzed': sum(
                        stats['total_pois'] for stats in summary.get('district_stats', {}).values()
                    )
                }
            }
            
            return insights
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo insights: {e}")
            return {
                'status': 'error',
                'city': city_name,
                'error': str(e)
            }