from pydantic import BaseModel, Field, validator, model_validator
from typing import List, Optional, Union, Literal, Dict
from datetime import date, time, datetime
from enum import Enum

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
    ACCOMMODATION = "accommodation"
    FOOD = "food"
    ESTABLISHMENT = "establishment"
    ART_GALLERY = "art_gallery"
    TOURIST_ATTRACTION = "tourist_attraction"

class TransportMode(str, Enum):
    WALK = "walk"
    DRIVE = "drive"
    TRANSIT = "transit"
    BIKE = "bike"

class Coordinates(BaseModel):
    """Coordenadas geográficas"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

class Place(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=100)
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)  # Campo primario para longitud
    long: Optional[float] = None  # Alias opcional para longitud
    type: Optional[PlaceType] = None  # Campo primario para tipo
    category: Optional[PlaceType] = None  # Alias opcional para tipo
    priority: Optional[int] = Field(default=5, ge=1, le=10)
    min_duration_hours: Optional[float] = Field(default=None, ge=0.5, le=8)
    opening_hours: Optional[str] = None
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    image: Optional[str] = None
    address: Optional[str] = None
    google_place_id: Optional[str] = None

    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('El nombre no puede estar vacío')
        return v.strip()

    @validator('lon', 'long', pre=True)
    def validate_longitude(cls, v, values):
        if v is None:
            return None
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

    @validator('type', 'category', pre=True)
    def validate_type(cls, v, values):
        if v is None:
            return None
        if isinstance(v, str):
            # Mapear categorías comunes a tipos válidos
            category_mapping = {
                'restaurant': PlaceType.RESTAURANT,
                'accommodation': PlaceType.ACCOMMODATION,
                'shopping': PlaceType.SHOPPING,
                'attraction': PlaceType.TOURIST_ATTRACTION,
                'lodging': PlaceType.LODGING,
                'cafe': PlaceType.CAFE,
                'bar': PlaceType.BAR,
                'store': PlaceType.STORE,
                'movie_theater': PlaceType.MOVIE_THEATER,
                'museum': PlaceType.MUSEUM,
                'park': PlaceType.PARK,
                'church': PlaceType.CHURCH,
                'monument': PlaceType.MONUMENT,
                'beach': PlaceType.BEACH,
                'zoo': PlaceType.ZOO,
                'night_club': PlaceType.NIGHT_CLUB,
                'shopping_mall': PlaceType.SHOPPING_MALL,
                'point_of_interest': PlaceType.POINT_OF_INTEREST,
                'tourist_attraction': PlaceType.TOURIST_ATTRACTION,
                'establishment': PlaceType.ESTABLISHMENT,
                'food': PlaceType.FOOD
            }
            normalized_type = v.lower().replace(' ', '_')
            return category_mapping.get(normalized_type, PlaceType.POINT_OF_INTEREST)
        return v

    @model_validator(mode='before')
    def check_longitude_and_type(cls, values):
        if isinstance(values, dict):
            # Manejar longitud (lon/long)
            lon = values.get('lon')
            long = values.get('long')
            if lon is None and long is not None:
                values['lon'] = long
            elif lon is not None and long is None:
                values['long'] = lon

            # Manejar tipo (type/category)
            type_val = values.get('type')
            category_val = values.get('category')
            if type_val is None and category_val is not None:
                values['type'] = category_val
            elif type_val is not None and category_val is None:
                values['category'] = type_val

        return values

    def get_longitude(self) -> float:
        """Obtener la longitud desde lon o long"""
        return self.lon if self.lon is not None else self.long

    def get_type(self) -> str:
        """Obtener el tipo desde type o category"""
        return self.type.value if self.type is not None else (self.category.value if self.category is not None else None)

    class Config:
        populate_by_name = True

class Activity(BaseModel):
    place: str
    start: str
    end: str
    duration_h: float
    lat: float
    lon: float
    type: str
    name: str
    category: str
    estimated_duration: float
    priority: int
    coordinates: Coordinates

class ItineraryRequest(BaseModel):
    places: List[Place] = Field(..., min_items=1, max_items=50)
    start_date: Union[date, str]
    end_date: Union[date, str]
    transport_mode: Union[TransportMode, str] = TransportMode.WALK
    daily_start_hour: int = Field(default=9, ge=6, le=12)
    daily_end_hour: int = Field(default=18, ge=15, le=23)
    max_walking_distance_km: Optional[float] = Field(default=15.0, ge=1, le=50)
    max_daily_activities: int = Field(default=6, ge=1, le=10)
    preferences: Optional[Dict] = Field(default_factory=dict)
    accommodations: Optional[List[Place]] = Field(default_factory=list)

    @validator('transport_mode', pre=True)
    def validate_transport_mode(cls, v):
        if isinstance(v, str):
            v = v.strip('"').lower()
            return TransportMode(v)
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

    class Config:
        validate_assignment = True
        extra = "ignore"

class ItineraryResponse(BaseModel):
    itinerary: List[Dict]
    optimization_metrics: Dict
    recommendations: List[str]

class HotelRecommendationRequest(BaseModel):
    places: List[Place]
    max_recommendations: Optional[int] = Field(default=5, ge=1, le=20)
    price_preference: Optional[str] = "any"  # "budget", "mid", "luxury", "any"

    class Config:
        validate_assignment = True
        extra = "ignore"

class PlaceSuggestion(BaseModel):
    suggestions: List[str]
    transport: str
    places: List[Dict]
    
    @classmethod
    def from_new_format(cls, data: Dict):
        """Convert new format suggestions to old format"""
        return cls(
            suggestions=data.get('suggestions', []),
            transport=data.get('transport', 'No especificado'),
            places=data.get('places', [])
        )

class PlaceSuggestionResponse(BaseModel):
    nature_escape: PlaceSuggestion
    cultural_immersion: PlaceSuggestion
    adventure_day: PlaceSuggestion
    performance: Optional[Dict] = None
