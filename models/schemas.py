from pydantic import BaseModel, Field, validator
from typing import List, Optional, Literal, Union
from datetime import date, time, datetime
from enum import Enum

class Coordinates(BaseModel):
    """Coordenadas geográficas"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

class TransportMode(str, Enum):
    WALK = "walk"
    DRIVE = "drive"
    TRANSIT = "transit"
    BIKE = "bike"

class PlaceType(str, Enum):
    # Tipos básicos
    RESTAURANT = "restaurant"
    CAFE = "cafe"
    BAR = "bar"
    
    # Atracciones y puntos de interés
    ATTRACTION = "attraction"
    MUSEUM = "museum"
    PARK = "park"
    CHURCH = "church"
    MONUMENT = "monument"
    VIEWPOINT = "viewpoint"
    BEACH = "beach"
    ZOO = "zoo"
    
    # Shopping y entretenimiento
    SHOPPING = "shopping"
    SHOPPING_MALL = "shopping_mall"
    STORE = "store"
    NIGHT_CLUB = "night_club"
    MOVIE_THEATER = "movie_theater"
    
    # Lugares al aire libre
    NATURAL_FEATURE = "natural_feature"
    POINT_OF_INTEREST = "point_of_interest"
    
    # Otros tipos comunes de Google Places
    LODGING = "lodging"
    FOOD = "food"
    ESTABLISHMENT = "establishment"
    ART_GALLERY = "art_gallery"
    TOURIST_ATTRACTION = "tourist_attraction"

class Place(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=100)
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(alias='long', ge=-180, le=180)  # Acepta tanto 'lon' como 'long'

    @validator('lon', pre=True)
    def validate_longitude(cls, v, values):
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                raise ValueError('La longitud debe ser un número válido')
        return v

    @validator('lat', pre=True)
    def validate_latitude(cls, v, values):
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                raise ValueError('La latitud debe ser un número válido')
        return v
    type: PlaceType = Field(alias='category')
    priority: Optional[int] = Field(default=5, ge=1, le=10)
    min_duration_hours: Optional[float] = Field(default=None, ge=0.5, le=8)
    opening_hours: Optional[str] = None
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    image: Optional[str] = None
    address: Optional[str] = None
    google_place_id: Optional[str] = None

    @validator('lon', pre=True)
    def validate_longitude(cls, v, values):
        if isinstance(v, str):
            return float(v)
        return v

    @validator('lat', pre=True)
    def validate_latitude(cls, v, values):
        if isinstance(v, str):
            return float(v)
        return v
    
    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('El nombre no puede estar vacío')
        return v.strip()
    
    @validator('type', pre=True)
    def validate_type(cls, v):
        if isinstance(v, str):
            # Mapear categorías comunes a tipos válidos
            category_mapping = {
                'restaurant': 'restaurant',
                'accommodation': 'accommodation',
                'shopping': 'shopping',
                'attraction': 'tourist_attraction',  # Mapear 'attraction' a 'tourist_attraction'
                'lodging': 'lodging',
                'cafe': 'cafe',
                'bar': 'bar',
                'store': 'store',
                'movie_theater': 'movie_theater',
                'museum': 'museum',
                'park': 'park',
                'church': 'church',
                'monument': 'monument',
                'beach': 'beach',
                'zoo': 'zoo',
                'night_club': 'night_club',
                'shopping_mall': 'shopping_mall',
                'point_of_interest': 'point_of_interest',
                'tourist_attraction': 'tourist_attraction',
                'establishment': 'establishment',
                'food': 'food'
            }
            normalized_type = v.lower().replace(' ', '_')
            return category_mapping.get(normalized_type, 'point_of_interest')  # Default a point_of_interest si no hay match
        return v

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class Accommodation(BaseModel):
    """Modelo para hoteles/alojamientos (completamente opcional)"""
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=100)
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    address: Optional[str] = None
    check_in_date: Optional[str] = None
    check_out_date: Optional[str] = None
    type: Optional[str] = Field(default="accommodation", description="hotel, airbnb, hostel, etc.")
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    image: Optional[str] = None
    google_place_id: Optional[str] = None
    category: Optional[str] = Field(default="accommodation")
    
    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('El nombre del alojamiento no puede estar vacío')
        return v.strip()
    
    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class Hotel(BaseModel):
    name: str
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    
class ItineraryRequest(BaseModel):
    places: List[Place] = Field(..., min_items=1, max_items=50)
    accommodations: Optional[List[Accommodation]] = Field(default=None, description="Hoteles/alojamientos opcionales para usar como centroides")
    start_date: Union[date, str]
    end_date: Union[date, str]
    daily_start_hour: int = Field(default=9, ge=6, le=12)
    daily_end_hour: int = Field(default=18, ge=15, le=23)
    hotel: Optional[Hotel] = None  # Mantenido para retrocompatibilidad
    transport_mode: Union[TransportMode, str] = TransportMode.WALK
    max_walking_distance_km: Optional[float] = Field(default=15.0, ge=1, le=50)
    max_daily_activities: int = Field(default=6, ge=1, le=10)
    preferences: Optional[dict] = {}

    @validator('transport_mode', pre=True)
    def validate_transport_mode(cls, v):
        if isinstance(v, str):
            # Eliminar comillas extras si las hay
            v = v.strip('"')
            return TransportMode(v.lower())
        return v

    @validator('start_date', 'end_date', pre=True)
    def validate_dates(cls, v):
        if isinstance(v, str):
            try:
                return datetime.strptime(v, '%Y-%m-%d').date()
            except ValueError as e:
                raise ValueError(f'Formato de fecha inválido. Debe ser YYYY-MM-DD: {str(e)}')
        return v
    
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
    coordinates: Optional[Coordinates] = None
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
    # Campos adicionales para recomendaciones
    name: Optional[str] = None
    category: Optional[str] = None
    estimated_duration: Optional[float] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        # Auto-genera coordinates si no están presentes
        if not self.coordinates and self.lat and self.lon:
            self.coordinates = Coordinates(latitude=self.lat, longitude=self.lon)
        # Auto-asigna name si no está presente
        if not self.name and self.place:
            self.name = self.place

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

class UserProfile(BaseModel):
    """Perfil de usuario inferido para recomendaciones"""
    preferred_categories: dict = {}
    activity_level: str = "balanced"  # indoor, outdoor, balanced
    avg_duration_preference: float = 2.0
    exploration_radius: float = 10.0  # km
    budget_level: str = "medium"  # low, medium, high
    travel_style: str = "explorer"  # explorer, relaxed, cultural, adventure
    confidence_score: float = 0.5  # Añadido campo faltante

class Recommendation(BaseModel):
    """Recomendación de lugar para días libres"""
    activity: "Activity"
    total_score: float = Field(..., ge=0.0, le=1.0)
    preference_score: float = Field(..., ge=0.0, le=1.0)
    geographic_score: float = Field(..., ge=0.0, le=1.0)
    temporal_score: float = Field(..., ge=0.0, le=1.0)
    novelty_score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = ""
    suggested_day: Optional[int] = None
    day_order: Optional[int] = None

class RecommendationRequest(BaseModel):
    """Request para generar recomendaciones"""
    user_activities: List["Activity"]
    free_days: int = Field(..., ge=1, le=7)
    user_location: dict = {"latitude": -33.4489, "longitude": -70.6693}
    preferences: Optional[dict] = {}
    include_reasoning: bool = True

class RecommendationResponse(BaseModel):
    """Response con recomendaciones organizadas"""
    recommendations: List[Recommendation]
    user_profile: UserProfile
    total_recommendations: int
    recommendations_per_day: int
    confidence_level: str  # low, medium, high
    generated_at: str

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
    # Nuevos campos para recomendaciones ML
    ml_recommendations: Optional[bool] = False
    recommendation_engine: Optional[str] = None

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
    ml_recommendations: Optional[List[dict]] = None
    free_days_analysis: Optional[dict] = None
    free_day_suggestions: Optional[List[dict]] = None  # 🗓️ Sugerencias para días libres
    suggested_accommodations: Optional[dict] = None     # 🏨 Hoteles recomendados

class HotelRecommendationRequest(BaseModel):
    """Request para recomendación de hoteles basado en lugares"""
    places: List[Place]
    max_recommendations: int = Field(default=5, ge=1, le=10)
    price_preference: str = Field(default="any", pattern="^(low|medium|high|any)$")
    
    class Config:
        json_schema_extra = {
            "example": {
                "places": [
                    {
                        "name": "Mercado Central",
                        "lat": -33.4369,
                        "lon": -70.6506,
                        "type": "restaurant"
                    },
                    {
                        "name": "Plaza de Armas", 
                        "lat": -33.4378,
                        "lon": -70.6504,
                        "type": "monument"
                    }
                ],
                "max_recommendations": 5,
                "price_preference": "medium"
            }
        }
