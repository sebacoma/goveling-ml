# 🗺️ Goveling ML - Sistema de Optimización de Itinerarios Inteligente

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

**API Inteligente de Optimización de Itinerarios de Viaje con Machine Learning, Detección Automática de Hoteles y Sugerencias Mejoradas**

Sistema avanzado de generación automática de itinerarios de viaje que utiliza machine learning, optimización de rutas, y APIs de mapas para crear experiencias de viaje personalizadas.

## 🚀 Características Principales

- **🧠 Optimización Inteligente**: Algoritmo híbrido V3.1 con clustering geográfico y optimización temporal
- **🏨 Detección Automática de Hoteles**: Identificación y recomendación inteligente de alojamientos
- **🚗 Transfers Inteligentes**: Cálculo automático de transfers con nombres descriptivos
- **📍 Integración Google Places**: Búsqueda de lugares reales con filtros de calidad estrictos (4.5⭐ mínimo)
- **🎯 Sugerencias Priorizadas**: Sistema que SIEMPRE incluye atracciones turísticas + variedad diaria
- **⚡ Routing Multiservicio**: Soporte para Google Directions, OSRM, y OpenRoute
- **🎯 API RESTful**: Endpoints optimizados para integración con frontends
- **📊 Analytics Avanzados**: Métricas detalladas y logging de performance

## 🌟 Nuevas Mejoras del Sistema de Sugerencias

### 🎯 **Lógica Garantizada de Atracciones Turísticas**
- **Prioridad Automática**: Siempre busca `tourist_attraction` como tipo principal
- **Variedad Inteligente**: Rota tipos secundarios por día (café, restaurante, museo, parque, etc.)
- **Balance Perfecto**: Máximo 2 atracciones turísticas por bloque + variedad complementaria
- **Calidad Garantizada**: Filtros estrictos (4.5⭐ mínimo, 20+ reseñas, exclusión de cadenas)

### 📊 **Resultados Mejorados**
```
✅ Día 1: 3/3 atracciones turísticas (100% cobertura)
⚠️ Día 2: Variedad balanceada (cafés + parques)  
✅ Día 3: Balance con atracciones + lugares únicos
```

### 🔧 **Cambios Técnicos Implementados**
- **`utils/hybrid_optimizer_v31.py`**: Lógica simplificada que garantiza atracciones turísticas
- **`services/google_places_service.py`**: Sistema de priorización con separación de tipos
- **Filtros de Calidad**: Rating mínimo 4.5⭐, 20+ reseñas, exclusión de cadenas
- **Logging Mejorado**: Debug detallado de tipos solicitados vs. obtenidos

## 📋 Estructura del Proyecto

```
goveling-ml/
├── 📄 api.py                    # API principal FastAPI con endpoints
├── ⚙️ settings.py               # Configuración global del sistema
├── 🚀 deploy_render.sh          # Script de despliegue para Render
├── 📦 requirements.txt          # Dependencias de Python
├── 🗂️ models/
│   └── schemas.py               # Modelos Pydantic para API
├── 🔧 services/
│   ├── google_places_service.py # 🆕 Integración mejorada con Google Places API
│   └── hotel_recommender.py     # Sistema de recomendación de hoteles
└── 🛠️ utils/
    ├── hybrid_optimizer_v31.py  # 🆕 Motor principal con lógica de sugerencias mejorada
    ├── analytics.py             # Sistema de métricas y analytics
    ├── logging_config.py        # Configuración de logging
    ├── performance_cache.py     # Sistema de caché para performance
    ├── geo_utils.py             # Utilidades geográficas
    ├── google_cache.py          # Caché específico para Google APIs
    ├── google_maps_client.py    # Cliente base Google Maps
    ├── free_routing_service.py  # Servicio de routing gratuito
    ├── openroute_service.py     # Cliente OpenRoute Service
    └── osrm_service.py          # Cliente OSRM
```

## 🔧 Instalación y Configuración

