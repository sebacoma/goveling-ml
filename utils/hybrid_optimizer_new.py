"""
🚀 OPTIMIZADOR HÍBRIDO REESTRUCTURADO V3.0
Flujo mejorado según especificaciones:
1. Clustering POIs (sin hoteles) con DBSCAN + Haversine
2. Asignación home_base por cluster (usuario/recomendado)
3. Asignación clusters a días respetando traslados inter-cluster
4. Orden intra-cluster con N-N + ETAs reales vía Google Directions
5. Timeline con activities + transfers explícitos
"""

import math
import asyncio
import logging
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import numpy as np
from sklearn.cluster import DBSCAN

from utils.google_directions_service import GoogleDirectionsService
from utils.geo_utils import haversine_km
from services.hotel_recommender import HotelRecommender
from settings import settings

@dataclass
class TimeWindow:
    start: int  # minutos desde medianoche (9:00 = 540)
    end: int    # minutos desde medianoche (18:00 = 1080)

@dataclass
class Cluster:
    label: int
    centroid: Tuple[float, float]  # (lat, lon)
    places: List[Dict]
    home_base: Optional[Dict] = None
    home_base_source: str = "none"  # "user_provided" | "recommended" | "none"

@dataclass
class TransferItem:
    type: str = "transfer"
    from_place: str = ""
    to_place: str = ""
    distance_km: float = 0.0
    duration_minutes: int = 0
    recommended_mode: str = "walk"
    is_intercity: bool = False

@dataclass
class ActivityItem:
    type: str = "activity"
    name: str = ""
    lat: float = 0.0
    lon: float = 0.0
    place_type: str = ""
    duration_minutes: int = 60
    start_time: int = 540  # minutos desde medianoche
    end_time: int = 600
    priority: int = 5
    # Compatibilidad con schema actual
    rating: float = 4.5
    image: str = ""
    address: str = ""

