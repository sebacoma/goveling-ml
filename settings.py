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
    
    class Config:
        env_file = ".env"

settings = Settings()
