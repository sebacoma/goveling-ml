# 🗺️ Goveling ML - Sistema de Optimización de Itinerarios Inteligente# 🗺️ Goveling ML - Sistema de Optimización de Itinerarios Inteligente# 🚀 Goveling ML API - Sistema Híbrido de Optimización de Itinerarios



![Python](https://img.shields.io/badge/python-3.11+-blue.svg)

![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)

![License](https://img.shields.io/badge/license-MIT-blue.svg)![Python](https://img.shields.io/badge/python-3.11+-blue.svg)**API Inteligente de Optimización de Itinerarios de Viaje con Machine Learning, Detección Automática de Hoteles y Sugerencias para Días Libres**



Sistema avanzado de generación automática de itinerarios de viaje que utiliza machine learning, optimización de rutas, y APIs de mapas para crear experiencias de viaje personalizadas.![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)



## 🚀 Características Principales![License](https://img.shields.io/badge/license-MIT-blue.svg)## ✨ **Características }



- **🧠 Optimización Inteligente**: Algoritmo híbrido V3.1 con clustering geográfico y optimización temporal```

- **🏨 Detección Automática de Hoteles**: Identificación y recomendación inteligente de alojamientos

- **🚗 Transfers Inteligentes**: Cálculo automático de transfers con nombres descriptivosSistema avanzado de generación automática de itinerarios de viaje que utiliza machine learning, optimización de rutas, y APIs de mapas para crear experiencias de viaje personalizadas.

- **📍 Integración Google Places**: Búsqueda de lugares reales y recomendaciones personalizadas  

- **⚡ Routing Multiservicio**: Soporte para Google Directions, OSRM, y OpenRoute### 🤖 **ML Recommendations**

- **🎯 API RESTful**: Endpoints optimizados para integración con frontends

- **📊 Analytics Avanzados**: Métricas detalladas y logging de performance## 🚀 Características Principales```



## 📋 Estructura del ProyectoPOST /api/v2/ml/recommendations



```- **🧠 Optimización Inteligente**: Algoritmo híbrido V3.1 con clustering geográfico y optimización temporal```

goveling-ml/

├── 📄 api.py                    # API principal FastAPI con endpoints- **🏨 Detección Automática de Hoteles**: Identificación y recomendación inteligente de alojamientos

├── ⚙️ settings.py               # Configuración global del sistema

├── 🚀 deploy_render.sh          # Script de despliegue para Render- **🚗 Transfers Inteligentes**: Cálculo automático de transfers con nombres descriptivos**Request:**

├── 📦 requirements.txt          # Dependencias de Python

├── 🗂️ models/- **📍 Integración Google Places**: Búsqueda de lugares reales y recomendaciones personalizadas  ```json

│   └── schemas.py               # Modelos Pydantic para API

├── 🔧 services/- **⚡ Routing Multiservicio**: Soporte para Google Directions, OSRM, y OpenRoute{

│   ├── google_places_service.py # Integración con Google Places API

│   └── hotel_recommender.py     # Sistema de recomendación de hoteles- **🎯 API RESTful**: Endpoints optimizados para integración con frontends  "user_preferences": {

└── 🛠️ utils/

    ├── hybrid_optimizer_v31.py  # Motor principal de optimización- **📊 Analytics Avanzados**: Métricas detalladas y logging de performance    "cultural_interest": 0.8,

    ├── analytics.py             # Sistema de métricas y analytics

    ├── logging_config.py        # Configuración de logging    "outdoor_activities": 0.6,

    ├── performance_cache.py     # Sistema de caché para performance

    ├── geo_utils.py             # Utilidades geográficas## 📋 Estructura del Proyecto    "food_exploration": 0.9,

    ├── google_cache.py          # Caché específico para Google APIs

    ├── google_maps_client.py    # Cliente base Google Maps    "budget_conscious": 0.7

    ├── free_routing_service.py  # Servicio de routing gratuito

    ├── openroute_service.py     # Cliente OpenRoute Service```  },

    └── osrm_service.py          # Cliente OSRM

```goveling-ml/  "visited_places": [



## 🔧 Instalación y Configuración├── 📄 api.py                    # API principal FastAPI con endpoints    "Plaza de Armas",



### Prerrequisitos├── ⚙️ settings.py               # Configuración global del sistema    "Mercado Central"

- Python 3.11+

- Google Maps API Key├── 🚀 deploy_render.sh          # Script de despliegue para Render  ],

- Cuenta de Google Cloud Platform (recomendado)

├── 📦 requirements.txt          # Dependencias de Python  "location": {

### 1. Clonar el Repositorio

```bash├── 🗂️ models/    "lat": -33.4372,

git clone https://github.com/your-username/goveling-ml.git

cd goveling-ml│   └── schemas.py               # Modelos Pydantic para API    "lon": -70.6506

```

├── 🔧 services/  },

### 2. Instalar Dependencias

```bash│   ├── google_places_service.py # Integración con Google Places API  "radius_km": 5,

pip install -r requirements.txt

```│   └── hotel_recommender.py     # Sistema de recomendación de hoteles  "max_recommendations": 5



### 3. Configurar Variables de Entorno└── 🛠️ utils/}

Crea un archivo `.env` basado en `.env.example`:

    ├── hybrid_optimizer_v31.py  # Motor principal de optimización```

```env

# Google APIs    ├── analytics.py             # Sistema de métricas y analytics

GOOGLE_MAPS_API_KEY=tu_google_maps_api_key_aqui

    ├── logging_config.py        # Configuración de logging**Response:**

# Base URLs

OPENROUTE_BASE_URL=https://api.openrouteservice.org    ├── performance_cache.py     # Sistema de caché para performance```json

OSRM_BASE_URL=https://router.project-osrm.org

    ├── geo_utils.py             # Utilidades geográficas{

# Configuración de Cache

ENABLE_CACHE=true    ├── google_cache.py          # Caché específico para Google APIs  "ml_recommendations": [

CACHE_TTL=3600

    ├── google_directions_service.py # Cliente Google Directions    {

# Logging

LOG_LEVEL=INFO    ├── google_maps_client.py    # Cliente base Google Maps      "place_name": "Galería Arte Contemporáneo",

ENVIRONMENT=production

    ├── free_routing_service.py  # Servicio de routing gratuito      "category": "art_gallery",

# Límites de Rendimiento

MAX_PLACES_PER_REQUEST=50    ├── openroute_service.py     # Cliente OpenRoute Service      "coordinates": {

MAX_DAYS_PER_REQUEST=30

DEFAULT_RADIUS_KM=50    └── osrm_service.py          # Cliente OSRM        "latitude": -33.4372,

```

```        "longitude": -70.6506

### 4. Iniciar el Servidor

```bash      },

uvicorn api:app --host 0.0.0.0 --port 8000 --reload

```## 🔧 Instalación y Configuración      "score": 0.64,



El API estará disponible en `http://localhost:8000`      "confidence": 0.4,



## 📖 Documentación de la API### Prerrequisitos      "reasoning": "Está bien ubicado para ti • Es algo nuevo que podrías disfrutar",



### Endpoints Principales- Python 3.11+      "predicted_duration_h": 1.5,



#### `POST /api/v2/itinerary/generate-hybrid`- Google Maps API Key      "optimal_time_slot": "afternoon",

Genera un itinerario optimizado usando el algoritmo híbrido V3.1.

- Cuenta de Google Cloud Platform (recomendado)      "compatibility_factors": {

**Request Body:**

```json        "cultural_alignment": 0.85,

{

  "places": [### 1. Clonar el Repositorio        "location_convenience": 0.92,

    {

      "place_id": "ChIJzfrCzAWKbJYRUhPIEfOOcWg",```bash        "novelty_factor": 0.75

      "name": "Restaurant Name",

      "lat": -23.6556843,git clone https://github.com/your-username/goveling-ml.git      }

      "lon": -70.4062554,

      "type": "restaurant"cd goveling-ml    }

    }

  ],```  ],

  "start_date": "2024-01-15",

  "end_date": "2024-01-17",   "insights": {

  "daily_start_hour": 9,

  "daily_end_hour": 18,### 2. Instalar Dependencias    "total_candidates": 45,

  "transport_mode": "drive",

  "max_walking_distance_km": 2.0,```bash    "filtered_by_preferences": 12,

  "max_daily_activities": 6,

  "preferences": {pip install -r requirements.txt    "geographic_clustering": "centro_historico",

    "budget": "mid",

    "pace": "relaxed"```    "confidence_threshold": 0.3

  }

}  }

```

### 3. Configurar Variables de Entorno}

**Response:**

```jsonCrea un archivo `.env` basado en `.env.example`:```

{

  "success": true,

  "itinerary": [

    {```env## 🌟 **Características Avanzadas**

      "day": 1,

      "date": "2024-01-15",# Google APIs

      "places": [

        {GOOGLE_MAPS_API_KEY=tu_google_maps_api_key_aqui### 🧠 **Sistema de Inteligencia**

          "id": "uuid",

          "name": "Check-in al hotel",- **ML Recommendations**: Sugerencias personalizadas basadas en machine learning

          "category": "hotel",

          "estimated_time": "0.5h",# Base URLs- **Transport Intelligence**: Recomendaciones automáticas de transporte (🚶 Caminar, 🚌 Transporte público, 🚕 Taxi)

          "order": 1

        },OPENROUTE_BASE_URL=https://api.openrouteservice.org- **Dynamic Spacing**: Espaciado inteligente entre actividades (gaps de 90+ minutos)

        {

          "id": "uuid", OSRM_BASE_URL=https://router.project-osrm.org- **Free Day Detection**: Detección automática de días libres con sugerencias categorizadas

          "name": "Traslado a Restaurant Name",

          "category": "transfer",

          "estimated_time": "1.0h",

          "order": 2# Configuración de Cache### 🏨 **Sistema de Hoteles**

        }

      ],ENABLE_CACHE=true- **Geographic Optimization**: Recomendaciones basadas en proximidad a actividades

      "base": {

        "name": "Hotel Terrado Antofagasta",CACHE_TTL=3600- **Convenience Scoring**: Algoritmo de puntuación por conveniencia (0-1)

        "lat": -23.6469,

        "lon": -70.4031- **Automatic Integration**: Sin hoteles → recomendaciones automáticas

      }

    }# Logging- **Quality Metrics**: Rating, rango de precios, y análisis de ubicación

  ],

  "recommendations": [LOG_LEVEL=INFO

    "✅ Todos los lugares están en la misma zona geográfica",

    "🏨 Hotel base inteligente asignado automáticamente"ENVIRONMENT=production### 🗓️ **Sugerencias de Días Libres**

  ],

  "optimization_metrics": {- **Nature Escape** 🏔️: Excursiones y actividades al aire libre

    "total_places": 5,

    "total_distance_km": 12.5,# Límites de Rendimiento- **Cultural Immersion** 🎨: Museos, arquitectura, y experiencias culturales  

    "estimated_total_time_hours": 8.2

  }MAX_PLACES_PER_REQUEST=50- **Adventure Quest** ⚡: Actividades de aventura y experiencias únicas

}

```MAX_DAYS_PER_REQUEST=30- **Auto-Detection**: Detección automática de días sin actividades programadas



#### `POST /api/v2/hotels/recommend`DEFAULT_RADIUS_KM=50

Obtiene recomendaciones de hoteles para lugares específicos.

```### 🚇 **Optimización de Transporte**

#### `POST /api/v2/places/search-nearby`

Busca lugares cercanos usando Google Places API.- **Mode Intelligence**: Análisis automático del mejor medio de transporte



### 📝 Documentación Interactiva### 4. Iniciar el Servidor- **Distance-Based**: Caminata (≤1km), Transporte público (1-5km), Taxi (>5km)

Accede a la documentación completa en:

- Swagger UI: `http://localhost:8000/docs````bash- **Visual Indicators**: Emojis intuitivos para cada modo de transporte

- ReDoc: `http://localhost:8000/redoc`

uvicorn api:app --host 0.0.0.0 --port 8000 --reload- **Integration**: Consideración de tiempo de traslado en horarios

## 🧠 Algoritmo de Optimización

```

### Hybrid Optimizer V3.1

## 🚀 **Despliegue en Vercel**cipales**

El motor principal del sistema utiliza un algoritmo híbrido que combina:

El API estará disponible en `http://localhost:8000`

1. **🗺️ Clustering Geográfico**: Agrupa lugares por proximidad usando DBSCAN

2. **🏨 Detección Inteligente de Hoteles**: Identifica automáticamente alojamientos como bases### 🎯 **Sistema Híbrido v2.2**

3. **⏰ Optimización Temporal**: Asigna actividades considerando time windows preferidos

4. **🚗 Routing Multiservicio**: Calcula rutas usando múltiples APIs de maps## 📖 Documentación de la API- **🏨 Detección Automática de Hoteles**: Usa alojamientos como centroides inteligentes

5. **📊 Transfers Inteligentes**: Genera nombres descriptivos para movimientos

- **�️ Sugerencias para Días Libres**: Detecta automáticamente días vacíos y genera recomendaciones categorizadas

### Flujo de Optimización

### Endpoints Principales- **�🗺️ Clustering Geográfico**: Fallback automático por proximidad

```

Lugares → Clustering → Detección Hoteles → Asignación Días → - **🚗 Recomendaciones de Transporte**: Sugiere modo óptimo por tramo (🚶 Caminar, 🚗 Auto/Taxi, 🚌 Transporte público)

Optimización Temporal → Cálculo Transfers → Timeline → Itinerario Final

```#### `POST /api/v2/itinerary/generate-hybrid`- **⚡ Método Híbrido**: Haversine + Google Directions API



## 🔌 IntegracionesGenera un itinerario optimizado usando el algoritmo híbrido V3.1.- **🎯 100% Eficiencia**: Scores perfectos en ambos modos



### Google Maps Platform- **⏰ Duraciones Inteligentes**: Adaptadas por tipo de lugar y prioridad

- **Places API**: Búsqueda de lugares y detalles

- **Directions API**: Cálculo de rutas y tiempos**Request Body:**

- **Geocoding API**: Conversión de direcciones a coordenadas

```json### 🤖 **Machine Learning & Recomendaciones**

### Servicios de Routing Alternativos

- **OSRM**: Open Source Routing Machine{- **Modelo Entrenado**: MAE 0.307h (±18 min precisión)

- **OpenRoute Service**: Routing gratuito con límites generosos

  "places": [- **R² Score**: 0.741 

## 🚀 Despliegue

    {- **Características**: 15+ variables predictivas

### Render (Recomendado)

```bash      "place_id": "ChIJzfrCzAWKbJYRUhPIEfOOcWg",- **Recomendaciones ML**: Automáticas para tiempo libre

./deploy_render.sh

```      "name": "Restaurant Name",- **Sugerencias Categorizadas**: Naturaleza, Cultura, Aventura



### Docker      "lat": -23.6556843,- **Actualización**: Automática con nuevos datos

```dockerfile

FROM python:3.11-slim      "lon": -70.4062554,



WORKDIR /app      "type": "restaurant"### 🏨 **Sistema de Hoteles Avanzado**

COPY requirements.txt .

RUN pip install -r requirements.txt    }- **Recomendación Geográfica**: Basada en centroide de actividades



COPY . .  ],- **Score de Conveniencia**: Algoritmo weighted con múltiples factores



CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]  "start_date": "2024-01-15",- **Base de Datos**: 10+ hoteles en Santiago con ratings reales

```

  "end_date": "2024-01-17", - **Integración Automática**: Mejor hotel aparece en campo `lodging`

### Variables de Entorno en Producción

```env  "daily_start_hour": 9,

GOOGLE_MAPS_API_KEY=your_production_key

ENVIRONMENT=production  "daily_end_hour": 18,### 🔧 **Tecnologías**

LOG_LEVEL=INFO

ENABLE_CACHE=true  "transport_mode": "drive",- **FastAPI 2.x**: Framework moderno y rápido

```

  "max_walking_distance_km": 2.0,- **Pydantic v2**: Validación automática de datos

## 📊 Métricas y Monitoreo

  "max_daily_activities": 6,- **scikit-learn**: Machine learning

El sistema incluye analytics avanzados:

  "preferences": {- **Google Maps API**: Rutas y tiempos reales

- **Performance Metrics**: Tiempo de respuesta, cache hits

- **Usage Analytics**: Requests por endpoint, lugares más buscados    "budget": "mid",- **Async/Await**: Rendimiento optimizado

- **Error Tracking**: Logs detallados de errores y warnings

- **Geographic Analytics**: Heatmaps de destinos populares    "pace": "relaxed"



## 🧪 Testing  }## 📋 **Endpoints Principales**



### Ejemplo de Uso Rápido}

```python

import requests```### 🏨 **Optimizador Híbrido** (Recomendado)



data = {```

    "places": [

        {**Response:**POST /api/v2/itinerary/generate-hybrid

            "place_id": "example_id",

            "name": "Restaurant Example",```json```

            "lat": -23.6556843,

            "lon": -70.4062554,{

            "type": "restaurant"

        }  "success": true,**Con Hoteles:**

    ],

    "start_date": "2024-01-15",  "itinerary": [```json

    "end_date": "2024-01-16",

    "transport_mode": "drive"    {{

}

      "day": 1,  "places": [

response = requests.post(

    "http://localhost:8000/api/v2/itinerary/generate-hybrid",      "date": "2024-01-15",    {

    json=data

)      "places": [      "name": "Plaza de Armas",



itinerary = response.json()        {      "lat": -33.4372,

print(f"Generated {len(itinerary['itinerary'])} days of activities")

```          "id": "uuid",      "lon": -70.6506,



## 🔧 Configuración Avanzada          "name": "Check-in al hotel",      "type": "monument",



### Parámetros de Optimización          "category": "hotel",      "priority": 8



```python          "estimated_time": "0.5h",    }

# settings.py

CLUSTERING_MAX_DISTANCE_KM = 50.0    # Distancia máxima entre clusters          "order": 1  ],

HOTEL_SEARCH_RADIUS_KM = 10.0        # Radio de búsqueda de hoteles

MAX_ACTIVITIES_PER_DAY = 8           # Máximo de actividades por día        },  "accommodations": [

WALK_THRESHOLD_KM = 2.0              # Distancia máxima para caminar

DRIVE_THRESHOLD_KM = 300.0           # Distancia máxima para manejar        {    {

```

          "id": "uuid",       "name": "Hotel Centro",

### Cache y Performance

          "name": "Traslado a Restaurant Name",      "lat": -33.4372,

```python

# Cache configurado para:          "category": "transfer",      "lon": -70.6506,

CACHE_TTL = 3600  # 1 hora para búsquedas de lugares

DIRECTIONS_CACHE_TTL = 7200  # 2 horas para direcciones          "estimated_time": "1.0h",      "address": "Centro Ciudad"

HOTELS_CACHE_TTL = 86400  # 24 horas para hoteles

```          "order": 2    }



## 🤝 Contribuir        }  ],



1. Fork el repositorio      ],  "start_date": "2024-03-15",

2. Crea una rama para tu feature: `git checkout -b feature/nueva-funcionalidad`

3. Commit tus cambios: `git commit -am 'Añadir nueva funcionalidad'`      "base": {  "end_date": "2024-03-16",

4. Push a la rama: `git push origin feature/nueva-funcionalidad`

5. Crea un Pull Request        "name": "Hotel Terrado Antofagasta",  "transport_mode": "walk"



## 📄 Licencia        "lat": -23.6469,}



Este proyecto está licenciado bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para detalles.        "lon": -70.4031```



## 🆘 Soporte      }



- **Issues**: [GitHub Issues](https://github.com/your-username/goveling-ml/issues)    }**Sin Hoteles (Automático con Sugerencias):**

- **Documentación**: [Wiki del Proyecto](https://github.com/your-username/goveling-ml/wiki)

- **Email**: support@goveling.com  ],```json



---  "recommendations": [{



**Desarrollado con ❤️ por el equipo de Goveling**    "✅ Todos los lugares están en la misma zona geográfica",  "places": [



*Sistema de IA para la optimización de itinerarios de viaje*    "🏨 Hotel base inteligente asignado automáticamente"    {

  ],      "name": "Plaza de Armas",

  "optimization_metrics": {      "lat": -33.4372,

    "total_places": 5,      "lon": -70.6506,

    "total_distance_km": 12.5,      "type": "monument",

    "estimated_total_time_hours": 8.2      "priority": 8

  }    },

}    {

```      "name": "Mercado Central",

      "lat": -33.4369,

#### `POST /api/v2/hotels/recommend`      "lon": -70.6506,

Obtiene recomendaciones de hoteles para lugares específicos.      "type": "restaurant",

      "priority": 7

#### `POST /api/v2/places/search-nearby`    }

Busca lugares cercanos usando Google Places API.  ],

  "start_date": "2024-03-15",

### 📝 Documentación Interactiva  "end_date": "2024-03-17",

Accede a la documentación completa en:  "transport_mode": "walk"

- Swagger UI: `http://localhost:8000/docs`}

- ReDoc: `http://localhost:8000/redoc````



## 🧠 Algoritmo de Optimización**Respuesta con Días Libres:**

```json

### Hybrid Optimizer V3.1{

  "days": [

El motor principal del sistema utiliza un algoritmo híbrido que combina:    {

      "date": "2024-03-15",

1. **🗺️ Clustering Geográfico**: Agrupa lugares por proximidad usando DBSCAN      "activities": [

2. **🏨 Detección Inteligente de Hoteles**: Identifica automáticamente alojamientos como bases        {

3. **⏰ Optimización Temporal**: Asigna actividades considerando time windows preferidos          "place": "Plaza de Armas",

4. **🚗 Routing Multiservicio**: Calcula rutas usando múltiples APIs de maps          "start": "09:00",

5. **📊 Transfers Inteligentes**: Genera nombres descriptivos para movimientos          "end": "10:18",

          "duration_h": 1.3,

### Flujo de Optimización          "recommended_transport": "🚶 Caminar"

        },

```        {

Lugares → Clustering → Detección Hoteles → Asignación Días →           "place": "Mercado Central",

Optimización Temporal → Cálculo Transfers → Timeline → Itinerario Final          "start": "12:00",

```          "end": "13:30",

          "duration_h": 1.5,

## 🔌 Integraciones          "recommended_transport": "🚶 Caminar"

        }

### Google Maps Platform      ],

- **Places API**: Búsqueda de lugares y detalles      "lodging": {

- **Directions API**: Cálculo de rutas y tiempos        "name": "Hotel Plaza San Francisco",

- **Geocoding API**: Conversión de direcciones a coordenadas        "lat": -33.4372,

        "lon": -70.6506,

### Servicios de Routing Alternativos        "address": "Alameda 816, Santiago Centro",

- **OSRM**: Open Source Routing Machine        "rating": 4.5,

- **OpenRoute Service**: Routing gratuito con límites generosos        "price_range": "medium",

        "convenience_score": 0.871,

## 🚀 Despliegue        "type": "recommended_hotel"

      },

### Render (Recomendado)      "free_minutes": 372

```bash    }

./deploy_render.sh  ],

```  "free_day_suggestions": [

    {

### Docker      "type": "day_trip_suggestion",

```dockerfile      "category": "nature_escape",

FROM python:3.11-slim      "title": "Escape a la Naturaleza - 2024-03-16",

      "suggestions": [

WORKDIR /app        "🏔️ Excursión a Cajón del Maipo y Embalse El Yeso",

COPY requirements.txt .        "🍷 Tour de viñas en Casablanca o Maipo Alto",

RUN pip install -r requirements.txt        "🌊 Excursión a Valparaíso y Viña del Mar (día completo)"

      ],

COPY . .      "duration": "8-10 horas",

      "transport": "Auto recomendado o tour organizado"

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]    },

```    {

      "type": "day_trip_suggestion",

### Variables de Entorno en Producción      "category": "cultural_immersion",

```env      "title": "Inmersión Cultural - 2024-03-16",

GOOGLE_MAPS_API_KEY=your_production_key      "suggestions": [

ENVIRONMENT=production        "🎨 Recorrido completo por museos: MNBA + MAC + Bellas Artes",

LOG_LEVEL=INFO        "🏛️ Tour arquitectónico: Centro Histórico + Barrio Yungay",

ENABLE_CACHE=true        "🛍️ Experiencia gastronómica: Mercados + Barrio Italia"

```      ],

      "duration": "6-8 horas",

## 📊 Métricas y Monitoreo      "transport": "🚶 A pie + Metro"

    }

El sistema incluye analytics avanzados:  ],

  "ml_recommendations": [

- **Performance Metrics**: Tiempo de respuesta, cache hits    {

- **Usage Analytics**: Requests por endpoint, lugares más buscados      "type": "ml_recommendation",

- **Error Tracking**: Logs detallados de errores y warnings      "place_name": "Galería Arte Contemporáneo",

- **Geographic Analytics**: Heatmaps de destinos populares      "category": "art_gallery",

      "coordinates": {

## 🧪 Testing        "latitude": -33.4372,

        "longitude": -70.6506

### Ejemplo de Uso Rápido      },

```python      "score": 0.64,

import requests      "confidence": 0.4,

      "reasoning": "Está bien ubicado para ti • Es algo nuevo que podrías disfrutar"

data = {    }

    "places": [  ],

        {  "recommendations": [

            "place_id": "example_id",    "🗓️ 2 día(s) completamente libre(s) detectado(s)",

            "name": "Restaurant Example",    "💡 Sugerencias de día completo disponibles en 'free_day_suggestions'",

            "lat": -23.6556843,    "🏨 Mejor alojamiento recomendado: Hotel Plaza San Francisco (score: 0.87)"

            "lon": -70.4062554,  ]

            "type": "restaurant"}

        }```

    ],

    "start_date": "2024-01-15",### 🏨 **Recomendación de Hoteles**

    "end_date": "2024-01-16",```

    "transport_mode": "drive"POST /api/v2/hotels/recommend

}```



response = requests.post(**Request:**

    "http://localhost:8000/api/v2/itinerary/generate-hybrid",```json

    json=data{

)  "places": [

    {

itinerary = response.json()      "name": "Plaza de Armas",

print(f"Generated {len(itinerary['itinerary'])} days of activities")      "lat": -33.4372,

```      "lon": -70.6506,

      "type": "monument"

## 🔧 Configuración Avanzada    },

    {

### Parámetros de Optimización      "name": "Mercado Central",

      "lat": -33.4369,

```python      "lon": -70.6506,

# settings.py      "type": "restaurant"

CLUSTERING_MAX_DISTANCE_KM = 50.0    # Distancia máxima entre clusters    }

HOTEL_SEARCH_RADIUS_KM = 10.0        # Radio de búsqueda de hoteles  ],

MAX_ACTIVITIES_PER_DAY = 8           # Máximo de actividades por día  "max_recommendations": 5,

WALK_THRESHOLD_KM = 2.0              # Distancia máxima para caminar  "price_preference": "any"

DRIVE_THRESHOLD_KM = 300.0           # Distancia máxima para manejar}

``````



### Cache y Performance**Response:**

```json

```python{

# Cache configurado para:  "hotel_recommendations": [

CACHE_TTL = 3600  # 1 hora para búsquedas de lugares    {

DIRECTIONS_CACHE_TTL = 7200  # 2 horas para direcciones      "name": "Hotel Plaza San Francisco",

HOTELS_CACHE_TTL = 86400  # 24 horas para hoteles      "coordinates": {

```        "latitude": -33.4372,

        "longitude": -70.6506

## 🤝 Contribuir      },

      "address": "Alameda 816, Santiago Centro",

1. Fork el repositorio      "rating": 4.5,

2. Crea una rama para tu feature: `git checkout -b feature/nueva-funcionalidad`      "price_range": "medium",

3. Commit tus cambios: `git commit -am 'Añadir nueva funcionalidad'`      "distance_to_centroid_km": 0.02,

4. Push a la rama: `git push origin feature/nueva-funcionalidad`      "avg_distance_to_places_km": 0.02,

5. Crea un Pull Request      "convenience_score": 0.899,

      "reasoning": "Muy cerca del centro de tus actividades • Hotel de alta calidad • Fácil acceso a tus destinos",

## 📄 Licencia      "recommendation_rank": 1

    }

Este proyecto está licenciado bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para detalles.  ],

  "analysis": {

## 🆘 Soporte    "places_analyzed": 2,

    "activity_centroid": {

- **Issues**: [GitHub Issues](https://github.com/your-username/goveling-ml/issues)      "latitude": -33.43705,

- **Documentación**: [Wiki del Proyecto](https://github.com/your-username/goveling-ml/wiki)      "longitude": -70.6506

- **Email**: support@goveling.com    },

    "best_option": {

---      "name": "Hotel Plaza San Francisco",

      "convenience_score": 0.899,

**Desarrollado con ❤️ por el equipo de Goveling**      "distance_to_centroid_km": 0.02

    }

*Sistema de IA para la optimización de itinerarios de viaje*  },
  "performance": {
    "processing_time_s": 0.0,
    "generated_at": "2025-09-09T11:28:49.968042"
  }
}
```

## 🚀 **Despliegue en Vercel**

### **2. Estructura**
```bash
vercel.json         # Configuración de rutas
requirements.txt    # Dependencias Python
api/
  index.py         # FastAPI app principal
```

### **3. Comandos**
```bash
# Instalar Vercel CLI
npm i -g vercel

# Deploy
vercel --prod
```

## 🧪 **Testing & Debug**

### **Endpoints de Test**
```bash
# Test básico
curl -X POST "http://localhost:8000/api/v2/itinerary/generate-hybrid" 
     -H "Content-Type: application/json" 
     -d '{
       "places": [
         {
           "name": "Plaza de Armas",
           "lat": -33.4372,
           "lon": -70.6506,
           "type": "monument",
           "priority": 8
         }
       ],
       "start_date": "2024-03-15",
       "end_date": "2024-03-16",
       "transport_mode": "walk"
     }'

# Test con días libres
curl -X POST "http://localhost:8000/api/v2/itinerary/generate-hybrid" 
     -H "Content-Type: application/json" 
     -d '{
       "places": [
         {
           "name": "Plaza de Armas",
           "lat": -33.4372,
           "lon": -70.6506,
           "type": "monument",
           "priority": 8
         }
       ],
       "start_date": "2024-03-15",
       "end_date": "2024-03-18",
       "transport_mode": "walk"
     }'

# Test recomendaciones de hoteles
curl -X POST "http://localhost:8000/api/v2/hotels/recommend" 
     -H "Content-Type: application/json" 
     -d '{
       "places": [
         {
           "name": "Plaza de Armas",
           "lat": -33.4372,
           "lon": -70.6506,
           "type": "monument"
         }
       ],
       "max_recommendations": 3
     }'
```

## 📊 **Performance & Analytics**

### **Métricas Clave**
- **Response Time**: < 2 segundos para itinerarios simples
- **Hotel Recommendations**: < 1 segundo para análisis geográfico
- **ML Processing**: < 3 segundos para recomendaciones personalizadas
- **Free Day Suggestions**: Generación instantánea de 6 opciones categorizadas

### **Logging & Monitoring**
```python
# Ejemplo de logs estructurados
{
  "timestamp": "2024-03-15T10:30:00Z",
  "level": "INFO",
  "component": "hybrid_optimizer",
  "action": "generate_itinerary",
  "duration_ms": 1250,
  "places_count": 5,
  "days_count": 3,
  "free_days_detected": 1,
  "hotels_recommended": 3
}
```

---

## 🎯 **Casos de Uso**

### **1. Viajero Sin Hotel**
- **Input**: Lista de lugares + fechas
- **Output**: Itinerario optimizado + recomendaciones de hoteles automáticas
- **Benefit**: Zero-config travel planning

### **2. Viaje Multi-día con Días Libres**
- **Input**: Lugares para algunos días, otros días vacíos
- **Output**: Sugerencias categorizadas para días libres (naturaleza, cultura, aventura)
- **Benefit**: Maximización de la experiencia de viaje

### **3. Optimización de Transporte**
- **Input**: Lugares con distancias variadas
- **Output**: Recomendaciones inteligentes de transporte por tramo
- **Benefit**: Eficiencia en tiempo y costo de traslados

---

**🔧 Built with FastAPI • 🤖 Powered by ML • 🗺️ Enhanced by Google Maps • 🏨 Optimized for Travel**

### 🌍 **Sugerencias de Lugares**
```
POST /api/v2/places/suggest
```

**Request:**
```json
{
  "latitude": -33.4372,
  "longitude": -70.6506
}
```

**Response:**
```json
{
  "nature_escape": {
    "suggestions": [
      "🏔️ Cerro San Cristóbal",
      "🌲 Parque Metropolitano",
      "🌅 Parque Bicentenario",
      "🌺 Jardín Botánico"
    ],
    "transport": "Transporte público o caminando",
    "places": [
      {
        "name": "Cerro San Cristóbal",
        "lat": -33.4251,
        "lon": -70.6314,
        "rating": 4.7,
        "types": ["park", "natural_feature"]
      }
    ]
  },
  "cultural_immersion": {
    "suggestions": [
      "🎨 Museo Nacional de Bellas Artes",
      "🏛️ Biblioteca Nacional",
      "🎭 Centro Cultural La Moneda",
      "🏺 Museo de Arte Precolombino"
    ],
    "transport": "A pie o bicicleta",
    "places": [
      {
        "name": "Museo Nacional de Bellas Artes",
        "lat": -33.4359,
        "lon": -70.6451,
        "rating": 4.5,
        "types": ["museum", "art_gallery"]
      }
    ]
  },
  "adventure_day": {
    "suggestions": [
      "🎢 Fantasilandia",
      "🏊 Piscina Olímpica",
      "🚴 Ciclovía Providencia",
      "🎯 Centro de Escalada"
    ],
    "transport": "A pie o transporte público",
    "places": [
      {
        "name": "Fantasilandia",
        "lat": -33.4666,
        "lon": -70.6487,
        "rating": 4.4,
        "types": ["amusement_park"]
      }
    ]
  }
}
```

### **3. Verificación**
- ✅ Endpoint health: `/`
- ✅ Documentación: `/docs`
- ✅ OpenAPI: `/openapi.json`

## 💡 **Ventajas del Sistema**

### 🏨 **Modo Hoteles**
- Rutas optimizadas desde/hacia alojamientos
- Información de distancia por actividad
- Distribución inteligente por días
- Base real de operaciones

### 🗺️ **Modo Geográfico** 
- Clustering automático por proximidad
- Sin dependencia de hoteles
- Compatible con requests existentes
- Optimización por zonas

## 📈 **Métricas de Rendimiento**

- **🎯 Eficiencia**: 100% en ambos modos
- **⚡ Velocidad**: <200ms promedio
- **🔄 Disponibilidad**: 99.9%
- **📊 Precisión ML**: 82% dentro de ±30min

## 🛡️ **Seguridad y Límites**

- **🔐 API Keys**: Autenticación opcional
- **⏱️ Rate Limiting**: 100 req/hora por IP
- **🛡️ Validación**: Pydantic automática
- **📝 Logs**: Analytics completo

## � **Soporte**

- **📧 Email**: soporte@goveling.com
- **🌐 Web**: https://goveling.com
- **📖 Docs**: https://api.goveling.com/docs

---

**🔥 Powered by Goveling ML Team | Versión 2.2.0**
