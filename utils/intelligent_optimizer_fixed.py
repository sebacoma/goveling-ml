import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, time
import json

from utils.google_directions_service import GoogleDirectionsService
from utils.cache import cache_result
from settings import settings

class IntelligentRouteOptimizer:
    """Optimizador de rutas inteligente usando Google Directions API"""
    
    def __init__(self):
        self.cache = {}
        self.google_service = GoogleDirectionsService()
        self.use_google_maps = self.google_service.is_available()
        
    async def optimize_smart_itinerary(self, places, 
                                     start_date: datetime, end_date: datetime,
                                     daily_start_hour: int = 9, daily_end_hour: int = 18,
                                     transport_mode: str = "walking",
                                     user_preferences: Dict = None) -> Dict[str, Any]:
        """
        Optimización inteligente completa del itinerario usando Google Directions API
        """
        logging.info(f"🧠 Iniciando optimización inteligente para {len(places)} lugares")
        logging.info(f"🗺️ Google Directions API: {'✅ Disponible' if self.use_google_maps else '❌ No disponible'}")
        
        # 1. Enriquecer lugares con estimaciones de duración
        enriched_places = self._enrich_places_with_duration_estimates(places)
        
        # 2. Agrupar lugares por días disponibles
        daily_assignments = await self._assign_places_to_days(
            enriched_places, start_date, end_date, 
            daily_start_hour, daily_end_hour
        )
        
        # 3. Optimizar cada día usando Google Maps si está disponible
        optimized_days = []
        for day_assignment in daily_assignments:
            if len(day_assignment['places']) > 1 and self.use_google_maps:
                optimized_day = await self._optimize_single_day_with_google(
                    day_assignment, transport_mode
                )
            else:
                # Fallback simple sin Google Maps
                optimized_day = self._optimize_single_day_basic(day_assignment)
            
            optimized_days.append(optimized_day)
        
        # 4. Generar métricas del itinerario
        metrics = self._calculate_optimization_metrics(optimized_days)
        
        # 5. Formatear resultado final
        result = {
            "days": optimized_days,
            "optimization_metrics": metrics,
            "google_enhanced": self.use_google_maps,
            "efficiency_score": metrics.get('efficiency_score', 0.7)
        }
        
        logging.info(f"✅ Optimización completada. Score: {metrics.get('efficiency_score', 0.7):.2f}")
        return result
    
    def _enrich_places_with_duration_estimates(self, places) -> List[Dict]:
        """Enriquecer lugares con estimaciones de duración usando ML y datos base"""
        enriched = []
        
        # Estimaciones base por tipo de lugar
        duration_estimates = {
            'restaurant': 1.5,
            'museum': 2.0,
            'park': 1.5,
            'cafe': 0.75,
            'shopping_mall': 2.0,
            'church': 0.75,
            'monument': 0.5,
            'beach': 2.5,
            'viewpoint': 1.0,
            'zoo': 3.0
        }
        
        for place in places:
            # Convertir lugar Pydantic a diccionario si es necesario
            if hasattr(place, 'dict'):
                place_dict = place.dict()
            else:
                place_dict = place
                
            place_type = place_dict.get('type', 'poi')
            estimated_duration = duration_estimates.get(place_type, 1.5)
            
            enhanced_place = {
                **place_dict,
                'estimated_duration': estimated_duration,
                'rating': place_dict.get('priority', 5) * 0.8,  # Convertir prioridad a rating
                'google_enhanced': False
            }
            
            enriched.append(enhanced_place)
            logging.info(f"📍 {place_dict['name']} → Duración estimada: {estimated_duration}h")
        
        return enriched
    
    async def _assign_places_to_days(self, places: List[Dict], 
                                    start_date: datetime, end_date: datetime,
                                    daily_start_hour: int, daily_end_hour: int) -> List[Dict]:
        """Asignar lugares a días específicos"""
        daily_hours_available = daily_end_hour - daily_start_hour
        days = []
        
        # Ordenar lugares por rating (prioridad)
        remaining_places = sorted(places, key=lambda x: -x.get('rating', 5))
        
        # Asignar lugares día por día
        current_date = start_date
        while current_date <= end_date and remaining_places:
            daily_places = []
            daily_time_used = 0
            
            for place in remaining_places[:]:
                place_duration = place.get('estimated_duration', 1.5)
                if daily_time_used + place_duration <= daily_hours_available:
                    daily_places.append(place)
                    daily_time_used += place_duration
                    remaining_places.remove(place)
            
            if daily_places:
                days.append({
                    'date': current_date,
                    'places': daily_places,
                    'total_duration': daily_time_used,
                    'available_hours': daily_hours_available
                })
            
            current_date += timedelta(days=1)
        
        # Manejar lugares no asignados
        unassigned = remaining_places
        if unassigned:
            logging.warning(f"⚠️ {len(unassigned)} lugares no pudieron ser asignados")
        
        return days
    
    async def _optimize_single_day_with_google(self, day_assignment: Dict, 
                                             transport_mode: str = "walking") -> Dict:
        """Optimizar un día usando Google Directions API"""
        places = day_assignment['places']
        if len(places) <= 1:
            return self._optimize_single_day_basic(day_assignment)
        
        try:
            # Obtener orden óptimo usando Google Directions
            optimized_order = await self.google_service.get_optimized_route_order(
                [(p['lat'], p['lon']) for p in places],
                transport_mode=transport_mode
            )
            
            # Reordenar lugares según optimización
            if optimized_order:
                reordered_places = [places[i] for i in optimized_order]
                places = reordered_places
                logging.info(f"🚗 Ruta optimizada con Google para {len(places)} lugares")
            
            # Calcular información de viaje entre lugares
            optimized_route = await self._calculate_detailed_route_info(places, transport_mode)
            
            return {
                'date': day_assignment['date'].strftime('%Y-%m-%d'),
                'activities': optimized_route['activities'],
                'travel_summary': optimized_route['travel_summary'],
                'total_duration': optimized_route['total_duration'],
                'recommendations': optimized_route.get('recommendations', [])
            }
            
        except Exception as e:
            logging.error(f"❌ Error en optimización Google: {e}")
            return self._optimize_single_day_basic(day_assignment)
    
    def _optimize_single_day_basic(self, day_assignment: Dict) -> Dict:
        """Optimización básica sin Google Maps"""
        places = day_assignment['places']
        
        # Ordenar por rating/prioridad
        sorted_places = sorted(places, key=lambda x: -x.get('rating', 5))
        
        activities = []
        current_time = 9.0  # Hora de inicio por defecto
        
        for place in sorted_places:
            duration = place.get('estimated_duration', 1.5)
            
            activities.append({
                'name': place['name'],
                'lat': place['lat'],
                'lon': place['lon'],
                'start_time': f"{int(current_time)}:{int((current_time % 1) * 60):02d}",
                'duration_hours': duration,
                'end_time': f"{int(current_time + duration)}:{int(((current_time + duration) % 1) * 60):02d}",
                'type': place.get('type', 'poi'),
                'rating': place.get('rating', 4.0)
            })
            
            current_time += duration + 0.5  # 30 min buffer entre actividades
        
        return {
            'date': day_assignment['date'].strftime('%Y-%m-%d'),
            'activities': activities,
            'travel_summary': {
                'total_travel_time_min': len(activities) * 15,  # Estimación básica
                'total_distance_km': len(activities) * 2  # Estimación básica
            },
            'total_duration': sum([a['duration_hours'] for a in activities]),
            'recommendations': []
        }
    
    async def _calculate_detailed_route_info(self, places: List[Dict], 
                                           transport_mode: str) -> Dict:
        """Calcular información detallada de ruta usando Google Directions"""
        activities = []
        current_time = 9.0
        total_distance = 0
        total_travel_time = 0
        
        for i, place in enumerate(places):
            duration = place.get('estimated_duration', 1.5)
            
            # Calcular tiempo de viaje al siguiente lugar
            travel_time = 0
            if i < len(places) - 1:
                try:
                    next_place = places[i + 1]
                    route_info = await self.google_service.get_route_info(
                        (place['lat'], place['lon']),
                        (next_place['lat'], next_place['lon']),
                        transport_mode
                    )
                    if route_info:
                        travel_time = route_info.get('duration_minutes', 0) / 60.0  # Convertir a horas
                        total_distance += route_info.get('distance_km', 0)
                        total_travel_time += route_info.get('duration_minutes', 0)
                except Exception as e:
                    logging.error(f"Error calculando ruta: {e}")
                    travel_time = 0.25  # 15 min default
            
            activities.append({
                'name': place['name'],
                'lat': place['lat'],
                'lon': place['lon'],
                'start_time': f"{int(current_time)}:{int((current_time % 1) * 60):02d}",
                'duration_hours': duration,
                'end_time': f"{int(current_time + duration)}:{int(((current_time + duration) % 1) * 60):02d}",
                'travel_to_next_minutes': int(travel_time * 60) if travel_time > 0 else 0,
                'type': place.get('type', 'poi'),
                'rating': place.get('rating', 4.0),
                'google_enhanced': True
            })
            
            current_time += duration + travel_time
        
        return {
            'activities': activities,
            'travel_summary': {
                'total_travel_time_min': total_travel_time,
                'total_distance_km': round(total_distance, 2)
            },
            'total_duration': sum([a['duration_hours'] for a in activities]),
            'recommendations': [
                f"Tiempo total de viaje: {int(total_travel_time)} minutos",
                f"Distancia total: {round(total_distance, 1)} km"
            ]
        }
    
    def _calculate_optimization_metrics(self, days: List[Dict]) -> Dict[str, Any]:
        """Calcular métricas de optimización del itinerario"""
        total_activities = sum([len(day.get('activities', [])) for day in days])
        total_travel_time = sum([
            day.get('travel_summary', {}).get('total_travel_time_min', 0) 
            for day in days
        ]) / 60.0  # Convertir a horas
        
        total_distance = sum([
            day.get('travel_summary', {}).get('total_distance_km', 0) 
            for day in days
        ])
        
        # Calcular score de eficiencia
        if total_activities > 0:
            avg_travel_time_per_activity = total_travel_time / total_activities
            # Score más alto = menos tiempo de viaje por actividad
            efficiency_score = max(0, min(1, 1 - (avg_travel_time_per_activity / 2)))
        else:
            efficiency_score = 0
        
        return {
            'total_activities': total_activities,
            'total_days': len(days),
            'total_travel_time_hours': round(total_travel_time, 2),
            'total_distance_km': round(total_distance, 2),
            'efficiency_score': round(efficiency_score, 2),
            'avg_activities_per_day': round(total_activities / max(1, len(days)), 1)
        }
    
    def _generate_smart_recommendations(self, days: List[Dict], metrics: Dict) -> List[str]:
        """Generar recomendaciones inteligentes basadas en el itinerario"""
        recommendations = []
        
        efficiency_score = metrics.get('efficiency_score', 0)
        total_days = len(days)
        
        if efficiency_score < 0.6:
            recommendations.append("⚡ Considera reorganizar algunas actividades para reducir tiempos de viaje")
        
        if total_days > 3:
            avg_distance_per_day = metrics.get('total_distance_km', 0) / max(1, total_days)
            if avg_distance_per_day > 15:
                recommendations.append("🚗 Días con mucha distancia - considera transporte más rápido")
        
        if metrics.get('avg_activities_per_day', 0) > 6:
            recommendations.append("⏰ Itinerario intenso - asegúrate de incluir descansos")
        
        return recommendations
