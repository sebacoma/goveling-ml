import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta

from utils.geo_utils import haversine_km, estimate_travel_minutes, total_route_distance
from settings import settings

class AdvancedRouteOptimizer:
    """Optimizador avanzado de rutas con múltiples algoritmos"""
    
    def __init__(self):
        self.cache = {}
    
    async def optimize_day_route(self, activities: List[Dict], start_point: Dict,
                                transport_mode: str = "walk", 
                                daily_start_hour: int = 9,
                                daily_end_hour: int = 18) -> List[Dict]:
        """Optimizar ruta de un día con múltiples estrategias"""
        
        logging.info(f"🚀 Optimizando ruta con {len(activities)} actividades")
        
        if not activities:
            logging.warning("⚠️ No hay actividades para optimizar")
            return []
        
        if len(activities) == 1:
            logging.info("📍 Una sola actividad, usando programación simple")
            result = self._schedule_single_activity(
                activities[0], daily_start_hour, daily_end_hour
            )
            logging.info(f"✅ Actividad programada: {result[0].get('name', 'Sin nombre')}")
            return result
        
        # Probar diferentes algoritmos
        strategies = [
            ("nearest_neighbor", self._nearest_neighbor_route),
            ("geographic_clustering", self._geographic_clustering_route),
            ("time_efficient", self._time_efficient_route)
        ]
        
        best_route = None
        best_score = float('inf')
        
        for strategy_name, strategy in strategies:
            try:
                logging.info(f"🧮 Probando estrategia: {strategy_name}")
                route = await strategy(
                    activities, start_point, transport_mode,
                    daily_start_hour, daily_end_hour
                )
                
                if route:
                    score = self._evaluate_route(route, start_point, transport_mode)
                    logging.info(f"📊 Estrategia {strategy_name}: score={score:.2f}, actividades={len(route)}")
                    
                    if score < best_score:
                        best_score = score
                        best_route = route
                        logging.info(f"🏆 Nueva mejor ruta con {strategy_name}")
                else:
                    logging.warning(f"⚠️ Estrategia {strategy_name} devolvió lista vacía")
                    
            except Exception as e:
                logging.error(f"❌ Error en estrategia {strategy_name}: {e}")
                continue
        
        # Fallback a orden original si falla todo
        if best_route is None or len(best_route) == 0:
            logging.warning("🔄 Todas las estrategias fallaron, usando fallback secuencial")
            best_route = self._schedule_activities_sequentially(
                activities, daily_start_hour, daily_end_hour, 
                start_point, transport_mode
            )
        
        logging.info(f"✅ Ruta final optimizada: {len(best_route)} actividades")
        return best_route
        
        return best_route
    
    async def _nearest_neighbor_route(self, activities: List[Dict], start_point: Dict,
                                    transport_mode: str, daily_start_hour: int,
                                    daily_end_hour: int) -> List[Dict]:
        """Algoritmo del vecino más cercano mejorado"""
        remaining = activities.copy()
        route = []
        current_pos = start_point
        current_time = daily_start_hour
        
        while remaining and current_time < daily_end_hour:
            # Encontrar actividad más cercana que quepa en el tiempo restante
            best_activity = None
            best_distance = float('inf')
            
            for activity in remaining:
                distance = haversine_km(
                    current_pos["lat"], current_pos["lon"],
                    activity["lat"], activity["lon"]
                )
                
                travel_time = estimate_travel_minutes(
                    current_pos["lat"], current_pos["lon"],
                    activity["lat"], activity["lon"], transport_mode
                ) / 60.0
                
                activity_duration = activity.get('predicted_duration_h', 1.5)
                
                # Verificar si cabe en el tiempo restante
                if current_time + travel_time + activity_duration <= daily_end_hour:
                    if distance < best_distance:
                        best_distance = distance
                        best_activity = activity
            
            if best_activity is None:
                break
            
            # Programar actividad
            travel_time = estimate_travel_minutes(
                current_pos["lat"], current_pos["lon"],
                best_activity["lat"], best_activity["lon"], transport_mode
            ) / 60.0
            
            current_time += travel_time
            start_time = self._format_time(current_time)
            duration = best_activity.get('predicted_duration_h', 1.5)
            end_time = self._format_time(current_time + duration)
            
            scheduled_activity = {
                **best_activity,
                'start': start_time,
                'end': end_time,
                'duration_h': duration
            }
            
            route.append(scheduled_activity)
            remaining.remove(best_activity)
            current_pos = best_activity
            current_time += duration
        
        return route
    
    async def _geographic_clustering_route(self, activities: List[Dict], start_point: Dict,
                                         transport_mode: str, daily_start_hour: int,
                                         daily_end_hour: int) -> List[Dict]:
        """Clustering geográfico para minimizar distancias"""
        from sklearn.cluster import KMeans
        import numpy as np
        
        if len(activities) < 3:
            return await self._nearest_neighbor_route(
                activities, start_point, transport_mode, 
                daily_start_hour, daily_end_hour
            )
        
        # Extraer coordenadas
        coords = np.array([[act["lat"], act["lon"]] for act in activities])
        
        # Clustering (máximo 3 clusters para un día)
        n_clusters = min(3, len(activities))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(coords)
        
        # Organizar por clusters
        clustered_activities = {}
        for i, activity in enumerate(activities):
            cluster_id = clusters[i]
            if cluster_id not in clustered_activities:
                clustered_activities[cluster_id] = []
            clustered_activities[cluster_id].append(activity)
        
        # Ordenar clusters por distancia al punto de inicio
        cluster_distances = []
        for cluster_id, cluster_activities in clustered_activities.items():
            center_lat = np.mean([act["lat"] for act in cluster_activities])
            center_lon = np.mean([act["lon"] for act in cluster_activities])
            distance = haversine_km(start_point["lat"], start_point["lon"], 
                                  center_lat, center_lon)
            cluster_distances.append((distance, cluster_id, cluster_activities))
        
        cluster_distances.sort()
        
        # Programar actividades por cluster
        route = []
        current_time = daily_start_hour
        current_pos = start_point
        
        for _, cluster_id, cluster_activities in cluster_distances:
            if current_time >= daily_end_hour:
                break
                
            # Optimizar dentro del cluster
            cluster_route = await self._optimize_cluster_internally(
                cluster_activities, current_pos, current_time, 
                daily_end_hour, transport_mode
            )
            
            route.extend(cluster_route)
            
            if cluster_route:
                last_activity = cluster_route[-1]
                current_pos = last_activity
                current_time = self._parse_time(last_activity['end'])
        
        return route
    
    async def _time_efficient_route(self, activities: List[Dict], start_point: Dict,
                                  transport_mode: str, daily_start_hour: int,
                                  daily_end_hour: int) -> List[Dict]:
        """Ruta optimizada por eficiencia temporal"""
        # Ordenar por duración (actividades cortas primero)
        sorted_activities = sorted(activities, 
                                 key=lambda x: x.get('predicted_duration_h', 1.5))
        
        return await self._nearest_neighbor_route(
            sorted_activities, start_point, transport_mode,
            daily_start_hour, daily_end_hour
        )
    
    async def _optimize_cluster_internally(self, activities: List[Dict], 
                                         start_pos: Dict, start_time: float,
                                         end_time: float, transport_mode: str) -> List[Dict]:
        """Optimizar ruta dentro de un cluster"""
        remaining = activities.copy()
        route = []
        current_pos = start_pos
        current_time = start_time
        
        while remaining and current_time < end_time:
            # Encontrar actividad más cercana
            nearest = min(remaining, key=lambda x: haversine_km(
                current_pos["lat"], current_pos["lon"], x["lat"], x["lon"]
            ))
            
            travel_time = estimate_travel_minutes(
                current_pos["lat"], current_pos["lon"],
                nearest["lat"], nearest["lon"], transport_mode
            ) / 60.0
            
            duration = nearest.get('predicted_duration_h', 1.5)
            
            # Verificar si cabe
            if current_time + travel_time + duration > end_time:
                break
            
            current_time += travel_time
            
            scheduled = {
                **nearest,
                'start': self._format_time(current_time),
                'end': self._format_time(current_time + duration),
                'duration_h': duration
            }
            
            route.append(scheduled)
            remaining.remove(nearest)
            current_pos = nearest
            current_time += duration
        
        return route
    
    def _evaluate_route(self, route: List[Dict], start_point: Dict, 
                       transport_mode: str) -> float:
        """Evaluar calidad de una ruta (menor es mejor)"""
        if not route:
            return float('inf')
        
        score = 0.0
        
        # Penalizar distancia total
        total_distance = total_route_distance([start_point] + route)
        score += total_distance * 10  # Factor de peso
        
        # Penalizar tiempo muerto (gaps grandes entre actividades)
        for i in range(len(route) - 1):
            end_time = self._parse_time(route[i]['end'])
            start_time = self._parse_time(route[i + 1]['start'])
            gap = start_time - end_time
            if gap > 0.5:  # Gap mayor a 30 min
                score += gap * 20
        
        # Bonificar utilización del tiempo
        if route:
            start_time = self._parse_time(route[0]['start'])
            end_time = self._parse_time(route[-1]['end'])
            time_utilization = (end_time - start_time) / 9.0  # 9 horas típicas
            score -= time_utilization * 5  # Bonificación
        
        return score
    
    def _schedule_activities_sequentially(self, activities: List[Dict], 
                                        daily_start_hour: int, daily_end_hour: int,
                                        start_point: Dict, transport_mode: str) -> List[Dict]:
        """Programar actividades en orden secuencial (fallback)"""
        route = []
        current_time = daily_start_hour
        current_pos = start_point
        
        for activity in activities:
            if current_time >= daily_end_hour:
                break
            
            travel_time = estimate_travel_minutes(
                current_pos["lat"], current_pos["lon"],
                activity["lat"], activity["lon"], transport_mode
            ) / 60.0
            
            current_time += travel_time
            duration = activity.get('predicted_duration_h', 1.5)
            
            if current_time + duration > daily_end_hour:
                break
            
            scheduled = {
                **activity,
                'start': self._format_time(current_time),
                'end': self._format_time(current_time + duration),
                'duration_h': duration
            }
            
            route.append(scheduled)
            current_pos = activity
            current_time += duration
        
        return route
    
    def _schedule_activities_sequentially(self, activities: List[Dict], 
                                         daily_start_hour: int, daily_end_hour: int,
                                         start_point: Dict, transport_mode: str) -> List[Dict]:
        """Fallback: programar actividades secuencialmente sin optimización"""
        scheduled_activities = []
        current_time = daily_start_hour + 0.5  # Empezar media hora después
        current_pos = start_point
        
        for activity in activities:
            duration = activity.get('duration_h', activity.get('predicted_duration_h', 1.5))
            
            # Calcular tiempo de viaje si no es la primera actividad
            travel_time_hours = 0
            if scheduled_activities:
                travel_time_min = estimate_travel_minutes(
                    current_pos['lat'], current_pos['lon'],
                    activity['lat'], activity['lon'], 
                    transport_mode
                )
                travel_time_hours = min(travel_time_min / 60.0, 4.0)  # Máximo 4 horas de viaje
                current_time += travel_time_hours
            
            # Verificar si cabe en el horario (con tiempo de viaje)
            if current_time + duration <= daily_end_hour:
                # Programar actividad
                scheduled = {
                    **activity,
                    'start': self._format_time(current_time),
                    'end': self._format_time(current_time + duration),
                    'duration_h': duration,
                    'travel_time_to_next': travel_time_hours
                }
                
                scheduled_activities.append(scheduled)
                current_time += duration
                current_pos = activity
            else:
                logging.warning(f"⚠️ Actividad {activity.get('name', 'Sin nombre')} no cabe en el horario")
                # Intentar programar para el día siguiente o en modo compacto
                if current_time < daily_end_hour - 0.5:  # Si queda al menos 30min
                    # Programar con duración reducida
                    reduced_duration = min(duration, daily_end_hour - current_time - 0.1)
                    if reduced_duration > 0.5:  # Mínimo 30 minutos
                        scheduled = {
                            **activity,
                            'start': self._format_time(current_time),
                            'end': self._format_time(current_time + reduced_duration),
                            'duration_h': reduced_duration,
                            'travel_time_to_next': travel_time_hours,
                            'note': 'Duración reducida por tiempo'
                        }
                        scheduled_activities.append(scheduled)
        
        logging.info(f"📅 Fallback secuencial: {len(scheduled_activities)} actividades programadas")
        return scheduled_activities

    def _schedule_single_activity(self, activity: Dict, 
                                 daily_start_hour: int, daily_end_hour: int) -> List[Dict]:
        """Programar una sola actividad"""
        duration = activity.get('predicted_duration_h', 1.5)
        start_time = daily_start_hour + 1  # 1 hora después del inicio
        
        if start_time + duration > daily_end_hour:
            start_time = daily_start_hour
        
        return [{
            **activity,
            'start': self._format_time(start_time),
            'end': self._format_time(start_time + duration),
            'duration_h': duration
        }]
    
    def _format_time(self, hour_float: float) -> str:
        """Formatear hora como HH:MM"""
        hour = int(hour_float)
        minute = int((hour_float - hour) * 60)
        return f"{hour:02d}:{minute:02d}"
    
    def _parse_time(self, time_str: str) -> float:
        """Parsear tiempo HH:MM a float"""
        try:
            hour, minute = map(int, time_str.split(':'))
            return hour + minute / 60.0
        except:
            return 0.0