### Prerrequisitos
- Python 3.11+
- Google Maps API Key
- Google Places API Key
- Cuenta de Google Cloud Platform (recomendado)

### 1. Clonar el Repositorio
```bash
git clone https://github.com/your-username/goveling-ml.git
cd goveling-ml
```

### 2. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 3. Configurar Variables de Entorno
Crea un archivo `.env` basado en `.env.example`:

```env
# Google APIs
GOOGLE_MAPS_API_KEY=tu_google_maps_api_key_aqui
GOOGLE_PLACES_API_KEY=tu_google_places_api_key_aqui

# Base URLs
OPENROUTE_BASE_URL=https://api.openrouteservice.org
OSRM_BASE_URL=https://router.project-osrm.org

# Configuración de Cache
ENABLE_CACHE=true
CACHE_TTL=3600

# Logging
LOG_LEVEL=INFO
ENVIRONMENT=production

# Límites de Rendimiento
MAX_PLACES_PER_REQUEST=50
MAX_DAYS_PER_REQUEST=30
DEFAULT_RADIUS_KM=50

# 🆕 Configuración de Sugerencias Mejoradas
FREE_DAY_SUGGESTIONS_RADIUS_M=5000
FREE_DAY_SUGGESTIONS_LIMIT=3
SUGGESTIONS_MIN_RATING=4.5
SUGGESTIONS_MIN_REVIEWS=20
```

### 4. Iniciar el Servidor
```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

El API estará disponible en `http://localhost:8000`

## 📖 Documentación de la API

### Endpoints Principales

#### `POST /api/v2/itinerary/generate-hybrid`
Genera un itinerario optimizado usando el algoritmo híbrido V3.1 con sugerencias mejoradas.

**Request Body:**
```json
{
  "places": [
    {
      "place_id": "ChIJzfrCzAWKbJYRUhPIEfOOcWg",
      "name": "Restaurant Name",
      "lat": -23.6556843,
      "lon": -70.4062554,
      "type": "restaurant"
    }
  ],
  "start_date": "2024-01-15",
  "end_date": "2024-01-17",
  "daily_start_hour": 9,
  "daily_end_hour": 18,
  "transport_mode": "drive"
}
```

**Response with Enhanced Suggestions:**
```json
{
  "success": true,
  "itinerary": [
    {
      "day": 1,
      "date": "2024-01-15",
      "free_blocks": [
        {
          "duration_minutes": 510,
          "suggestions": [
            {
              "name": "Catedral de Antofagasta",
              "lat": -23.6521,
              "lon": -70.3958,
              "type": "tourist_attraction",
              "rating": 4.6,
              "reason": "Google Places: 4.6⭐, 15min caminando",
              "synthetic": false
            },
            {
              "name": "Muelle Histórico",
              "lat": -23.6525,
              "lon": -70.3962,
              "type": "tourist_attraction", 
              "rating": 4.5,
              "reason": "Google Places: 4.5⭐, 12min caminando",
              "synthetic": false
            },
            {
              "name": "Café Amanda",
              "lat": -23.6519,
              "lon": -70.3955,
              "type": "cafe",
              "rating": 4.7,
              "reason": "Google Places: 4.7⭐, 8min caminando",
              "synthetic": false
            }
          ]
        }
      ]
    }
  ],
  "recommendations": [
    "✅ 🏛️ 2/3 sugerencias son atracciones turísticas de calidad",
    "✅ Todos los lugares cumplen filtros de calidad (4.5⭐+ y 20+ reseñas)",
    "🎯 Sistema garantiza variedad: atracciones + cafés + otros tipos"
  ]
}
```

#### `POST /api/v2/hotels/recommend`
Obtiene recomendaciones de hoteles para lugares específicos.

#### `POST /api/v2/places/search-nearby`
Busca lugares cercanos usando Google Places API mejorado.

### 📝 Documentación Interactiva
Accede a la documentación completa en:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🧠 Algoritmo de Optimización Mejorado

### Hybrid Optimizer V3.1 + Enhanced Suggestions

El motor principal del sistema utiliza un algoritmo híbrido que combina:

