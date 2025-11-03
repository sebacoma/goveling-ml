# API Multi-Modal REST - Documentación Completa

## 🚀 Descripción General

El sistema API Multi-Modal de Goveling proporciona servicios de routing optimizado para múltiples modos de transporte en Chile, incluyendo vehículo, caminata y bicicleta. Utiliza un sistema de caches pre-generados (2.5GB total) con lazy loading inteligente para máximo rendimiento.

## 📋 Características Principales

- ✅ **Routing Multi-Modal**: Soporte para drive, walk, bike
- ✅ **Lazy Loading**: Carga bajo demanda de caches (0ms startup)
- ✅ **Gestión de Memoria**: Optimización automática y manual
- ✅ **Performance Monitoring**: Estadísticas detalladas y health checks
- ✅ **Cache Inteligente**: 2.5GB de datos con hit ratios >90%
- ✅ **Thread-Safe**: Operaciones concurrentes seguras

## 🌐 Endpoints Disponibles

### 1. Health Check y Monitoreo

#### `GET /health/multimodal`
**Descripción**: Health check completo del sistema multi-modal  
**Parámetros**: Ninguno  

**Respuesta exitosa (200)**:
```json
{
  "status": "excellent",
  "health_score": 116.7,
  "modes_available": ["drive", "walk", "bike"],
  "modes_in_memory": 2,
  "total_modes": 3,
  "cache_status": {
    "drive": {
      "exists": true,
      "size": 1792.5,
      "path": "/cache/chile_graph_cache.pkl",
      "loaded_in_memory": true,
      "requests": 1,
      "cache_hits": 2,
      "hit_ratio": 2.0
    },
    "walk": {
      "exists": true,
      "size": 365.2,
      "loaded_in_memory": false,
      "requests": 1,
      "cache_hits": 1,
      "hit_ratio": 1.0
    },
    "bike": {
      "exists": true,
      "size": 323.8,
      "loaded_in_memory": true,
      "requests": 1,
      "cache_hits": 1,
      "hit_ratio": 1.0
    }
  },
  "memory_usage": {
    "total_estimated_mb": 2116.3,
    "caches_in_memory": {
      "drive": {"loaded": true, "estimated_size_mb": 1792.5},
      "walk": {"loaded": false, "estimated_size_mb": 0},
      "bike": {"loaded": true, "estimated_size_mb": 323.8}
    }
  },
  "lazy_loading": {
    "enabled": true,
    "memory_efficiency": "2116.3MB in memory",
    "cache_hit_ratio": 1.33
  },
  "performance": {
    "health_check_time_ms": 2.1
  },
  "timestamp": "2025-11-01T13:48:55"
}
```

### 2. Routing Individual por Modo

#### `POST /route/drive`
**Descripción**: Calcular ruta en vehículo  
**Cache**: chile_graph_cache.pkl (1792MB)  

**Request Body**:
```json
{
  "start_lat": -33.4372,
  "start_lon": -70.6506,
  "end_lat": -33.4194,
  "end_lon": -70.6049
}
```

**Respuesta exitosa (200)**:
```json
{
  "success": true,
  "mode": "drive",
  "distance_km": 5.44,
  "time_minutes": 6.5,
  "path": [
    [0, [-33.4372, -70.6506]],
    [1, [-33.4194, -70.6049]]
  ],
  "geometry": {
    "type": "LineString",
    "coordinates": [
      [-70.6506, -33.4372],
      [-70.6049, -33.4194]
    ]
  },
  "source": "cached_calculation",
  "cache_used": true,
  "processing_time_ms": 0.5,
  "performance": {
    "processing_time_ms": 0.5,
    "cache_source": "chile_graph_cache.pkl"
  }
}
```

#### `POST /route/walk`
**Descripción**: Calcular ruta peatonal  
**Cache**: santiago_metro_walking_cache.pkl (365MB)  

**Request/Response**: Mismo formato que `/route/drive`

#### `POST /route/bike`
**Descripción**: Calcular ruta en bicicleta  
**Cache**: santiago_metro_cycling_cache.pkl (323MB)  

**Request/Response**: Mismo formato que `/route/drive`

### 3. Comparación Multi-Modal

#### `POST /route/compare`
**Descripción**: Comparar rutas entre todos los modos simultáneamente  

