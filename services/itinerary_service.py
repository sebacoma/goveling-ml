import asyncio
import time
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta

from ml.pipeline import DurationModelPipeline
from optimizer.advanced_optimizer import AdvancedRouteOptimizer
from models.schemas import ItineraryRequest, ItineraryResponse, DayPlan, Activity, Hotel
from utils.cache import cache_result
from utils.analytics import AnalyticsLogger

class ItineraryService:
    """Servicio principal para generación de itinerarios"""
    
    def __init__(self):
        self.ml_pipeline = DurationModelPipeline()
        self.route_optimizer = AdvancedRouteOptimizer()
        self.analytics = AnalyticsLogger()
        
    async def generate_optimized_itinerary(self, request: ItineraryRequest) -> ItineraryResponse:
        """Generación completa de itinerario con optimizaciones"""
        start_time = time.time()
        
        try:
            logging.info(f"🚀 ItineraryService iniciado con {len(request.places)} lugares")
            
            # 1. Convertir request a formato interno
            places = [self._place_to_dict(place) for place in request.places]
            logging.info(f"📝 Lugares convertidos: {[p.get('name', 'Sin nombre') for p in places]}")
            
            hotel = self._hotel_to_dict(request.hotel) if request.hotel else None
            
            # 2. Enriquecer lugares con predicciones ML
            enriched_places = await self._enrich_places_with_ml(places, request.start_date)
            logging.info(f"🤖 Lugares enriquecidos: {len(enriched_places)}")
            
            # 3. Programar lugares por días
            scheduled = self._schedule_places(
                enriched_places, request.start_date, request.end_date,
                request.daily_start_hour, request.daily_end_hour
            )
            logging.info(f"📅 Scheduler resultado: {len(scheduled.get('days', []))} días, {len(scheduled.get('unassigned', []))} no asignados")
            
            # 4. Optimizar rutas por día
            optimized_days = await self._optimize_daily_routes(
                scheduled["days"], hotel, request
            )
            logging.info(f"🗺️ Días optimizados: {len(optimized_days)}")
            
            # 5. Crear respuesta final
            response = ItineraryResponse(
                days=optimized_days,
                unassigned=[self._dict_to_place(p) for p in scheduled.get("unassigned", [])],
                generated_at=datetime.now().isoformat(),
                model_version="2.0.0"
            )
            
            # 6. Analytics
            generation_time = time.time() - start_time
            await self._log_analytics(request, response, generation_time)
            
            logging.info(f"✅ Itinerario generado en {generation_time:.3f}s")
            return response
            
        except Exception as e:
            logging.error(f"❌ Error generando itinerario: {e}")
            raise
    
    async def _enrich_places_with_ml(self, places: List[Dict], start_date) -> List[Dict]:
        """Enriquecer lugares con predicciones ML de duración"""
        enriched = []
        
        for place in places:
            enriched_place = place.copy()
            
            # Predicción ML de duración
            try:
                duration = self.ml_pipeline.predict(
                    place_type=place.get('type', 'poi'),
                    hour=12,  # Hora promedio
                    day_of_week=start_date.weekday()
                )
                enriched_place['predicted_duration_h'] = duration
            except Exception as e:
                logging.warning(f"Error prediciendo duración para {place['name']}: {e}")
                enriched_place['predicted_duration_h'] = 1.5
            
            enriched.append(enriched_place)
        
        return enriched
    
    def _schedule_places(self, places: List[Dict], start_date, end_date, 
                        daily_start_hour: int, daily_end_hour: int) -> Dict:
        """Programar lugares en días disponibles"""
        from itinerary.scheduler import schedule_places
        
        return schedule_places(
            places=places,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            daily_start_hour=daily_start_hour,
            daily_end_hour=daily_end_hour
        )
    
    async def _optimize_daily_routes(self, days: List[Dict], hotel: Dict, 
                                   request: ItineraryRequest) -> List[DayPlan]:
        """Optimizar rutas para cada día"""
        optimized_days = []
        
        # Determinar base de operaciones
        if not hotel:
            from itinerary.lodging_recommender import pick_lodging_base
            all_places = []
            for day in days:
                all_places.extend(day["activities"])
            hotel = pick_lodging_base(all_places)
        
        for day_data in days:
            try:
                # Optimizar orden de actividades
                optimized_activities = await self.route_optimizer.optimize_day_route(
                    activities=day_data["activities"],
                    start_point=hotel,
                    transport_mode=request.transport_mode,
                    daily_start_hour=request.daily_start_hour,
                    daily_end_hour=request.daily_end_hour
                )
                
                # Convertir a formato de respuesta
                activities = [
                    Activity(
                        place=act["name"],
                        start=act["start"],
                        end=act["end"],
                        duration_h=act["duration_h"],
                        lat=act["lat"],
                        lon=act["lon"],
                        type=act.get("type", "poi")
                    ) for act in optimized_activities
                ]
                
                # Calcular minutos libres
                used_minutes = sum(int(act.duration_h * 60) for act in activities)
                total_minutes = (request.daily_end_hour - request.daily_start_hour) * 60
                free_minutes = max(0, total_minutes - used_minutes)
                
                day_plan = DayPlan(
                    date=day_data["date"],
                    activities=activities,
                    lodging=Hotel(**hotel),
                    free_minutes=free_minutes
                )
                
                optimized_days.append(day_plan)
                
            except Exception as e:
                logging.error(f"Error optimizando día {day_data['date']}: {e}")
                # Crear día básico sin optimización
                basic_day = self._create_basic_day(day_data, hotel, request)
                optimized_days.append(basic_day)
        
        return optimized_days
    
    def _create_basic_day(self, day_data: Dict, hotel: Dict, 
                         request: ItineraryRequest) -> DayPlan:
        """Crear día básico sin optimización avanzada"""
        activities = [
            Activity(
                place=act["name"],
                start=act.get("start", "09:00"),
                end=act.get("end", "10:30"),
                duration_h=act.get("duration_h", 1.5),
                lat=act["lat"],
                lon=act["lon"],
                type=act.get("type", "poi")
            ) for act in day_data["activities"]
        ]
        
        return DayPlan(
            date=day_data["date"],
            activities=activities,
            lodging=Hotel(**hotel),
            free_minutes=480  # 8 horas por defecto
        )
    
    def _place_to_dict(self, place) -> Dict:
        """Convertir Place a dict"""
        return place.dict() if hasattr(place, 'dict') else place
    
    def _hotel_to_dict(self, hotel) -> Dict:
        """Convertir Hotel a dict"""
        return hotel.dict() if hasattr(hotel, 'dict') else hotel
    
    def _dict_to_place(self, place_dict: Dict):
        """Convertir dict a Place"""
        from models.schemas import Place, PlaceType
        
        return Place(
            name=place_dict["name"],
            lat=place_dict["lat"],
            lon=place_dict["lon"],
            type=PlaceType(place_dict.get("type", "museum"))
        )
    
    async def _log_analytics(self, request: ItineraryRequest, 
                           response: ItineraryResponse, duration: float):
        """Log analytics en background"""
        try:
            self.analytics.log_itinerary_generation(
                request=request.dict(),
                response=response.dict(),
                duration=duration
            )
        except Exception as e:
            logging.warning(f"Error logging analytics: {e}")
    
    def model_ready(self) -> bool:
        """Verificar si el modelo ML está listo"""
        return self.ml_pipeline.is_model_ready()
    
    async def retrain_model(self):
        """Reentrenar modelo ML en background"""
        try:
            logging.info("Iniciando reentrenamiento del modelo...")
            results = self.ml_pipeline.train()
            logging.info(f"Modelo reentrenado exitosamente: {results}")
        except Exception as e:
            logging.error(f"Error reentrenando modelo: {e}")
            raise
