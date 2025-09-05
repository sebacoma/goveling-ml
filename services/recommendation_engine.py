"""
Goveling ML - Intelligent Recommendation Engine
Sistema de recomendaciones multi-algoritmo para días libres
"""

import math
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from collections import Counter, defaultdict
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
import numpy as np

from models.schemas import Activity, Recommendation, UserProfile
from utils.geo_utils import calculate_distance, get_city_bounds


@dataclass
class RecommendationScore:
    """Score detallado de una recomendación"""
    total_score: float
    preference_score: float
    geographic_score: float
    temporal_score: float
    novelty_score: float
    confidence: float


class RecommendationEngine:
    """
    Motor de recomendaciones inteligente que combina múltiples algoritmos:
    - Análisis de preferencias del usuario
    - Filtrado colaborativo  
    - Optimización geográfica
    - Factores temporales
    """
    
    def __init__(self):
        self.activity_database = self._load_activity_database()
        self.user_patterns = self._load_user_patterns()
        self.category_weights = {
            'museum': 0.8, 'restaurant': 0.9, 'park': 0.7,
            'shopping': 0.6, 'nightlife': 0.5, 'sports': 0.6,
            'culture': 0.8, 'adventure': 0.7, 'relaxation': 0.8
        }
    
    def generate_recommendations(self, 
                               user_activities: List[Activity],
                               free_days: int,
                               user_location: Dict[str, float],
                               preferences: Optional[Dict] = None) -> List[Dict]:
        """
        Genera recomendaciones inteligentes para días libres
        
        Args:
            user_activities: Actividades ya seleccionadas por el usuario
            free_days: Número de días libres disponibles
            user_location: Ubicación base del usuario
            preferences: Preferencias adicionales del usuario
        
        Returns:
            Lista de recomendaciones rankeadas con scores detallados
        """
        
        # 1. Analizar perfil del usuario
        user_profile = self._analyze_user_profile(user_activities, preferences)
        
        # 2. Generar candidatos usando múltiples algoritmos
        candidates = self._generate_candidates(user_profile, user_location)
        
        # 3. Calcular scores multi-dimensionales
        scored_candidates = []
        for candidate in candidates:
            score = self._calculate_recommendation_score(
                candidate, user_profile, user_activities, user_location
            )
            scored_candidates.append({
                'activity': candidate,
                'score': score,
                'reasoning': self._generate_reasoning(candidate, score, user_profile)
            })
        
        # 4. Ranking y selección final
        ranked_recommendations = sorted(
            scored_candidates, 
            key=lambda x: x['score'].total_score, 
            reverse=True
        )
        
        # 5. Diversificación y optimización para múltiples días
        final_recommendations = self._optimize_for_multiple_days(
            ranked_recommendations, free_days, user_location
        )
        
        return final_recommendations[:free_days * 4]  # ~4 recomendaciones por día
    
    def _analyze_user_profile(self, activities: List[Activity], preferences: Dict) -> UserProfile:
        """Analiza las actividades del usuario para inferir preferencias"""
        
        # Análisis de categorías preferidas
        categories = [act.category for act in activities if act.category]
        category_preferences = Counter(categories)
        
        # Análisis de duración promedio
        durations = [act.estimated_duration for act in activities if act.estimated_duration]
        avg_duration = np.mean(durations) if durations else 2.0
        
        # Análisis de nivel de actividad (indoor vs outdoor)
        outdoor_categories = {'park', 'adventure', 'sports', 'beach', 'hiking'}
        indoor_categories = {'museum', 'shopping', 'restaurant', 'culture', 'art'}
        
        outdoor_count = sum(1 for act in activities if act.category in outdoor_categories)
        indoor_count = sum(1 for act in activities if act.category in indoor_categories)
        
        activity_level = 'balanced'
        if outdoor_count > indoor_count * 1.5:
            activity_level = 'outdoor'
        elif indoor_count > outdoor_count * 1.5:
            activity_level = 'indoor'
        
        # Análisis de distribución geográfica
        if len(activities) >= 2:
            distances = []
            for i in range(len(activities)-1):
                for j in range(i+1, len(activities)):
                    dist = calculate_distance(
                        activities[i].coordinates.latitude,
                        activities[i].coordinates.longitude,
                        activities[j].coordinates.latitude,
                        activities[j].coordinates.longitude
                    )
                    distances.append(dist)
            
            avg_distance = np.mean(distances) if distances else 5.0
            exploration_radius = avg_distance * 1.5  # Radio de exploración preferido
        else:
            exploration_radius = 10.0  # Default 10km
        
        return UserProfile(
            preferred_categories=dict(category_preferences),
            activity_level=activity_level,
            avg_duration_preference=avg_duration,
            exploration_radius=exploration_radius,
            budget_level=preferences.get('budget_level', 'medium') if preferences else 'medium',
            travel_style=preferences.get('travel_style', 'explorer') if preferences else 'explorer',
            confidence_score=min(1.0, len(activities) / 5.0)  # Más confianza con más actividades
        )
    
    def _generate_candidates(self, user_profile: UserProfile, user_location: Dict) -> List[Activity]:
        """Genera candidatos usando múltiples estrategias"""
        
        candidates = []
        
        # 1. Candidatos basados en preferencias de categoría
        category_candidates = self._get_category_based_candidates(user_profile, user_location)
        candidates.extend(category_candidates)
        
        # 2. Candidatos de filtrado colaborativo
        collaborative_candidates = self._get_collaborative_candidates(user_profile, user_location)
        candidates.extend(collaborative_candidates)
        
        # 3. Candidatos geográficos (hidden gems, lugares populares cercanos)
        geo_candidates = self._get_geographic_candidates(user_profile, user_location)
        candidates.extend(geo_candidates)
        
        # 4. Candidatos por novedad (lugares únicos/especiales)
        novelty_candidates = self._get_novelty_candidates(user_profile, user_location)
        candidates.extend(novelty_candidates)
        
        # Eliminar duplicados
        unique_candidates = []
        seen_names = set()
        for candidate in candidates:
            if candidate.name not in seen_names:
                unique_candidates.append(candidate)
                seen_names.add(candidate.name)
        
        return unique_candidates
    
    def _calculate_recommendation_score(self, 
                                      candidate: Activity, 
                                      user_profile: UserProfile,
                                      user_activities: List[Activity],
                                      user_location: Dict) -> RecommendationScore:
        """Calcula score multi-dimensional para una recomendación"""
        
        # 1. Score de preferencias (40%)
        preference_score = self._calculate_preference_score(candidate, user_profile)
        
        # 2. Score geográfico (25%)
        geographic_score = self._calculate_geographic_score(candidate, user_location, user_profile)
        
        # 3. Score temporal/contextual (20%)
        temporal_score = self._calculate_temporal_score(candidate, user_profile)
        
        # 4. Score de novedad (15%)
        novelty_score = self._calculate_novelty_score(candidate, user_activities)
        
        # Score total ponderado
        total_score = (
            preference_score * 0.40 +
            geographic_score * 0.25 +
            temporal_score * 0.20 +
            novelty_score * 0.15
        )
        
        # Confianza basada en cantidad de datos disponibles
        confidence = min(1.0, len(user_activities) / 5.0)  # Más confianza con más datos
        
        return RecommendationScore(
            total_score=total_score,
            preference_score=preference_score,
            geographic_score=geographic_score,
            temporal_score=temporal_score,
            novelty_score=novelty_score,
            confidence=confidence
        )
    
    def _calculate_preference_score(self, candidate: Activity, user_profile: UserProfile) -> float:
        """Calcula score basado en preferencias del usuario"""
        
        score = 0.0
        
        # Score por categoría
        if candidate.category in user_profile.preferred_categories:
            category_frequency = user_profile.preferred_categories[candidate.category]
            total_activities = sum(user_profile.preferred_categories.values())
            category_preference = category_frequency / total_activities
            score += category_preference * 0.6
        
        # Score por duración
        duration_diff = abs(candidate.estimated_duration - user_profile.avg_duration_preference)
        duration_score = max(0, 1 - (duration_diff / 4.0))  # Penaliza diferencias >4h
        score += duration_score * 0.2
        
        # Score por nivel de actividad
        outdoor_categories = {'park', 'adventure', 'sports', 'beach', 'hiking'}
        indoor_categories = {'museum', 'shopping', 'restaurant', 'culture', 'art'}
        
        if user_profile.activity_level == 'outdoor' and candidate.category in outdoor_categories:
            score += 0.2
        elif user_profile.activity_level == 'indoor' and candidate.category in indoor_categories:
            score += 0.2
        elif user_profile.activity_level == 'balanced':
            score += 0.1
        
        return min(1.0, score)
    
    def _calculate_geographic_score(self, candidate: Activity, user_location: Dict, user_profile: UserProfile) -> float:
        """Calcula score basado en factores geográficos"""
        
        distance = calculate_distance(
            user_location['latitude'],
            user_location['longitude'],
            candidate.coordinates.latitude,
            candidate.coordinates.longitude
        )
        
        # Score inversamente proporcional a la distancia, pero respetando radio de exploración
        if distance <= user_profile.exploration_radius:
            # Dentro del radio preferido - score alto
            score = 1.0 - (distance / user_profile.exploration_radius) * 0.3
        else:
            # Fuera del radio - penalización gradual
            excess_distance = distance - user_profile.exploration_radius
            penalty = min(0.7, excess_distance / 20.0)  # Penalización máxima 70%
            score = 0.3 - penalty
        
        return max(0.0, min(1.0, score))
    
    def _calculate_temporal_score(self, candidate: Activity, user_profile: UserProfile) -> float:
        """Score basado en factores temporales y contextuales"""
        
        score = 0.5  # Base score
        
        # Factor por popularidad/rating (si está disponible)
        if hasattr(candidate, 'rating') and candidate.rating:
            rating_normalized = candidate.rating / 5.0  # Asumiendo escala 1-5
            score += rating_normalized * 0.3
        
        # Factor por disponibilidad de horarios
        if hasattr(candidate, 'opening_hours') and candidate.opening_hours:
            if 'closed' not in candidate.opening_hours.lower():
                score += 0.2
        
        return min(1.0, score)
    
    def _calculate_novelty_score(self, candidate: Activity, user_activities: List[Activity]) -> float:
        """Score de novedad - qué tan diferente es de las actividades ya seleccionadas"""
        
        if not user_activities:
            return 1.0
        
        # Verificar si la categoría ya está representada
        user_categories = set(act.category for act in user_activities if act.category)
        
        if candidate.category not in user_categories:
            # Nueva categoría - alta novedad
            return 1.0
        else:
            # Categoría repetida - score basado en frecuencia
            category_count = sum(1 for act in user_activities if act.category == candidate.category)
            novelty = max(0.2, 1.0 - (category_count * 0.3))
            return novelty
    
    def _generate_reasoning(self, candidate: Activity, score: RecommendationScore, user_profile: UserProfile) -> str:
        """Genera explicación textual de por qué se recomienda este lugar"""
        
        reasons = []
        
        # Razón principal
        if score.preference_score > 0.7:
            if candidate.category in user_profile.preferred_categories:
                reasons.append(f"Te gustan los {candidate.category}s")
        
        if score.geographic_score > 0.7:
            reasons.append("Está bien ubicado para ti")
        
        if score.novelty_score > 0.8:
            reasons.append("Es algo nuevo que podrías disfrutar")
        
        if score.temporal_score > 0.7:
            reasons.append("Tiene buenas reseñas")
        
        # Razón por defecto
        if not reasons:
            reasons.append("Creemos que podría interesarte")
        
        return " • ".join(reasons[:2])  # Máximo 2 razones principales
    
    def _optimize_for_multiple_days(self, 
                                  recommendations: List[Dict], 
                                  free_days: int, 
                                  user_location: Dict) -> List[Dict]:
        """Optimiza recomendaciones para múltiples días"""
        
        if free_days <= 1:
            return recommendations
        
        # Agrupa recomendaciones por día usando clustering geográfico
        activities = [rec['activity'] for rec in recommendations]
        
        if len(activities) < free_days:
            return recommendations
        
        # Extrae coordenadas para clustering
        coordinates = np.array([
            [act.coordinates.latitude, act.coordinates.longitude] 
            for act in activities
        ])
        
        # KMeans clustering
        n_clusters = min(free_days, len(activities))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(coordinates)
        
        # Organiza por clusters (días)
        organized_recommendations = []
        for day in range(n_clusters):
            day_activities = [
                recommendations[i] for i, cluster in enumerate(clusters) 
                if cluster == day
            ]
            # Ordena por score dentro del día
            day_activities.sort(key=lambda x: x['score'].total_score, reverse=True)
            
            for i, rec in enumerate(day_activities):
                rec['suggested_day'] = day + 1
                rec['day_order'] = i + 1
                organized_recommendations.append(rec)
        
        return organized_recommendations
    
    def _load_activity_database(self) -> List[Activity]:
        """Carga base de datos de actividades disponibles"""
        # Aquí cargarías desde una base de datos real
        # Por ahora retorno dataset simulado
        return self._generate_sample_activities()
    
    def _load_user_patterns(self) -> Dict:
        """Carga patrones de comportamiento de usuarios similares"""
        # Aquí cargarías datos históricos de usuarios
        return {
            'collaborative_data': {},
            'popular_combinations': [],
            'seasonal_preferences': {}
        }
    
    def _get_category_based_candidates(self, user_profile: UserProfile, user_location: Dict) -> List[Activity]:
        """Obtiene candidatos basados en categorías preferidas"""
        candidates = []
        
        for category in user_profile.preferred_categories.keys():
            category_activities = [
                act for act in self.activity_database 
                if act.category == category
            ]
            # Ordena por proximidad y rating
            category_activities.sort(
                key=lambda x: calculate_distance(
                    user_location['latitude'], user_location['longitude'],
                    x.coordinates.latitude, x.coordinates.longitude
                )
            )
            candidates.extend(category_activities[:3])  # Top 3 por categoría
        
        return candidates
    
    def _get_collaborative_candidates(self, user_profile: UserProfile, user_location: Dict) -> List[Activity]:
        """Candidatos de filtrado colaborativo"""
        # Implementación simplificada - en producción usarías ML más avanzado
        candidates = []
        
        # Simula "usuarios que visitaron X también visitaron Y"
        popular_combinations = [
            {'if_visited': 'museum', 'then_recommend': 'art_gallery'},
            {'if_visited': 'restaurant', 'then_recommend': 'local_market'},
            {'if_visited': 'park', 'then_recommend': 'viewpoint'}
        ]
        
        for combo in popular_combinations:
            if combo['if_visited'] in user_profile.preferred_categories:
                similar_activities = [
                    act for act in self.activity_database
                    if combo['then_recommend'] in act.category.lower()
                ]
                candidates.extend(similar_activities[:2])
        
        return candidates
    
    def _get_geographic_candidates(self, user_profile: UserProfile, user_location: Dict) -> List[Activity]:
        """Candidatos basados en optimización geográfica"""
        candidates = []
        
        # Hidden gems dentro del radio de exploración
        nearby_activities = [
            act for act in self.activity_database
            if calculate_distance(
                user_location['latitude'], user_location['longitude'],
                act.coordinates.latitude, act.coordinates.longitude
            ) <= user_profile.exploration_radius
        ]
        
        # Filtra por actividades menos conocidas pero bien puntuadas
        hidden_gems = [
            act for act in nearby_activities
            if hasattr(act, 'rating') and act.rating and act.rating > 4.0
        ]
        
        candidates.extend(hidden_gems[:3])
        
        return candidates
    
    def _get_novelty_candidates(self, user_profile: UserProfile, user_location: Dict) -> List[Activity]:
        """Candidatos que ofrecen experiencias nuevas"""
        candidates = []
        
        # Actividades únicas o especiales
        unique_categories = {'unique_experience', 'local_tradition', 'off_the_beaten_path'}
        
        unique_activities = [
            act for act in self.activity_database
            if any(cat in act.category.lower() for cat in unique_categories)
        ]
        
        candidates.extend(unique_activities[:2])
        
        return candidates
    
    def _generate_sample_activities(self) -> List[Activity]:
        """Genera dataset de muestra para testing"""
        from models.schemas import Coordinates
        
        sample_data = [
            {
                "name": "Mirador Sky Costanera",
                "coordinates": {"latitude": -33.4167, "longitude": -70.6067},
                "category": "viewpoint",
                "estimated_duration": 1.5,
                "rating": 4.5
            },
            {
                "name": "Barrio Bellavista",
                "coordinates": {"latitude": -33.4262, "longitude": -70.6344},
                "category": "culture",
                "estimated_duration": 3.0,
                "rating": 4.3
            },
            {
                "name": "Mercado Central",
                "coordinates": {"latitude": -33.4369, "longitude": -70.6506},
                "category": "restaurant",
                "estimated_duration": 2.0,
                "rating": 4.2
            },
            {
                "name": "Parque Bicentenario",
                "coordinates": {"latitude": -33.4039, "longitude": -70.5897},
                "category": "park",
                "estimated_duration": 2.5,
                "rating": 4.4
            },
            {
                "name": "Galería Arte Contemporáneo",
                "coordinates": {"latitude": -33.4372, "longitude": -70.6506},
                "category": "art_gallery",
                "estimated_duration": 1.5,
                "rating": 4.6
            }
        ]
        
        activities = []
        for data in sample_data:
            # Crear Activity con todos los campos requeridos
            activity = Activity(
                place=data["name"],                    # Campo requerido
                start="09:00",                        # Campo requerido
                end="11:30",                          # Campo requerido
                duration_h=data["estimated_duration"], # Campo requerido
                lat=data["coordinates"]["latitude"],   # Campo requerido
                lon=data["coordinates"]["longitude"],  # Campo requerido
                type="museum",                        # Campo requerido (PlaceType)
                name=data["name"],                    # Campo opcional
                category=data["category"],            # Campo opcional
                estimated_duration=data["estimated_duration"], # Campo opcional
                priority=8,                           # Campo opcional
                rating=data["rating"],                # Campo opcional (ya está en el schema)
                coordinates=Coordinates(
                    latitude=data["coordinates"]["latitude"],
                    longitude=data["coordinates"]["longitude"]
                )
            )
            activities.append(activity)
        
        return activities
