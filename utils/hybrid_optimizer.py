import math
import asyncio
import logging
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import numpy as np
from sklearn.cluster import DBSCAN

from utils.google_directions_service import GoogleDirectionsService
from utils.google_maps_client import GoogleMapsClient
from settings import settings

@dataclass
class TimeWindow:
    start: int  # hora en minutos desde medianoche (9:00 = 540)
    end: int    # hora en minutos desde medianoche (18:00 = 1080)

@dataclass
class OptimizedActivity:
    name: str
    lat: float
    lon: float
    type: str
    duration_minutes: int
    start_time: int  # minutos desde medianoche
    end_time: int
    priority: int
    # Campos opcionales al final
    travel_time_to_next: Optional[int] = None
    zone_cluster: Optional[int] = None
    hotel_name: Optional[str] = None
    hotel_distance_km: Optional[float] = None
    recommended_transport: Optional[str] = None
    opening_hours_info: Optional[str] = None

class HybridIntelligentOptimizer:
    def __init__(self):
        self.google_service = GoogleDirectionsService()
        self.logger = logging.getLogger(__name__)
        
        # Configuraciones
        self.max_daily_activities = 6
        self.buffer_between_activities = 15  # minutos
        self.min_activity_spacing = 90      # mínimo 1.5h entre actividades para mejor distribución
        self.max_walking_distance_km = 2.0   # usar Google API si es mayor
        self.cluster_radius_km = 3.0         # agrupar lugares cercanos
        
    def haversine_km(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calcular distancia usando fórmula de Haversine"""
        R = 6371.0  # Radio de la Tierra en km
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (math.sin(dlat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    async def estimate_travel_time_hybrid(self, lat1: float, lon1: float, 
                                         lat2: float, lon2: float, 
                                         transport_mode: str) -> int:
        """Estimar tiempo de viaje usando método híbrido mejorado con detección de traslados largos"""
        
        # 1. Calcular distancia con Haversine
        distance_km = self.haversine_km(lat1, lon1, lat2, lon2)
        
        # 2. Detectar y manejar traslados largos (inter-ciudades)
        if distance_km > settings.INTERCITY_THRESHOLD_KM:
            self.logger.warning(f"🚗 Traslado interurbano detectado: {distance_km:.1f}km - forzando modo auto/bus")
            # Para traslados largos, siempre usar auto/bus independiente de user preference
            return await self._calculate_long_distance_travel(distance_km, 'drive')
        
        # 3. Para distancias medias (>2km pero <30km), verificar modo de transporte
        if distance_km > settings.WALK_MAX_KM:
            # Prohibir caminar si es >2km
            if transport_mode == 'walk':
                self.logger.info(f"🚫 Distancia {distance_km:.1f}km excede límite para caminar - usando auto")
                transport_mode = 'drive'
        
        # 4. Decidir si usar Google API o fallback
        if distance_km <= self.max_walking_distance_km:
            # Distancias cortas: usar estimación rápida para ahorrar API calls
            return self._estimate_travel_time_fast(distance_km, transport_mode)
        else:
            # Distancias medias: intentar Google API, fallback si falla
            try:
                return await self._estimate_travel_time_google(lat1, lon1, lat2, lon2, transport_mode)
            except Exception as e:
                self.logger.warning(f"Google API falló para {distance_km:.1f}km, usando fallback: {e}")
                return self._estimate_travel_time_fallback(distance_km, transport_mode)
    
    async def _calculate_long_distance_travel(self, distance_km: float, mode: str = 'drive') -> int:
        """Calcular tiempo de viaje para traslados largos con velocidades realistas"""
        
        # Velocidades para traslados largos (carretera)
        if mode == 'drive':
            speed_kmh = settings.DRIVE_KMH  # 50 km/h promedio interurbano
        elif mode == 'transit':
            speed_kmh = settings.TRANSIT_KMH  # 35 km/h promedio bus interurbano
        else:
            speed_kmh = settings.DRIVE_KMH  # Default auto
        
        # Calcular tiempo base
        time_hours = distance_km / speed_kmh
        time_minutes = int(time_hours * 60)
        
        # Añadir buffer para traslados largos (paradas, tráfico, etc.)
        if distance_km > 100:
            time_minutes += 30  # 30min buffer para traslados >100km
        elif distance_km > 50:
            time_minutes += 15  # 15min buffer para traslados >50km
        
        self.logger.info(f"🗺️ Traslado largo: {distance_km:.1f}km → {time_minutes}min ({speed_kmh}km/h + buffer)")
        return time_minutes
    
    def _estimate_travel_time_fallback(self, distance_km: float, mode: str) -> int:
        """Estimación de fallback usando velocidades configurables de settings"""
        speeds = {
            'walk': settings.WALK_KMH,
            'bike': 15.0,  # Velocidad fija para bicicleta
            'drive': settings.DRIVE_KMH,
            'transit': settings.TRANSIT_KMH
        }
        
        speed = speeds.get(mode, settings.WALK_KMH)
        time_hours = distance_km / speed
        time_minutes = int(time_hours * 60)
        
        # Mínimo realista
        time_minutes = max(time_minutes, settings.MIN_TRAVEL_MIN if hasattr(settings, 'MIN_TRAVEL_MIN') else 8)
        
        return time_minutes
    
    def _estimate_travel_time_fast(self, distance_km: float, mode: str) -> int:
        """Estimación rápida basada en velocidades promedio"""
        speeds = {
            'walk': 5.0,     # km/h
            'bike': 15.0,    # km/h  
            'drive': 30.0,   # km/h en ciudad con tráfico
            'transit': 20.0  # km/h promedio transporte público
        }
        
        speed = speeds.get(mode, 5.0)
        time_hours = distance_km / speed
        return int(time_hours * 60)  # convertir a minutos
    
    async def _estimate_travel_time_google(self, lat1: float, lon1: float, 
                                          lat2: float, lon2: float, 
                                          mode: str) -> int:
        """Usar Google Directions API para distancias largas"""
        if not settings.GOOGLE_MAPS_API_KEY:
            raise Exception("Google API key no disponible")
            
        try:
            route_info = await self.google_service.get_route_info(
                (lat1, lon1), (lat2, lon2), mode
            )
            if route_info:
                return route_info.get('duration_minutes', 0)
            else:
                raise Exception("No se pudo obtener información de ruta")
        except Exception as e:
            raise Exception(f"Error Google API: {e}")
    
    def cluster_places_geographically(self, places: List[Dict]) -> Dict[int, List[Dict]]:
        """Agrupar lugares por proximidad geográfica usando DBSCAN para detectar ciudades separadas"""
        
        if len(places) < 2:
            return {0: places}
        
        # Extraer coordenadas para DBSCAN
        coordinates = np.array([[place['lat'], place['lon']] for place in places])
        
        # Configurar DBSCAN con métrica de distancia Haversine
        # eps está en radianes, necesitamos convertir desde km
        earth_radius_km = 6371.0
        eps_radians = settings.CLUSTER_EPS_KM / earth_radius_km
        
        # DBSCAN con métrica Haversine para detectar clusters geográficos
        dbscan = DBSCAN(
            eps=eps_radians, 
            min_samples=settings.CLUSTER_MIN_SAMPLES, 
            metric='haversine'
        )
        
        # Convertir coordenadas a radianes para Haversine
        coordinates_rad = np.radians(coordinates)
        cluster_labels = dbscan.fit_predict(coordinates_rad)
        
        # Organizar lugares por cluster
        clusters = {}
        outliers = []  # Lugares marcados como ruido por DBSCAN (-1)
        
        for i, label in enumerate(cluster_labels):
            place = places[i].copy()
            
            if label == -1:  # Outlier/ruido - lugar muy alejado
                outliers.append(place)
                self.logger.warning(f"🗺️ Outlier detectado: {place['name']} está >={settings.CLUSTER_EPS_KM}km de otros lugares")
            else:
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append(place)
                place['cluster_id'] = label
        
        # Asignar outliers a clusters individuales
        next_cluster_id = max(clusters.keys()) + 1 if clusters else 0
        for outlier in outliers:
            clusters[next_cluster_id] = [outlier]
            outlier['cluster_id'] = next_cluster_id
            next_cluster_id += 1
        
        # Log detallado del clustering
        total_clusters = len(clusters)
        cluster_info = []
        
        for cluster_id, cluster_places in clusters.items():
            if len(cluster_places) == 1:
                place_name = cluster_places[0]['name']
                cluster_info.append(f"Cluster {cluster_id}: {place_name} (aislado)")
            else:
                place_names = [p['name'] for p in cluster_places]
                cluster_info.append(f"Cluster {cluster_id}: {len(cluster_places)} lugares ({', '.join(place_names[:2])}{'...' if len(place_names) > 2 else ''})")
        
        self.logger.info(f"🗺️ Clustering DBSCAN: {len(places)} lugares en {total_clusters} clusters geográficos")
        for info in cluster_info[:5]:  # Mostrar solo los primeros 5 clusters
            self.logger.info(f"  - {info}")
        
        if len(outliers) > 0:
            self.logger.warning(f"⚠️ {len(outliers)} lugar(es) detectado(s) como outlier(s) - posibles traslados interurbanos")
        
        return clusters
    
    def optimize_cluster_order(self, cluster_places: List[Dict], 
                              transport_mode: str) -> List[Dict]:
        """Optimizar orden dentro de un cluster usando nearest neighbor"""
        if len(cluster_places) <= 1:
            return cluster_places
        
        # Empezar con lugar de mayor prioridad
        cluster_places.sort(key=lambda x: x.get('priority', 5), reverse=True)
        optimized = [cluster_places[0]]
        remaining = cluster_places[1:]
        
        # Nearest neighbor algorithm
        while remaining:
            current = optimized[-1]
            
            # Encontrar el lugar más cercano
            nearest = min(remaining, 
                         key=lambda p: self.haversine_km(
                             current['lat'], current['lon'],
                             p['lat'], p['lon']
                         ))
            
            optimized.append(nearest)
            remaining.remove(nearest)
        
        self.logger.info(f"🔄 Optimizado cluster con {len(optimized)} lugares usando nearest neighbor")
        return optimized
    
    async def schedule_activities_multi_day(self, places: List[Dict], 
                                          start_date: datetime,
                                          end_date: datetime,
                                          daily_window: TimeWindow,
                                          transport_mode: str = 'walk') -> Dict[str, List[OptimizedActivity]]:
        """Programar actividades en múltiples días"""
        
        self.logger.info(f"📅 Programando {len(places)} lugares en múltiples días desde {start_date.date()} hasta {end_date.date()}")
        
        # 1. Clustering geográfico
        clusters = self.cluster_places_geographically(places)
        
        # 2. Optimizar orden dentro de cada cluster
        optimized_clusters = {}
        for cluster_id, cluster_places in clusters.items():
            optimized_clusters[cluster_id] = self.optimize_cluster_order(
                cluster_places, transport_mode
            )
        
        # 3. 🚗 ANALIZAR DISTANCIAS ENTRE CLUSTERS ANTES DE ASIGNAR DÍAS
        cluster_distances = self._calculate_cluster_distances(optimized_clusters)
        
        # 4. Distribuir clusters entre días disponibles INTELIGENTEMENTE
        days_available = (end_date - start_date).days + 1
        daily_schedule = {}
        
        current_date = start_date
        for day in range(days_available):
            date_str = current_date.strftime('%Y-%m-%d')
            daily_schedule[date_str] = []
            current_date += timedelta(days=1)
        
        # 5. 🧠 ASIGNAR CLUSTERS A DÍAS EVITANDO TRASLADOS LARGOS
        day_keys = list(daily_schedule.keys())
        unscheduled_places = []
        
        # Estrategia inteligente: Separar clusters distantes en días diferentes
        await self._assign_clusters_to_days_smart(
            optimized_clusters, cluster_distances, daily_schedule, 
            daily_window, transport_mode, unscheduled_places
        )
        
        # 6. Redistribuir lugares que no cupieron
        if unscheduled_places:
            self.logger.info(f"🔄 Redistribuyendo {len(unscheduled_places)} lugares que no cupieron inicialmente")
            await self._redistribute_unscheduled_places(unscheduled_places, daily_schedule, daily_window, transport_mode)
        
        # 7. 🚗 DETECTAR E INSERTAR TRASLADOS LARGOS ENTRE CLUSTERS/DÍAS (verificación final)
        long_transfers = await self._detect_and_insert_long_transfers(daily_schedule, clusters, transport_mode)
        
        # 8. Log resumen
        total_scheduled = sum(len(activities) for activities in daily_schedule.values())
        self.logger.info(f"✅ Programación completada: {total_scheduled} actividades en {days_available} días")
        
        # 9. Guardar información de traslados largos para el formateo
        self.long_transfers_detected = long_transfers
        
        return daily_schedule
    
    async def _schedule_cluster_in_day_with_overflow(self, places: List[Dict], 
                                                   time_window: TimeWindow,
                                                   date: str,
                                                   transport_mode: str) -> Tuple[List[OptimizedActivity], List[Dict]]:
        """Programar un cluster de lugares en un día específico, retornando también los que no cupieron"""
        activities = []
        leftover_places = []
        current_time = time_window.start  # minutos desde medianoche
        
        self.logger.info(f"📍 Programando {len(places)} lugares para {date}")
        
        for i, place in enumerate(places):
            # Estimar duración de la actividad
            duration = self._estimate_activity_duration(place)
            
            # Validar y ajustar horario apropiado para el tipo de lugar
            appropriate_start = self._get_appropriate_start_time(place, current_time)
            
            # Si el horario apropiado es diferente, ajustar
            if appropriate_start != current_time:
                current_time = appropriate_start
            
            # Validar horarios de apertura usando Google Places API
            is_open, verified_time, hours_info = await self._validate_opening_hours(place, current_time, date)
            
            if not is_open:
                self.logger.warning(f"⚠️ {place['name']} estará cerrado, saltando...")
                continue
            
            if verified_time != current_time:
                current_time = verified_time
                self.logger.info(f"🕒 {place['name']}: horario ajustado según apertura real")
            
            # Verificar si cabe en el día
            activity_end = current_time + duration
            if activity_end > time_window.end:
                self.logger.warning(f"⚠️ Lugar {place['name']} no cabe en {date} (requiere hasta {int(activity_end)//60}:{int(activity_end)%60:02d})")
                # En lugar de break, añadir los lugares restantes a leftover_places
                leftover_places.extend(places[i:])
                break
            
            # Calcular tiempo de viaje al siguiente lugar y recomendación de transporte ANTES de crear la actividad
            travel_time = 0
            recommended_transport = '🚶 Caminar'  # Default mejorado
            
            if i < len(places) - 1:
                next_place = places[i + 1]
                
                # Calcular distancia y tiempo de viaje
                distance_km = self.haversine_km(
                    place['lat'], place['lon'],
                    next_place['lat'], next_place['lon']
                )
                
                travel_time = await self.estimate_travel_time_hybrid(
                    place['lat'], place['lon'],
                    next_place['lat'], next_place['lon'],
                    transport_mode
                )
                
                # Recomendar modo de transporte basado en distancia y tiempo
                recommended_transport = self.recommend_transport_mode(
                    distance_km, travel_time, [transport_mode, 'walk', 'drive', 'transit']
                )
            
            # Crear actividad CON el transporte ya asignado
            activity = OptimizedActivity(
                name=place['name'],
                lat=place['lat'],
                lon=place['lon'],
                type=place['type'],
                duration_minutes=duration,
                start_time=current_time,
                end_time=activity_end,
                priority=place.get('priority', 5),
                zone_cluster=place.get('cluster_id'),
                opening_hours_info=hours_info,  # Información de horarios verificados
                recommended_transport=recommended_transport  # Asignar desde la creación
            )
            
            # Asignar tiempo de viaje y calcular mejor espaciado
            if travel_time > 0:
                activity.travel_time_to_next = int(travel_time)
                # Calcular espaciado dinámico basado en tiempo disponible
                available_time = (time_window.end * 60) - current_time
                remaining_activities = len(places) - (places.index(place) + 1)
                
                if remaining_activities > 0 and available_time > (remaining_activities * 120):  # Si hay mucho tiempo libre
                    # Usar espaciado más generoso para mejor distribución
                    dynamic_spacing = min(self.min_activity_spacing, available_time // (remaining_activities + 1))
                    current_time = activity_end + travel_time + max(self.buffer_between_activities, dynamic_spacing)
                    self.logger.info(f"  🕒 Espaciado dinámico aplicado: {dynamic_spacing}min")
                else:
                    current_time = activity_end + travel_time + self.buffer_between_activities
            else:
                current_time = activity_end
            
            activities.append(activity)
            
            # Log actividad programada
            start_str = f"{int(activity.start_time)//60}:{int(activity.start_time)%60:02d}"
            end_str = f"{int(activity_end)//60}:{int(activity_end)%60:02d}"
            travel_str = f" (viaje: {travel_time}min)" if travel_time > 0 else ""
            self.logger.info(f"  ✓ {place['name']}: {start_str}-{end_str} ({duration}min){travel_str}")
        
        return activities, leftover_places
    
    async def _redistribute_unscheduled_places(self, unscheduled_places: List[Dict], 
                                              daily_schedule: Dict[str, List], 
                                              daily_window: TimeWindow,
                                              transport_mode: str):
        """Intentar redistribuir lugares que no cupieron en su día inicial CON VALIDACIÓN DE DISTANCIAS"""
        self.logger.info(f"🔄 Redistribuyendo {len(unscheduled_places)} lugares no programados")
        
        for place in unscheduled_places:
            scheduled = False
            
            # Ordenar días por cantidad de actividades (priorizar días con menos actividades)
            days_by_activity_count = sorted(daily_schedule.items(), 
                                          key=lambda x: len(x[1]))
            
            for date, existing_activities in days_by_activity_count:
                if scheduled:
                    break
                
                # 🚗 VALIDACIÓN DE DISTANCIA: Verificar si este lugar puede estar en este día
                if existing_activities:
                    day_compatible = True
                    
                    for existing_activity in existing_activities:
                        # Calcular distancia entre el lugar a redistribuir y las actividades existentes
                        distance_km = self.haversine_km(
                            place['lat'], place['lon'],
                            existing_activity.lat, existing_activity.lon
                        )
                        
                        # Si la distancia excede el umbral interurbano, NO redistribuir aquí
                        if distance_km > settings.INTERCITY_THRESHOLD_KM:
                            self.logger.warning(
                                f"⚠️ {place['name']} NO puede ir en {date}: "
                                f"distancia con {existing_activity.name} = {distance_km:.1f}km "
                                f"(>{settings.INTERCITY_THRESHOLD_KM}km)"
                            )
                            day_compatible = False
                            break
                    
                    # Si hay conflicto de distancia, saltar este día
                    if not day_compatible:
                        continue
                
                # Validación de tiempo (lógica original)
                total_used_time = 0
                if existing_activities:
                    for activity in existing_activities:
                        total_used_time += activity.duration_minutes
                        total_used_time += activity.travel_time_to_next or 0
                
                # Estimar duración del nuevo lugar
                new_duration = self._estimate_activity_duration(place)
                available_time = (daily_window.end - daily_window.start) - total_used_time
                
                # Si hay suficiente tiempo Y es compatible por distancia, añadir al día
                if available_time >= new_duration + 30:  # 30 min buffer
                    try:
                        # Intentar programar el lugar individual
                        new_activities, _ = await self._schedule_cluster_in_day_with_overflow(
                            [place], daily_window, date, transport_mode
                        )
                        
                        if new_activities:
                            daily_schedule[date].extend(new_activities)
                            scheduled = True
                            self.logger.info(f"✅ {place['name']} redistribuido al {date} (compatible por distancia)")
                        
                    except Exception as e:
                        self.logger.warning(f"⚠️ Error redistribuyendo {place['name']}: {e}")
                        continue
            
            if not scheduled:
                self.logger.warning(f"⚠️ No se pudo redistribuir {place['name']} (sin días compatibles por distancia/tiempo)")
    
    async def _detect_and_insert_long_transfers(self, daily_schedule: Dict[str, List], 
                                               clusters: Dict[int, List[Dict]], 
                                               transport_mode: str):
        """
        🚗 Detectar y documentar traslados largos entre clusters en días consecutivos
        """
        days = sorted(daily_schedule.keys())
        transfer_warnings = []
        
        for i in range(len(days) - 1):
            current_day = days[i]
            next_day = days[i + 1]
            
            current_activities = daily_schedule[current_day]
            next_activities = daily_schedule[next_day]
            
            if not current_activities or not next_activities:
                continue
            
            # Obtener última actividad del día actual y primera del siguiente
            last_activity = current_activities[-1]
            first_next_activity = next_activities[0]
            
            # Calcular distancia entre el último lugar del día y el primero del siguiente
            distance_km = self.haversine_km(
                last_activity.lat, last_activity.lon,
                first_next_activity.lat, first_next_activity.lon
            )
            
            # Detectar traslado largo
            if distance_km > settings.INTERCITY_THRESHOLD_KM:
                travel_time_min = await self._calculate_long_distance_travel(distance_km, 'drive')
                
                transfer_info = {
                    'from_city': last_activity.name,
                    'to_city': first_next_activity.name,
                    'from_day': current_day,
                    'to_day': next_day,
                    'distance_km': distance_km,
                    'estimated_time_min': travel_time_min,
                    'recommended_transport': '🚗 Auto' if distance_km < 100 else f'🚗 Auto/Bus ({distance_km:.0f}km)'
                }
                
                transfer_warnings.append(transfer_info)
                
                # Log del traslado detectado
                self.logger.warning(
                    f"🗺️ Traslado interurbano detectado: {last_activity.name} → {first_next_activity.name} "
                    f"({distance_km:.1f}km, ~{travel_time_min//60}h{travel_time_min%60:02d}min)"
                )
                
                # Actualizar el travel_time_to_next de la última actividad del día
                # para reflejar el traslado largo al día siguiente
                last_activity.travel_time_to_next = travel_time_min
                last_activity.recommended_transport = transfer_info['recommended_transport']
        
        # Almacenar información de traslados para recommendations
        if transfer_warnings:
            self.long_transfers_detected = transfer_warnings
            self.logger.info(f"🚗 {len(transfer_warnings)} traslado(s) interurbano(s) detectado(s) y documentado(s)")
        else:
            self.long_transfers_detected = []
        
        return transfer_warnings
    
    def _calculate_cluster_distances(self, clusters: Dict[int, List[Dict]]) -> Dict[tuple, float]:
        """
        Calcular distancias entre todos los pares de clusters para detectar traslados largos
        """
        cluster_distances = {}
        cluster_ids = list(clusters.keys())
        
        for i, cluster_a_id in enumerate(cluster_ids):
            for j, cluster_b_id in enumerate(cluster_ids):
                if i >= j:  # Evitar duplicados y auto-comparación
                    continue
                    
                cluster_a = clusters[cluster_a_id]
                cluster_b = clusters[cluster_b_id]
                
                # Calcular centroide de cada cluster
                centroid_a = self._get_cluster_centroid(cluster_a)
                centroid_b = self._get_cluster_centroid(cluster_b)
                
                # Distancia entre centroides
                distance_km = self.haversine_km(
                    centroid_a[0], centroid_a[1],
                    centroid_b[0], centroid_b[1]
                )
                
                cluster_pair = (cluster_a_id, cluster_b_id)
                cluster_distances[cluster_pair] = distance_km
                
                # Log para clusters muy separados
                if distance_km > settings.INTERCITY_THRESHOLD_KM:
                    cluster_a_name = cluster_a[0]['name'] if cluster_a else f"Cluster {cluster_a_id}"
                    cluster_b_name = cluster_b[0]['name'] if cluster_b else f"Cluster {cluster_b_id}"
                    self.logger.warning(
                        f"🗺️ Clusters distantes detectados: {cluster_a_name} ↔ {cluster_b_name} "
                        f"({distance_km:.1f}km) - DEBEN estar en días separados"
                    )
        
        return cluster_distances
    
    def _get_cluster_centroid(self, cluster_places: List[Dict]) -> tuple:
        """Calcular centroide geográfico de un cluster"""
        if not cluster_places:
            return (0, 0)
        
        lat_sum = sum(place['lat'] for place in cluster_places)
        lon_sum = sum(place['lon'] for place in cluster_places)
        count = len(cluster_places)
        
        return (lat_sum / count, lon_sum / count)
    
    async def _assign_clusters_to_days_smart(self, clusters: Dict[int, List[Dict]], 
                                           cluster_distances: Dict[tuple, float],
                                           daily_schedule: Dict[str, List],
                                           daily_window: TimeWindow,
                                           transport_mode: str,
                                           unscheduled_places: List[Dict]):
        """
        Asignar clusters a días de forma inteligente, evitando traslados largos el mismo día
        """
        day_keys = list(daily_schedule.keys())
        cluster_items = list(clusters.items())
        assigned_clusters = {}  # cluster_id -> day_key
        
        self.logger.info(f"🧠 Asignación inteligente de {len(clusters)} clusters en {len(day_keys)} días")
        
        # Paso 1: Identificar clusters que NO pueden estar el mismo día
        forbidden_same_day = set()
        for (cluster_a, cluster_b), distance in cluster_distances.items():
            if distance > settings.INTERCITY_THRESHOLD_KM:
                forbidden_same_day.add((cluster_a, cluster_b))
                forbidden_same_day.add((cluster_b, cluster_a))  # Ambas direcciones
        
        # Paso 2: Asignar clusters uno por uno, respetando restricciones
        for i, (cluster_id, cluster_places) in enumerate(cluster_items):
            
            # Encontrar un día válido para este cluster
            assigned_day = None
            
            for day_idx, day_key in enumerate(day_keys):
                # Verificar si este día ya tiene clusters incompatibles
                day_has_conflicting_cluster = False
                
                for other_cluster_id in assigned_clusters:
                    if assigned_clusters[other_cluster_id] == day_key:
                        # Verificar si hay conflicto de distancia
                        if ((cluster_id, other_cluster_id) in forbidden_same_day or 
                            (other_cluster_id, cluster_id) in forbidden_same_day):
                            day_has_conflicting_cluster = True
                            self.logger.info(
                                f"⚠️ Cluster {cluster_id} NO puede ir en {day_key} "
                                f"(conflicto de distancia con cluster {other_cluster_id})"
                            )
                            break
                
                # Si no hay conflicto, asignar a este día
                if not day_has_conflicting_cluster:
                    assigned_day = day_key
                    break
            
            # Si no encontramos día válido, usar el siguiente disponible (round-robin)
            if assigned_day is None:
                assigned_day = day_keys[i % len(day_keys)]
                self.logger.warning(
                    f"⚠️ Cluster {cluster_id} forzado a {assigned_day} "
                    f"(no hay días sin conflictos disponibles)"
                )
            
            # Asignar cluster al día elegido
            assigned_clusters[cluster_id] = assigned_day
            
            # Programar actividades del cluster en el día
            activities, leftover_places = await self._schedule_cluster_in_day_with_overflow(
                cluster_places, daily_window, assigned_day, transport_mode
            )
            daily_schedule[assigned_day].extend(activities)
            
            # Guardar lugares que no cupieron
            if leftover_places:
                unscheduled_places.extend(leftover_places)
            
            cluster_name = cluster_places[0]['name'] if cluster_places else f"Cluster {cluster_id}"
            self.logger.info(f"📅 {cluster_name} asignado a {assigned_day}")
        
        # Log resumen de asignación
        self.logger.info("📊 Resumen de asignación por días:")
        for day_key, activities in daily_schedule.items():
            if activities:
                activity_names = [a.name for a in activities]
                self.logger.info(f"  {day_key}: {', '.join(activity_names)}")
    
    async def _schedule_cluster_in_day(self, places: List[Dict], 
                                      time_window: TimeWindow,
                                      date: str,
                                      transport_mode: str) -> List[OptimizedActivity]:
        """Wrapper para mantener compatibilidad - solo retorna actividades programadas"""
        activities, _ = await self._schedule_cluster_in_day_with_overflow(
            places, time_window, date, transport_mode
        )
        return activities
    
    def _estimate_activity_duration(self, place: Dict) -> int:
        """Estimar duración de actividad en minutos"""
        # Duraciones base por tipo de lugar
        durations = {
            'museum': 120,        # 2 horas
            'park': 90,           # 1.5 horas
            'restaurant': 90,     # 1.5 horas (incluye comida)
            'church': 45,         # 45 minutos
            'shopping_mall': 120, # 2 horas
            'beach': 180,         # 3 horas
            'viewpoint': 60,      # 1 hora
            'monument': 60,       # 1 hora - INCREMENTADO (era muy poco)
            'cafe': 45,           # 45 minutos
            'zoo': 180            # 3 horas
        }
        
        base_duration = durations.get(place['type'], 90)
        
        # Ajustar por prioridad
        priority = place.get('priority', 5)
        if priority >= 8:
            base_duration = int(base_duration * 1.3)  # +30% para alta prioridad
        elif priority <= 3:
            base_duration = int(base_duration * 0.7)  # -30% para baja prioridad
        
        return base_duration
    
    def _get_appropriate_start_time(self, place: Dict, proposed_time: int) -> int:
        """Validar y ajustar horario apropiado según tipo de lugar"""
        place_type = place['type']
        
        # Convertir PlaceType enum a string si es necesario
        if hasattr(place_type, 'value'):
            place_type = place_type.value
        elif not isinstance(place_type, str):
            place_type = str(place_type).lower()
        
        # Asegurar que proposed_time es entero
        proposed_time = int(proposed_time)
        
        # Horarios apropiados por tipo (en minutos desde medianoche)
        time_rules = {
            'restaurant': {
                'breakfast': (420, 660),    # 7:00-11:00 desayuno
                'lunch': (720, 900),        # 12:00-15:00 almuerzo
                'dinner': (1080, 1320)      # 18:00-22:00 cena
            },
            'cafe': {
                'morning': (420, 720),      # 7:00-12:00 mañana
                'afternoon': (840, 1080)    # 14:00-18:00 tarde
            },
            'museum': (600, 1020),          # 10:00-17:00
            'church': (480, 1200),          # 8:00-20:00
            'shopping_mall': (600, 1320),   # 10:00-22:00
            'park': (360, 1200),            # 6:00-20:00 (flexible)
            'beach': (480, 1080),           # 8:00-18:00
            'viewpoint': (360, 1200),       # 6:00-20:00 (flexible)
            'monument': (480, 1080),        # 8:00-18:00
            'zoo': (540, 1020)              # 9:00-17:00
        }
        
        # Si no hay reglas específicas, usar horario propuesto
        if place_type not in time_rules:
            return proposed_time
        
        rules = time_rules[place_type]
        
        # Para restaurantes, determinar mejor franja horaria
        if place_type == 'restaurant':
            # Lógica mejorada: priorizar almuerzo para horarios entre 9:00-17:00
            if 420 <= proposed_time <= 540:     # Muy temprano (7:00-9:00) -> desayuno
                start, end = rules['breakfast']
            elif 540 <= proposed_time <= 1020:  # Día (9:00-17:00) -> FORZAR ALMUERZO
                start, end = rules['lunch']
                # Si está antes del almuerzo, ajustar al inicio del almuerzo
                if proposed_time < 720:  # antes de 12:00
                    proposed_time = 720  # forzar a 12:00
            elif proposed_time >= 1020:         # Noche (17:00+)
                start, end = rules['dinner']
            else:  # Caso de seguridad
                start, end = rules['lunch']
        
        # Para cafés, elegir franja apropiada
        elif place_type == 'cafe':
            if proposed_time <= 720:
                start, end = rules['morning']
            else:
                start, end = rules['afternoon']
        
        # Para otros lugares, usar rango directo
        else:
            start, end = rules
        
        # Ajustar tiempo propuesto al rango válido
        if proposed_time < start:
            adjusted_time = start
            self.logger.info(f"⏰ {place['name']} ({place_type}): ajustado de {proposed_time//60}:{proposed_time%60:02d} a {adjusted_time//60}:{adjusted_time%60:02d}")
            return adjusted_time
        elif proposed_time > end:
            # Si es muy tarde, programar para el día siguiente en horario válido
            adjusted_time = start
            self.logger.warning(f"⚠️ {place['name']} ({place_type}): muy tarde, programar para horario válido {adjusted_time//60}:{adjusted_time%60:02d}")
            return adjusted_time
        else:
            self.logger.info(f"✅ {place['name']} ({place_type}): horario {proposed_time//60}:{proposed_time%60:02d} es apropiado")
            return proposed_time
    
    def _get_meal_type(self, place_type: str, start_time: int) -> Optional[str]:
        """Determinar tipo de comida según horario"""
        if place_type not in ['restaurant', 'cafe']:
            return None
        
        # Convertir PlaceType enum a string si es necesario
        if hasattr(place_type, 'value'):
            place_type = place_type.value
        elif not isinstance(place_type, str):
            place_type = str(place_type).lower()
        
        start_time = int(start_time)
        
        if place_type == 'restaurant':
            if 420 <= start_time <= 660:    # 7:00-11:00
                return "desayuno"
            elif 720 <= start_time <= 900:  # 12:00-15:00
                return "almuerzo"
            elif 1080 <= start_time <= 1320: # 18:00-22:00
                return "cena"
            else:
                return "comida"
        elif place_type == 'cafe':
            if 420 <= start_time <= 720:    # 7:00-12:00
                return "desayuno/merienda"
            else:
                return "merienda"
        
        return None
    
    async def _validate_opening_hours(self, place: Dict, proposed_time: int, date: str) -> Tuple[bool, int, Optional[str]]:
        """Validar horarios de apertura usando Google Places API"""
        try:
            # Usar Google Places API para obtener horarios reales
            async with GoogleMapsClient() as client:
                place_details = await client.get_place_details(
                    place_name=place['name'],
                    lat=place['lat'],
                    lon=place['lon']
                )
                
                opening_hours = place_details.get('opening_hours', {})
                parsed_hours = opening_hours.get('parsed_hours', {})
                
                # Convertir fecha a día de la semana (0=Lunes, 6=Domingo)
                from datetime import datetime
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                weekday = date_obj.weekday()  # 0=Monday, 6=Sunday
                
                # Verificar si el lugar está abierto ese día
                if weekday not in parsed_hours:
                    self.logger.warning(f"⚠️ {place['name']}: No hay horarios para {date}")
                    return True, proposed_time, "sin horarios específicos"
                
                open_time_str, close_time_str = parsed_hours[weekday]
                
                # Convertir horarios a minutos
                def time_str_to_minutes(time_str: str) -> int:
                    hours, minutes = map(int, time_str.split(':'))
                    return hours * 60 + minutes
                
                open_minutes = time_str_to_minutes(open_time_str)
                close_minutes = time_str_to_minutes(close_time_str)
                
                # Verificar si el horario propuesto está dentro del horario de apertura
                # Ser más flexible: permitir visitar hasta 30 min antes del cierre (en lugar de 1h)
                buffer_minutes = 30
                if open_minutes <= proposed_time <= close_minutes - buffer_minutes:
                    return True, proposed_time, f"abierto {open_time_str}-{close_time_str}"
                
                # Si está cerrado, ajustar al horario de apertura
                if proposed_time < open_minutes:
                    adjusted_time = open_minutes
                    self.logger.info(f"⏰ {place['name']}: ajustado a horario apertura {open_time_str}")
                    return True, adjusted_time, f"ajustado a apertura ({open_time_str})"
                elif proposed_time > close_minutes - buffer_minutes:
                    # Ser más flexible: si es un restaurante o bar, permitir horarios nocturnos
                    place_type = place.get('type', '').lower()
                    if place_type in ['restaurant', 'bar', 'cafe', 'night_club'] and close_minutes > 1200:  # Cierra después de 20:00
                        # Para lugares nocturnos, ajustar a horario de apertura
                        adjusted_time = open_minutes
                        self.logger.info(f"🌙 {place['name']}: lugar nocturno, ajustado a apertura {open_time_str}")
                        return True, adjusted_time, f"lugar nocturno - apertura {open_time_str}"
                    else:
                        # Para otros lugares, ser más flexible y permitir visitas más cerca del cierre
                        if proposed_time <= close_minutes:
                            self.logger.info(f"⏰ {place['name']}: horario ajustado (cierra {close_time_str})")
                            return True, proposed_time, f"visita tardía - cierra {close_time_str}"
                        else:
                            # Solo rechazar si está completamente fuera del horario
                            self.logger.warning(f"⚠️ {place['name']}: cierra a {close_time_str}, muy tarde para visitar")
                            return False, proposed_time, f"cierra {close_time_str}"
                
                return True, proposed_time, f"horario verificado {open_time_str}-{close_time_str}"
                
        except Exception as e:
            self.logger.warning(f"⚠️ Error validando horarios para {place['name']}: {e}")
            # En caso de error, usar validación de horarios por defecto
            return True, proposed_time, "horarios no verificados"
    
    def format_activities_for_api(self, daily_schedule: Dict[str, List[OptimizedActivity]]) -> Dict:
        """Formatear actividades para respuesta API"""
        
        def minutes_to_time_str(minutes: int) -> str:
            """Convertir minutos desde medianoche a formato HH:MM"""
            # Asegurar que minutes es int
            minutes = int(minutes)
            hours = minutes // 60
            mins = minutes % 60
            return f"{hours:02d}:{mins:02d}"
        
        formatted_days = []
        total_activities = 0
        total_travel_time = 0
        total_distance = 0
        
        for date, activities in daily_schedule.items():
            if not activities:  # Saltar días sin actividades
                continue
                
            formatted_activities = []
            day_travel_time = 0
            day_distance = 0
            
            for activity in activities:
                travel_time_next = activity.travel_time_to_next or 0
                day_travel_time += travel_time_next
                
                # Estimar distancia usando Haversine si hay viaje
                if activity.travel_time_to_next and activity.travel_time_to_next > 0:
                    # Estimar distancia basada en tiempo de viaje (aprox)
                    estimated_distance = (travel_time_next / 60) * 5  # 5 km/h velocidad promedio
                    day_distance += estimated_distance
                
                # Determinar tipo de comida si es restaurante/cafe
                meal_type = self._get_meal_type(activity.type, activity.start_time)
                meal_context = f" ({meal_type})" if meal_type else ""
                
                formatted_activities.append({
                    'place': activity.name,
                    'start': minutes_to_time_str(activity.start_time),
                    'end': minutes_to_time_str(activity.end_time),
                    'duration_h': round(activity.duration_minutes / 60, 2),
                    'lat': activity.lat,
                    'lon': activity.lon,
                    'type': activity.type,
                    'travel_time_to_next': travel_time_next,
                    'zone_cluster': activity.zone_cluster,
                    'priority': activity.priority,
                    'confidence_score': 0.9,  # Sistema híbrido tiene alta confianza
                    'meal_type': meal_type,  # Nuevo campo
                    'display_name': f"{activity.name}{meal_context}",  # Nombre con contexto
                    'opening_hours_info': activity.opening_hours_info,  # Horarios verificados
                    'verified_schedule': True if activity.opening_hours_info and 'verificado' in activity.opening_hours_info else False,
                    'recommended_transport': activity.recommended_transport  # ✅ CAMPO FALTANTE AGREGADO
                })
            
            # Calcular tiempo libre del día
            daily_window_minutes = 9 * 60  # 9 horas por día típico (9 AM - 6 PM)
            used_minutes = sum(a.duration_minutes + (a.travel_time_to_next or 0) 
                             for a in activities)
            free_minutes = int(max(0, daily_window_minutes - used_minutes))
            
            # Calcular centroide del día para lodging
            if activities:
                center_lat = sum(a.lat for a in activities) / len(activities)
                center_lon = sum(a.lon for a in activities) / len(activities)
            else:
                center_lat, center_lon = 0, 0
            
            # Añadir contexto de comidas si hay restaurantes/cafés
            restaurants = [a for a in activities if a.type in ['restaurant', 'cafe']]
            recommendations = [
                f"Día optimizado con {len(activities)} actividades",
                f"Tiempo libre: {free_minutes} minutos",
                f"Distancia total: {round(day_distance, 1)}km",
                f"Tiempo de traslados: {int(day_travel_time)}min",
                f"Medios de transporte: {', '.join(set(a.recommended_transport for a in activities if a.recommended_transport))}",
                f"Clusters visitados: {len(set(a.zone_cluster for a in activities if a.zone_cluster is not None))}"
            ]
            
            if restaurants:
                meal_info = []
                for rest in restaurants:
                    meal_type = self._get_meal_type(rest.type, rest.start_time)
                    if meal_type:
                        meal_info.append(f"{rest.name} ({meal_type})")
                if meal_info:
                    recommendations.append(f"Comidas programadas: {', '.join(meal_info)}")
            
            # Añadir información sobre horarios verificados
            verified_count = sum(1 for a in activities if a.opening_hours_info and 'verificado' in str(a.opening_hours_info))
            if verified_count > 0:
                recommendations.append(f"🕒 {verified_count} lugares con horarios verificados por Google")
            
            # Advertencias sobre lugares con horarios ajustados
            adjusted_places = [a for a in activities if a.opening_hours_info and 'ajustado' in str(a.opening_hours_info)]
            if adjusted_places:
                place_names = [a.name for a in adjusted_places]
                recommendations.append(f"⏰ Horarios ajustados: {', '.join(place_names)}")
            
            formatted_days.append({
                    'date': date,
                    'activities': formatted_activities,
                    'lodging': {
                        'name': f'Área central {date}',
                        'lat': center_lat,
                        'lon': center_lon
                    },
                    'free_minutes': free_minutes,
                    'total_walking_km': round(day_distance, 2),
                    'travel_summary': {
                        'total_distance_m': int(day_distance * 1000),
                        'total_travel_time_s': day_travel_time * 60,
                        'transport_mode': 'hybrid',
                        'route_polyline': None
                    },
                    'recommendations': recommendations,
                    'zone_clusters_visited': list(set(a.zone_cluster for a in activities if a.zone_cluster is not None))
                })
            
            total_activities += len(activities)
            total_travel_time += day_travel_time
            total_distance += day_distance
        
        # Calcular métricas globales
        efficiency_score = 0.9  # Sistema híbrido es muy eficiente
        if total_activities > 0 and total_travel_time > 0:
            # Score basado en ratio actividades/tiempo de viaje
            activity_to_travel_ratio = total_activities / (total_travel_time / 60)  # actividades por hora de viaje
            efficiency_score = min(1.0, activity_to_travel_ratio / 10)  # normalizar
            
            # Penalizar eficiencia si hay traslados muy largos
            if hasattr(self, 'long_transfers_detected') and self.long_transfers_detected:
                long_transfer_penalty = len(self.long_transfers_detected) * 0.1  # -10% por traslado largo
                efficiency_score = max(0.1, efficiency_score - long_transfer_penalty)
        
        # Añadir información sobre traslados largos a las métricas
        long_transfer_info = {}
        if hasattr(self, 'long_transfers_detected') and self.long_transfers_detected:
            long_transfer_info = {
                'long_transfers_detected': len(self.long_transfers_detected),
                'intercity_transfers': [
                    {
                        'from': transfer['from_city'],
                        'to': transfer['to_city'],
                        'distance_km': round(transfer['distance_km'], 1),
                        'estimated_time_hours': round(transfer['estimated_time_min'] / 60, 1),
                        'transport': transfer['recommended_transport'],
                        'from_day': transfer['from_day'],
                        'to_day': transfer['to_day']
                    }
                    for transfer in self.long_transfers_detected
                ],
                'total_intercity_distance_km': round(sum(t['distance_km'] for t in self.long_transfers_detected), 1),
                'total_intercity_time_hours': round(sum(t['estimated_time_min'] for t in self.long_transfers_detected) / 60, 1)
            }

        return {
            'success': True,
            'days': formatted_days,
            'optimization_metrics': {
                'total_activities_scheduled': total_activities,
                'days_used': len(formatted_days),
                'total_travel_time_minutes': total_travel_time,
                'total_distance_km': round(total_distance, 2),
                'efficiency_score': round(efficiency_score, 2),
                'geographic_clustering': True,
                'hybrid_travel_estimation': True,
                'avg_activities_per_day': round(total_activities / max(1, len(formatted_days)), 1),
                **long_transfer_info  # Incluir información de traslados largos
            }
        }
    
    def should_use_accommodations(self, accommodations: Optional[List[Dict]]) -> bool:
        """
        🔍 DETECCIÓN AUTOMÁTICA: Determinar si usar hoteles como centroides
        """
        if not accommodations:
            return False
            
        # Validar que los hoteles tengan coordenadas válidas
        for acc in accommodations:
            if not acc.get('lat') or not acc.get('lon') or not acc.get('name'):
                self.logger.warning(f"Hotel {acc.get('name', 'sin nombre')} con datos inválidos")
                return False
                
        self.logger.info(f"✅ Detectados {len(accommodations)} hoteles válidos - usando como centroides")
        return True

    def cluster_places_by_hotels(self, places: List[Dict], 
                                accommodations: List[Dict]) -> Dict[int, List[Dict]]:
        """
        🏨 Agrupar lugares por hotel más cercano
        """
        clusters = {i: [] for i in range(len(accommodations))}
        
        self.logger.info(f"🗺️ Clustering: {len(places)} lugares por {len(accommodations)} hoteles")
        
        # Asignar cada lugar al hotel más cercano
        for place in places:
            closest_hotel_idx = 0
            min_distance = float('inf')
            
            for i, hotel in enumerate(accommodations):
                distance = self.haversine_km(
                    place['lat'], place['lon'],
                    hotel['lat'], hotel['lon']
                )
                
                if distance < min_distance:
                    min_distance = distance
                    closest_hotel_idx = i
            
            # Asignar al cluster del hotel más cercano
            clusters[closest_hotel_idx].append(place)
            place['assigned_hotel'] = accommodations[closest_hotel_idx]['name']
            place['hotel_distance_km'] = round(min_distance, 2)
            place['cluster_id'] = closest_hotel_idx
            
            self.logger.info(f"📍 {place['name']} → Hotel: {place['assigned_hotel']} ({min_distance:.2f}km)")
        
        return clusters

    def recommend_transport_mode(self, distance_km: float, travel_time_min: float, 
                               available_modes: List[str] = None) -> str:
        """
        🚗 Recomendar modo de transporte basado en distancia y tiempo con detección de traslados largos
        """
        if not available_modes:
            available_modes = ['walk', 'drive', 'transit']
        
        # Detectar traslados interurbanos
        if distance_km > settings.INTERCITY_THRESHOLD_KM:
            if travel_time_min > settings.LONG_TRANSFER_MIN:
                return f'� Auto (traslado largo {distance_km:.0f}km, ~{travel_time_min//60}h{travel_time_min%60:02d}min)'
            else:
                return f'🚗 Auto ({distance_km:.0f}km)'
        
        # Prohibir caminar si excede el límite
        if distance_km > settings.WALK_MAX_KM:
            if distance_km <= 5.0:
                return '🚌 Transporte público' if 'transit' in available_modes else '🚗 Auto/Taxi'
            elif distance_km <= 15.0:
                return '🚗 Auto/Taxi'
            else:
                return f'🚗 Auto ({distance_km:.1f}km)'
        
        # Lógica normal para distancias cortas
        if distance_km <= 0.3:
            return '🚶 Caminar'  # Muy cerca
        elif distance_km <= 0.8:
            return '� Caminar'  # Caminata corta
        elif distance_km <= settings.WALK_MAX_KM:
            if travel_time_min <= 25:
                return '🚶 Caminar'  # Caminata razonable
            else:
                return '🚌 Transporte público' if 'transit' in available_modes else '🚗 Auto/Taxi'
        else:
            return '🚗 Auto/Taxi'  # Fallback

    async def schedule_with_hotels(self, places: List[Dict], 
                                 accommodations: List[Dict],
                                 start_date: datetime, 
                                 end_date: datetime,
                                 daily_window: TimeWindow,
                                 transport_mode: str = 'walk') -> Dict[str, List[OptimizedActivity]]:
        """
        🏨 Programar actividades usando hoteles como centroides
        """
        
        # 1. Agrupar lugares por hotel más cercano
        clusters = self.cluster_places_by_hotels(places, accommodations)
        
        # 2. Distribuir clusters/hoteles entre días disponibles
        days_available = (end_date - start_date).days + 1
        daily_schedule = {}
        
        current_date = start_date
        for day in range(days_available):
            date_str = current_date.strftime('%Y-%m-%d')
            daily_schedule[date_str] = []
            current_date += timedelta(days=1)
        
        # 3. Estrategia inteligente de asignación
        day_keys = list(daily_schedule.keys())
        
        # Asignar cada cluster (hotel) a un día
        for i, (hotel_idx, cluster_places) in enumerate(clusters.items()):
            if not cluster_places:
                continue
                
            day_key = day_keys[i % len(day_keys)]
            hotel = accommodations[hotel_idx]
            
            # Programar actividades del cluster optimizadas desde el hotel
            activities = await self._schedule_cluster_from_hotel(
                cluster_places, daily_window, day_key, hotel, transport_mode
            )
            
            daily_schedule[day_key].extend(activities)
        
        return daily_schedule

    async def _schedule_cluster_from_hotel(self, places: List[Dict],
                                         time_window: TimeWindow,
                                         date: str,
                                         hotel: Dict,
                                         transport_mode: str) -> List[OptimizedActivity]:
        """
        📅 Programar un cluster optimizado desde el hotel
        """
        if not places:
            return []
        
        hotel_point = (hotel['lat'], hotel['lon'])
        
        # Optimizar orden empezando desde el hotel
        optimized_places = self._optimize_route_from_point(places, hotel_point)
        
        activities = []
        current_time = time_window.start
        
        self.logger.info(f"📍 Programando {len(optimized_places)} lugares para {date} desde {hotel['name']}")
        
        # Tiempo desde hotel al primer lugar
        if optimized_places:
            first_place = optimized_places[0]
            travel_to_first = await self.estimate_travel_time_hybrid(
                hotel_point[0], hotel_point[1],
                first_place['lat'], first_place['lon'],
                transport_mode
            )
            current_time += int(travel_to_first)
        
        # Programar cada actividad
        for i, place in enumerate(optimized_places):
            duration = self._estimate_activity_duration(place)
            activity_end = current_time + duration
            
            # Verificar si cabe en el horario del día
            if activity_end > time_window.end:
                self.logger.warning(f"⏰ {place['name']} no cabe en {date} (requiere hasta {activity_end//60:02d}:{activity_end%60:02d})")
                break
            
            # Calcular tiempo de viaje al siguiente lugar
            travel_time_next = 0
            recommended_transport = 'walk'
            
            if i < len(optimized_places) - 1:
                next_place = optimized_places[i + 1]
                distance_km = self.haversine_km(
                    place['lat'], place['lon'],
                    next_place['lat'], next_place['lon']
                )
                
                travel_time_next = int(await self.estimate_travel_time_hybrid(
                    place['lat'], place['lon'],
                    next_place['lat'], next_place['lon'],
                    transport_mode
                ))
                
                # Recomendar modo de transporte
                recommended_transport = self.recommend_transport_mode(
                    distance_km, travel_time_next, [transport_mode, 'walk', 'drive']
                )
            else:
                # Tiempo de regreso al hotel al final del día
                distance_to_hotel = self.haversine_km(
                    place['lat'], place['lon'],
                    hotel_point[0], hotel_point[1]
                )
                travel_time_next = int(await self.estimate_travel_time_hybrid(
                    place['lat'], place['lon'],
                    hotel_point[0], hotel_point[1],
                    transport_mode
                ))
                recommended_transport = self.recommend_transport_mode(
                    distance_to_hotel, travel_time_next, [transport_mode, 'walk', 'drive']
                )
            
            activity = OptimizedActivity(
                name=place['name'],
                lat=place['lat'],
                lon=place['lon'],
                type=place['type'],
                duration_minutes=duration,
                start_time=current_time,
                end_time=activity_end,
                priority=place.get('priority', 5),
                zone_cluster=place.get('cluster_id'),
                travel_time_to_next=travel_time_next,
                hotel_name=hotel['name'],
                hotel_distance_km=place.get('hotel_distance_km', 0),
                recommended_transport=recommended_transport
            )
            
            activities.append(activity)
            
            self.logger.info(f"   ✓ {place['name']}: {int(current_time)//60:02d}:{int(current_time)%60:02d}-{int(activity_end)//60:02d}:{int(activity_end)%60:02d} ({duration}min) → {recommended_transport}")
            
            # Actualizar tiempo para la siguiente actividad
            if i < len(optimized_places) - 1:
                current_time = activity_end + travel_time_next + self.buffer_between_activities
        
        return activities

    def _optimize_route_from_point(self, places: List[Dict], start_point: Tuple[float, float]) -> List[Dict]:
        """
        🗺️ Optimizar ruta empezando desde un punto específico (hotel)
        """
        if len(places) <= 1:
            return places
        
        # Encontrar el lugar más cercano al punto de inicio para empezar
        places_with_distance = []
        for place in places:
            distance = self.haversine_km(
                start_point[0], start_point[1],
                place['lat'], place['lon']
            )
            places_with_distance.append((place, distance))
        
        # Ordenar por distancia al punto de inicio y prioridad
        places_with_distance.sort(key=lambda x: (x[1], -x[0].get('priority', 5)))
        
        # Usar nearest neighbor desde el punto más cercano al inicio
        optimized = [places_with_distance[0][0]]
        remaining = [p[0] for p in places_with_distance[1:]]
        
        while remaining:
            current = optimized[-1]
            nearest = min(remaining, 
                         key=lambda p: self.haversine_km(
                             current['lat'], current['lon'],
                             p['lat'], p['lon']
                         ))
            optimized.append(nearest)
            remaining.remove(nearest)
        
        return optimized

    def format_activities_with_hotels(self, daily_schedule: Dict[str, List[OptimizedActivity]],
                                    accommodations: Optional[List[Dict]] = None) -> Dict:
        """
        📊 Formatear respuesta incluyendo información de hoteles y recomendaciones de transporte
        """
        def minutes_to_time_str(minutes: int) -> str:
            hours = int(minutes) // 60
            mins = int(minutes) % 60
            return f"{hours:02d}:{mins:02d}"
        
        formatted_days = []
        total_activities = 0
        total_travel_time = 0
        total_distance = 0
        
        for date, activities in daily_schedule.items():
            if not activities:
                continue
                
            formatted_activities = []
            day_travel_time = 0
            day_distance = 0
            
            for activity in activities:
                travel_time_next = activity.travel_time_to_next or 0
                day_travel_time += travel_time_next
                
                activity_data = {
                    'place': activity.name,
                    'start': minutes_to_time_str(activity.start_time),
                    'end': minutes_to_time_str(activity.end_time),
                    'duration_h': round(activity.duration_minutes / 60, 2),
                    'lat': activity.lat,
                    'lon': activity.lon,
                    'type': activity.type,
                    'travel_time_to_next': travel_time_next,
                    'zone_cluster': activity.zone_cluster,
                    'priority': activity.priority,
                    'recommended_transport': activity.recommended_transport
                }
                
                # 🏨 Agregar información del hotel si está disponible
                if activity.hotel_name:
                    activity_data['hotel_name'] = activity.hotel_name
                    activity_data['hotel_distance_km'] = activity.hotel_distance_km
                
                formatted_activities.append(activity_data)
            
            # Calcular lodging (hotel del día si está disponible)
            day_lodging = {
                'name': 'Área central (auto)',
                'lat': sum(a.lat for a in activities) / len(activities) if activities else 0,
                'lon': sum(a.lon for a in activities) / len(activities) if activities else 0
            }
            
            # 🏨 Usar hotel real si está disponible
            if activities and activities[0].hotel_name:
                hotel_for_day = None
                if accommodations:
                    for acc in accommodations:
                        if acc['name'] == activities[0].hotel_name:
                            hotel_for_day = acc
                            break
                
                if hotel_for_day:
                    day_lodging = {
                        'name': hotel_for_day['name'],
                        'lat': hotel_for_day['lat'],
                        'lon': hotel_for_day['lon'],
                        'address': hotel_for_day.get('address', ''),
                        'type': hotel_for_day.get('type', 'hotel')
                    }
            
            # Calcular tiempo libre
            total_day_minutes = 9 * 60  # 9 horas típicas
            used_minutes = sum(int(a.duration_minutes) + int(a.travel_time_to_next or 0) 
                             for a in activities)
            free_minutes = max(0, total_day_minutes - used_minutes)
            
            # Calcular distancia del día
            day_distance = sum([
                self.haversine_km(activities[i].lat, activities[i].lon,
                                activities[i+1].lat, activities[i+1].lon)
                for i in range(len(activities)-1)
            ])
            
            recommendations = [
                f"Día optimizado con {len(activities)} actividades",
                f"Tiempo libre: {free_minutes} minutos",
                f"Distancia total: {round(day_distance, 1)}km",
                f"Tiempo de traslados: {int(day_travel_time)}min",
                f"Medios de transporte: {', '.join(set(a.recommended_transport for a in activities if a.recommended_transport))}"
            ]
            
            if activities and activities[0].hotel_name:
                recommendations.append(f"Base: {activities[0].hotel_name}")
            
            formatted_days.append({
                'date': date,
                'activities': formatted_activities,
                'lodging': day_lodging,
                'free_minutes': int(free_minutes),
                'total_walking_km': round(day_distance, 2),
                'travel_summary': {
                    'total_distance_m': int(day_distance * 1000),
                    'total_travel_time_s': day_travel_time * 60,
                    'transport_mode': 'hybrid',
                    'route_polyline': None
                },
                'recommendations': recommendations,
                'hotel_based_optimization': bool(activities and activities[0].hotel_name)
            })
            
            total_activities += len(activities)
            total_travel_time += day_travel_time
            total_distance += day_distance
        
        # Calcular eficiencia
        efficiency_score = min(1.0, total_activities / max(1, len(formatted_days) * 4)) if formatted_days else 0.9
        
        return {
            'success': True,
            'days': formatted_days,
            'optimization_metrics': {
                'total_activities_scheduled': total_activities,
                'days_used': len(formatted_days),
                'total_travel_time_minutes': total_travel_time,
                'total_distance_km': round(total_distance, 2),
                'efficiency_score': round(efficiency_score, 2),
                'accommodation_based_clustering': bool(accommodations),
                'geographic_clustering': not bool(accommodations),
                'hybrid_travel_estimation': True,
                'transport_recommendations': True,
                'avg_activities_per_day': round(total_activities / max(1, len(formatted_days)), 1)
            }
        }

# Función principal actualizada con detección automática
async def optimize_itinerary_hybrid(places: List[Dict], 
                                   start_date: datetime,
                                   end_date: datetime,
                                   daily_start_hour: int = 9,
                                   daily_end_hour: int = 18,
                                   transport_mode: str = 'walk',
                                   accommodations: Optional[List[Dict]] = None) -> Dict:
    """
    🚀 Función principal con detección automática de hoteles y recomendaciones de transporte
    
    - ✅ Si envías hoteles: Los usa como centroides inteligentes
    - ✅ Si NO envías hoteles: Usa clustering geográfico automático 
    - ✅ Recomendaciones de transporte automáticas
    - ✅ Completamente retrocompatible
    """
    
    optimizer = HybridIntelligentOptimizer()
    
    # Configurar ventana de tiempo diaria
    time_window = TimeWindow(
        start=daily_start_hour * 60,  # convertir a minutos
        end=daily_end_hour * 60
    )
    
    # 🔍 DETECCIÓN AUTOMÁTICA DE HOTELES
    if optimizer.should_use_accommodations(accommodations):
        # 🏨 MODO: Con Hoteles como Centroides
        optimizer.logger.info("🏨 Optimizando con hoteles como centroides")
        daily_schedule = await optimizer.schedule_with_hotels(
            places, accommodations, start_date, end_date, time_window, transport_mode
        )
        
        # Formatear para API con soporte completo para hoteles
        return optimizer.format_activities_with_hotels(daily_schedule, accommodations)
    else:
        # 🗺️ MODO: Clustering Geográfico Normal (comportamiento actual)
        optimizer.logger.info("🗺️ Optimizando con clustering geográfico automático")
        daily_schedule = await optimizer.schedule_activities_multi_day(
            places, start_date, end_date, time_window, transport_mode
        )
        
        # Formatear para API (modo estándar)
        return optimizer.format_activities_for_api(daily_schedule)

# Función de conveniencia (retrocompatibilidad)
async def optimize_itinerary_hybrid_legacy(places: List[Dict], 
                                          start_date: datetime,
                                          end_date: datetime,
                                          daily_start_hour: int = 9,
                                          daily_end_hour: int = 18,
                                          transport_mode: str = 'walk') -> Dict:
    """Función legacy para mantener retrocompatibilidad"""
    return await optimize_itinerary_hybrid(
        places, start_date, end_date, daily_start_hour, 
        daily_end_hour, transport_mode, None
    )
