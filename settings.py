import os
from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///goveling.db"
    
    # ML Model
    MODEL_PATH: str = "models/duration_model.pkl"
    RETRAIN_THRESHOLD_DAYS: int = 30
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = False
    API_KEY: Optional[str] = None
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 3600
    
    # External APIs
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    
    # Business Logic
    MAX_DAILY_ACTIVITIES: int = 8
    MAX_WALKING_DISTANCE_KM: float = 15.0
    DEFAULT_ACTIVITY_BUFFER_MIN: int = 15
    
    # Horario comercial universal (MVP)
    BUSINESS_START_H: int = 9    # 09:00
    BUSINESS_END_H: int = 18     # 18:00

    # Velocidades aproximadas (para traslados)
    CITY_SPEED_KMH_WALK: float = 4.5   # caminata urbana
    CITY_SPEED_KMH_DRIVE: float = 22.0  # conducción urbana
    CITY_SPEED_KMH_BIKE: float = 15.0   # ciclismo urbana
    CITY_SPEED_KMH_TRANSIT: float = 25.0  # transporte público
    MIN_TRAVEL_MIN: int = 8     # mínimo realista por traslado
    
    # Clustering geográfico y detección de traslados largos
    CLUSTER_EPS_KM_URBAN: float = 8.0   # Radio clustering en zonas urbanas densas
    CLUSTER_EPS_KM_RURAL: float = 15.0  # Radio clustering en zonas rurales/turisticas
    CLUSTER_MIN_SAMPLES: int = 1        # Mínimo de lugares para formar un cluster
    WALK_MAX_KM: float = 2.0           # Máximo para caminar (>2km forzar auto/bus)
    INTERCITY_THRESHOLD_KM_URBAN: float = 25.0   # Umbral intercity urbano
    INTERCITY_THRESHOLD_KM_RURAL: float = 40.0   # Umbral intercity rural
    LONG_TRANSFER_MIN: int = 120       # Minutos para considerar un traslado "largo"
    
    # Velocidades para fallback cuando Google Directions falla
    WALK_KMH: float = 4.5              # Velocidad caminando
    DRIVE_KMH: float = 50.0            # Velocidad en auto (interurbano)
    TRANSIT_KMH: float = 35.0          # Velocidad transporte público
    
    # Políticas de transporte por distancia
    WALK_THRESHOLD_KM: float = 2.0     # <= 2km: caminar OK
    DRIVE_THRESHOLD_KM: float = 15.0   # > 15km: driving recomendado
    TRANSIT_AVAILABLE: bool = True      # Si hay transporte público disponible
    
    # Ventanas horarias por tipo de lugar
    RESTAURANT_LUNCH_START: int = 12    # 12:00
    RESTAURANT_LUNCH_END: int = 15      # 15:00
    RESTAURANT_DINNER_START: int = 19   # 19:00
    RESTAURANT_DINNER_END: int = 22     # 22:00
    MUSEUM_PREFERRED_START: int = 10    # 10:00
    MUSEUM_PREFERRED_END: int = 17      # 17:00
    SHOPPING_PREFERRED_START: int = 10  # 10:00
    SHOPPING_PREFERRED_END: int = 20    # 20:00
    
    # Estrategias de empaquetado
    DEFAULT_PACKING_STRATEGY: str = "balanced"  # "compact" | "balanced" | "cluster_first"
    MIN_ACTIVITIES_PER_DAY: int = 2
    MAX_ACTIVITIES_PER_DAY: int = 6
    TARGET_MINUTES_PER_DAY: int = 300   # 5 horas de actividades por día
    
    # Sugerencias para días libres
    FREE_DAY_SUGGESTIONS_RADIUS_M: int = 3000
    FREE_DAY_SUGGESTIONS_LIMIT: int = 6
    
    class Config:
        env_file = ".env"

settings = Settings()
