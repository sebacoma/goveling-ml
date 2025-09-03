from pydantic import BaseModel, Field, validator
from typing import List, Optional, Literal
from datetime import date, time
from enum import Enum

class TransportMode(str, Enum):
    WALK = "walk"
    DRIVE = "drive"
    TRANSIT = "transit"
    BIKE = "bike"

class PlaceType(str, Enum):
    MUSEUM = "museum"
    PARK = "park"
    RESTAURANT = "restaurant"
    CHURCH = "church"
    MALL = "shopping_mall"
    BEACH = "beach"
    VIEWPOINT = "viewpoint"
    MONUMENT = "monument"
    CAFE = "cafe"
    ZOO = "zoo"

class Place(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    type: PlaceType
    priority: Optional[int] = Field(default=5, ge=1, le=10)
    min_duration_hours: Optional[float] = Field(default=None, ge=0.5, le=8)
    opening_hours: Optional[str] = None
    
    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('El nombre no puede estar vacío')
        return v.strip()

class Accommodation(BaseModel):
    """Modelo para hoteles/alojamientos (completamente opcional)"""
    name: str = Field(..., min_length=1, max_length=100)
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    address: Optional[str] = None
    check_in_date: Optional[str] = None
    check_out_date: Optional[str] = None
    type: Optional[str] = Field(default="hotel", description="hotel, airbnb, hostel, etc.")
    
    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('El nombre del alojamiento no puede estar vacío')
        return v.strip()

class Hotel(BaseModel):
    name: str
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    
class ItineraryRequest(BaseModel):
    places: List[Place] = Field(..., min_items=2, max_items=50)
    accommodations: Optional[List[Accommodation]] = Field(default=None, description="Hoteles/alojamientos opcionales para usar como centroides")
    start_date: date
    end_date: date
    daily_start_hour: int = Field(default=9, ge=6, le=12)
    daily_end_hour: int = Field(default=18, ge=15, le=23)
    hotel: Optional[Hotel] = None  # Mantenido para retrocompatibilidad
    transport_mode: TransportMode = TransportMode.WALK
    max_walking_distance_km: Optional[float] = Field(default=15.0, ge=1, le=50)
    max_daily_activities: int = Field(default=6, ge=1, le=10)
    preferences: Optional[dict] = {}
    
    @validator('end_date')
    def end_date_after_start(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('Fecha fin debe ser posterior a fecha inicio')
        return v
    
    @validator('daily_end_hour')
    def end_hour_after_start(cls, v, values):
        if 'daily_start_hour' in values and v <= values['daily_start_hour']:
            raise ValueError('Hora fin debe ser posterior a hora inicio')
        return v

class Activity(BaseModel):
    place: str
    start: str  # HH:MM format
    end: str
    duration_h: float
    lat: float
    lon: float
    type: PlaceType
    travel_time_to_next: Optional[float] = None
    confidence_score: Optional[float] = None
    rating: Optional[float] = None
    zone_cluster: Optional[int] = None
    priority: Optional[int] = None
    # Nuevos campos para soporte de hoteles
    hotel_name: Optional[str] = None
    hotel_distance_km: Optional[float] = None
    recommended_transport: Optional[str] = None

class TravelSummary(BaseModel):
    total_distance_m: int = 0
    total_travel_time_s: int = 0
    transport_mode: str = "walking"
    route_polyline: Optional[str] = None

class DayPlan(BaseModel):
    date: str
    activities: List[Activity]
    lodging: Optional[dict] = None  # Flexible para soportar hoteles automáticos y especificados
    free_minutes: int
    total_walking_km: Optional[float] = None
    weather_note: Optional[str] = None
    travel_summary: Optional[TravelSummary] = None
    recommendations: Optional[List[str]] = []
    hotel_based_optimization: Optional[bool] = False

class OptimizationMetrics(BaseModel):
    efficiency_score: Optional[float] = None
    total_distance_km: Optional[float] = None
    avg_travel_per_activity_min: Optional[float] = None
    google_maps_enhanced: Optional[bool] = False
    # Nuevos campos para el sistema híbrido con hoteles
    optimization_mode: Optional[str] = None
    hotels_provided: Optional[bool] = False
    hotels_count: Optional[int] = 0
    accommodation_based_clustering: Optional[bool] = False
    geographic_clustering: Optional[bool] = True

class SystemInfo(BaseModel):
    optimizer: Optional[str] = None
    version: Optional[str] = None
    google_maps_api: Optional[bool] = False
    generated_at: Optional[str] = None
    # Nuevos campos para sistema híbrido con hoteles
    auto_hotel_detection: Optional[bool] = False
    backward_compatible: Optional[bool] = True
    hotel_centroid_clustering: Optional[bool] = False
    geographic_clustering: Optional[bool] = True
    transport_recommendations: Optional[bool] = False

class ItineraryResponse(BaseModel):
    days: List[DayPlan]
    unassigned: List[Place]
    total_activities: Optional[int] = None
    total_travel_time_minutes: Optional[float] = None
    average_activities_per_day: Optional[float] = None
    total_cost_estimate: Optional[float] = None
    sustainability_score: Optional[float] = None
    generated_at: Optional[str] = None
    model_version: Optional[str] = None
    optimization_metrics: Optional[OptimizationMetrics] = None
    recommendations: Optional[List[str]] = []
    system_info: Optional[SystemInfo] = None
