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
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    API_KEY: Optional[str] = None
    
    # Performance
    ENABLE_CACHE: bool = os.getenv("ENABLE_CACHE", "true").lower() == "true"
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "300"))
    MAX_CONCURRENT_REQUESTS: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "3"))
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 3600
    
    # External APIs
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    GOOGLE_PLACES_API_KEY: Optional[str] = os.getenv("GOOGLE_PLACES_API_KEY")
    OPENAI_API_KEY: Optional[str] = None
    ENABLE_REAL_PLACES: bool = os.getenv("ENABLE_REAL_PLACES", "true").lower() == "true"
    
    # Free Routing APIs (alternativas gratuitas a Google Directions)
    OPENROUTE_API_KEY: Optional[str] = os.getenv('OPENROUTE_API_KEY', None)  # Obtener clave gratuita en openrouteservice.org
    FREE_ROUTING_TIMEOUT: int = 8  # segundos
    ROUTING_FALLBACK_BUFFER_URBAN: float = 1.4  # 40% buffer en ciudades
    ROUTING_FALLBACK_BUFFER_RURAL: float = 1.2  # 20% buffer en zonas rurales
    
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
    AIR_SPEED_KMPH: float = 750.0      # Velocidad promedio vuelo comercial (incluyendo tiempo aeropuerto)
    AIR_BUFFERS_MIN: int = 90          # Buffers aeropuerto (check-in, security, boarding, etc.)
    
    # Políticas de transporte por distancia
    WALK_THRESHOLD_KM: float = 2.0     # <= 2km: caminar OK
    DRIVE_THRESHOLD_KM: float = 15.0   # > 15km: driving recomendado
    FLIGHT_THRESHOLD_KM: float = 1000.0 # > 1000km: vuelo recomendado
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
    FREE_DAY_SUGGESTIONS_LIMIT: int = 3  # Reducido de 6 a 3 para mejor UX
    
    # ========================================================================
    # 🧠 CITY2GRAPH CONFIGURATION - FASE 1 (FEATURE FLAGS)
    # ========================================================================
    
    # Master switch - DESHABILITADO POR DEFECTO para máxima seguridad
    ENABLE_CITY2GRAPH: bool = os.getenv("ENABLE_CITY2GRAPH", "false").lower() == "true"
    
    # Criterios de activación automática (solo para casos complejos)
    CITY2GRAPH_MIN_PLACES: int = int(os.getenv("CITY2GRAPH_MIN_PLACES", "8"))      # Mínimo 8 lugares
    CITY2GRAPH_MIN_DAYS: int = int(os.getenv("CITY2GRAPH_MIN_DAYS", "3"))          # Mínimo 3 días
    CITY2GRAPH_COMPLEXITY_THRESHOLD: float = float(os.getenv("CITY2GRAPH_COMPLEXITY_THRESHOLD", "5.0"))  # Score 0-10
    
    # Control geográfico (piloto gradual)
    CITY2GRAPH_CITIES: str = os.getenv("CITY2GRAPH_CITIES", "")  # "santiago,valparaiso" - ciudades habilitadas
    CITY2GRAPH_EXCLUDE_CITIES: str = os.getenv("CITY2GRAPH_EXCLUDE_CITIES", "")  # Ciudades excluidas explícitamente
    
    # Performance y reliability
    CITY2GRAPH_TIMEOUT_S: int = int(os.getenv("CITY2GRAPH_TIMEOUT_S", "30"))      # Timeout para City2Graph
    CITY2GRAPH_FALLBACK_ENABLED: bool = os.getenv("CITY2GRAPH_FALLBACK_ENABLED", "true").lower() == "true"
    CITY2GRAPH_MAX_CONCURRENT: int = int(os.getenv("CITY2GRAPH_MAX_CONCURRENT", "1"))  # Concurrencia limitada
    
    # Circuit Breaker configuration (Fase 2)
    CITY2GRAPH_FAILURE_THRESHOLD: int = int(os.getenv("CITY2GRAPH_FAILURE_THRESHOLD", "5"))    # Fallos antes de abrir circuit
    CITY2GRAPH_RECOVERY_TIMEOUT: int = int(os.getenv("CITY2GRAPH_RECOVERY_TIMEOUT", "300"))    # Segundos para recuperación
    
    # A/B Testing y gradual rollout
    CITY2GRAPH_USER_PERCENTAGE: int = int(os.getenv("CITY2GRAPH_USER_PERCENTAGE", "0"))  # % usuarios (0-100)
    CITY2GRAPH_TRACK_DECISIONS: bool = os.getenv("CITY2GRAPH_TRACK_DECISIONS", "true").lower() == "true"
    
    # Configuración avanzada de detección
    CITY2GRAPH_GEO_SPREAD_THRESHOLD_KM: float = float(os.getenv("CITY2GRAPH_GEO_SPREAD_THRESHOLD_KM", "50.0"))
    CITY2GRAPH_SEMANTIC_TYPES_THRESHOLD: int = int(os.getenv("CITY2GRAPH_SEMANTIC_TYPES_THRESHOLD", "3"))
    
    # ========================================================================
    # 🧮 OR-TOOLS CONFIGURATION - FASE 2 (POST-BENCHMARK INTEGRATION)
    # ========================================================================
    
    # Master switch - DESHABILITADO POR DEFECTO para rollout gradual
    ENABLE_ORTOOLS: bool = os.getenv("ENABLE_ORTOOLS", "false").lower() == "true"
    
    # Criterios de activación basados en benchmarks exitosos (WEEK 4 - más agresivo)
    ORTOOLS_MIN_PLACES: int = int(os.getenv("ORTOOLS_MIN_PLACES", "4"))         # Reducido de 6 a 4 para mayor cobertura
    ORTOOLS_MIN_DAYS: int = int(os.getenv("ORTOOLS_MIN_DAYS", "1"))            # OR-Tools maneja días simples exitosamente
    ORTOOLS_MAX_PLACES: int = int(os.getenv("ORTOOLS_MAX_PLACES", "50"))       # Límite razonable para performance
    ORTOOLS_MAX_DISTANCE_KM: int = int(os.getenv("ORTOOLS_MAX_DISTANCE_KM", "500"))  # Límite geográfico
    
    # Performance basada en benchmarks reales (2000ms promedio)
    ORTOOLS_TIMEOUT_S: int = int(os.getenv("ORTOOLS_TIMEOUT_S", "10"))         # OR-Tools es 4x más rápido que legacy
    ORTOOLS_SLOW_THRESHOLD_MS: int = int(os.getenv("ORTOOLS_SLOW_THRESHOLD_MS", "5000"))  # 2.5x benchmark time
    ORTOOLS_EXPECTED_EXEC_TIME_MS: int = 2000  # Basado en benchmarks
    
    # Control geográfico (WEEK 4 EXPANSION - más ciudades chilenas)
    ORTOOLS_CITIES: str = os.getenv("ORTOOLS_CITIES", "santiago,valparaiso,antofagasta,la_serena,concepcion,temuco,iquique,calama")   # Expansión a ciudades principales Chile
    ORTOOLS_EXCLUDE_CITIES: str = os.getenv("ORTOOLS_EXCLUDE_CITIES", "")
    
    # Circuit Breaker OR-Tools (más permisivo por demostrada confiabilidad)
    ORTOOLS_FAILURE_THRESHOLD: int = int(os.getenv("ORTOOLS_FAILURE_THRESHOLD", "3"))     # Tolerante, OR-Tools mostró 100% success
    ORTOOLS_RECOVERY_TIMEOUT: int = int(os.getenv("ORTOOLS_RECOVERY_TIMEOUT", "60"))      # Recovery rápido
    ORTOOLS_HEALTH_CHECK_TTL: int = int(os.getenv("ORTOOLS_HEALTH_CHECK_TTL", "300"))     # Cache health check 5min
    
    # A/B Testing gradual (WEEK 4 SCALING - más agresivo por éxito comprobado)
    ORTOOLS_USER_PERCENTAGE: int = int(os.getenv("ORTOOLS_USER_PERCENTAGE", "50"))        # Escalar a 50% usuarios tras validación
    ORTOOLS_TRACK_PERFORMANCE: bool = os.getenv("ORTOOLS_TRACK_PERFORMANCE", "true").lower() == "true"
    
    # Configuración avanzada OR-Tools (WEEK 4 - Advanced Constraints)
    ORTOOLS_ENABLE_TIME_WINDOWS: bool = os.getenv("ORTOOLS_ENABLE_TIME_WINDOWS", "true").lower() == "true"
    ORTOOLS_ENABLE_VEHICLE_ROUTING: bool = os.getenv("ORTOOLS_ENABLE_VEHICLE_ROUTING", "true").lower() == "true"
    ORTOOLS_ENABLE_ADVANCED_CONSTRAINTS: bool = os.getenv("ORTOOLS_ENABLE_ADVANCED_CONSTRAINTS", "true").lower() == "true"
    ORTOOLS_OPTIMIZATION_TARGET: str = os.getenv("ORTOOLS_OPTIMIZATION_TARGET", "minimize_travel_time")  # minimize_travel_time | minimize_distance
    
    # Performance Optimization (WEEK 4)
    ORTOOLS_ENABLE_PARALLEL_OPTIMIZATION: bool = os.getenv("ORTOOLS_ENABLE_PARALLEL_OPTIMIZATION", "true").lower() == "true"
    ORTOOLS_CACHE_DISTANCE_MATRIX: bool = os.getenv("ORTOOLS_CACHE_DISTANCE_MATRIX", "true").lower() == "true"
    ORTOOLS_DISTANCE_CACHE_TTL: int = int(os.getenv("ORTOOLS_DISTANCE_CACHE_TTL", "3600"))  # 1 hora
    ORTOOLS_MAX_PARALLEL_REQUESTS: int = int(os.getenv("ORTOOLS_MAX_PARALLEL_REQUESTS", "3"))
    
    # Multi-City Integration (WEEK 4)
    ORTOOLS_ENABLE_MULTI_CITY: bool = os.getenv("ORTOOLS_ENABLE_MULTI_CITY", "true").lower() == "true"
    ORTOOLS_MULTI_CITY_THRESHOLD_KM: int = int(os.getenv("ORTOOLS_MULTI_CITY_THRESHOLD_KM", "100"))  # Distancia para considerar multi-ciudad
    ORTOOLS_ACCOMMODATE_MULTI_CITY: bool = os.getenv("ORTOOLS_ACCOMMODATE_MULTI_CITY", "true").lower() == "true"
    
    # Fallback strategy
    ORTOOLS_FALLBACK_TO_LEGACY: bool = os.getenv("ORTOOLS_FALLBACK_TO_LEGACY", "true").lower() == "true"
    ORTOOLS_FALLBACK_ON_SLOW: bool = os.getenv("ORTOOLS_FALLBACK_ON_SLOW", "false").lower() == "true"  # No fallar por lentitud
    
    # Monitoreo y alertas
    ORTOOLS_LOG_PERFORMANCE: bool = os.getenv("ORTOOLS_LOG_PERFORMANCE", "true").lower() == "true"
    ORTOOLS_ALERT_ON_DEGRADATION: bool = os.getenv("ORTOOLS_ALERT_ON_DEGRADATION", "true").lower() == "true"
    
    # Benchmark validation
    ORTOOLS_VALIDATE_VS_BENCHMARKS: bool = os.getenv("ORTOOLS_VALIDATE_VS_BENCHMARKS", "true").lower() == "true"
    ORTOOLS_BENCHMARK_SUCCESS_RATE_THRESHOLD: float = float(os.getenv("ORTOOLS_BENCHMARK_SUCCESS_RATE_THRESHOLD", "0.95"))  # 95% vs 100% benchmark
    
    class Config:
        env_file = ".env"

settings = Settings()