**Request Body**:
```json
{
  "start_lat": -33.4372,
  "start_lon": -70.6506,
  "end_lat": -33.4194,
  "end_lon": -70.6049
}
```

**Respuesta exitosa (200)**:
```json
{
  "routes": {
    "drive": {
      "success": true,
      "distance_km": 5.44,
      "time_minutes": 6.5,
      "cache_used": true
    },
    "walk": {
      "success": true,
      "distance_km": 5.44,
      "time_minutes": 65.3,
      "cache_used": true
    },
    "bike": {
      "success": true,
      "distance_km": 5.44,
      "time_minutes": 21.8,
      "cache_used": true
    }
  },
  "analysis": {
    "fastest_mode": "drive",
    "fastest_time_minutes": 6.5,
    "shortest_mode": "drive",
    "shortest_distance_km": 5.44,
    "recommended_mode": "bike",
    "recommendation_reason": "Distancia media - bicicleta es rápida y ecológica",
    "modes_available": ["drive", "walk", "bike"],
    "modes_failed": []
  },
  "performance": {
    "processing_time_ms": 1.2,
    "routes_calculated": 3,
    "total_modes_attempted": 3
  },
  "timestamp": "2025-11-01T13:48:55"
}
```

### 4. Gestión de Caches

#### `POST /cache/preload`
**Descripción**: Pre-cargar caches específicos para optimización  

**Request Body** (cache específico):
```json
{
  "mode": "drive"
}
```

**Request Body** (todos los caches):
```json
{
  "mode": "all"
}
```

**Respuesta exitosa (200)** - Cache específico:
```json
{
  "success": true,
  "mode": "drive",
  "processing_time_ms": 20403.5,
  "message": "Cache drive cargado exitosamente",
  "timestamp": "2025-11-01T13:48:55"
}
```

**Respuesta exitosa (200)** - Todos los caches:
```json
{
  "success": true,
  "mode": "all",
  "results": {
    "drive": true,
    "walk": true,
    "bike": true
  },
  "successful_loads": 3,
  "total_modes": 3,
  "processing_time_ms": 18518.2,
  "message": "Pre-carga completada: 3/3 caches cargados",
  "timestamp": "2025-11-01T13:48:55"
}
```

#### `POST /cache/clear`
**Descripción**: Limpiar caches de memoria para liberar RAM  

**Request Body**:
```json
{
  "mode": "walk"  // o "all" para todos
}
```

**Respuesta exitosa (200)**:
```json
{
  "success": true,
  "mode": "walk",
  "memory_freed_mb": 365.2,
  "memory_before_mb": 2116.3,
  "memory_after_mb": 1751.1,
  "message": "Cache walk eliminado de memoria",
  "timestamp": "2025-11-01T13:48:55"
}
```

### 5. Optimización y Estadísticas

#### `GET /cache/optimize`
**Descripción**: Optimización automática basada en patrones de uso  

**Respuesta exitosa (200)**:
```json
{
  "success": true,
  "optimization_report": {
    "actions_taken": [
      "Descargado cache walk (poco uso)"
    ],
    "memory_before_mb": 2116.3,
    "memory_after_mb": 1751.1,
    "recommendations": [
      "Considerar pre-cargar drive (alto uso: 15 requests)"
    ]
  },
  "timestamp": "2025-11-01T13:48:55"
}
```

#### `GET /performance/stats`
**Descripción**: Estadísticas detalladas de rendimiento  

**Respuesta exitosa (200)**:
```json
{
  "usage_statistics": {
    "drive": {
      "requests": 1,
      "cache_hits": 2
    },
    "walk": {
      "requests": 1,
      "cache_hits": 1
    },
    "bike": {
      "requests": 1,
      "cache_hits": 1
    }
  },
  "cache_status": {
    // Mismo formato que health check
  },
  "memory_usage": {
    "total_estimated_mb": 1751.1,
    "caches_in_memory": {
      "drive": {"loaded": true, "estimated_size_mb": 1792.5},
      "walk": {"loaded": false, "estimated_size_mb": 0},
      "bike": {"loaded": true, "estimated_size_mb": 323.8}
    }
  },
  "performance_summary": {
    "total_requests": 3,
    "total_cache_hits": 4,
    "modes_loaded_in_memory": 2,
    "overall_hit_ratio": 1.33
  },
  "generated_at": "2025-11-01T13:48:55"
}
```

