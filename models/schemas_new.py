from pydantic import BaseModel, Field, validator
from typing import List, Optional, Union
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
    
    # Alojamiento
    ACCOMMODATION = "accommodation"
    LODGING = "lodging"
    
    # Otros tipos comunes
    FOOD = "food"
    ESTABLISHMENT = "establishment"
    TOURIST_ATTRACTION = "tourist_attraction"
    POINT_OF_INTEREST = "point_of_interest"

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
    lon: Optional[float] = Field(None, ge=-180, le=180)
    long: Optional[float] = Field(None, ge=-180, le=180)
    type: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[int] = Field(default=5, ge=1, le=10)
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    image: Optional[str] = None
    address: Optional[str] = None
    
    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('El nombre no puede estar vacío')
        return v.strip()
    
    @validator('lon', 'long', pre=True)
    def validate_longitude(cls, v, values):
        if v is None:
            return v
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                raise ValueError('La longitud debe ser un número válido')
        return v
    
    @validator('lat', pre=True)
    def validate_latitude(cls, v):
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                raise ValueError('La latitud debe ser un número válido')
        return v
    
    @validator('type', 'category', pre=True)
    def validate_place_type(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            # Mapear categorías comunes a tipos válidos
            category_mapping = {
                'restaurant': 'restaurant',
                'accommodation': 'accommodation',
                'shopping': 'shopping',
                'attraction': 'tourist_attraction',
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
            return category_mapping.get(normalized_type, 'point_of_interest')
        return v

    def get_longitude(self) -> float:
        """Obtener la longitud desde lon o long"""
        return self.lon if self.lon is not None else self.long

    def get_type(self) -> str:
        """Obtener el tipo desde type o category"""
        return self.type if self.type is not None else self.category

    class Config:
        validate_assignment = True
        extra = "ignore"

class ItineraryRequest(BaseModel):
    places: List[Place] = Field(..., min_items=1, max_items=50)
    start_date: Union[date, str]
    end_date: Union[date, str]
    transport_mode: Union[TransportMode, str] = TransportMode.WALK
    daily_start_hour: int = Field(default=9, ge=6, le=12)
    daily_end_hour: int = Field(default=18, ge=15, le=23)
    max_walking_distance_km: Optional[float] = Field(default=15.0, ge=1, le=50)
    max_daily_activities: int = Field(default=6, ge=1, le=10)
    preferences: Optional[dict] = Field(default_factory=dict)

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
    ACCOMMODATION = "accommodation"
    FOOD = "food"
    ESTABLISHMENT = "establishment"
    ART_GALLERY = "art_gallery"
    TOURIST_ATTRACTION = "tourist_attraction"

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
                'restaurant': 'restaurant',
                'accommodation': 'accommodation',
                'shopping': 'shopping',
                'attraction': 'tourist_attraction',
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
            return category_mapping.get(normalized_type, 'point_of_interest')
        return v

    @root_validator(pre=True)
    def check_longitude_and_type(cls, values):
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

    class Config:
        allow_population_by_field_name = True