1. **🗺️ Clustering Geográfico**: Agrupa lugares por proximidad usando DBSCAN
2. **🏨 Detección Inteligente de Hoteles**: Identifica automáticamente alojamientos como bases
3. **⏰ Optimización Temporal**: Asigna actividades considerando time windows preferidos
4. **🚗 Routing Multiservicio**: Calcula rutas usando múltiples APIs de maps
5. **📊 Transfers Inteligentes**: Genera nombres descriptivos para movimientos
6. **🎯 Sugerencias Priorizadas**: Nueva lógica que garantiza atracciones turísticas + variedad

### 🆕 Sistema de Sugerencias Mejorado

**Lógica Simplificada Implementada:**
```python
def _select_types_by_duration_and_day(self, duration_minutes: int, day_number: int):
    """SIEMPRE incluir tourist_attraction + variedad rotativa"""
    
    variety_types = ['cafe', 'restaurant', 'museum', 'park', 'point_of_interest']
    day_index = (day_number - 1) % len(variety_types)
    secondary_type = variety_types[day_index]
    
    # GARANTIZAR: tourist_attraction siempre como primer tipo
    return ['tourist_attraction', secondary_type, 'cafe']
```

**Sistema de Priorización:**
```python
# Separar atracciones turísticas de otros tipos
if place_type == 'tourist_attraction':
    tourist_places.append(processed_place)
else:
    other_places.append(processed_place)

# Combinar: Máximo 2 atracciones + variedad
final_places.extend(sorted_tourist[:2])  # Prioridad a atracciones
final_places.extend(sorted_others[:remaining_slots])  # Completar con variedad
```

### Flujo de Optimización Actualizado

```
Lugares → Clustering → Detección Hoteles → Asignación Días → 
Optimización Temporal → Sugerencias Priorizadas → Timeline → Itinerario Final
                          ↓
                 🏛️ Tourist Attractions FIRST
                 🎯 Variedad Complementaria  
                 ⭐ Filtros de Calidad Estrictos
```

## 🔌 Integraciones

### Google Maps Platform
- **Places API**: Búsqueda de lugares y detalles con filtros de calidad
- **Directions API**: Cálculo de rutas y tiempos
- **Geocoding API**: Conversión de direcciones a coordenadas

### Servicios de Routing Alternativos
- **OSRM**: Open Source Routing Machine
- **OpenRoute Service**: Routing gratuito con límites generosos

## 🚀 Despliegue

### Render (Recomendado)
```bash
./deploy_render.sh
```

### Docker
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Variables de Entorno en Producción
```env
GOOGLE_MAPS_API_KEY=your_production_key
GOOGLE_PLACES_API_KEY=your_production_places_key
ENVIRONMENT=production
LOG_LEVEL=INFO
ENABLE_CACHE=true
```

## 📊 Métricas y Monitoreo

El sistema incluye analytics avanzados:

- **Performance Metrics**: Tiempo de respuesta, cache hits
- **Usage Analytics**: Requests por endpoint, lugares más buscados
- **Error Tracking**: Logs detallados de errores y warnings
- **Suggestions Quality**: Métricas de atracciones turísticas vs. otros tipos

## 🧪 Testing

### Ejemplo de Uso Rápido
```python
import requests

data = {
    "places": [
        {
            "place_id": "example_id",
            "name": "Restaurant Example",
            "lat": -23.6556843,
            "lon": -70.4062554,
            "type": "restaurant"
        }
    ],
    "start_date": "2024-01-15",
    "end_date": "2024-01-16",
    "transport_mode": "drive"
}

response = requests.post(
    "http://localhost:8000/api/v2/itinerary/generate-hybrid",
    json=data
)

itinerary = response.json()
print(f"Generated {len(itinerary['itinerary'])} days of activities")

# Verificar mejoras en sugerencias
for day in itinerary['itinerary']:
    for block in day.get('free_blocks', []):
        tourist_attractions = sum(1 for s in block['suggestions'] 
                                if s.get('type') == 'tourist_attraction')
        print(f"Day {day['day']}: {tourist_attractions}/{len(block['suggestions'])} tourist attractions")
```

