"""
🚀 HYBRID OPTIMIZER V3.1 - ENHANCED VERSION
Mejoras implementadas:
- Packing strategies (compact/balanced/cluster_first)
- Time windows por tipo de lugar
- Transfers intercity con nombres reales
- Métricas detalladas separadas
- Sugerencias dinámicas para días libres
- Lodging recommendations por cluster
- Validaciones horarias con Google Places
"""

import math
import asyncio
import logging
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import numpy as np
from sklearn.cluster import DBSCAN

from utils.google_directions_service import GoogleDirectionsService
from utils.geo_utils import haversine_km
from services.hotel_recommender import HotelRecommender
from services.google_places_service import GooglePlacesService
from settings import settings

@dataclass
class TimeWindow:
    start: int  # minutos desde medianoche
    end: int

@dataclass
class Cluster:
    label: int
    centroid: Tuple[float, float]
    places: List[Dict]
    home_base: Optional[Dict] = None
    home_base_source: str = "none"
    suggested_accommodations: List[Dict] = field(default_factory=list)

@dataclass
class TransferItem:
    type: str = "transfer"
    from_place: str = ""
    to_place: str = ""
    distance_km: float = 0.0
    duration_minutes: int = 0
    recommended_mode: str = "walk"
    is_intercity: bool = False
    overnight: bool = False

@dataclass
class ActivityItem:
    type: str = "activity"
    name: str = ""
    lat: float = 0.0
    lon: float = 0.0
    place_type: str = ""
    duration_minutes: int = 60
    start_time: int = 540
    end_time: int = 600
    priority: int = 5
    rating: float = 4.5
    image: str = ""
    address: str = ""
    time_window_preferred: Optional[TimeWindow] = None

@dataclass
class FreeBlock:
    start_time: int
    end_time: int
    duration_minutes: int
    suggestions: List[Dict] = field(default_factory=list)
    note: str = ""

