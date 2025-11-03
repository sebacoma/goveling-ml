"""
🧠 SEMANTIC CITY2GRAPH - VERSIÓN SIMPLIFICADA PARA DEMOSTRACIÓN
Sistema semántico completo sin dependencia de OSM para descarga de grafos
"""

import logging
import asyncio
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass
from shapely.geometry import Point, Polygon
import numpy as np
from sklearn.cluster import DBSCAN
import json
import os

logger = logging.getLogger(__name__)

@dataclass
class SemanticDistrict:
    name: str
    center: Tuple[float, float]
    polygon: Polygon
    district_type: str
    walkability_score: float
    transit_accessibility: float
    cultural_context: Dict
    peak_hours: Dict
    poi_density: Dict
    confidence_score: float

class SemanticCity2GraphService:
    """
    🏙️ Servicio semántico simplificado que demuestra todos los beneficios
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.semantic_districts = {}
        self.cultural_contexts = {}
        
        # Base de datos de POIs de Santiago para demostración
        self.santiago_pois = {
            'financial': [
                {'name': 'Banco Central', 'lat': -33.4372, 'lon': -70.6506, 'importance': 'high'},
                {'name': 'Banco de Chile', 'lat': -33.4375, 'lon': -70.6510, 'importance': 'high'},
                {'name': 'Centro Financiero', 'lat': -33.4380, 'lon': -70.6500, 'importance': 'medium'},
                {'name': 'Torre Entel', 'lat': -33.4385, 'lon': -70.6495, 'importance': 'medium'},
            ],
            'tourist': [
                {'name': 'Plaza de Armas', 'lat': -33.4378, 'lon': -70.6504, 'importance': 'very_high'},
                {'name': 'Catedral Metropolitana', 'lat': -33.4375, 'lon': -70.6501, 'importance': 'high'},
                {'name': 'Casa de la Moneda', 'lat': -33.4425, 'lon': -70.6540, 'importance': 'very_high'},
                {'name': 'Cerro Santa Lucía', 'lat': -33.4403, 'lon': -70.6436, 'importance': 'high'},
            ],
            'commercial': [
                {'name': 'Mall Plaza Italia', 'lat': -33.4378, 'lon': -70.6377, 'importance': 'high'},
                {'name': 'Mercado Central', 'lat': -33.4325, 'lon': -70.6517, 'importance': 'high'},
                {'name': 'Portal Lyon', 'lat': -33.4156, 'lon': -70.6022, 'importance': 'medium'},
                {'name': 'Costanera Center', 'lat': -33.4180, 'lon': -70.6063, 'importance': 'very_high'},
            ],
            'cultural': [
                {'name': 'Museo Nacional', 'lat': -33.4336, 'lon': -70.6394, 'importance': 'high'},
                {'name': 'Teatro Municipal', 'lat': -33.4366, 'lon': -70.6482, 'importance': 'high'},
                {'name': 'Centro Gabriela Mistral', 'lat': -33.4424, 'lon': -70.6394, 'importance': 'medium'},
                {'name': 'Biblioteca Nacional', 'lat': -33.4415, 'lon': -70.6500, 'importance': 'medium'},
            ],
            'nightlife': [
                {'name': 'Barrio Bellavista', 'lat': -33.4267, 'lon': -70.6287, 'importance': 'very_high'},
                {'name': 'Patio Bellavista', 'lat': -33.4273, 'lon': -70.6295, 'importance': 'high'},
                {'name': 'Barrio Brasil', 'lat': -33.4450, 'lon': -70.6700, 'importance': 'medium'},
                {'name': 'Providencia Nightlife', 'lat': -33.4250, 'lon': -70.6150, 'importance': 'high'},
            ],
            'residential': [
                {'name': 'Las Condes', 'lat': -33.4000, 'lon': -70.5500, 'importance': 'high'},
                {'name': 'Providencia', 'lat': -33.4250, 'lon': -70.6150, 'importance': 'high'},
                {'name': 'Ñuñoa', 'lat': -33.4567, 'lon': -70.5984, 'importance': 'medium'},
                {'name': 'Santiago Centro', 'lat': -33.4489, 'lon': -70.6693, 'importance': 'medium'},
            ]
        }
    
    async def initialize_city(self, city_name: str, bbox: Tuple) -> bool:
        """
        🏗️ Inicializar análisis semántico de una ciudad
        """
        try:
            self.logger.info(f"🏙️ Inicializando análisis semántico para {city_name}")
            
            if city_name.lower() == 'santiago':
                # Crear distritos semánticos usando datos de Santiago
                await self._create_santiago_districts()
                await self._analyze_cultural_context(city_name)
                
                self.logger.info(f"✅ {city_name} inicializada con {len(self.semantic_districts[city_name])} distritos")
                return True
            else:
                # Para otras ciudades, crear distritos básicos
                await self._create_generic_districts(city_name, bbox)
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Error inicializando {city_name}: {e}")
            return False
    
    async def _create_santiago_districts(self):
        """
        🏛️ Crear distritos semánticos reales de Santiago
        """
        city_name = 'santiago'
        districts = []
        
        for district_type, pois in self.santiago_pois.items():
            if len(pois) >= 3:
                # Clustering DBSCAN de los POIs
                coords = np.array([[poi['lat'], poi['lon']] for poi in pois])
                clustering = DBSCAN(eps=0.01, min_samples=2).fit(coords)
                
                # Crear distritos por cluster
                unique_labels = set(clustering.labels_)
                unique_labels.discard(-1)  # Remover noise
                
                for cluster_id in unique_labels:
                    cluster_pois = [pois[i] for i, label in enumerate(clustering.labels_) if label == cluster_id]
                    
                    if len(cluster_pois) >= 2:
                        # Calcular centro del distrito
                        center_lat = sum(poi['lat'] for poi in cluster_pois) / len(cluster_pois)
                        center_lon = sum(poi['lon'] for poi in cluster_pois) / len(cluster_pois)
                        
                        # Crear polígono (círculo para simplicidad)
                        radius = 0.008  # ~800m radius
                        polygon = Point(center_lon, center_lat).buffer(radius)
                        
                        # Calcular métricas realistas
                        walkability = self._calculate_realistic_walkability(district_type, cluster_pois)
                        transit_access = self._calculate_realistic_transit(district_type, cluster_pois)
                        confidence = self._calculate_confidence(cluster_pois)
                        
                        district = SemanticDistrict(
                            name=f"{district_type.title()} {self._get_district_name(district_type, cluster_id)}",
                            center=(center_lat, center_lon),
                            polygon=polygon,
                            district_type=district_type,
                            walkability_score=walkability,
                            transit_accessibility=transit_access,
                            cultural_context=self._get_cultural_context(district_type),
                            peak_hours=self._get_peak_hours(district_type),
                            poi_density={
                                'total': len(cluster_pois),
                                district_type: len(cluster_pois),
                                'density_per_km2': len(cluster_pois) * 20  # Estimación realista
                            },
                            confidence_score=confidence
                        )
                        
                        districts.append(district)
                        self.logger.info(f"✅ Creado distrito: {district.name} con {len(cluster_pois)} POIs")
        
        self.semantic_districts[city_name] = districts
        self.logger.info(f"🎯 Total distritos creados para Santiago: {len(districts)}")
    
    def _calculate_realistic_walkability(self, district_type: str, pois: List[Dict]) -> float:
        """
        🚶‍♂️ Calcular walkability realista basado en tipo y características
        """
        base_scores = {
            'financial': 0.85,      # Centro financiero muy walkable
            'tourist': 0.90,        # Áreas turísticas optimizadas para peatones
            'commercial': 0.88,     # Centros comerciales muy accesibles
            'cultural': 0.82,       # Museos y teatros generalmente accesibles
            'nightlife': 0.75,      # Variable según zona
            'residential': 0.65     # Depende mucho del barrio
        }
        
        base_score = base_scores.get(district_type, 0.6)
        
        # Ajustar por importancia de POIs
        importance_bonus = 0
        for poi in pois:
            if poi.get('importance') == 'very_high':
                importance_bonus += 0.05
            elif poi.get('importance') == 'high':
                importance_bonus += 0.03
            elif poi.get('importance') == 'medium':
                importance_bonus += 0.01
        
        # Normalizar y limitar
        final_score = min(1.0, base_score + (importance_bonus / len(pois)))
        return round(final_score, 2)
    
    def _calculate_realistic_transit(self, district_type: str, pois: List[Dict]) -> float:
        """
        🚌 Calcular accesibilidad de transporte realista
        """
        base_scores = {
            'financial': 0.95,      # Centro muy conectado
            'tourist': 0.88,        # Bien conectado para turistas
            'commercial': 0.92,     # Centros comerciales muy accesibles
            'cultural': 0.85,       # Buena conectividad cultural
            'nightlife': 0.80,      # Conectado para vida nocturna
            'residential': 0.75     # Varía por zona residencial
        }
        
        base_score = base_scores.get(district_type, 0.7)
        
        # Ajustar por centralidad (POIs más céntricos mejor conectados)
        centrality_bonus = 0
        for poi in pois:
            # Distancia al centro de Santiago (-33.4489, -70.6693)
            dist_to_center = ((poi['lat'] + 33.4489)**2 + (poi['lon'] + 70.6693)**2)**0.5
            if dist_to_center < 0.02:  # ~2km del centro
                centrality_bonus += 0.05
            elif dist_to_center < 0.05:  # ~5km del centro
                centrality_bonus += 0.02
        
        final_score = min(1.0, base_score + (centrality_bonus / len(pois)))
        return round(final_score, 2)
    
    def _calculate_confidence(self, pois: List[Dict]) -> float:
        """
        🎯 Calcular confianza del análisis basado en cantidad y calidad de datos
        """
        base_confidence = min(0.9, len(pois) * 0.15)  # Más POIs = mayor confianza
        
        # Bonus por importancia
        importance_bonus = 0
        for poi in pois:
            if poi.get('importance') == 'very_high':
                importance_bonus += 0.2
            elif poi.get('importance') == 'high':
                importance_bonus += 0.1
            elif poi.get('importance') == 'medium':
                importance_bonus += 0.05
        
        final_confidence = min(1.0, base_confidence + (importance_bonus / len(pois)))
        return round(final_confidence, 2)
    
    def _get_district_name(self, district_type: str, cluster_id: int) -> str:
        """
        🏛️ Nombres específicos de distritos de Santiago
        """
        district_names = {
            'financial': ['Centro Financiero', 'Distrito Bancario', 'Zona Corporativa'],
            'tourist': ['Centro Histórico', 'Zona Turística', 'Patrimonio'],
            'commercial': ['Zona Comercial', 'Centro de Compras', 'Distrito Shopping'],
            'cultural': ['Distrito Cultural', 'Zona Artística', 'Centro Cultural'],
            'nightlife': ['Zona Bohemia', 'Distrito Nocturno', 'Vida Nocturna'],
            'residential': ['Zona Residencial', 'Barrio', 'Distrito Habitacional']
        }
        
        names = district_names.get(district_type, ['Distrito'])
        return names[cluster_id % len(names)]
    
    async def _create_generic_districts(self, city_name: str, bbox: Tuple):
        """
        🌐 Crear distritos genéricos para ciudades no predefinidas
        """
        # Distrito genérico básico
        center_lat = (bbox[0] + bbox[1]) / 2
        center_lon = (bbox[2] + bbox[3]) / 2
        
        district = SemanticDistrict(
            name=f"{city_name.title()} Centro",
            center=(center_lat, center_lon),
            polygon=Point(center_lon, center_lat).buffer(0.01),
            district_type='general',
            walkability_score=0.6,
            transit_accessibility=0.6,
            cultural_context=self._get_cultural_context('general'),
            peak_hours=self._get_peak_hours('general'),
            poi_density={'total': 5, 'general': 5},
            confidence_score=0.3
        )
        
        self.semantic_districts[city_name] = [district]
    
    def _get_cultural_context(self, district_type: str) -> Dict:
        """
        🎭 Contexto cultural por tipo de distrito
        """
        contexts = {
            'financial': {
                'business_hours': '09:00-18:00',
                'dress_code': 'formal',
                'pace': 'fast',
                'noise_level': 'moderate',
                'language': 'business_spanish',
                'tipping_culture': 'optional',
                'safety_level': 'high'
            },
            'tourist': {
                'business_hours': '09:00-20:00',
                'dress_code': 'casual',
                'pace': 'slow',
                'noise_level': 'high',
                'language': 'tourist_friendly',
                'tipping_culture': 'expected',
                'safety_level': 'high',
                'photo_opportunities': 'excellent'
            },
            'commercial': {
                'business_hours': '10:00-22:00',
                'dress_code': 'casual',
                'pace': 'moderate',
                'noise_level': 'high',
                'language': 'spanish_english',
                'tipping_culture': 'restaurants_only',
                'safety_level': 'high'
            },
            'cultural': {
                'business_hours': '10:00-18:00',
                'dress_code': 'smart_casual',
                'pace': 'slow',
                'noise_level': 'low',
                'language': 'spanish',
                'tipping_culture': 'rare',
                'safety_level': 'very_high',
                'educational_value': 'high'
            },
            'nightlife': {
                'business_hours': '20:00-03:00',
                'dress_code': 'trendy',
                'pace': 'variable',
                'noise_level': 'very_high',
                'language': 'spanish_party',
                'tipping_culture': 'expected',
                'safety_level': 'moderate',
                'age_restrictions': '18+'
            },
            'residential': {
                'business_hours': '24/7',
                'dress_code': 'casual',
                'pace': 'slow',
                'noise_level': 'low',
                'language': 'local_spanish',
                'tipping_culture': 'minimal',
                'safety_level': 'variable'
            }
        }
        
        return contexts.get(district_type, contexts['tourist'])
    
    def _get_peak_hours(self, district_type: str) -> Dict:
        """
        ⏰ Horarios pico específicos de Santiago
        """
        schedules = {
            'financial': {
                'morning_rush': (8, 10),
                'lunch_peak': (12, 15),
                'evening_rush': (17, 19),
                'optimal_visit': (10, 12),
                'avoid_times': [(12, 15), (18, 19)]
            },
            'tourist': {
                'morning_optimal': (9, 11),
                'afternoon_peak': (14, 17),
                'golden_hour': (18, 20),
                'optimal_visit': (9, 11),
                'avoid_times': [(13, 14)]  # Siesta time
            },
            'commercial': {
                'morning_start': (10, 12),
                'afternoon_peak': (15, 18),
                'evening_shopping': (19, 21),
                'weekend_peak': (11, 20),
                'optimal_visit': (10, 12),
                'avoid_times': [(21, 10)]
            },
            'cultural': {
                'morning_calm': (10, 12),
                'afternoon_peak': (14, 17),
                'evening_events': (19, 22),
                'optimal_visit': (10, 12),
                'avoid_times': [(12, 14)]  # Lunch closure
            },
            'nightlife': {
                'pre_party': (19, 21),
                'peak_night': (22, 2),
                'late_night': (2, 4),
                'optimal_visit': (21, 23),
                'avoid_times': [(4, 19)]
            },
            'residential': {
                'morning_activity': (7, 9),
                'lunch_quiet': (13, 15),
                'evening_activity': (18, 20),
                'optimal_visit': (15, 17),
                'avoid_times': [(22, 7)]
            }
        }
        
        return schedules.get(district_type, {
            'general_hours': (9, 18),
            'optimal_visit': (10, 16),
            'avoid_times': [(0, 8)]
        })
    
    async def _analyze_cultural_context(self, city_name: str):
        """
        🌍 Análisis cultural específico de Santiago
        """
        santiago_culture = {
            'city_type': 'metropolitan',
            'primary_language': 'spanish',
            'secondary_languages': ['english', 'french'],
            'timezone': 'America/Santiago',
            'currency': 'CLP',
            'business_culture': 'latin_american',
            'walking_culture': 'moderate_high',
            'public_transport_usage': 'very_high',
            'meal_times': {
                'breakfast': (7, 10),
                'once': (17, 19),  # Traditional Chilean afternoon tea
                'dinner': (20, 22)
            },
            'social_customs': {
                'greeting': 'cheek_kiss',
                'punctuality': 'flexible',
                'dress_style': 'conservative_casual'
            },
            'weather_patterns': {
                'summer': 'dry_hot',
                'winter': 'rainy_mild',
                'optimal_walking_months': ['Oct', 'Nov', 'Mar', 'Apr']
            }
        }
        
        self.cultural_contexts[city_name] = santiago_culture
    
    async def get_semantic_context(self, lat: float, lon: float, city_name: str) -> Dict:
        """
        🎯 Obtener contexto semántico detallado de una ubicación
        """
        if city_name not in self.semantic_districts or not self.semantic_districts[city_name]:
            return {
                'district': 'Unknown',
                'district_type': 'general',
                'walkability_score': 0.5,
                'transit_accessibility': 0.5,
                'cultural_context': self._get_cultural_context('general'),
                'peak_hours': self._get_peak_hours('general'),
                'poi_density': {'total': 0},
                'confidence': 0.1,
                'recommendation': 'Initialize city analysis first'
            }
        
        point = Point(lon, lat)
        
        # Buscar distrito que contenga el punto
        for district in self.semantic_districts[city_name]:
            try:
                if district.polygon.contains(point):
                    return {
                        'district': district.name,
                        'district_type': district.district_type,
                        'walkability_score': district.walkability_score,
                        'transit_accessibility': district.transit_accessibility,
                        'peak_hours': district.peak_hours,
                        'poi_density': district.poi_density,
                        'cultural_context': district.cultural_context,
                        'center': district.center,
                        'confidence': district.confidence_score,
                        'inside_district': True,
                        'city_culture': self.cultural_contexts.get(city_name, {})
                    }
            except Exception as e:
                self.logger.debug(f"Error verificando contención: {e}")
                continue
        
        # Buscar distrito más cercano
        if self.semantic_districts[city_name]:
            closest_district = min(
                self.semantic_districts[city_name],
                key=lambda d: Point(d.center[1], d.center[0]).distance(point)
            )
            
            distance = Point(closest_district.center[1], closest_district.center[0]).distance(point)
            
            return {
                'district': f"Near {closest_district.name}",
                'district_type': closest_district.district_type,
                'walkability_score': closest_district.walkability_score * 0.8,
                'transit_accessibility': closest_district.transit_accessibility * 0.8,
                'peak_hours': closest_district.peak_hours,
                'poi_density': closest_district.poi_density,
                'cultural_context': closest_district.cultural_context,
                'distance_to_center_km': distance * 111.32,
                'confidence': closest_district.confidence_score * 0.7,
                'inside_district': False,
                'city_culture': self.cultural_contexts.get(city_name, {})
            }
        
        # Fallback
        return {
            'district': 'Unknown Area',
            'district_type': 'general',
            'walkability_score': 0.5,
            'transit_accessibility': 0.5,
            'cultural_context': self._get_cultural_context('general'),
            'peak_hours': self._get_peak_hours('general'),
            'poi_density': {'total': 0},
            'confidence': 0.1,
            'inside_district': False
        }
    
    async def get_smart_clustering_suggestions(self, places: List[Dict], city_name: str) -> Dict:
        """
        🧠 Sugerencias inteligentes de clustering semántico
        """
        if city_name not in self.semantic_districts:
            return {
                'strategy': 'geographic_fallback',
                'reason': 'city_not_initialized',
                'district_groups': {},
                'recommendations': []
            }
        
        self.logger.info(f"🧠 Analizando {len(places)} lugares para clustering semántico")
        
        # Obtener contexto de cada lugar
        place_contexts = []
        for place in places:
            context = await self.get_semantic_context(place['lat'], place['lon'], city_name)
            place_contexts.append({
                'place': place,
                'context': context
            })
        
        # Agrupar por distritos
        district_groups = {}
        for pc in place_contexts:
            district = pc['context']['district']
            if district not in district_groups:
                district_groups[district] = []
            district_groups[district].append(pc)
        
        # Generar recomendaciones
        recommendations = []
        for district, places_group in district_groups.items():
            if len(places_group) >= 1:  # Al menos 1 lugar
                first_context = places_group[0]['context']
                
                # Calcular métricas del grupo
                avg_confidence = sum(pc['context']['confidence'] for pc in places_group) / len(places_group)
                
                recommendation = {
                    'district': district,
                    'district_type': first_context['district_type'],
                    'places_count': len(places_group),
                    'place_names': [pc['place'].get('name', 'Unknown') for pc in places_group],
                    'walkability': first_context['walkability_score'],
                    'transit_accessibility': first_context['transit_accessibility'],
                    'recommended_time_slots': first_context['peak_hours'],
                    'cultural_context': first_context['cultural_context'],
                    'confidence': round(avg_confidence, 2),
                    'clustering_reason': f"Semantic grouping in {first_context['district_type']} district",
                    'optimization_tips': self._generate_optimization_tips(first_context)
                }
                
                recommendations.append(recommendation)
        
        return {
            'strategy': 'semantic',
            'city': city_name,
            'district_groups': district_groups,
            'recommendations': recommendations,
            'total_districts_analyzed': len(self.semantic_districts[city_name]),
            'city_cultural_context': self.cultural_contexts.get(city_name, {}),
            'optimization_insights': self._generate_global_insights(recommendations)
        }
    
    def _generate_optimization_tips(self, context: Dict) -> List[str]:
        """
        💡 Generar tips de optimización específicos por contexto
        """
        tips = []
        district_type = context['district_type']
        walkability = context['walkability_score']
        
        # Tips por tipo de distrito
        if district_type == 'financial':
            tips.extend([
                "🕐 Visit during business hours (9-18) for full experience",
                "💼 Professional dress recommended",
                "🍽️ Excellent lunch options nearby (12-15)"
            ])
        elif district_type == 'tourist':
            tips.extend([
                "📸 Excellent photo opportunities available",
                "🗺️ Allow extra time for exploration",
                "👥 Expect crowds, especially weekends"
            ])
        elif district_type == 'commercial':
            tips.extend([
                "🛍️ Best shopping hours: 10-12 and 15-18",
                "💳 Cards widely accepted",
                "🍽️ Great food court options"
            ])
        elif district_type == 'cultural':
            tips.extend([
                "📚 Check opening hours - many closed Mondays",
                "🎫 Consider combined tickets for multiple venues",
                "⏰ Allow 2-3 hours per major cultural site"
            ])
        elif district_type == 'nightlife':
            tips.extend([
                "🌙 Plan for evening visits (20:00+)",
                "🎉 Dress trendy/fashionable",
                "🚖 Arrange safe transportation for late hours"
            ])
        
        # Tips por walkability
        if walkability >= 0.85:
            tips.append("🚶‍♂️ Excellent walkability - plan walking routes between venues")
        elif walkability >= 0.70:
            tips.append("👟 Good walkability - comfortable shoes recommended")
        elif walkability >= 0.50:
            tips.append("🚗 Moderate walkability - consider transportation for longer distances")
        else:
            tips.append("🚖 Limited walkability - transportation recommended between venues")
        
        # Tips por accesibilidad
        transit = context['transit_accessibility']
        if transit >= 0.9:
            tips.append("🚇 Metro/Bus excellent - use public transportation")
        elif transit >= 0.7:
            tips.append("🚌 Good public transport connections available")
        
        return tips
    
    def _generate_global_insights(self, recommendations: List[Dict]) -> List[str]:
        """
        📊 Insights globales del análisis
        """
        insights = []
        
        if not recommendations:
            return ["No semantic districts identified - using geographic clustering"]
        
        # Diversidad de distritos
        district_types = set(rec['district_type'] for rec in recommendations)
        if len(district_types) >= 3:
            insights.append(f"🎯 Excellent diversity: {len(district_types)} different district types for varied experience")
        
        # Walkability general
        avg_walkability = sum(rec['walkability'] for rec in recommendations) / len(recommendations)
        if avg_walkability >= 0.8:
            insights.append("🚶‍♂️ High walkability areas - optimize for pedestrian routes")
        elif avg_walkability <= 0.5:
            insights.append("🚗 Lower walkability - prioritize transportation optimization")
        
        # Confianza del análisis
        avg_confidence = sum(rec['confidence'] for rec in recommendations) / len(recommendations)
        if avg_confidence >= 0.8:
            insights.append("✅ High confidence semantic analysis - reliable clustering recommendations")
        elif avg_confidence >= 0.6:
            insights.append("⚖️ Good confidence semantic analysis - clustering recommendations reliable")
        else:
            insights.append("⚠️ Moderate confidence - recommendations based on limited data")
        
        return insights
    
    def get_city_summary(self, city_name: str) -> Dict:
        """
        📊 Resumen completo de análisis de ciudad
        """
        if city_name not in self.semantic_districts:
            return {'status': 'not_initialized', 'city': city_name}
        
        districts = self.semantic_districts[city_name]
        cultural_context = self.cultural_contexts.get(city_name, {})
        
        # Estadísticas por tipo
        district_stats = {}
        total_pois = 0
        total_walkability = 0
        total_transit = 0
        
        for district in districts:
            dtype = district.district_type
            if dtype not in district_stats:
                district_stats[dtype] = {
                    'count': 0,
                    'total_pois': 0,
                    'avg_walkability': 0,
                    'avg_transit': 0
                }
            
            district_stats[dtype]['count'] += 1
            district_stats[dtype]['total_pois'] += district.poi_density.get('total', 0)
            district_stats[dtype]['avg_walkability'] += district.walkability_score
            district_stats[dtype]['avg_transit'] += district.transit_accessibility
            
            total_pois += district.poi_density.get('total', 0)
            total_walkability += district.walkability_score
            total_transit += district.transit_accessibility
        
        # Promediar métricas
        for dtype in district_stats:
            count = district_stats[dtype]['count']
            if count > 0:
                district_stats[dtype]['avg_walkability'] = round(district_stats[dtype]['avg_walkability'] / count, 2)
                district_stats[dtype]['avg_transit'] = round(district_stats[dtype]['avg_transit'] / count, 2)
        
        return {
            'status': 'initialized',
            'city': city_name,
            'total_districts': len(districts),
            'district_types': list(district_stats.keys()),
            'district_stats': district_stats,
            'city_metrics': {
                'total_pois_analyzed': total_pois,
                'avg_walkability': round(total_walkability / len(districts), 2) if districts else 0,
                'avg_transit_accessibility': round(total_transit / len(districts), 2) if districts else 0,
                'diversity_index': len(district_stats)
            },
            'cultural_context': cultural_context,
            'analysis_quality': 'high' if total_pois > 15 else 'medium' if total_pois > 5 else 'basic'
        }