class HybridOptimizerV3:
    def __init__(self):
        self.google_service = GoogleDirectionsService()
        self.hotel_recommender = HotelRecommender()
        self.logger = logging.getLogger(__name__)
        
    # =========================================================================
    # 1. CLUSTERING DE POIS (SIN HOTELES)
    # =========================================================================
    
    def cluster_pois(self, places: List[Dict]) -> List[Cluster]:
        """
        🗺️ Clustering de POIs usando DBSCAN con métrica Haversine
        Ignora lugares de tipo 'accommodation'
        """
        # Filtrar solo POIs (excluir hoteles)
        pois = [p for p in places if p.get('type', '').lower() != 'accommodation']
        
        if not pois:
            self.logger.warning("No hay POIs para clustering")
            return []
        
        self.logger.info(f"🗺️ Clustering {len(pois)} POIs (excluyendo {len(places) - len(pois)} hoteles)")
        
        # Preparar datos para DBSCAN
        coordinates = np.array([[p['lat'], p['lon']] for p in pois])
        
        # Elegir eps dinámicamente (urbano vs rural)
        eps_km = self._choose_eps_km(coordinates)
        eps_rad = eps_km / 6371.0  # Convertir km a radianes
        
        # DBSCAN con métrica haversine
        clustering = DBSCAN(
            eps=eps_rad,
            min_samples=settings.CLUSTER_MIN_SAMPLES,
            metric='haversine'
        ).fit(np.radians(coordinates))
        
        # Agrupar lugares por cluster
        clusters = {}
        for i, label in enumerate(clustering.labels_):
            if label == -1:  # Ruido: crear cluster individual
                label = f"noise_{i}"
            
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(pois[i])
        
        # Crear objetos Cluster
        cluster_objects = []
        for label, cluster_places in clusters.items():
            centroid = self._calculate_centroid(cluster_places)
            cluster_obj = Cluster(
                label=label,
                centroid=centroid,
                places=cluster_places
            )
            cluster_objects.append(cluster_obj)
        
        self.logger.info(f"✅ {len(cluster_objects)} clusters creados con eps={eps_km}km")
        for i, cluster in enumerate(cluster_objects):
            self.logger.info(f"  Cluster {cluster.label}: {len(cluster.places)} lugares, centroide {cluster.centroid}")
        
        return cluster_objects
    
    def _choose_eps_km(self, coordinates: np.ndarray) -> float:
        """Elegir eps dinámicamente basado en densidad de puntos"""
        if len(coordinates) < 5:
            return settings.CLUSTER_EPS_KM_RURAL
        
        # Calcular dispersión
        lat_range = np.max(coordinates[:, 0]) - np.min(coordinates[:, 0])
        lon_range = np.max(coordinates[:, 1]) - np.min(coordinates[:, 1])
        total_span = math.sqrt(lat_range**2 + lon_range**2)
        
        # Si los puntos están muy dispersos, usar eps rural
        if total_span > 0.5:  # > ~55km de span total
            return settings.CLUSTER_EPS_KM_RURAL
        else:
            return settings.CLUSTER_EPS_KM_URBAN
    
    def _calculate_centroid(self, places: List[Dict]) -> Tuple[float, float]:
        """Calcular centroide geográfico de un grupo de lugares"""
        lats = [p['lat'] for p in places]
        lons = [p['lon'] for p in places]
        return (sum(lats) / len(lats), sum(lons) / len(lons))
    
    # =========================================================================
    # 2. ASIGNACIÓN HOME BASE POR CLUSTER
    # =========================================================================
    
    async def assign_home_base_to_clusters(
        self, 
        clusters: List[Cluster], 
        accommodations: Optional[List[Dict]] = None
    ) -> List[Cluster]:
        """
        🏨 Asignar hotel/home_base a cada cluster
        """
        self.logger.info(f"🏨 Asignando home_base a {len(clusters)} clusters")
        
        if not accommodations:
            # Recomendar hoteles para cada cluster
            return await self._recommend_hotels_for_clusters(clusters)
        else:
            # Asignar hoteles del usuario
            return self._assign_user_hotels_to_clusters(clusters, accommodations)
    
    def _assign_user_hotels_to_clusters(
        self, 
        clusters: List[Cluster], 
        accommodations: List[Dict]
    ) -> List[Cluster]:
        """Asignar hoteles proporcionados por el usuario"""
        for cluster in clusters:
            # Encontrar hotel más cercano al centroide del cluster
            min_distance = float('inf')
            closest_hotel = None
            
            for hotel in accommodations:
                distance = haversine_km(
                    cluster.centroid[0], cluster.centroid[1],
                    hotel['lat'], hotel['lon']
                )
                if distance < min_distance:
                    min_distance = distance
                    closest_hotel = hotel
            
            if closest_hotel:
                cluster.home_base = closest_hotel.copy()
                cluster.home_base_source = "user_provided"
                self.logger.info(f"  Cluster {cluster.label}: {closest_hotel['name']} ({min_distance:.1f}km)")
        
        return clusters
    
    async def _recommend_hotels_for_clusters(self, clusters: List[Cluster]) -> List[Cluster]:
        """Recomendar hoteles para clusters sin home_base"""
        for cluster in clusters:
            try:
                # Usar HotelRecommender para obtener recomendación
                recommendations = self.hotel_recommender.recommend_hotels(
                    cluster.places,
                    max_recommendations=1,
                    price_preference="mid"
                )
                
                if recommendations:
                    top_hotel = recommendations[0]
                    cluster.home_base = {
                        'name': top_hotel.name,
                        'lat': top_hotel.lat,
                        'lon': top_hotel.lon,
                        'address': top_hotel.address,
                        'rating': top_hotel.rating,
                        'type': 'accommodation'
                    }
                    cluster.home_base_source = "recommended"
                    self.logger.info(f"  Cluster {cluster.label}: {top_hotel.name} (recomendado)")
                else:
                    # Fallback: usar centroide como "punto base virtual"
                    cluster.home_base = {
                        'name': f"Punto base Cluster {cluster.label}",
                        'lat': cluster.centroid[0],
                        'lon': cluster.centroid[1],
                        'address': "Ubicación central estimada",
                        'rating': 0.0,
                        'type': 'virtual_base'
                    }
                    cluster.home_base_source = "centroid_fallback"
                    self.logger.warning(f"  Cluster {cluster.label}: usando centroide como fallback")
                    
            except Exception as e:
                self.logger.error(f"Error recomendando hotel para cluster {cluster.label}: {e}")
                # Fallback igual que arriba
                cluster.home_base = {
                    'name': f"Punto base Cluster {cluster.label}",
                    'lat': cluster.centroid[0],
                    'lon': cluster.centroid[1],
                    'address': "Ubicación central estimada",
                    'rating': 0.0,
                    'type': 'virtual_base'
                }
                cluster.home_base_source = "error_fallback"
        
        return clusters
    
    # =========================================================================
    # 3. ASIGNACIÓN DE CLUSTERS A DÍAS
    # =========================================================================
    
    def allocate_clusters_to_days(
        self,
        clusters: List[Cluster],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, List[Cluster]]:
        """
        📅 Asignar clusters a días respetando traslados inter-cluster
        """
        num_days = (end_date - start_date).days + 1
        self.logger.info(f"📅 Asignando {len(clusters)} clusters a {num_days} días")
        
        # Calcular distancias entre clusters
        cluster_distances = self._calculate_inter_cluster_distances(clusters)
        
        # Determinar umbral intercity dinámico
        intercity_threshold = self._get_intercity_threshold(clusters)
        
        # Algoritmo de asignación: greedy evitando conflictos
        day_assignments = {}
        current_date = start_date
        
        for day_num in range(num_days):
            date_str = current_date.strftime('%Y-%m-%d')
            day_assignments[date_str] = []
            current_date += timedelta(days=1)
        
        # Asignar clusters evitando traslados largos el mismo día
        available_clusters = clusters.copy()
        day_keys = list(day_assignments.keys())
        
        for day_idx, date_str in enumerate(day_keys):
            if not available_clusters:
                break
            
            # Si es el primer día, tomar cualquier cluster
            if day_idx == 0:
                chosen_cluster = available_clusters.pop(0)
                day_assignments[date_str].append(chosen_cluster)
                self.logger.info(f"  {date_str}: Cluster {chosen_cluster.label} (inicial)")
                continue
            
            # Para días siguientes, buscar cluster compatible
            previous_clusters = []
            for prev_day in day_keys[:day_idx]:
                previous_clusters.extend(day_assignments[prev_day])
            
            compatible_cluster = None
            for cluster in available_clusters:
                is_compatible = True
                
                # Verificar compatibilidad con clusters de días anteriores
                for prev_cluster in previous_clusters:
                    distance_key = tuple(sorted([cluster.label, prev_cluster.label]))
                    distance = cluster_distances.get(distance_key, 0)
                    
                    if distance > intercity_threshold:
                        # Solo es incompatible si está en el día inmediatamente anterior
                        prev_date_idx = day_keys.index([k for k, v in day_assignments.items() if prev_cluster in v][0])
                        if abs(day_idx - prev_date_idx) <= 1:  # Días consecutivos
                            is_compatible = False
                            break
                
                if is_compatible:
                    compatible_cluster = cluster
                    break
            
            if compatible_cluster:
                available_clusters.remove(compatible_cluster)
                day_assignments[date_str].append(compatible_cluster)
                self.logger.info(f"  {date_str}: Cluster {compatible_cluster.label} (compatible)")
            else:
                # Si no hay compatibles, tomar el primero y log warning
                if available_clusters:
                    fallback_cluster = available_clusters.pop(0)
                    day_assignments[date_str].append(fallback_cluster)
                    self.logger.warning(f"  {date_str}: Cluster {fallback_cluster.label} (FORZADO - posible traslado largo)")
        
        # Clusters que no cupieron en ningún día
        if available_clusters:
            self.logger.warning(f"⚠️ {len(available_clusters)} clusters no asignados a ningún día")
            # Distribuir en días con menos carga
            for cluster in available_clusters:
                # Encontrar día con menos clusters
                min_clusters_day = min(day_assignments.keys(), key=lambda d: len(day_assignments[d]))
                day_assignments[min_clusters_day].append(cluster)
                self.logger.info(f"  Spillover: Cluster {cluster.label} → {min_clusters_day}")
        
        return day_assignments
    
    def _calculate_inter_cluster_distances(self, clusters: List[Cluster]) -> Dict[tuple, float]:
        """Calcular distancias entre centroides de clusters"""
        distances = {}
        
        for i, cluster_a in enumerate(clusters):
            for j, cluster_b in enumerate(clusters[i+1:], i+1):
                distance = haversine_km(
                    cluster_a.centroid[0], cluster_a.centroid[1],
                    cluster_b.centroid[0], cluster_b.centroid[1]
                )
                key = tuple(sorted([cluster_a.label, cluster_b.label]))
                distances[key] = distance
        
        return distances
    
    def _get_intercity_threshold(self, clusters: List[Cluster]) -> float:
        """Determinar umbral intercity dinámico"""
        # Si hay muchos clusters dispersos, usar umbral rural
        if len(clusters) > 3:
            return settings.INTERCITY_THRESHOLD_KM_RURAL
        else:
            return settings.INTERCITY_THRESHOLD_KM_URBAN
    
    # =========================================================================
    # 4. ROUTING INTRA-CLUSTER Y TIMELINE POR DÍA
    # =========================================================================
    
    async def route_day(
        self,
        date: str,
        assigned_clusters: List[Cluster],
        daily_window: TimeWindow,
        transport_mode: str,
        previous_day_end_location: Optional[Tuple[float, float]] = None
    ) -> Dict:
        """
        🗓️ Generar timeline completo para un día con activities + transfers
        """
        self.logger.info(f"🗓️ Routing día {date} con {len(assigned_clusters)} clusters")
        
        timeline = []
        transfers = []  # Transfers explícitos para exponer al frontend
        current_time = daily_window.start
        current_location = previous_day_end_location
        total_travel_time = 0
        total_distance = 0
        walking_time = 0  # Solo para transfers <2km
        transport_time = 0  # Para transfers >2km (driving/transit)
        activities_scheduled = []
        
        for cluster_idx, cluster in enumerate(assigned_clusters):
            # Insertar transfer inter-cluster si es necesario
            if current_location and cluster.home_base:
                transfer = await self._build_intercity_transfer(
                    current_location,
                    (cluster.home_base['lat'], cluster.home_base['lon']),
                    transport_mode
                )
                
                if transfer.duration_minutes > 0:
                    # Verificar si el transfer cabe en el día
                    if current_time + transfer.duration_minutes > daily_window.end:
                        self.logger.warning(f"  ⚠️ Transfer intercity no cabe en {date} ({transfer.duration_minutes}min) - SPILL")
                        # TODO: Implementar spill del cluster al día siguiente
                        break
                    
                    timeline.append(transfer)
                    transfers.append({
                        "type": "intercity_transfer",
                        "from": transfer.from_place,
                        "to": transfer.to_place,
                        "distance_km": transfer.distance_km,
                        "duration_minutes": transfer.duration_minutes,
                        "mode": transfer.recommended_mode,
                        "time": f"{current_time//60:02d}:{current_time%60:02d}"
                    })
                    
                    current_time += transfer.duration_minutes
                    total_travel_time += transfer.duration_minutes
                    total_distance += transfer.distance_km
                    
                    # Clasificar el tiempo según el modo de transporte
                    if transfer.recommended_mode in ['walk'] and transfer.distance_km <= settings.WALK_THRESHOLD_KM:
                        walking_time += transfer.duration_minutes
                    else:
                        transport_time += transfer.duration_minutes
                    
                    self.logger.info(f"  Transfer intercity: {transfer.duration_minutes}min, {transfer.distance_km:.1f}km ({transfer.recommended_mode})")
            
            # Routear actividades dentro del cluster
            cluster_activities, cluster_timeline = await self._route_cluster_activities(
                cluster,
                current_time,
                daily_window.end,
                transport_mode
            )
            
            activities_scheduled.extend(cluster_activities)
            timeline.extend(cluster_timeline)
            
            # Actualizar tiempo y ubicación actual
            if cluster_timeline:
                last_item = cluster_timeline[-1]
                if hasattr(last_item, 'end_time'):
                    current_time = last_item.end_time
                if hasattr(last_item, 'lat') and hasattr(last_item, 'lon'):
                    current_location = (last_item.lat, last_item.lon)
            
            # Acumular métricas de viaje intra-cluster
            for item in cluster_timeline:
                if isinstance(item, TransferItem):
                    total_travel_time += item.duration_minutes
                    total_distance += item.distance_km
                    
                    # Clasificar intra-cluster también
                    if item.recommended_mode in ['walk'] and item.distance_km <= settings.WALK_THRESHOLD_KM:
                        walking_time += item.duration_minutes
                    else:
                        transport_time += item.duration_minutes
        
        # Calcular tiempo libre
        total_activity_time = sum(
            act.duration_minutes for act in activities_scheduled
        )
        total_window_minutes = daily_window.end - daily_window.start
        free_minutes = max(0, total_window_minutes - total_activity_time - total_travel_time)
        
        return {
            "date": date,
            "activities": activities_scheduled,
            "timeline": timeline,  # Con transfers explícitos
            "transfers": transfers,  # Transfers explícitos para frontend
            "travel_summary": {
                "total_travel_time_s": total_travel_time * 60,
                "total_distance_km": total_distance,
                "walking_time_minutes": walking_time,
                "transport_time_minutes": transport_time
            },
            "free_minutes": free_minutes,
            "end_location": current_location
        }
    
    async def _build_intercity_transfer(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        transport_mode: str
    ) -> TransferItem:
        """Construir transfer inter-cluster con política de transporte estricta"""
        eta_info = await self.google_service.eta_between(origin, destination, transport_mode)
        
        # Determinar si es intercity
        is_intercity = eta_info['distance_km'] > settings.INTERCITY_THRESHOLD_KM_URBAN
        
        # Forzar modo apropiado para distancia
        final_mode = self._decide_mode_by_distance_km(eta_info['distance_km'], transport_mode)
        
        # Si el modo cambió, recalcular con el modo correcto
        if final_mode != eta_info.get('recommended_mode', transport_mode):
            self.logger.info(f"🚗 Forzando modo: {transport_mode} → {final_mode} para {eta_info['distance_km']:.1f}km")
            eta_info = await self.google_service.eta_between(origin, destination, final_mode)
        
        return TransferItem(
            type="transfer",
            from_place="Ubicación anterior",
            to_place="Nueva zona",
            distance_km=eta_info['distance_km'],
            duration_minutes=int(eta_info['duration_minutes']),
            recommended_mode=final_mode,
            is_intercity=is_intercity
        )
    
    def _decide_mode_by_distance_km(self, distance_km: float, requested_mode: str) -> str:
        """
        🚗 Política de transporte estricta por distancia
        """
        if distance_km <= settings.WALK_THRESHOLD_KM:
            return "walk"
        elif distance_km <= settings.DRIVE_THRESHOLD_KM:
            # Para distancias medias, preferir transit si está disponible
            if settings.TRANSIT_AVAILABLE and requested_mode in ["walk", "transit"]:
                return "transit"
            else:
                return "drive"
        else:
            # Para distancias largas, FORZAR driving
            return "drive"
    
    async def _route_cluster_activities(
        self,
        cluster: Cluster,
        start_time: int,
        end_time: int,
        transport_mode: str
    ) -> Tuple[List[ActivityItem], List]:
        """
        Routear actividades dentro de un cluster usando N-N + ETAs reales
        """
        if not cluster.places:
            return [], []
        
        self.logger.info(f"  🎯 Routing {len(cluster.places)} lugares en cluster {cluster.label}")
        
        # Punto de inicio: home_base del cluster o primer lugar
        start_location = (cluster.home_base['lat'], cluster.home_base['lon']) if cluster.home_base else (cluster.places[0]['lat'], cluster.places[0]['lon'])
        
        # Optimizar orden con Nearest Neighbor usando ETAs reales
        waypoints = [(p['lat'], p['lon']) for p in cluster.places]
        optimal_order = await self.google_service.get_optimized_route_order(
            waypoints, start_location, transport_mode
        )
        
        # Crear timeline con actividades y transfers
        activities = []
        timeline = []
        current_time = start_time
        current_location = start_location
        
        for i, place_idx in enumerate(optimal_order):
            place = cluster.places[place_idx]
            place_location = (place['lat'], place['lon'])
            
            # Transfer al lugar (si no es el primer lugar desde home_base)
            if current_location != place_location:
                eta_info = await self.google_service.eta_between(
                    current_location, place_location, transport_mode
                )
                
                # Aplicar política de transporte
                final_mode = self._decide_mode_by_distance_km(eta_info['distance_km'], transport_mode)
                if final_mode != eta_info.get('recommended_mode', transport_mode):
                    eta_info = await self.google_service.eta_between(
                        current_location, place_location, final_mode
                    )
                
                transfer = TransferItem(
                    type="transfer",
                    from_place=getattr(current_location, 'name', 'Ubicación anterior'),
                    to_place=place['name'],
                    distance_km=eta_info['distance_km'],
                    duration_minutes=int(eta_info['duration_minutes']),
                    recommended_mode=final_mode,
                    is_intercity=False
                )
                
                timeline.append(transfer)
                current_time += transfer.duration_minutes
            
            # Verificar si cabe en el día
            activity_duration = self._estimate_activity_duration(place)
            if current_time + activity_duration > end_time:
                self.logger.warning(f"    ⚠️ {place['name']} no cabe en el día (spillover)")
                break
            
            # Crear actividad
            activity = ActivityItem(
                type="activity",
                name=place['name'],
                lat=place['lat'],
                lon=place['lon'],
                place_type=place.get('type', 'point_of_interest'),
                duration_minutes=activity_duration,
                start_time=current_time,
                end_time=current_time + activity_duration,
                priority=place.get('priority', 5),
                rating=place.get('rating', 4.5),
                image=place.get('image', ''),
                address=place.get('address', '')
            )
            
            activities.append(activity)
            timeline.append(activity)
            current_time = activity.end_time
            current_location = place_location
        
        self.logger.info(f"    ✅ {len(activities)} actividades programadas en cluster {cluster.label}")
        return activities, timeline
    
    def _estimate_activity_duration(self, place: Dict) -> int:
        """Estimar duración de actividad basada en tipo"""
        place_type = place.get('type', '').lower()
        
        duration_map = {
            'restaurant': 90,
            'museum': 120,
            'tourist_attraction': 90,
            'shopping': 120,
            'park': 60,
            'entertainment': 180,
            'sports': 120,
            'cultural': 90
        }
        
        return duration_map.get(place_type, 60)  # Default 1 hora
    
    # =========================================================================
    # 5. FORMATEO Y MÉTRICAS
    # =========================================================================
    
    def calculate_optimization_metrics(self, days: List[Dict]) -> Dict:
        """Calcular métricas globales de optimización"""
        total_travel_time_min = sum(
            day.get('travel_summary', {}).get('total_travel_time_s', 0) / 60
            for day in days
        )
        total_distance_km = sum(
            day.get('travel_summary', {}).get('total_distance_km', 0)
            for day in days
        )
        total_activities = sum(len(day.get('activities', [])) for day in days)
        
        # Score de eficiencia: penalizar traslados largos
        efficiency_base = 0.95
        travel_penalty = min(0.4, total_travel_time_min / 480 * 0.2)  # 8h = 480min
        efficiency_score = max(0.1, efficiency_base - travel_penalty)
        
        # Detectar traslados largos
        long_transfers = []
        intercity_time = 0
        intercity_distance = 0
        
        for day in days:
            for item in day.get('timeline', []):
                if isinstance(item, TransferItem) and item.is_intercity:
                    long_transfers.append({
                        'from': item.from_place,
                        'to': item.to_place,
                        'distance_km': item.distance_km,
                        'estimated_time_hours': item.duration_minutes / 60
                    })
                    intercity_time += item.duration_minutes / 60
                    intercity_distance += item.distance_km
        
        return {
            'efficiency_score': efficiency_score,
            'total_distance_km': total_distance_km,
            'total_travel_time_minutes': total_travel_time_min,
            'long_transfers_detected': len(long_transfers),
            'intercity_transfers': long_transfers,
            'total_intercity_time_hours': intercity_time,
            'total_intercity_distance_km': intercity_distance
        }