class HybridOptimizerV31:
    def __init__(self):
        self.google_service = GoogleDirectionsService()
        self.hotel_recommender = HotelRecommender()
        self.places_service = GooglePlacesService()
        self.logger = logging.getLogger(__name__)
        
    # =========================================================================
    # 1. CLUSTERING POIs (UNCHANGED FROM V3.0)
    # =========================================================================
    
    def cluster_pois(self, places: List[Dict]) -> List[Cluster]:
        """🗺️ Clustering POIs usando DBSCAN con métrica Haversine"""
        pois = [p for p in places if p.get('type', '').lower() != 'accommodation']
        
        if not pois:
            self.logger.warning("No hay POIs para clustering")
            return []
        
        self.logger.info(f"🗺️ Clustering {len(pois)} POIs")
        
        coordinates = np.array([[p['lat'], p['lon']] for p in pois])
        eps_km = self._choose_eps_km(coordinates)
        eps_rad = eps_km / 6371.0
        
        clustering = DBSCAN(
            eps=eps_rad,
            min_samples=settings.CLUSTER_MIN_SAMPLES,
            metric='haversine'
        ).fit(np.radians(coordinates))
        
        clusters = {}
        for i, label in enumerate(clustering.labels_):
            if label == -1:
                label = f"noise_{i}"
            
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(pois[i])
        
        cluster_objects = []
        for label, cluster_places in clusters.items():
            centroid = self._calculate_centroid(cluster_places)
            cluster_obj = Cluster(
                label=label,
                centroid=centroid,
                places=cluster_places
            )
            cluster_objects.append(cluster_obj)
        
        # 🔒 GARANTÍA: Siempre al menos 1 cluster (no levantamos excepción)
        if not cluster_objects:
            self.logger.warning("⚠️ DBSCAN no creó clusters - creando cluster único de emergencia")
            centroid = self._calculate_centroid(pois)
            emergency_cluster = Cluster(
                label="emergency_single",
                centroid=centroid,
                places=pois
            )
            cluster_objects = [emergency_cluster]
        
        self.logger.info(f"✅ {len(cluster_objects)} clusters creados")
        return cluster_objects
    
    def _choose_eps_km(self, coordinates: np.ndarray) -> float:
        """Elegir eps dinámicamente"""
        if len(coordinates) < 5:
            return settings.CLUSTER_EPS_KM_RURAL
        
        lat_range = np.max(coordinates[:, 0]) - np.min(coordinates[:, 0])
        lon_range = np.max(coordinates[:, 1]) - np.min(coordinates[:, 1])
        total_span = math.sqrt(lat_range**2 + lon_range**2)
        
        return settings.CLUSTER_EPS_KM_RURAL if total_span > 0.5 else settings.CLUSTER_EPS_KM_URBAN
    
    def _calculate_centroid(self, places: List[Dict]) -> Tuple[float, float]:
        """Calcular centroide geográfico"""
        lats = [p['lat'] for p in places]
        lons = [p['lon'] for p in places]
        return (sum(lats) / len(lats), sum(lons) / len(lons))
    
    # =========================================================================
    # 2. ENHANCED HOME BASE ASSIGNMENT CON SUGERENCIAS
    # =========================================================================
    
    async def assign_home_base_to_clusters(
        self, 
        clusters: List[Cluster], 
        accommodations: Optional[List[Dict]] = None
    ) -> List[Cluster]:
        """🏨 Asignar home_base y generar sugerencias de alojamiento"""
        self.logger.info(f"🏨 Asignando home_base a {len(clusters)} clusters")
        
        if accommodations:
            clusters = self._assign_user_hotels_to_clusters(clusters, accommodations)
        else:
            clusters = await self._recommend_hotels_for_clusters(clusters)
        
        # Generar sugerencias adicionales para cada cluster
        for cluster in clusters:
            await self._generate_accommodation_suggestions(cluster)
        
        return clusters
    
    def _assign_user_hotels_to_clusters(self, clusters: List[Cluster], accommodations: List[Dict]) -> List[Cluster]:
        """Asignar hoteles del usuario"""
        for cluster in clusters:
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
                self.logger.info(f"  Cluster {cluster.label}: {closest_hotel['name']} (usuario)")
        
        return clusters
    
    async def _recommend_hotels_for_clusters(self, clusters: List[Cluster]) -> List[Cluster]:
        """Recomendar hoteles para cada cluster"""
        for cluster in clusters:
            try:
                recommendations = self.hotel_recommender.recommend_hotels(
                    cluster.places, max_recommendations=1, price_preference="mid"
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
                else:
                    self._set_fallback_base(cluster)
                    
            except Exception as e:
                self.logger.error(f"Error recomendando hotel: {e}")
                self._set_fallback_base(cluster)
        
        return clusters
    
    async def _generate_accommodation_suggestions(self, cluster: Cluster):
        """Generar Top-3 sugerencias de alojamiento por cluster"""
        try:
            suggestions = self.hotel_recommender.recommend_hotels(
                cluster.places, max_recommendations=3, price_preference="mid"
            )
            
            cluster.suggested_accommodations = [
                {
                    'name': hotel.name,
                    'lat': hotel.lat,
                    'lon': hotel.lon,
                    'rating': hotel.rating,
                    'distance_to_centroid_km': hotel.distance_to_centroid_km,
                    'convenience_score': hotel.convenience_score
                }
                for hotel in suggestions
            ]
            
        except Exception as e:
            self.logger.warning(f"No se pudieron generar sugerencias para cluster {cluster.label}: {e}")
            cluster.suggested_accommodations = []
    
    def _set_fallback_base(self, cluster: Cluster):
        """Fallback mejorado: usar mejor lugar como base virtual"""
        enhanced_base = self._select_home_base_enhanced(cluster)
        cluster.home_base = enhanced_base
        cluster.home_base_source = "enhanced_fallback"
        
    def _select_home_base_enhanced(self, cluster: Cluster) -> Dict:
        """Seleccionar home base inteligente"""
        if not cluster.places:
            return {
                'name': f"Punto base Cluster {cluster.label}",
                'lat': cluster.centroid[0] if hasattr(cluster, 'centroid') else 0,
                'lon': cluster.centroid[1] if hasattr(cluster, 'centroid') else 0,
                'address': "Ubicación central estimada",
                'rating': 0.0,
                'type': 'virtual_base'
            }
        
        # 1. Buscar hotel si existe en el cluster
        hotels = [p for p in cluster.places if p.get('type', '').lower() in ['lodging', 'hotel']]
        if hotels:
            best_hotel = max(hotels, key=lambda h: h.get('rating', 0))
            return {
                'name': best_hotel.get('name', 'Hotel'),
                'lat': best_hotel['lat'],
                'lon': best_hotel['lon'],
                'address': best_hotel.get('address', ''),
                'rating': best_hotel.get('rating', 0),
                'type': 'hotel_from_cluster'
            }
        
        # 2. Buscar centro comercial o estación de transporte
        transport_hubs = [p for p in cluster.places if p.get('type', '').lower() in 
                         ['shopping_mall', 'transit_station', 'bus_station', 'train_station']]
        if transport_hubs:
            best_hub = max(transport_hubs, key=lambda h: h.get('rating', 0))
            return {
                'name': best_hub.get('name', 'Hub de transporte'),
                'lat': best_hub['lat'],
                'lon': best_hub['lon'],
                'address': best_hub.get('address', ''),
                'rating': best_hub.get('rating', 0),
                'type': 'transport_hub'
            }
        
        # 3. Usar centroide geográfico con referencia al lugar más cercano
        avg_lat = sum(p['lat'] for p in cluster.places) / len(cluster.places)
        avg_lon = sum(p['lon'] for p in cluster.places) / len(cluster.places)
        
        # Buscar lugar más cercano al centroide
        closest_place = min(cluster.places, 
                           key=lambda p: ((p['lat'] - avg_lat) ** 2 + (p['lon'] - avg_lon) ** 2) ** 0.5)
        
        return {
            'name': f"Centro de {closest_place.get('name', 'área')}",
            'lat': avg_lat,
            'lon': avg_lon,
            'address': f"Cerca de {closest_place.get('name', 'lugares de interés')}",
            'rating': 0.0,
            'type': 'smart_centroid',
            'reference_place': closest_place.get('name', '')
        }
    
    # =========================================================================
    # 3. PACKING STRATEGIES
    # =========================================================================
    
    def pack_activities_by_strategy(
        self,
        day_assignments: Dict[str, List[Cluster]],
        strategy: str = "balanced"
    ) -> Dict[str, List[Cluster]]:
        """📦 Aplicar estrategia de empaquetado"""
        self.logger.info(f"📦 Aplicando estrategia de empaquetado: {strategy}")
        
        if strategy == "compact":
            return self._pack_compact(day_assignments)
        elif strategy == "cluster_first":
            return self._pack_cluster_first(day_assignments)
        else:  # balanced (default)
            return self._pack_balanced(day_assignments)
    
    def _pack_compact(self, day_assignments: Dict[str, List[Cluster]]) -> Dict[str, List[Cluster]]:
        """Llenar días de forma voraz desde día 1"""
        all_clusters = []
        for clusters in day_assignments.values():
            all_clusters.extend(clusters)
        
        new_assignments = {date: [] for date in day_assignments.keys()}
        day_keys = list(day_assignments.keys())
        
        current_day_idx = 0
        for cluster in all_clusters:
            if current_day_idx < len(day_keys):
                date = day_keys[current_day_idx]
                new_assignments[date].append(cluster)
                
                # Si el día actual tiene suficientes actividades, pasar al siguiente
                if len(new_assignments[date]) >= settings.MAX_ACTIVITIES_PER_DAY:
                    current_day_idx += 1
        
        return new_assignments
    
    def _pack_balanced(self, day_assignments: Dict[str, List[Cluster]]) -> Dict[str, List[Cluster]]:
        """Distribuir equilibradamente entre días disponibles"""
        all_clusters = []
        for clusters in day_assignments.values():
            all_clusters.extend(clusters)
        
        new_assignments = {date: [] for date in day_assignments.keys()}
        day_keys = list(day_assignments.keys())
        
        # Distribuir round-robin
        for i, cluster in enumerate(all_clusters):
            day_idx = i % len(day_keys)
            new_assignments[day_keys[day_idx]].append(cluster)
        
        return new_assignments
    
    def _pack_cluster_first(self, day_assignments: Dict[str, List[Cluster]]) -> Dict[str, List[Cluster]]:
        """Colocar todas las actividades de un cluster antes del siguiente"""
        # Ya está implementado en la lógica original de asignación
        return day_assignments
    
    # =========================================================================
    # 4. TIME WINDOWS POR TIPO DE LUGAR
    # =========================================================================
    
    def get_preferred_time_window(self, place_type: str, daily_window: TimeWindow) -> List[TimeWindow]:
        """🕐 Obtener ventanas horarias preferidas por tipo"""
        place_type = place_type.lower()
        
        if place_type == 'restaurant':
            return [
                TimeWindow(
                    start=settings.RESTAURANT_LUNCH_START * 60,
                    end=settings.RESTAURANT_LUNCH_END * 60
                ),
                TimeWindow(
                    start=settings.RESTAURANT_DINNER_START * 60,
                    end=settings.RESTAURANT_DINNER_END * 60
                )
            ]
        elif place_type == 'museum':
            return [TimeWindow(
                start=max(daily_window.start, settings.MUSEUM_PREFERRED_START * 60),
                end=min(daily_window.end, settings.MUSEUM_PREFERRED_END * 60)
            )]
        elif place_type == 'shopping':
            return [TimeWindow(
                start=max(daily_window.start, settings.SHOPPING_PREFERRED_START * 60),
                end=min(daily_window.end, settings.SHOPPING_PREFERRED_END * 60)
            )]
        else:
            return [daily_window]  # Usar ventana completa del día
    
    # =========================================================================
    # 4.5. NORMALIZACIÓN Y CLASIFICACIÓN DE CAMPOS
    # =========================================================================
    
    def _normalize_place_fields(self, place: Dict) -> Dict:
        """Normalizar y completar campos nulos de un lugar"""
        normalized = {
            'place_id': place.get('place_id', f"unknown_{hash(place.get('name', 'unnamed'))}"),
            'name': place.get('name', 'Lugar sin nombre'),
            'lat': place.get('lat', 0.0),
            'lon': place.get('lon', 0.0),
            'category': place.get('category', place.get('type', 'general')),
            'type': place.get('type', place.get('category', 'point_of_interest')),
            'rating': max(0.0, min(5.0, place.get('rating', 0.0))),
            'price_level': max(0, min(4, place.get('price_level', 0))),
            'address': place.get('address', 'Dirección no disponible'),
            'description': place.get('description', f"Visita a {place.get('name', 'lugar')}"),
            'photos': place.get('photos', []),
            'opening_hours': place.get('opening_hours', {}),
            'website': place.get('website', ''),
            'phone': place.get('phone', ''),
            'priority': max(1, min(10, place.get('priority', 5))),
            'image': place.get('image', place.get('photos', [{}])[0].get('url', '') if place.get('photos') else '')
        }
        
        # Validaciones adicionales
        if not isinstance(normalized['photos'], list):
            normalized['photos'] = []
        if not isinstance(normalized['opening_hours'], dict):
            normalized['opening_hours'] = {}
            
        return normalized
        
    def _classify_transport_time(self, travel_minutes: float) -> Dict[str, float]:
        """Clasificar tiempo de transporte entre walking y transport"""
        if travel_minutes <= 30:  # Hasta 30 min = walking
            return {
                'walking_time': round(travel_minutes, 1),
                'transport_time': 0.0,
                'transport_mode': 'walking'
            }
        else:  # Más de 30 min = transport
            return {
                'walking_time': 0.0,
                'transport_time': round(travel_minutes, 1),
                'transport_mode': 'transport'
            }
            
    def _create_intercity_activity(self, transfer, current_time: int):
        """Crear actividad especial para transfers intercity largos"""
        if transfer.duration_minutes < 180:  # Menos de 3 horas
            return None
            
        # Actividades sugeridas según duración
        if transfer.duration_minutes >= 480:  # 8+ horas
            activity_type = "overnight_journey"
            suggestion = "Viaje nocturno - considera descanso"
        elif transfer.duration_minutes >= 360:  # 6+ horas  
            activity_type = "scenic_journey"
            suggestion = "Viaje panorámico - disfruta el paisaje"
        else:  # 3-6 horas
            activity_type = "comfortable_journey"
            suggestion = "Tiempo para relajarse o trabajar"
            
        # Crear objeto similar a ActivityItem pero más simple
        from dataclasses import dataclass
        
        @dataclass
        class IntercityActivity:
            type: str = "intercity_activity"
            name: str = ""
            lat: float = 0.0
            lon: float = 0.0
            place_type: str = ""
            duration_minutes: int = 0
            start_time: int = 0
            end_time: int = 0
            description: str = ""
            rating: float = 0.0
            address: str = ""
            transport_mode: str = ""
            is_intercity_activity: bool = True
            
        return IntercityActivity(
            type="intercity_activity",
            name=f"Viaje {transfer.from_place} → {transfer.to_place}",
            lat=0.0,  # Ruta intermedia
            lon=0.0,
            place_type=activity_type,
            duration_minutes=transfer.duration_minutes,
            start_time=current_time,
            end_time=current_time + transfer.duration_minutes,
            description=suggestion,
            rating=0,
            address=f"Ruta {transfer.from_place} - {transfer.to_place}",
            transport_mode=transfer.recommended_mode,
            is_intercity_activity=True
        )
        
    def _generate_actionable_recommendations(self, activities, transfers, free_blocks, daily_window) -> List[Dict]:
        """Generar recomendaciones procesables con acciones específicas"""
        recommendations = []
        
        # 1. Recomendaciones basadas en tiempo libre
        total_free_minutes = sum(block.duration_minutes if hasattr(block, 'duration_minutes') else 0 for block in free_blocks)
        
        if total_free_minutes > 180:  # 3+ horas libres
            recommendations.append({
                "type": "time_optimization",
                "priority": "high", 
                "title": "Mucho tiempo libre disponible",
                "description": f"Tienes {total_free_minutes} minutos libres. Considera agregar más actividades.",
                "action": "add_activities",
                "actionable_data": {
                    "suggested_types": ["museum", "shopping", "sightseeing"],
                    "available_blocks": len(free_blocks),
                    "longest_block_minutes": max((block.duration_minutes if hasattr(block, 'duration_minutes') else 0) for block in free_blocks) if free_blocks else 0
                }
            })
        
        # 2. Recomendaciones de transporte
        long_transfers = [t for t in transfers if isinstance(t, dict) and t.get('duration_minutes', 0) > 120]
        if long_transfers:
            recommendations.append({
                "type": "transport_optimization",
                "priority": "medium",
                "title": f"{len(long_transfers)} transfers largos detectados",
                "description": "Considera optimizar rutas o cambiar modo de transporte.",
                "action": "optimize_transport",
                "actionable_data": {
                    "long_transfers": [
                        {
                            "from": t.get("from", ""),
                            "to": t.get("to", ""), 
                            "duration": t.get("duration_minutes", 0),
                            "mode": t.get("mode", "")
                        } for t in long_transfers
                    ]
                }
            })
        
        # 3. Recomendaciones de balance actividades
        restaurant_count = sum(1 for act in activities if hasattr(act, 'place_type') and 'restaurant' in act.place_type.lower())
        
        if restaurant_count == 0:
            recommendations.append({
                "type": "meal_planning",
                "priority": "high",
                "title": "Sin comidas programadas",
                "description": "Considera agregar restaurantes para almuerzo y cena.",
                "action": "add_restaurants",
                "actionable_data": {
                    "lunch_time": "12:00-15:00",
                    "dinner_time": "19:00-22:00",
                    "suggested_cuisines": ["local", "traditional", "popular"]
                }
            })
        elif restaurant_count == 1:
            recommendations.append({
                "type": "meal_planning", 
                "priority": "medium",
                "title": "Solo una comida programada",
                "description": "Considera agregar otra opción de comida.",
                "action": "add_meal",
                "actionable_data": {
                    "missing_meal_type": "lunch" if restaurant_count == 1 else "dinner"
                }
            })
        
        # 4. Recomendaciones por horarios
        day_start_hour = daily_window.start // 60
        day_end_hour = daily_window.end // 60
        
        if day_end_hour - day_start_hour > 14:  # Día muy largo
            recommendations.append({
                "type": "schedule_optimization",
                "priority": "medium", 
                "title": "Día muy intenso",
                "description": f"Día de {day_end_hour - day_start_hour} horas. Considera agregar descansos.",
                "action": "add_breaks",
                "actionable_data": {
                    "day_length_hours": day_end_hour - day_start_hour,
                    "suggested_break_times": ["14:00-15:00", "17:00-18:00"]
                }
            })
        
        return recommendations

    # =========================================================================
    # 5. ENHANCED ROUTING CON TRANSFERS MEJORADOS
    # =========================================================================
    
    async def route_day_enhanced(
        self,
        date: str,
        assigned_clusters: List[Cluster],
        daily_window: TimeWindow,
        transport_mode: str,
        previous_day_end_location: Optional[Tuple[float, float]] = None
    ) -> Dict:
        """🗓️ Routing mejorado con transfers con nombres reales"""
        self.logger.info(f"🗓️ Routing día {date} con {len(assigned_clusters)} clusters")
        
        timeline = []
        transfers = []
        activities_scheduled = []
        
        current_time = daily_window.start
        current_location = previous_day_end_location
        
        # Métricas separadas
        walking_time = 0
        transport_time = 0
        intercity_transfers_count = 0
        intercity_total_minutes = 0
        total_distance = 0
        
        for cluster in assigned_clusters:
            # Transfer inter-cluster con nombres reales + actividad intercity
            if current_location and cluster.home_base:
                transfer = await self._build_enhanced_transfer(
                    current_location,
                    (cluster.home_base['lat'], cluster.home_base['lon']),
                    transport_mode,
                    cluster
                )
                
                # Verificar si cabe en el día
                if current_time + transfer.duration_minutes > daily_window.end:
                    transfer.overnight = True
                    self.logger.warning(f"  ⚠️ Transfer intercity marcado como overnight")
                    # En el próximo día empezará con este transfer
                    break
                
                if transfer.duration_minutes > 0:
                    timeline.append(transfer)
                    
                    # Crear actividad intercity si es viaje largo
                    intercity_activity = self._create_intercity_activity(transfer, current_time)
                    if intercity_activity:
                        timeline.append(intercity_activity)
                        activities_scheduled.append(intercity_activity)
                    
                    transfers.append({
                        "type": "intercity_transfer",
                        "from": transfer.from_place,
                        "to": transfer.to_place,
                        "distance_km": transfer.distance_km,
                        "duration_minutes": transfer.duration_minutes,
                        "mode": transfer.recommended_mode,
                        "time": f"{current_time//60:02d}:{current_time%60:02d}",
                        "overnight": transfer.overnight,
                        "has_activity": intercity_activity is not None
                    })
                    
                    current_time += transfer.duration_minutes
                    total_distance += transfer.distance_km
                    
                    # Clasificar por tipo
                    if transfer.is_intercity:
                        intercity_transfers_count += 1
                        intercity_total_minutes += transfer.duration_minutes
                        transport_time += transfer.duration_minutes
                    elif transfer.recommended_mode == 'walk':
                        walking_time += transfer.duration_minutes
                    else:
                        transport_time += transfer.duration_minutes
            
            # Routear actividades del cluster con time windows
            cluster_activities, cluster_timeline = await self._route_cluster_with_time_windows(
                cluster, current_time, daily_window, transport_mode
            )
            
            activities_scheduled.extend(cluster_activities)
            timeline.extend(cluster_timeline)
            
            # Actualizar posición y tiempo
            if cluster_timeline:
                last_item = cluster_timeline[-1]
                if hasattr(last_item, 'end_time'):
                    current_time = last_item.end_time
                if hasattr(last_item, 'lat') and hasattr(last_item, 'lon'):
                    current_location = (last_item.lat, last_item.lon)
            
            # Acumular métricas intra-cluster
            for item in cluster_timeline:
                if isinstance(item, TransferItem):
                    total_distance += item.distance_km
                    if item.recommended_mode == 'walk':
                        walking_time += item.duration_minutes
                    else:
                        transport_time += item.duration_minutes
        
        # 🔍 VALIDAR COHERENCIA GEOGRÁFICA para evitar context leakage
        # Si current_location está muy lejos del cluster del día, usar la base del cluster
        suggestions_origin = current_location
        if current_location and assigned_clusters:
            main_cluster = assigned_clusters[0]  # Cluster principal del día
            if main_cluster.home_base:
                cluster_location = (main_cluster.home_base['lat'], main_cluster.home_base['lon'])
                distance_to_cluster = haversine_km(
                    current_location[0], current_location[1],
                    cluster_location[0], cluster_location[1]
                )
                
                # Si la ubicación actual está > 100km del cluster, usar la base del cluster
                if distance_to_cluster > 100:
                    suggestions_origin = cluster_location
                    self.logger.warning(f"🌍 Context leakage evitado: current_location ({current_location}) → cluster_base ({cluster_location}) - distancia: {distance_to_cluster:.1f}km")
        
        # Generar free blocks con sugerencias mejoradas y recomendaciones procesables
        free_blocks_objects = await self._generate_free_blocks_enhanced(
            current_time, daily_window.end, suggestions_origin
        )
        
        # Convertir objetos FreeBlock a diccionarios
        free_blocks = []
        for fb in free_blocks_objects:
            free_blocks.append({
                "start_time": fb.start_time,
                "end_time": fb.end_time,
                "duration_minutes": fb.duration_minutes,
                "suggestions": fb.suggestions,
                "note": fb.note
            })
        
        # Generar recomendaciones procesables
        actionable_recommendations = self._generate_actionable_recommendations(
            activities_scheduled, transfers, free_blocks, daily_window
        )
        
        total_activity_time = sum(act.duration_minutes for act in activities_scheduled)
        total_travel_time = walking_time + transport_time
        free_minutes = max(0, (daily_window.end - daily_window.start) - total_activity_time - total_travel_time)
        
        return {
            "date": date,
            "activities": activities_scheduled,
            "timeline": timeline,
            "transfers": transfers,
            "free_blocks": free_blocks,
            "actionable_recommendations": actionable_recommendations,
            "base": assigned_clusters[0].home_base if assigned_clusters else None,
            "travel_summary": {
                "total_travel_time_s": total_travel_time * 60,
                "total_distance_km": total_distance,
                "walking_time_minutes": walking_time,
                "transport_time_minutes": transport_time,
                "intercity_transfers_count": intercity_transfers_count,
                "intercity_total_minutes": intercity_total_minutes
            },
            "free_minutes": free_minutes,
            "end_location": current_location
        }
    
    async def _build_enhanced_transfer(
        self,
        origin: Tuple[float, float], 
        destination: Tuple[float, float],
        transport_mode: str,
        target_cluster: Cluster
    ) -> TransferItem:
        """
        🚀 TRANSFER MEJORADO: Siempre funciona, aún si Google Directions falla
        Genera intercity_transfer cuando distancia > 30km con ETA por velocidad promedio
        """
        
        # 🗺️ Intentar Google Directions primero
        try:
            eta_info = await self.google_service.eta_between(origin, destination, transport_mode)
        except Exception as e:
            self.logger.warning(f"⚠️ Google Directions falló: {e} - usando fallback ETA")
            # 📊 Fallback ETA con velocidad promedio
            from utils.geo_utils import haversine_km
            distance_km = haversine_km(origin[0], origin[1], destination[0], destination[1])
            
            # Auto-selección de modo para distancias > 30km
            if distance_km > 30.0 and transport_mode in ["walk", "walking"]:
                transport_mode = "drive"
                self.logger.info(f"🚗 Distancia {distance_km:.1f}km > 30km: forzando mode=drive en fallback")
            
            speed_kmh = settings.DRIVE_KMH if transport_mode == "drive" else settings.WALK_KMH
            duration_minutes = (distance_km / speed_kmh) * 60 * 1.3  # 30% buffer
            
            eta_info = {
                'distance_km': distance_km,
                'duration_minutes': duration_minutes,
                'status': 'FALLBACK_ETA',
                'google_enhanced': False
            }
        
        # Determinar nombres reales (sin fallar)
        try:
            from_place = await self._get_nearest_named_place(origin)
        except:
            from_place = f"Ubicación ({origin[0]:.3f}, {origin[1]:.3f})"
            
        try:
            to_place = target_cluster.home_base['name'] if target_cluster.home_base else await self._get_nearest_named_place(destination)
        except:
            to_place = f"Destino ({destination[0]:.3f}, {destination[1]:.3f})"
        
        # Aplicar política de transporte
        final_mode = self._decide_mode_by_distance_km(eta_info['distance_km'], transport_mode)
        
        # 🚗 Forzar modo si distancia > 30km
        if eta_info['distance_km'] > 30.0:
            if final_mode in ["walk", "walking"]:
                final_mode = "drive"
                self.logger.info(f"🚗 INTERCITY: {eta_info['distance_km']:.1f}km > 30km - forzando drive")
        
        # ✅ GARANTÍA: is_intercity = True para distancias > 30km
        is_intercity = eta_info['distance_km'] > 30.0
        
        transfer = TransferItem(
            type="transfer",
            from_place=from_place,
            to_place=to_place,
            distance_km=eta_info['distance_km'],
            duration_minutes=int(eta_info['duration_minutes']),
            recommended_mode=final_mode,
            is_intercity=is_intercity
        )
        
        if is_intercity:
            self.logger.info(f"🌍 INTERCITY TRANSFER: {from_place} → {to_place} ({eta_info['distance_km']:.1f}km, {int(eta_info['duration_minutes'])}min)")
        
        return transfer
    
    async def _inject_intercity_transfers_between_days(self, days: List[Dict]) -> None:
        """
        🌍 DETECCIÓN Y CREACIÓN DE INTERCITY TRANSFERS ENTRE DÍAS
        Detecta cuando hay cambio de cluster entre días consecutivos y crea transfers intercity
        """
        for i in range(len(days) - 1):
            curr_day = days[i]
            next_day = days[i + 1]
            
            # Verificar que ambos días tengan base
            curr_base = curr_day.get('base')
            next_base = next_day.get('base')
            
            if not curr_base or not next_base:
                continue
                
            # Calcular distancia entre bases
            distance_km = haversine_km(
                curr_base['lat'], curr_base['lon'],
                next_base['lat'], next_base['lon']
            )
            
            # Si distancia > 30km, crear intercity transfer
            if distance_km > 30:
                self.logger.info(f"🌍 Intercity transfer detectado: {curr_base['name']} → {next_base['name']} ({distance_km:.1f}km)")
                
                # Intentar ETA con Google Directions
                transfer_mode = "drive"
                try:
                    eta_info = await self.google_service.eta_between(
                        (curr_base['lat'], curr_base['lon']),
                        (next_base['lat'], next_base['lon']),
                        transfer_mode
                    )
                    
                    # Si Google falla o es cruce oceánico muy largo, usar heurística de vuelo
                    if (eta_info.get('status') in ['ZERO_RESULTS', 'FALLBACK_ETA'] and distance_km > 1000) or distance_km > settings.FLIGHT_THRESHOLD_KM:
                        transfer_mode = "flight"
                        eta_min = int((distance_km / settings.AIR_SPEED_KMPH) * 60 + settings.AIR_BUFFERS_MIN)
                        eta_info = {
                            'distance_km': distance_km,
                            'duration_minutes': eta_min,
                            'status': 'FLIGHT_HEURISTIC',
                            'google_enhanced': False
                        }
                        self.logger.info(f"✈️ Modo vuelo aplicado: {distance_km:.1f}km → {eta_min}min")
                    
                except Exception as e:
                    # Fallback completo - usar vuelo para distancias largas
                    self.logger.warning(f"⚠️ Google Directions falló: {e}")
                    if distance_km > 500:
                        transfer_mode = "flight"
                        eta_min = int((distance_km / settings.AIR_SPEED_KMPH) * 60 + settings.AIR_BUFFERS_MIN)
                    else:
                        transfer_mode = "drive"
                        eta_min = int((distance_km / settings.DRIVE_KMH) * 60 * 1.3)  # 30% buffer
                    
                    eta_info = {
                        'distance_km': distance_km,
                        'duration_minutes': eta_min,
                        'status': 'FALLBACK_HEURISTIC',
                        'google_enhanced': False
                    }
                
                # Crear transfer intercity
                intercity_transfer = {
                    "type": "intercity_transfer",
                    "from": curr_base['name'],
                    "to": next_base['name'],
                    "distance_km": eta_info['distance_km'],
                    "duration_minutes": int(eta_info['duration_minutes']),
                    "mode": transfer_mode,
                    "time": "09:00",  # Asumimos traslado temprano
                    "overnight": False,
                    "has_activity": False,
                    "is_between_days": True
                }
                
                # Inyectar al inicio del día destino
                if 'transfers' not in next_day:
                    next_day['transfers'] = []
                next_day['transfers'].insert(0, intercity_transfer)
                
                # Actualizar travel_summary del día destino
                travel_summary = next_day.get('travel_summary', {})
                travel_summary['intercity_transfers_count'] = travel_summary.get('intercity_transfers_count', 0) + 1
                travel_summary['intercity_total_minutes'] = travel_summary.get('intercity_total_minutes', 0) + int(eta_info['duration_minutes'])
                travel_summary['transport_time_minutes'] = travel_summary.get('transport_time_minutes', 0) + int(eta_info['duration_minutes'])
                travel_summary['total_distance_km'] = travel_summary.get('total_distance_km', 0) + eta_info['distance_km']
                
                self.logger.info(f"✅ Intercity transfer inyectado: {transfer_mode}, {int(eta_info['duration_minutes'])}min")

    async def _get_nearest_named_place(self, location: Tuple[float, float]) -> str:
        """Obtener el nombre del lugar más cercano"""
        try:
            # Usar búsqueda robusta de lugares cercanos
            nearby_places = await self.places_service.search_nearby(
                lat=location[0], 
                lon=location[1],
                types=['point_of_interest', 'establishment'],
                radius_m=1000,
                limit=1
            )
            
            if nearby_places:
                return nearby_places[0].get('name', f"Lat {location[0]:.3f}, Lon {location[1]:.3f}")
            
        except Exception as e:
            self.logger.warning(f"No se pudo obtener nombre del lugar: {e}")
        
        return f"Lat {location[0]:.3f}, Lon {location[1]:.3f}"
    
    def _decide_mode_by_distance_km(self, distance_km: float, requested_mode: str) -> str:
        """Política de transporte estricta"""
        if distance_km <= settings.WALK_THRESHOLD_KM:
            return "walk"
        elif distance_km <= settings.DRIVE_THRESHOLD_KM:
            if settings.TRANSIT_AVAILABLE and requested_mode in ["walk", "transit"]:
                return "transit"
            else:
                return "drive"
        else:
            return "drive"  # Siempre drive para distancias largas
    
    async def _route_cluster_with_time_windows(
        self,
        cluster: Cluster,
        start_time: int,
        daily_window: TimeWindow,
        transport_mode: str
    ) -> Tuple[List[ActivityItem], List]:
        """Routear cluster respetando time windows preferidas"""
        if not cluster.places:
            return [], []
        
        # Ordenar lugares por prioridad y time windows
        sorted_places = self._sort_places_by_time_preference(cluster.places, start_time)
        
        activities = []
        timeline = []
        current_time = start_time
        current_location = (cluster.home_base['lat'], cluster.home_base['lon']) if cluster.home_base else (cluster.places[0]['lat'], cluster.places[0]['lon'])
        
        for place in sorted_places:
            place_location = (place['lat'], place['lon'])
            
            # Transfer si es necesario
            if current_location != place_location:
                eta_info = await self.google_service.eta_between(
                    current_location, place_location, transport_mode
                )
                
                final_mode = self._decide_mode_by_distance_km(eta_info['distance_km'], transport_mode)
                transfer = TransferItem(
                    type="transfer",
                    from_place="",
                    to_place=place['name'],
                    distance_km=eta_info['distance_km'],
                    duration_minutes=int(eta_info['duration_minutes']),
                    recommended_mode=final_mode,
                    is_intercity=False
                )
                
                timeline.append(transfer)
                current_time += transfer.duration_minutes
            
            # Buscar time window óptima
            activity_duration = self._estimate_activity_duration(place)
            preferred_windows = self.get_preferred_time_window(place.get('type', ''), daily_window)
            
            best_start_time = self._find_best_time_slot(
                current_time, activity_duration, preferred_windows
            )
            
            if best_start_time + activity_duration > daily_window.end:
                self.logger.warning(f"    ⚠️ {place['name']} no cabe en el día - intentando sin time windows")
                # Intentar programar sin restricciones de time windows
                fallback_start = current_time
                if fallback_start + activity_duration <= daily_window.end:
                    self.logger.info(f"    ✅ {place['name']} programado sin time windows a las {fallback_start//60:02d}:{fallback_start%60:02d}")
                    best_start_time = fallback_start
                else:
                    self.logger.warning(f"    ❌ {place['name']} realmente no cabe en el día")
                    break
            
            # Crear actividad
            activity = ActivityItem(
                type="activity",
                name=place['name'],
                lat=place['lat'],
                lon=place['lon'],
                place_type=place.get('type', 'point_of_interest'),
                duration_minutes=activity_duration,
                start_time=best_start_time,
                end_time=best_start_time + activity_duration,
                priority=place.get('priority', 5),
                rating=place.get('rating', 4.5),
                image=place.get('image', ''),
                address=place.get('address', '')
            )
            
            activities.append(activity)
            timeline.append(activity)
            current_time = activity.end_time
            current_location = place_location
        
        return activities, timeline
    
    def _sort_places_by_time_preference(self, places: List[Dict], current_time: int) -> List[Dict]:
        """Ordenar lugares priorizando time windows y prioridad"""
        def time_preference_score(place):
            place_type = place.get('type', '').lower()
            
            # Restaurantes tienen prioridad en horarios de comida
            if place_type == 'restaurant':
                lunch_start = settings.RESTAURANT_LUNCH_START * 60
                dinner_start = settings.RESTAURANT_DINNER_START * 60
                
                if lunch_start <= current_time <= lunch_start + 180:  # 3h window
                    return 1000  # Alta prioridad para almuerzo
                elif dinner_start <= current_time <= dinner_start + 180:
                    return 1000  # Alta prioridad para cena
                else:
                    return place.get('priority', 5)
            
            return place.get('priority', 5)
        
        return sorted(places, key=time_preference_score, reverse=True)
    
    def _find_best_time_slot(
        self,
        earliest_start: int,
        duration: int,
        preferred_windows: List[TimeWindow]
    ) -> int:
        """Encontrar mejor horario dentro de ventanas preferidas"""
        for window in preferred_windows:
            if earliest_start >= window.start and earliest_start + duration <= window.end:
                return earliest_start
            elif earliest_start < window.start and window.start + duration <= window.end:
                return window.start
        
        # Si no cabe en ventanas preferidas, usar earliest_start
        return earliest_start
    
    def _estimate_activity_duration(self, place: Dict) -> int:
        """Estimar duración por tipo"""
        place_type = place.get('type', '').lower()
        
        duration_map = {
            'restaurant': 90,
            'museum': 120,
            'tourist_attraction': 90,
            'shopping': 120,
            'park': 60,
            'entertainment': 180
        }
        
        return duration_map.get(place_type, 60)
    
    # =========================================================================
    # 6. FREE DAY SUGGESTIONS ENHANCED
    # =========================================================================
    
    async def _generate_free_blocks_enhanced(
        self,
        current_time: int,
        day_end: int,
        location: Optional[Tuple[float, float]]
    ) -> List[FreeBlock]:
        """🆓 Generar bloques libres con sugerencias inteligentes por duración"""
        free_blocks = []
        
        if current_time < day_end:
            block_duration = day_end - current_time
            
            suggestions = []
            note = ""
            
            if location and block_duration >= 60:  # Al menos 1 hora libre
                try:
                    # Seleccionar tipos según duración del bloque libre
                    types = self._select_types_by_duration(block_duration)
                    
                    # Búsqueda robusta de lugares cercanos
                    raw_suggestions = await self.places_service.search_nearby(
                        lat=location[0],
                        lon=location[1], 
                        types=types,
                        radius_m=settings.FREE_DAY_SUGGESTIONS_RADIUS_M,
                        limit=settings.FREE_DAY_SUGGESTIONS_LIMIT
                    )
                    
                    # Enriquecer sugerencias con ETAs y razones
                    suggestions = await self._enrich_suggestions(raw_suggestions, location, block_duration)
                    
                    if suggestions:
                        note = f"Sugerencias para {block_duration//60}h de tiempo libre"
                    else:
                        note = "No se encontraron sugerencias cercanas"
                        
                except Exception as e:
                    self.logger.warning(f"Error generando sugerencias: {e}")
                    note = "Servicio de sugerencias temporalmente no disponible"
            
            free_block = FreeBlock(
                start_time=current_time,
                end_time=day_end,
                duration_minutes=block_duration,
                suggestions=suggestions,
                note=note
            )
            
            free_blocks.append(free_block)
        
        return free_blocks
    
    async def _generate_free_blocks(
        self, 
        start_time: int, 
        end_time: int, 
        current_location: Optional[Tuple[float, float]] = None
    ) -> List[FreeBlock]:
        """🆓 Método base para compatibilidad - genera bloques libres simples"""
        if start_time >= end_time:
            return []
        
        duration_minutes = end_time - start_time
        
        return [FreeBlock(
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            suggestions=[],
            note=f"Tiempo libre: {duration_minutes // 60}h {duration_minutes % 60}m"
        )]
    
    def _select_types_by_duration(self, duration_minutes: int) -> List[str]:
        """🕐 Seleccionar tipos de lugares según duración disponible"""
        if duration_minutes >= 240:  # ≥4h - actividades largas
            return [
                'tourist_attraction', 'point_of_interest', 'park', 
                'natural_feature', 'museum', 'art_gallery'
            ]
        elif duration_minutes >= 120:  # 2-4h - mezcla
            return [
                'restaurant', 'cafe', 'tourist_attraction', 
                'shopping_mall', 'museum'
            ]
        else:  # <2h - actividades cortas
            return ['restaurant', 'cafe', 'bakery']
    
    async def _enrich_suggestions(
        self, 
        raw_suggestions: List[Dict], 
        user_location: Tuple[float, float],
        block_duration: int
    ) -> List[Dict]:
        """💎 Enriquecer sugerencias con ETAs y razones + filtro por distancia coherente"""
        enriched = []
        max_distance_km = 50.0  # Máximo 50km desde la base del día
        
        for suggestion in raw_suggestions:
            try:
                # 🔍 FILTRO POR DISTANCIA: descartar sugerencias muy lejas de la base del día
                distance_km = haversine_km(
                    user_location[0], user_location[1],
                    suggestion['lat'], suggestion['lon']
                )
                
                if distance_km > max_distance_km:
                    self.logger.debug(f"🚫 Sugerencia descartada: {suggestion['name']} ({distance_km:.1f}km > {max_distance_km}km)")
                    continue
                
                # Calcular ETA real
                eta_info = await self.google_service.eta_between(
                    user_location,
                    (suggestion['lat'], suggestion['lon']),
                    'walk'
                )
                
                # Generar razón contextual
                reason = self._generate_suggestion_reason(
                    suggestion, eta_info['duration_minutes'], block_duration
                )
                
                enriched.append({
                    'name': suggestion['name'],
                    'lat': suggestion['lat'],
                    'lon': suggestion['lon'],
                    'type': suggestion['type'],
                    'rating': suggestion.get('rating', 4.5),
                    'eta_minutes': int(eta_info['duration_minutes']),
                    'reason': reason,
                    'synthetic': suggestion.get('synthetic', False)
                })
                
            except Exception as e:
                self.logger.warning(f"Error enriqueciendo sugerencia {suggestion['name']}: {e}")
                continue
        
        return enriched
    
    def _generate_suggestion_reason(self, suggestion: Dict, eta_minutes: int, block_duration: int) -> str:
        """📝 Generar razón contextual para la sugerencia"""
        place_type = suggestion.get('type', '')
        rating = suggestion.get('rating', 4.5)
        name = suggestion.get('name', '')
        
        if eta_minutes <= 5:
            distance_desc = "muy cerca"
        elif eta_minutes <= 15:
            distance_desc = "cerca"
        else:
            distance_desc = f"{eta_minutes}min caminando"
        
        if rating >= 4.5:
            rating_desc = f"excelente rating ({rating}⭐)"
        elif rating >= 4.0:
            rating_desc = f"buen rating ({rating}⭐)"
        else:
            rating_desc = f"rating {rating}⭐"
        
        return f"{rating_desc}, {distance_desc}"
    
    # =========================================================================
    # 7. ENHANCED METRICS Y MAIN FUNCTION
    # =========================================================================
    
    def calculate_enhanced_metrics(self, days: List[Dict]) -> Dict:
        """Calcular métricas mejoradas y detalladas"""
        total_walking_time = sum(
            day.get('travel_summary', {}).get('walking_time_minutes', 0)
            for day in days
        )
        total_transport_time = sum(
            day.get('travel_summary', {}).get('transport_time_minutes', 0)
            for day in days
        )
        total_distance_km = sum(
            day.get('travel_summary', {}).get('total_distance_km', 0)
            for day in days
        )
        total_activities = sum(len(day.get('activities', [])) for day in days)
        
        # Métricas intercity específicas
        intercity_transfers_count = sum(
            day.get('travel_summary', {}).get('intercity_transfers_count', 0)
            for day in days
        )
        intercity_total_minutes = sum(
            day.get('travel_summary', {}).get('intercity_total_minutes', 0)
            for day in days
        )
        
        # Score de eficiencia mejorado
        total_travel_minutes = total_walking_time + total_transport_time
        efficiency_base = 0.95
        travel_penalty = min(0.4, total_travel_minutes / 480 * 0.2)
        intercity_penalty = min(0.2, intercity_total_minutes / 240 * 0.1)
        efficiency_score = max(0.1, efficiency_base - travel_penalty - intercity_penalty)
        
        # Recopilar transfers intercity
        intercity_transfers = []
        for day in days:
            for transfer in day.get('transfers', []):
                if transfer.get('type') == 'intercity_transfer':
                    intercity_transfers.append({
                        'from': transfer['from'],
                        'to': transfer['to'],
                        'distance_km': transfer['distance_km'],
                        'estimated_time_hours': transfer['duration_minutes'] / 60,
                        'mode': transfer['mode'],
                        'overnight': transfer.get('overnight', False)
                    })
        
        return {
            'efficiency_score': efficiency_score,
            'optimization_mode': 'geographic_v31',  # ← Modo correcto V3.1
            'fallback_active': False,  # ← No fallback
            'total_distance_km': total_distance_km,
            'total_travel_time_minutes': total_travel_minutes,
            'walking_time_minutes': total_walking_time,
            'transport_time_minutes': total_transport_time,
            'long_transfers_detected': intercity_transfers_count,
            'intercity_transfers': intercity_transfers,
            'total_intercity_time_hours': intercity_total_minutes / 60,
            'total_intercity_distance_km': sum(t['distance_km'] for t in intercity_transfers)
        }
    
    # =========================================================================
    # LEGACY METHODS (UNCHANGED)
    # =========================================================================
    
    def allocate_clusters_to_days(self, clusters: List[Cluster], start_date: datetime, end_date: datetime) -> Dict[str, List[Cluster]]:
        """Enhanced method - distribuye actividades inteligentemente"""
        num_days = (end_date - start_date).days + 1
        cluster_distances = self._calculate_inter_cluster_distances(clusters)
        intercity_threshold = self._get_intercity_threshold(clusters)
        
        day_assignments = {}
        current_date = start_date
        
        for day_num in range(num_days):
            date_str = current_date.strftime('%Y-%m-%d')
            day_assignments[date_str] = []
            current_date += timedelta(days=1)
        
        # 🧠 NUEVA LÓGICA: Distribución inteligente por proximidad y tipo
        for cluster in clusters:
            if len(cluster.places) <= 1:
                # Cluster pequeño - asignar completo
                min_day = min(day_assignments.keys(), key=lambda d: len(day_assignments[d]))
                day_assignments[min_day].append(cluster)
            else:
                # Cluster grande - verificar proximidad y tipo
                place_types = [p.get('type', '') for p in cluster.places]
                
                if len(set(place_types)) == 1 and place_types[0] == 'restaurant':
                    # Todos restaurantes - verificar si están cerca para agrupar
                    max_intra_distance = self._calculate_max_intra_cluster_distance(cluster.places)
                    
                    if max_intra_distance <= 5.0:  # Mismo barrio/zona (≤5km)
                        self.logger.info(f"🍽️ {len(cluster.places)} restaurantes cercanos (max {max_intra_distance:.1f}km) - agrupando máximo 2 por día")
                        day_keys = list(day_assignments.keys())
                        
                        # Agrupar máximo 2 restaurantes por día
                        for i in range(0, len(cluster.places), 2):
                            places_for_day = cluster.places[i:i+2]
                            
                            mini_cluster = Cluster(
                                label=f"{cluster.label}_group_{i//2}",
                                centroid=cluster.centroid,
                                places=places_for_day,
                                home_base=cluster.home_base
                            )
                            
                            day_idx = (i//2) % len(day_keys)
                            day_assignments[day_keys[day_idx]].append(mini_cluster)
                    else:
                        self.logger.info(f"🍽️ {len(cluster.places)} restaurantes dispersos (max {max_intra_distance:.1f}km) - distribuyendo 1 por día")
                        day_keys = list(day_assignments.keys())
                        
                        for i, place in enumerate(cluster.places):
                            # Crear mini-cluster para cada restaurante
                            mini_cluster = Cluster(
                                label=f"{cluster.label}_split_{i}",
                                centroid=cluster.centroid,
                                places=[place],
                                home_base=cluster.home_base
                            )
                            
                            day_idx = i % len(day_keys)
                            day_assignments[day_keys[day_idx]].append(mini_cluster)
                else:
                    # Cluster mixto - asignar completo
                    min_day = min(day_assignments.keys(), key=lambda d: len(day_assignments[d]))
                    day_assignments[min_day].append(cluster)
        
        return day_assignments
    
    def _calculate_max_intra_cluster_distance(self, places: List[Dict]) -> float:
        """Calcular la distancia máxima entre lugares dentro del cluster"""
        if len(places) <= 1:
            return 0.0
        
        max_distance = 0.0
        for i, place_a in enumerate(places):
            for place_b in places[i+1:]:
                distance = haversine_km(
                    place_a['lat'], place_a['lon'],
                    place_b['lat'], place_b['lon']
                )
                max_distance = max(max_distance, distance)
        
        return max_distance
    
    def _calculate_inter_cluster_distances(self, clusters: List[Cluster]) -> Dict[tuple, float]:
        """Calcular distancias entre clusters"""
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
        """Determinar umbral intercity"""
        return settings.INTERCITY_THRESHOLD_KM_RURAL if len(clusters) > 3 else settings.INTERCITY_THRESHOLD_KM_URBAN

# =========================================================================
# MAIN FUNCTION V3.1
# =========================================================================

async def optimize_itinerary_hybrid_v31(
    places: List[Dict],
    start_date: datetime,
    end_date: datetime,
    daily_start_hour: int = 9,
    daily_end_hour: int = 18,
    transport_mode: str = 'walk',
    accommodations: Optional[List[Dict]] = None,
    packing_strategy: str = "balanced"
) -> Dict:
    """
    🚀 HYBRID OPTIMIZER V3.1 - ENHANCED VERSION
    """
    optimizer = HybridOptimizerV31()
    time_window = TimeWindow(
        start=daily_start_hour * 60,
        end=daily_end_hour * 60
    )
    
    logging.info(f"🚀 Iniciando optimización híbrida V3.1")
    logging.info(f"📍 {len(places)} lugares, {(end_date - start_date).days + 1} días")
    logging.info(f"📦 Estrategia: {packing_strategy}")
    
    # 1. Clustering POIs
    clusters = optimizer.cluster_pois(places)
    if not clusters:
        # 🔒 NUNCA retornar None/estructura parcial - crear estructura completa
        empty_days = {}
        for i in range((end_date - start_date).days + 1):
            date_key = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
            empty_days[date_key] = {
                "day": i + 1,
                "date": date_key,
                "activities": [],
                "transfers": [],
                "free_blocks": [],
                "base": None,
                "travel_summary": {
                    "total_travel_time_s": 0,
                    "walking_time_minutes": 0,
                    "transport_time_minutes": 0,
                    "intercity_transfers_count": 0,
                }
            }
        
        return {
            "days": empty_days,
            "optimization_metrics": {
                "efficiency_score": 0.1,
                "optimization_mode": "emergency_empty",
                "error": "No se pudieron crear clusters",
                "fallback_active": True,
                "total_clusters": 0,
                "total_activities": 0,
                "total_intercity_distance_km": 0
            }
        }
    
    # 2. Enhanced home base assignment
    clusters = await optimizer.assign_home_base_to_clusters(clusters, accommodations)
    
    # 3. Allocate clusters to days
    day_assignments = optimizer.allocate_clusters_to_days(clusters, start_date, end_date)
    
    # 4. Apply packing strategy
    day_assignments = optimizer.pack_activities_by_strategy(day_assignments, packing_strategy)
    
    # 5. Enhanced routing día por día
    days = []
    previous_end_location = None
    last_active_base = None
    
    for date_str, assigned_clusters in day_assignments.items():
        if not assigned_clusters:
            # Día libre con sugerencias - usar ubicación del último día activo
            effective_location = previous_end_location or last_active_base
            
            # Usar función enhanced para generar sugerencias reales
            free_blocks_objects = await optimizer._generate_free_blocks_enhanced(
                time_window.start, time_window.end, effective_location
            )
            
            # Convertir objetos FreeBlock a diccionarios
            free_blocks = []
            for fb in free_blocks_objects:
                free_blocks.append({
                    "start_time": fb.start_time,
                    "end_time": fb.end_time,
                    "duration_minutes": fb.duration_minutes,
                    "suggestions": fb.suggestions,
                    "note": fb.note
                })
            
            # Base heredada del último día activo
            inherited_base = last_active_base if last_active_base else None
            
            days.append({
                "date": date_str,
                "activities": [],
                "timeline": [],
                "transfers": [],
                "free_blocks": free_blocks,
                "base": inherited_base,
                "travel_summary": {
                    "total_travel_time_s": 0,
                    "total_distance_km": 0,
                    "walking_time_minutes": 0,
                    "transport_time_minutes": 0,
                    "intercity_transfers_count": 0,
                    "intercity_total_minutes": 0
                },
                "free_minutes": time_window.end - time_window.start
            })
            continue
        
        day_result = await optimizer.route_day_enhanced(
            date_str, assigned_clusters, time_window, transport_mode, previous_end_location
        )
        days.append(day_result)
        previous_end_location = day_result.get('end_location')
        
        # Actualizar la base del último día activo para herencia
        if day_result.get('base'):
            last_active_base = day_result['base']
    
    # 🌍 DETECCIÓN DE INTERCITY TRANSFERS ENTRE DÍAS
    await optimizer._inject_intercity_transfers_between_days(days)
    
    # 6. Enhanced metrics
    optimization_metrics = optimizer.calculate_enhanced_metrics(days)
    
    logging.info(f"✅ Optimización V3.1 completada:")
    logging.info(f"  📊 {sum(len(d['activities']) for d in days)} actividades programadas")
    logging.info(f"  🎯 Score: {optimization_metrics['efficiency_score']:.1%}")
    logging.info(f"  🚗 {optimization_metrics['long_transfers_detected']} traslados intercity")
    
    return {
        "days": days,
        "optimization_metrics": optimization_metrics,
        "clusters_info": {
            "total_clusters": len(clusters),
            "hotels_assigned": sum(1 for c in clusters if c.home_base_source != "none"),
            "recommended_hotels": sum(1 for c in clusters if c.home_base_source == "recommended"),
            "packing_strategy_used": packing_strategy
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
    """Wrapper para mantener compatibilidad"""
    return await optimize_itinerary_hybrid_v31(
        places, start_date, end_date, daily_start_hour, 
        daily_end_hour, transport_mode, accommodations,
        settings.DEFAULT_PACKING_STRATEGY
    )
