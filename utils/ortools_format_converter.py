#!/usr/bin/env python3
"""
🔄 OR-Tools Format Conversion Utilities
Conversión bidireccional entre formatos legacy y OR-Tools para mantener compatibilidad

Garantiza que:
- Frontend recibe el mismo formato independiente del motor usado
- OR-Tools recibe datos en su formato esperado
- Zero breaking changes en APIs existentes

Autor: Goveling ML Team - OR-Tools Integration
Fecha: Oct 19, 2025 - Post Benchmark Analysis
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class FormatConversionResult:
    """Resultado de conversión de formato"""
    success: bool
    data: Dict[str, Any]
    warnings: List[str]
    conversion_metadata: Dict[str, Any]

class ORToolsFormatConverter:
    """
    🔄 Conversor de formatos OR-Tools ↔ Legacy
    Mantiene compatibilidad total con APIs existentes
    """
    
    def __init__(self):
        self.conversion_stats = {
            "legacy_to_ortools": 0,
            "ortools_to_legacy": 0,
            "conversion_warnings": 0
        }
        logger.info("🔄 OR-Tools Format Converter initialized")
    
    async def convert_legacy_to_ortools_format(self, legacy_request: Dict[str, Any]) -> FormatConversionResult:
        """
        📥 Convertir request legacy a formato OR-Tools
        
        Args:
            legacy_request: Request en formato actual del sistema
            
        Returns:
            FormatConversionResult con datos para OR-Tools
        """
        try:
            warnings = []
            conversion_metadata = {
                "conversion_type": "legacy_to_ortools",
                "timestamp": datetime.now().isoformat(),
                "input_keys": list(legacy_request.keys())
            }
            
            # Extraer datos básicos
            places = legacy_request.get("places", [])
            accommodations = legacy_request.get("accommodations") or []  # ✅ ARREGLADO: handle None
            start_date = legacy_request.get("start_date")
            end_date = legacy_request.get("end_date")
            
            # Convertir lugares a formato OR-Tools
            ortools_places = await self._convert_places_to_ortools(places, warnings)
            
            # Convertir accommodations a formato OR-Tools
            ortools_accommodations = await self._convert_accommodations_to_ortools(accommodations, warnings)
            
            # Convertir fechas
            ortools_dates = self._convert_dates_to_ortools(start_date, end_date, warnings)
            
            # Convertir preferencias
            ortools_preferences = self._convert_preferences_to_ortools(legacy_request, warnings)
            
            # Construir request OR-Tools
            ortools_request = {
                "places": ortools_places,
                "accommodations": ortools_accommodations,  # ✅ AÑADIDO: accommodations
                "start_date": ortools_dates["start_date"],
                "end_date": ortools_dates["end_date"],
                "preferences": ortools_preferences,
                "metadata": {
                    "original_format": "legacy",
                    "conversion_version": "1.0",
                    "places_converted": len(ortools_places),
                    "accommodations_converted": len(ortools_accommodations),  # ✅ AÑADIDO
                    "original_places_count": len(places)
                }
            }
            
            self.conversion_stats["legacy_to_ortools"] += 1
            if warnings:
                self.conversion_stats["conversion_warnings"] += len(warnings)
            
            conversion_metadata["output_keys"] = list(ortools_request.keys())
            conversion_metadata["places_converted"] = len(ortools_places)
            conversion_metadata["accommodations_converted"] = len(ortools_accommodations)
            
            logger.info(f"📥 Legacy→OR-Tools conversion: {len(places)} places → {len(ortools_places)} places, {len(ortools_accommodations)} accommodations")
            
            return FormatConversionResult(
                success=True,
                data=ortools_request,
                warnings=warnings,
                conversion_metadata=conversion_metadata
            )
            
        except Exception as e:
            logger.error(f"❌ Legacy→OR-Tools conversion failed: {e}")
            return FormatConversionResult(
                success=False,
                data={},
                warnings=[f"conversion_error: {str(e)}"],
                conversion_metadata={"error": str(e)}
            )
    
    async def convert_ortools_to_legacy_format(self, ortools_result: Dict[str, Any]) -> FormatConversionResult:
        """
        📤 Convertir resultado OR-Tools a formato legacy
        
        Args:
            ortools_result: Resultado de OR-Tools optimization
            
        Returns:
            FormatConversionResult con datos en formato legacy
        """
        try:
            warnings = []
            conversion_metadata = {
                "conversion_type": "ortools_to_legacy",
                "timestamp": datetime.now().isoformat(),
                "input_keys": list(ortools_result.keys())
            }
            
            # Convertir itinerario a estructura días legacy
            legacy_days = await self._convert_itinerary_to_legacy_days(ortools_result, warnings)
            
            # Convertir métricas de optimización
            legacy_metrics = self._convert_metrics_to_legacy(ortools_result, warnings)
            
            # Convertir clusters info (simulado para compatibilidad)
            legacy_clusters = self._convert_clusters_to_legacy(ortools_result, warnings)
            
            # Convertir recomendaciones
            legacy_recommendations = self._convert_recommendations_to_legacy(ortools_result, warnings)
            
            # Construir resultado legacy completo
            legacy_result = {
                "days": legacy_days,
                "optimization_metrics": legacy_metrics,
                "clusters_info": legacy_clusters,
                "additional_recommendations": legacy_recommendations,
                # Metadata OR-Tools (transparente para frontend legacy)
                "_ortools_metadata": {
                    "algorithm_used": "ortools_professional",
                    "conversion_version": "1.0",
                    "original_result_keys": list(ortools_result.keys()),
                    "conversion_timestamp": datetime.now().isoformat()
                }
            }
            
            self.conversion_stats["ortools_to_legacy"] += 1
            if warnings:
                self.conversion_stats["conversion_warnings"] += len(warnings)
            
            conversion_metadata["output_keys"] = list(legacy_result.keys())
            conversion_metadata["days_converted"] = len(legacy_days)
            
            logger.info(f"📤 OR-Tools→Legacy conversion: {len(legacy_days)} days converted")
            
            return FormatConversionResult(
                success=True,
                data=legacy_result,
                warnings=warnings,
                conversion_metadata=conversion_metadata
            )
            
        except Exception as e:
            logger.error(f"❌ OR-Tools→Legacy conversion failed: {e}")
            return FormatConversionResult(
                success=False,
                data={},
                warnings=[f"conversion_error: {str(e)}"],
                conversion_metadata={"error": str(e)}
            )
    
    async def _convert_places_to_ortools(self, legacy_places: List[Dict], warnings: List[str]) -> List[Dict]:
        """Convertir lugares legacy a formato OR-Tools"""
        ortools_places = []
        
        for i, place in enumerate(legacy_places):
            try:
                # Mapeo de campos legacy → OR-Tools
                ortools_place = {
                    "name": place.get("name", f"Place_{i+1}"),
                    "lat": self._extract_latitude(place),  # OR-Tools Professional espera 'lat'
                    "lon": self._extract_longitude(place),  # OR-Tools Professional espera 'lon'
                    "place_type": self._normalize_place_type(place.get("type", "tourist_attraction")),
                    "rating": place.get("rating", place.get("user_rating", 4.0)),
                    "visit_duration_minutes": self._extract_duration(place),
                    "address": place.get("address", place.get("vicinity", "")),
                    "price_level": place.get("price_level", 2),
                    "opening_hours": self._extract_opening_hours(place),
                    "metadata": {
                        "original_index": i,
                        "legacy_fields": list(place.keys()),
                        "place_id": place.get("place_id", place.get("google_place_id", ""))
                    }
                }
                
                # Validar campos requeridos
                if not self._validate_ortools_place(ortools_place):
                    warnings.append(f"place_{i}_validation_failed")
                    continue
                
                ortools_places.append(ortools_place)
                
            except Exception as e:
                warnings.append(f"place_{i}_conversion_error: {str(e)}")
                logger.warning(f"⚠️ Failed to convert place {i}: {e}")
        
        return ortools_places
    
    def _extract_latitude(self, place: Dict) -> float:
        """Extraer latitud de diferentes formatos legacy"""
        lat = place.get("lat", place.get("latitude"))
        if lat is not None:
            return float(lat)
        
        # Intentar extraer de geometry
        geometry = place.get("geometry", {})
        location = geometry.get("location", {})
        if "lat" in location:
            return float(location["lat"])
        
        # Fallback a coordenadas por defecto (Santiago)
        return -33.4372
    
    def _extract_longitude(self, place: Dict) -> float:
        """Extraer longitud de diferentes formatos legacy"""
        lon = place.get("lon", place.get("lng", place.get("longitude")))
        if lon is not None:
            return float(lon)
        
        # Intentar extraer de geometry
        geometry = place.get("geometry", {})
        location = geometry.get("location", {})
        if "lng" in location:
            return float(location["lng"])
        
        # Fallback a coordenadas por defecto (Santiago)
        return -70.6506
    
    def _normalize_place_type(self, legacy_type: str) -> str:
        """Normalizar tipos de lugar para OR-Tools"""
        type_mapping = {
            "tourist_attraction": "tourist_attraction",
            "restaurant": "restaurant",
            "museum": "museum", 
            "park": "park",
            "shopping_mall": "shopping",
            "hotel": "lodging",
            "cafe": "restaurant",
            "bar": "restaurant",
            "church": "place_of_worship",
            "beach": "natural_feature",
            "viewpoint": "tourist_attraction",
            "market": "shopping"
        }
        
        return type_mapping.get(legacy_type.lower(), "tourist_attraction")
    
    def _extract_duration(self, place: Dict) -> int:
        """Extraer duración de visita en minutos"""
        duration = place.get("duration", place.get("visit_duration"))
        
        if duration is not None:
            if isinstance(duration, str):
                # Parsear string como "1.5 hours", "90 minutes", etc.
                duration_str = duration.lower()
                if "hour" in duration_str:
                    hours = float(duration_str.split()[0])
                    return int(hours * 60)
                elif "min" in duration_str:
                    return int(duration_str.split()[0])
            else:
                return int(duration)
        
        # Duración por defecto según tipo
        place_type = place.get("type", "tourist_attraction")
        default_durations = {
            "restaurant": 90,
            "museum": 120,
            "tourist_attraction": 60,
            "park": 90,
            "shopping": 120,
            "hotel": 0  # No tiempo de visita
        }
        
        return default_durations.get(place_type, 60)
    
    def _extract_opening_hours(self, place: Dict) -> Dict[str, Any]:
        """Extraer horarios de apertura"""
        opening_hours = place.get("opening_hours", {})
        
        if opening_hours:
            return {
                "open_now": opening_hours.get("open_now", True),
                "periods": opening_hours.get("periods", []),
                "weekday_text": opening_hours.get("weekday_text", [])
            }
        
        # Horarios por defecto
        return {
            "open_now": True,
            "periods": [],
            "weekday_text": ["Monday: 9:00 AM – 6:00 PM", "Tuesday: 9:00 AM – 6:00 PM", 
                           "Wednesday: 9:00 AM – 6:00 PM", "Thursday: 9:00 AM – 6:00 PM",
                           "Friday: 9:00 AM – 6:00 PM", "Saturday: 9:00 AM – 6:00 PM",
                           "Sunday: 10:00 AM – 5:00 PM"]
        }
    
    def _validate_ortools_place(self, ortools_place: Dict) -> bool:
        """Validar que lugar OR-Tools tenga campos requeridos"""
        required_fields = ["name", "lat", "lon", "place_type"]  # OR-Tools Professional usa lat/lon
        
        for field in required_fields:
            if field not in ortools_place or ortools_place[field] is None:
                return False
        
        # Validar rango de coordenadas (Chile aproximado)
        lat = ortools_place["lat"]
        lon = ortools_place["lon"]
        
        if not (-56 <= lat <= -17 and -80 <= lon <= -66):
            return False
        
        return True
    
    def _convert_dates_to_ortools(self, start_date: Any, end_date: Any, warnings: List[str]) -> Dict[str, str]:
        """Convertir fechas a formato OR-Tools (ISO string)"""
        try:
            # Convertir start_date
            if isinstance(start_date, str):
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            elif isinstance(start_date, datetime):
                start_dt = start_date
            else:
                start_dt = datetime.now()
                warnings.append("start_date_defaulted_to_now")
            
            # Convertir end_date
            if isinstance(end_date, str):
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            elif isinstance(end_date, datetime):
                end_dt = end_date
            else:
                end_dt = start_dt + timedelta(days=1)
                warnings.append("end_date_defaulted_to_next_day")
            
            return {
                "start_date": start_dt.date().isoformat(),
                "end_date": end_dt.date().isoformat()
            }
            
        except Exception as e:
            warnings.append(f"date_conversion_error: {str(e)}")
            today = datetime.now().date()
            return {
                "start_date": today.isoformat(),
                "end_date": (today + timedelta(days=1)).isoformat()
            }
    
    def _convert_preferences_to_ortools(self, legacy_request: Dict, warnings: List[str]) -> Dict[str, Any]:
        """Convertir preferencias legacy a formato OR-Tools"""
        preferences = {
            "transport_mode": legacy_request.get("transport_mode", "driving"),
            "daily_start_hour": legacy_request.get("daily_start_hour", 9),
            "daily_end_hour": legacy_request.get("daily_end_hour", 18),
            "optimization_target": "minimize_travel_time",  # Default OR-Tools
            "max_walking_distance_km": legacy_request.get("max_walking_distance", 2.0),
            "enable_time_windows": True,
            "enable_vehicle_routing": legacy_request.get("multi_day", True),
            "constraints": {
                "max_daily_activities": legacy_request.get("max_daily_activities", 6),
                "min_daily_activities": legacy_request.get("min_daily_activities", 2),
                "lunch_time_window": {
                    "start": legacy_request.get("lunch_start", "12:00"),
                    "end": legacy_request.get("lunch_end", "15:00")
                }
            }
        }
        
        # Agregar preferencias específicas si existen
        if "budget" in legacy_request:
            preferences["budget_constraints"] = {
                "max_daily_budget": legacy_request["budget"],
                "currency": legacy_request.get("currency", "CLP")
            }
        
        if "accessibility" in legacy_request:
            preferences["accessibility_requirements"] = legacy_request["accessibility"]
        
        return preferences
    
    async def _convert_accommodations_to_ortools(self, accommodations: List[Dict], warnings: List[str]) -> List[Dict]:
        """
        🏨 Convertir accommodations legacy a formato OR-Tools
        
        Args:
            accommodations: Lista de hoteles/hostales en formato legacy
            warnings: Lista para acumular warnings
            
        Returns:
            Lista de accommodations en formato OR-Tools
        """
        ortools_accommodations = []
        
        for i, accommodation in enumerate(accommodations):
            try:
                # Mapeo de campos legacy → OR-Tools
                ortools_accommodation = {
                    "name": accommodation.get("name", f"Accommodation_{i+1}"),
                    "lat": self._extract_latitude(accommodation),
                    "lon": self._extract_longitude(accommodation),
                    "type": self._normalize_accommodation_type(accommodation.get("type", "hotel")),
                    "rating": accommodation.get("rating", 3.5),
                    "address": accommodation.get("address", ""),
                    "city": accommodation.get("city", "").lower(),
                    "price_level": accommodation.get("price_level", 2),
                    "amenities": accommodation.get("amenities", []),
                    "availability": True,  # Assume available unless specified
                    "check_in_time": accommodation.get("check_in_time", "15:00"),
                    "check_out_time": accommodation.get("check_out_time", "11:00")
                }
                
                # Validar accommodation OR-Tools
                if self._validate_ortools_accommodation(ortools_accommodation):
                    ortools_accommodations.append(ortools_accommodation)
                else:
                    warnings.append(f"invalid_accommodation_skipped: {accommodation.get('name', f'Accommodation_{i+1}')}")
                    
            except Exception as e:
                warnings.append(f"accommodation_conversion_error: {str(e)} for {accommodation.get('name', f'accommodation_{i+1}')}")
        
        return ortools_accommodations
    
    def _normalize_accommodation_type(self, type_str: str) -> str:
        """Normalizar tipos de accommodation para OR-Tools"""
        type_mapping = {
            "hotel": "hotel",
            "hostel": "hostel", 
            "motel": "motel",
            "guest_house": "guest_house",
            "apartment": "apartment",
            "lodge": "lodge",
            "inn": "inn",
            "resort": "resort"
        }
        
        normalized = type_str.lower().replace(" ", "_").replace("-", "_")
        return type_mapping.get(normalized, "hotel")  # Default a hotel
    
    def _validate_ortools_accommodation(self, ortools_accommodation: Dict) -> bool:
        """Validar que accommodation tiene campos requeridos para OR-Tools"""
        required_fields = ["name", "lat", "lon", "type", "city"]
        
        for field in required_fields:
            if field not in ortools_accommodation or ortools_accommodation[field] is None:
                return False
        
        # Validar coordenadas válidas (Chile)
        lat = ortools_accommodation["lat"]
        lon = ortools_accommodation["lon"]
        
        if not (-56 <= lat <= -17 and -80 <= lon <= -66):
            return False
        
        return True
    
    async def _convert_itinerary_to_legacy_days(self, ortools_result: Dict, warnings: List[str]) -> Dict[str, Dict]:
        """Convertir itinerario OR-Tools a estructura days legacy"""
        legacy_days = {}
        
        # Manejar formato específico de OR-Tools Professional
        if "optimized_route" in ortools_result and "optimized_pois" in ortools_result:
            return await self._convert_ortools_route_to_legacy(ortools_result, warnings)
        
        # Intentar extraer itinerario de diferentes keys posibles (formato genérico)
        itinerary_data = (
            ortools_result.get("optimized_itinerary") or 
            ortools_result.get("itinerary") or 
            ortools_result.get("days") or
            ortools_result.get("solution") or
            []
        )
        
        if not itinerary_data:
            warnings.append("no_itinerary_data_found")
            return legacy_days
        
        # Si itinerary_data es dict con días como keys
        if isinstance(itinerary_data, dict):
            for day_key, day_data in itinerary_data.items():
                legacy_day = await self._convert_day_to_legacy(day_data, day_key, warnings)
                legacy_days[day_key] = legacy_day
        
        # Si itinerary_data es lista de días
        elif isinstance(itinerary_data, list):
            for i, day_data in enumerate(itinerary_data):
                day_key = f"day_{i + 1}"
                legacy_day = await self._convert_day_to_legacy(day_data, day_key, warnings)
                legacy_days[day_key] = legacy_day
        
        return legacy_days
    
    async def _convert_ortools_route_to_legacy(self, ortools_result: Dict, warnings: List[str]) -> Dict[str, Dict]:
        """Convertir resultado específico de OR-Tools Professional a formato legacy"""
        legacy_days = {}
        
        optimized_route = ortools_result.get("optimized_route", [])
        optimized_pois = ortools_result.get("optimized_pois", [])
        
        if not optimized_route or not optimized_pois:
            warnings.append("ortools_route_data_incomplete")
            return legacy_days
        
        # Reorganizar POIs según la ruta optimizada
        ordered_pois = []
        for index in optimized_route:
            if 0 <= index < len(optimized_pois):
                ordered_pois.append(optimized_pois[index])
        
        if not ordered_pois:
            warnings.append("ortools_route_ordering_failed")
            return legacy_days
        
        # Crear día único (day_1) con todos los POIs ordenados
        day_key = "day_1"
        legacy_places = []
        
        for i, poi in enumerate(ordered_pois):
            # Estimar tiempos de visita (valores por defecto realistas)
            start_hour = 9 + (i * 2)  # Empezar a las 9:00, 2 horas entre lugares
            end_hour = start_hour + 1  # 1 hora de visita por defecto
            
            legacy_place = {
                "name": poi.get("name", f"Place {i+1}"),
                "lat": poi.get("lat", poi.get("latitude", 0)),
                "lon": poi.get("lon", poi.get("lng", poi.get("longitude", 0))),
                "type": poi.get("place_type", poi.get("type", "tourist_attraction")),
                "rating": poi.get("rating", 4.0),
                "duration": poi.get("visit_duration_minutes", 60),
                "start_time": f"{start_hour:02d}:00",
                "end_time": f"{end_hour:02d}:00",
                "travel_time_to_next": 0,  # Se calculará si es necesario
                "order": i + 1
            }
            legacy_places.append(legacy_place)
        
        # Crear estructura del día
        legacy_day = {
            "places": legacy_places,
            "total_places": len(legacy_places),
            "total_distance_km": ortools_result.get("total_distance_km", 0),
            "total_time_minutes": ortools_result.get("total_time_minutes", 0),
            "optimization_algorithm": ortools_result.get("algorithm_used", "OR_TOOLS"),
            "constraints_satisfied": ortools_result.get("constraints_satisfied", True)
        }
        
        legacy_days[day_key] = legacy_day
        return legacy_days
    
    async def _convert_day_to_legacy(self, day_data: Dict, day_key: str, warnings: List[str]) -> Dict[str, Any]:
        """Convertir día OR-Tools a formato legacy"""
        
        # Extraer lugares del día
        places = day_data.get("places", day_data.get("activities", []))
        
        # Convertir lugares a formato legacy
        legacy_places = []
        for place in places:
            legacy_place = {
                "name": place.get("name", "Unknown Place"),
                "lat": place.get("latitude", place.get("lat", 0)),
                "lon": place.get("longitude", place.get("lon", place.get("lng", 0))),
                "type": place.get("place_type", place.get("type", "tourist_attraction")),
                "rating": place.get("rating", 4.0),
                "duration": place.get("visit_duration_minutes", 60),
                "start_time": place.get("visit_start_time", ""),
                "end_time": place.get("visit_end_time", ""),
                "travel_time_to_next": place.get("travel_time_to_next", 0),
                "distance_to_next_km": place.get("distance_to_next_km", 0)
            }
            legacy_places.append(legacy_place)
        
        # Métricas del día
        total_distance = day_data.get("total_distance_km", day_data.get("distance_km", 0))
        total_time = day_data.get("total_time_hours", day_data.get("travel_time_minutes", 0) / 60)
        
        return {
            "places": legacy_places,
            "total_distance_km": total_distance,
            "total_travel_time_hours": total_time,
            "route_optimization": "ortools_tsp",
            "start_time": day_data.get("start_time", "09:00"),
            "end_time": day_data.get("end_time", "18:00"),
            "day_summary": day_data.get("summary", f"Optimized itinerary for {day_key}"),
            "optimization_notes": day_data.get("notes", [])
        }
    
    def _convert_metrics_to_legacy(self, ortools_result: Dict, warnings: List[str]) -> Dict[str, Any]:
        """Convertir métricas OR-Tools a formato legacy"""
        
        return {
            "algorithm_used": "ortools_professional",
            "total_distance_km": ortools_result.get("total_distance_km", 0),
            "total_time_minutes": ortools_result.get("total_time_minutes", 0),
            "places_optimized": ortools_result.get("places_count", 0),
            "optimization_score": ortools_result.get("optimization_score", 0),
            "execution_time_ms": ortools_result.get("execution_time_ms", 0),
            "success_rate": 1.0 if ortools_result.get("success", True) else 0.0,
            "constraints_satisfied": ortools_result.get("constraints_satisfied", True),
            "ortools_metadata": {
                "solver_status": ortools_result.get("solver_status", "OPTIMAL"),
                "solution_quality": ortools_result.get("solution_quality", "HIGH"),
                "dropped_places": ortools_result.get("dropped_places", 0)
            }
        }
    
    def _convert_clusters_to_legacy(self, ortools_result: Dict, warnings: List[str]) -> List[Dict]:
        """Convertir clusters OR-Tools a formato legacy (simulado)"""
        
        # OR-Tools no usa clustering tradicional, pero simulamos para compatibilidad
        clusters = []
        
        # Si hay información de agrupamiento en OR-Tools
        if "clusters" in ortools_result:
            for cluster in ortools_result["clusters"]:
                legacy_cluster = {
                    "cluster_id": cluster.get("id", 0),
                    "places_count": len(cluster.get("places", [])),
                    "center_lat": cluster.get("center", {}).get("lat", 0),
                    "center_lon": cluster.get("center", {}).get("lon", 0),
                    "radius_km": cluster.get("radius_km", 0),
                    "optimization_method": "ortools_vrp"
                }
                clusters.append(legacy_cluster)
        else:
            # Simular cluster único para compatibilidad
            warnings.append("clusters_simulated_for_compatibility")
            clusters.append({
                "cluster_id": 1,
                "places_count": ortools_result.get("places_count", 0),
                "center_lat": 0,
                "center_lon": 0,
                "radius_km": 0,
                "optimization_method": "ortools_single_cluster"
            })
        
        return clusters
    
    def _convert_recommendations_to_legacy(self, ortools_result: Dict, warnings: List[str]) -> List[str]:
        """Convertir recomendaciones OR-Tools a formato legacy"""
        
        recommendations = []
        
        # Extraer recomendaciones OR-Tools
        ortools_recommendations = ortools_result.get("recommendations", [])
        
        for rec in ortools_recommendations:
            if isinstance(rec, str):
                recommendations.append(rec)
            elif isinstance(rec, dict):
                recommendations.append(rec.get("text", str(rec)))
        
        # Agregar recomendaciones basadas en métricas OR-Tools
        if ortools_result.get("dropped_places", 0) > 0:
            recommendations.append(f"OR-Tools optimized route by excluding {ortools_result['dropped_places']} places that didn't fit constraints")
        
        if ortools_result.get("optimization_score", 0) > 0.8:
            recommendations.append("Excellent route optimization achieved with OR-Tools algorithm")
        
        return recommendations
    
    def get_conversion_stats(self) -> Dict[str, Any]:
        """📊 Estadísticas de conversiones realizadas"""
        total_conversions = (
            self.conversion_stats["legacy_to_ortools"] + 
            self.conversion_stats["ortools_to_legacy"]
        )
        
        return {
            "total_conversions": total_conversions,
            "legacy_to_ortools": self.conversion_stats["legacy_to_ortools"],
            "ortools_to_legacy": self.conversion_stats["ortools_to_legacy"],
            "total_warnings": self.conversion_stats["conversion_warnings"],
            "warning_rate": (
                self.conversion_stats["conversion_warnings"] / max(total_conversions, 1)
            ),
            "conversion_success_rate": 1.0  # Assumimos éxito si no hay errores
        }

# Factory function para instancia singleton
_format_converter_instance = None

def get_format_converter() -> ORToolsFormatConverter:
    """Factory function para obtener instancia singleton"""
    global _format_converter_instance
    
    if _format_converter_instance is None:
        _format_converter_instance = ORToolsFormatConverter()
    
    return _format_converter_instance

# Helper functions para uso directo
async def convert_legacy_to_ortools_format(legacy_request: Dict[str, Any]) -> FormatConversionResult:
    """Helper para conversión legacy → OR-Tools"""
    converter = get_format_converter()
    return await converter.convert_legacy_to_ortools_format(legacy_request)

async def convert_ortools_to_legacy_format(ortools_result: Dict[str, Any]) -> FormatConversionResult:
    """Helper para conversión OR-Tools → legacy"""
    converter = get_format_converter()
    return await converter.convert_ortools_to_legacy_format(ortools_result)