# =========================================================================
# FUNCIÓN PRINCIPAL REESTRUCTURADA
# =========================================================================

async def optimize_itinerary_hybrid_v3(
    places: List[Dict],
    start_date: datetime,
    end_date: datetime,
    daily_start_hour: int = 9,
    daily_end_hour: int = 18,
    transport_mode: str = 'walk',
    accommodations: Optional[List[Dict]] = None
) -> Dict:
    """
    🚀 OPTIMIZADOR HÍBRIDO V3.0 - FLUJO REESTRUCTURADO
    
    1. Clustering POIs (sin hoteles)
    2. Asignación home_base por cluster
    3. Asignación clusters a días
    4. Routing intra-cluster + timeline
    5. Métricas y formato final
    """
    optimizer = HybridOptimizerV3()
    time_window = TimeWindow(
        start=daily_start_hour * 60,
        end=daily_end_hour * 60
    )
    
    logging.info(f"🚀 Iniciando optimización híbrida V3.0")
    logging.info(f"📍 {len(places)} lugares, {(end_date - start_date).days + 1} días")
    
    # 1. Clustering POIs
    clusters = optimizer.cluster_pois(places)
    if not clusters:
        return {"error": "No se pudieron crear clusters", "days": []}
    
    # 2. Asignación home_base
    clusters = await optimizer.assign_home_base_to_clusters(clusters, accommodations)
    
    # 3. Asignación a días
    day_assignments = optimizer.allocate_clusters_to_days(clusters, start_date, end_date)
    
    # 4. Routing día por día
    days = []
    previous_end_location = None
    
    for date_str, assigned_clusters in day_assignments.items():
        if not assigned_clusters:
            # Día libre
            days.append({
                "date": date_str,
                "activities": [],
                "timeline": [],
                "travel_summary": {"total_travel_time_s": 0, "total_distance_km": 0},
                "free_minutes": time_window.end - time_window.start
            })
            continue
        
        day_result = await optimizer.route_day(
            date_str, assigned_clusters, time_window, transport_mode, previous_end_location
        )
        days.append(day_result)
        previous_end_location = day_result.get('end_location')
    
    # 5. Métricas finales
    optimization_metrics = optimizer.calculate_optimization_metrics(days)
    
    logging.info(f"✅ Optimización completada:")
    logging.info(f"  📊 {sum(len(d['activities']) for d in days)} actividades programadas")
    logging.info(f"  🎯 Score: {optimization_metrics['efficiency_score']:.1%}")
    logging.info(f"  🚗 {optimization_metrics['long_transfers_detected']} traslados largos")
    
    return {
        "days": days,
        "optimization_metrics": optimization_metrics,
        "clusters_info": {
            "total_clusters": len(clusters),
            "hotels_assigned": sum(1 for c in clusters if c.home_base_source != "none"),
            "recommended_hotels": sum(1 for c in clusters if c.home_base_source == "recommended")
        }
    }

# Función de compatibilidad
async def optimize_itinerary_hybrid(
    places: List[Dict],
    start_date: datetime,
    end_date: datetime,
    daily_start_hour: int = 9,
    daily_end_hour: int = 18,
    transport_mode: str = 'walk',
    accommodations: Optional[List[Dict]] = None
) -> Dict:
    """Wrapper para mantener compatibilidad con API actual"""
    return await optimize_itinerary_hybrid_v3(
        places, start_date, end_date, daily_start_hour, 
        daily_end_hour, transport_mode, accommodations
    )