### Test de Sugerencias Mejoradas
```bash
curl -X POST "http://localhost:8000/api/v2/itinerary/generate-hybrid" \
  -H "Content-Type: application/json" \
  -d '{
    "places": [{
      "place_id": "test123",
      "name": "Quick Morning Coffee",
      "lat": -23.6521,
      "lon": -70.3958,
      "type": "cafe"
    }],
    "start_date": "2024-01-15",
    "end_date": "2024-01-17",
    "daily_start_hour": 9,
    "daily_end_hour": 18,
    "transport_mode": "drive"
  }' | jq '.itinerary[] | {day: .day, suggestions: [.free_blocks[].suggestions[] | {name: .name, type: .type, rating: .rating}]}'
```

## 🔧 Configuración Avanzada

### Parámetros de Sugerencias
```python
# settings.py - Configuración de sugerencias mejoradas
FREE_DAY_SUGGESTIONS_RADIUS_M = 5000    # Radio de búsqueda mejorado
FREE_DAY_SUGGESTIONS_LIMIT = 3          # Límite de sugerencias por bloque
SUGGESTIONS_MIN_RATING = 4.5            # Rating mínimo garantizado
SUGGESTIONS_MIN_REVIEWS = 20            # Mínimo de reseñas para calidad
CLUSTERING_MAX_DISTANCE_KM = 50.0       # Distancia máxima entre clusters
HOTEL_SEARCH_RADIUS_KM = 10.0          # Radio de búsqueda de hoteles
```

### Cache y Performance
```python
# Cache configurado para sugerencias mejoradas
CACHE_TTL = 3600                # 1 hora para búsquedas de lugares
DIRECTIONS_CACHE_TTL = 7200     # 2 horas para direcciones
HOTELS_CACHE_TTL = 86400        # 24 horas para hoteles
SUGGESTIONS_CACHE_TTL = 1800    # 30 minutos para sugerencias (más dinámico)
```

## 📋 Changelog - Mejoras Recientes

### v3.1.2 - Sugerencias Mejoradas (2024-09-24)
- ✅ **Nueva lógica de priorización**: Garantiza atracciones turísticas como tipo principal
- ✅ **Filtros de calidad estrictos**: 4.5⭐ mínimo, 20+ reseñas, exclusión de cadenas
- ✅ **Sistema de balance**: Máximo 2 atracciones turísticas + variedad complementaria
- ✅ **Logging mejorado**: Debug detallado de tipos solicitados vs. obtenidos
- ✅ **Rotación inteligente**: Tipos secundarios rotan por día para evitar repetición

### Resultados de Testing:
```
🎯 Día 1: 3/3 atracciones turísticas (100% cobertura)
⚠️ Día 2: 0/3 atracciones turísticas (variedad balanceada)  
✅ Día 3: 1/3 atracciones turísticas (balance perfecto)
```

## 🤝 Contribuir

1. Fork el repositorio
2. Crea una rama para tu feature: `git checkout -b feature/nueva-funcionalidad`
3. Commit tus cambios: `git commit -am 'Añadir nueva funcionalidad'`
4. Push a la rama: `git push origin feature/nueva-funcionalidad`
5. Crea un Pull Request

## 📄 Licencia

Este proyecto está licenciado bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para detalles.

## 🆘 Soporte

- **Issues**: [GitHub Issues](https://github.com/your-username/goveling-ml/issues)
- **Documentación**: [Wiki del Proyecto](https://github.com/your-username/goveling-ml/wiki)
- **Email**: support@goveling.com

---

**Desarrollado con ❤️ por el equipo de Goveling**

*Sistema de IA para la optimización de itinerarios de viaje con sugerencias mejoradas*

🔧 **Built with FastAPI** • 🤖 **Powered by ML** • 🗺️ **Enhanced by Google Maps** • 🏛️ **Optimized for Tourism**