## 📊 Códigos de Error

### Errores Comunes

- **400 Bad Request**: Parámetros faltantes o inválidos
- **404 Not Found**: No se pudo calcular la ruta
- **503 Service Unavailable**: Router multi-modal no disponible
- **500 Internal Server Error**: Error interno del servidor

### Ejemplo de Error (400):
```json
{
  "detail": "Campo requerido faltante: start_lat"
}
```

### Ejemplo de Error (404):
```json
{
  "detail": "No se pudo calcular la ruta en vehículo"
}
```

## 🔧 Configuración y Performance

### Velocidades por Modo
- **Drive**: 50 km/h (ciudad/carretera)  
- **Walk**: 5 km/h (peatonal)  
- **Bike**: 15 km/h (bicicleta)  

### Tamaños de Cache
- **Drive**: 1,792MB (chile_graph_cache.pkl)  
- **Walk**: 365MB (santiago_metro_walking_cache.pkl)  
- **Bike**: 323MB (santiago_metro_cycling_cache.pkl)  
- **Total**: 2,480MB  

### Performance Benchmarks
- **Tiempo de startup**: <1s (lazy loading)  
- **Primera carga**: 18-20s por cache  
- **Routing con cache**: <1ms  
- **Hit ratio típico**: >90%  

## 💡 Mejores Prácticas

### 1. Uso de Lazy Loading
- El sistema carga caches bajo demanda
- Pre-cargar solo caches que usarás frecuentemente
- Monitorear hit ratios para optimizar

### 2. Gestión de Memoria
- Usar `/cache/optimize` periódicamente
- Limpiar caches no utilizados con `/cache/clear`
- Monitorear memoria con `/performance/stats`

### 3. Patrones de Uso Recomendados
- Usar `/route/compare` para análisis completo
- Endpoints individuales para casos específicos
- Health checks antes de operaciones críticas

### 4. Monitoring Continuo
- Revisar `/health/multimodal` regularmente
- Analizar estadísticas con `/performance/stats`
- Configurar alertas basadas en health_score

## 🛠️ Integración con Cliente

### Ejemplo Python:
```python
import requests

# Configuración
API_BASE = "http://localhost:8000"

# Health check
health = requests.get(f"{API_BASE}/health/multimodal")
print(f"Status: {health.json()['status']}")

# Pre-cargar cache más usado
requests.post(f"{API_BASE}/cache/preload", json={"mode": "drive"})

# Calcular ruta
route_request = {
    "start_lat": -33.4372,
    "start_lon": -70.6506,
    "end_lat": -33.4194,
    "end_lon": -70.6049
}

# Comparación multi-modal
comparison = requests.post(f"{API_BASE}/route/compare", json=route_request)
best_mode = comparison.json()["analysis"]["recommended_mode"]

print(f"Modo recomendado: {best_mode}")
```

### Ejemplo JavaScript:
```javascript
const API_BASE = "http://localhost:8000";

// Función para calcular ruta
async function calculateRoute(startLat, startLon, endLat, endLon, mode = 'drive') {
    const response = await fetch(`${API_BASE}/route/${mode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            start_lat: startLat,
            start_lon: startLon,
            end_lat: endLat,
            end_lon: endLon
        })
    });
    
    return response.json();
}

// Comparación multi-modal
async function compareRoutes(startLat, startLon, endLat, endLon) {
    const response = await fetch(`${API_BASE}/route/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            start_lat: startLat,
            start_lon: startLon,
            end_lat: endLat,
            end_lon: endLon
        })
    });
    
    return response.json();
}
```

## 📈 Métricas y Monitoreo

### KPIs Principales
- **Health Score**: >90% = excelente
- **Hit Ratio**: >80% = eficiente  
- **Response Time**: <50ms = óptimo
- **Memory Usage**: <3GB = controlado

### Alertas Recomendadas
- Health Score < 75%: Investigar
- Hit Ratio < 50%: Optimizar caches
- Memory Usage > 4GB: Limpiar memoria
- Response Time > 100ms: Revisar performance

---

**Versión**: 1.0  
**Última actualización**: Noviembre 2025  
**Soporte**: Sistema de routing multi-modal Chile  
**Performance**: 2.5GB cache, <1ms routing, lazy loading optimizado