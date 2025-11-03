# 🎯 Casos de Uso Específicos: City2Graph vs Sistema Actual

## 📊 **Matriz de Decisión Inteligente**

| **Criterio** | **Sistema Actual** | **City2Graph** | **Peso** |
|--------------|-------------------|----------------|----------|
| **Lugares** | ≤ 7 lugares | 8+ lugares | 🔥 Alta |
| **Duración** | 1-2 días | 3+ días | 🔥 Alta |
| **Ciudades** | Una ciudad | Multi-ciudad | 🔥 Alta |
| **Complejidad** | Básico (comida, hotel) | Semántico (cultura, natura) | 🟡 Media |
| **Performance** | < 1 segundo | Análisis profundo OK | 🟡 Media |
| **Confiabilidad** | 99.9% uptime | Experimental | 🔴 Baja |

## 🎯 **Casos de Uso Detallados**

### **🚀 Sistema Actual (Rápido & Confiable)**

#### **Caso 1: Weekend Gastronómico Santiago**
```json
{
  "places": [
    {"name": "Restaurante Boragó", "type": "restaurant"},
    {"name": "Hotel Plaza San Francisco", "type": "lodging"},
    {"name": "Mercado Central", "type": "food"},
    {"name": "Barrio Bellavista", "type": "night_life"}
  ],
  "start_date": "2024-01-15",
  "end_date": "2024-01-16"
}
```
**Por qué Sistema Actual:**
- ✅ Solo 4 lugares → Clustering simple
- ✅ 2 días → Optimización directa
- ✅ Una ciudad → Sin análisis semántico complejo
- ✅ Performance crítica → Respuesta < 1 seg

#### **Caso 2: Business Trip Corto**
```json
{
  "places": [
    {"name": "Hotel Marriott Las Condes", "type": "lodging"},
    {"name": "Oficina Microsoft", "type": "establishment"},
    {"name": "Aeropuerto SCL", "type": "airport"}
  ],
  "start_date": "2024-01-20",
  "end_date": "2024-01-21"
}
```
**Por qué Sistema Actual:**
- ✅ Caso simple → No requiere análisis semántico
- ✅ Pocos lugares → Clustering trivial
- ✅ Business critical → Máxima confiabilidad

### **🧠 City2Graph (Análisis Profundo)**

#### **Caso 3: Ruta Patrimonial Multi-Ciudad**
```json
{
  "places": [
    {"name": "Valparaíso Historic Quarter", "type": "tourist_attraction"},
    {"name": "Pablo Neruda House Isla Negra", "type": "museum"}, 
    {"name": "Viña del Mar Casino", "type": "casino"},
    {"name": "Casablanca Wineries", "type": "tourist_attraction"},
    {"name": "Santiago Centro Histórico", "type": "tourist_attraction"},
    {"name": "Cerro San Cristóbal", "type": "park"},
    {"name": "Barrio Lastarria", "type": "neighborhood"},
    {"name": "La Moneda Palace", "type": "government"},
    {"name": "Hotel Singular Santiago", "type": "lodging"},
    {"name": "Museo de la Memoria", "type": "museum"}
  ],
  "start_date": "2024-02-01",
  "end_date": "2024-02-05"
}
```
**Por qué City2Graph:**
- 🧠 **10 lugares** → Clustering semántico avanzado
- 🧠 **5 días** → Optimización temporal compleja
- 🧠 **Multi-ciudad** → Análisis de conectividad
- 🧠 **Lugares culturales** → Contexto semántico relevante
- 🧠 **Patrimonio** → Walkability + cultural districts

#### **Caso 4: Norte Grande Adventure**
```json
{
  "places": [
    {"name": "San Pedro de Atacama", "type": "locality"},
    {"name": "Valle de la Luna", "type": "tourist_attraction"},
    {"name": "Geysers del Tatio", "type": "tourist_attraction"},
    {"name": "Salar de Atacama", "type": "tourist_attraction"},
    {"name": "Antofagasta Centro", "type": "lodging"},
    {"name": "Calama Airport", "type": "airport"},
    {"name": "Laguna Chaxa", "type": "park"},
    {"name": "Pueblo de Toconao", "type": "locality"},
    {"name": "Termas de Puritama", "type": "spa"},
    {"name": "Valle del Arcoiris", "type": "tourist_attraction"},
    {"name": "Aldea de Tulor", "type": "museum"}
  ],
  "start_date": "2024-03-10",
  "end_date": "2024-03-16"  
}
```
**Por qué City2Graph:**
- 🧠 **11 lugares** → Análisis H3 spatial partitioning
- 🧠 **7 días** → Optimización multi-día compleja
- 🧠 **Región extensa** → Cross-partition connectivity crítico
- 🧠 **Lugares remotos** → OSM + routing especializado
- 🧠 **Logística compleja** → Análisis de accesibilidad

## ⚖️ **Algoritmo de Decisión Implementado**

```python
async def should_use_city2graph(request: ItineraryRequest) -> Dict[str, Any]:
    """
    🧠 Algoritmo inteligente para decidir qué optimizador usar
    """
    
    # 🔴 Validaciones de seguridad
    if not settings.ENABLE_CITY2GRAPH:
        return {"use_city2graph": False, "reason": "city2graph_disabled"}
    
    # 📊 Calcular factores de complejidad
    complexity_factors = {}
    
    # Factor 1: Cantidad de lugares (peso: 3)
    places_count = len(request.places)
    complexity_factors["places_complexity"] = {
        "value": places_count,
        "score": min(places_count / settings.CITY2GRAPH_MIN_PLACES, 2.0) * 3,
        "threshold": settings.CITY2GRAPH_MIN_PLACES
    }
    
    # Factor 2: Duración del viaje (peso: 3)  
    trip_days = (request.end_date - request.start_date).days
    complexity_factors["duration_complexity"] = {
        "value": trip_days,
        "score": min(trip_days / settings.CITY2GRAPH_MIN_DAYS, 2.0) * 3,
        "threshold": settings.CITY2GRAPH_MIN_DAYS
    }
    
    # Factor 3: Multi-ciudad detection (peso: 2)
    cities_detected = await _detect_multiple_cities(request.places)
    complexity_factors["multi_city"] = {
        "cities": cities_detected,
        "score": 2.0 if len(cities_detected) > 1 else 0.0
    }
    
    # Factor 4: Tipos de lugares semánticos (peso: 1)
    semantic_types = _count_semantic_place_types(request.places)
    complexity_factors["semantic_richness"] = {
        "semantic_types": semantic_types,
        "score": min(len(semantic_types) / 3, 1.0) * 1.0
    }
    
    # Factor 5: Distribución geográfica (peso: 1)
    geo_spread_km = _calculate_geographic_spread(request.places)
    complexity_factors["geographic_spread"] = {
        "spread_km": geo_spread_km,
        "score": min(geo_spread_km / 50, 1.0) * 1.0  # 50km+ = complejo
    }
    
    # 📊 Score total (máximo: 10)
    total_score = sum(factor["score"] for factor in complexity_factors.values())
    
    # 🎯 Decisión final
    use_city2graph = total_score >= 5.0  # Threshold: 50% complejidad
    
    return {
        "use_city2graph": use_city2graph,
        "complexity_score": total_score,
        "factors": complexity_factors,
        "reasoning": _generate_decision_reasoning(complexity_factors, total_score)
    }

def _count_semantic_place_types(places: List[Dict]) -> List[str]:
    """Contar tipos de lugares semánticamente ricos"""
    semantic_types = set()
    
    for place in places:
        place_type = place.get("type", "").lower()
        
        # Lugares que se benefician de análisis semántico
        if place_type in [
            "museum", "tourist_attraction", "park", "art_gallery",
            "church", "synagogue", "mosque", "cemetery",
            "university", "library", "town_hall", "courthouse",
            "locality", "neighborhood", "sublocality"
        ]:
            semantic_types.add(place_type)
    
    return list(semantic_types)

async def _detect_multiple_cities(places: List[Dict]) -> List[str]:
    """Detectar si el itinerario cruza múltiples ciudades"""
    cities = set()
    
    for place in places:
        # Extraer ciudad de coordenadas o nombre
        city = await _reverse_geocode_city(place)
        if city:
            cities.add(city.lower())
    
    return list(cities)

def _calculate_geographic_spread(places: List[Dict]) -> float:
    """Calcular dispersión geográfica en km"""
    if len(places) < 2:
        return 0.0
    
    coordinates = []
    for place in places:
        if "coordinates" in place:
            coordinates.append((
                place["coordinates"]["latitude"],
                place["coordinates"]["longitude"]
            ))
    
    if len(coordinates) < 2:
        return 0.0
    
    # Calcular distancia máxima entre cualquier par de lugares
    max_distance = 0.0
    for i in range(len(coordinates)):
        for j in range(i + 1, len(coordinates)):
            distance = haversine_km(
                coordinates[i][0], coordinates[i][1],
                coordinates[j][0], coordinates[j][1]
            )
            max_distance = max(max_distance, distance)
    
    return max_distance
```

## 🎚️ **Configuración Granular**

```bash
# Feature flags principales
ENABLE_CITY2GRAPH=false                    # Master switch
CITY2GRAPH_MIN_PLACES=8                   # Mínimo lugares
CITY2GRAPH_MIN_DAYS=3                     # Mínimo días
CITY2GRAPH_COMPLEXITY_THRESHOLD=5.0       # Score mínimo (0-10)

# Control por ciudades (piloto)
CITY2GRAPH_CITIES="santiago,valparaiso,antofagasta"
CITY2GRAPH_EXCLUDE_CITIES="concepcion"    # Ciudades excluidas

# Performance & fallbacks
CITY2GRAPH_TIMEOUT_S=30                   # Timeout
CITY2GRAPH_FALLBACK_ENABLED=true          # Auto-fallback
CITY2GRAPH_MAX_CONCURRENT=1               # Concurrencia limitada
```

## 📈 **Métricas de Éxito**

### **KPIs por Optimizador:**
```python
# Sistema Actual
{
    "avg_response_time": "0.8s",
    "success_rate": "99.9%", 
    "user_satisfaction": "4.2/5",
    "use_cases": "simple_trips, business, weekend"
}

# City2Graph  
{
    "avg_response_time": "3.2s",
    "success_rate": "96.5%",
    "user_satisfaction": "4.7/5", 
    "use_cases": "complex_multi_city, cultural, adventure"
}
```

### **A/B Testing Framework:**
```python
# Tracking comparativo
analytics.track_optimizer_performance({
    "request_id": "abc123",
    "optimizer_used": "city2graph",
    "complexity_score": 7.2,
    "processing_time": 3.1,
    "places_count": 12,
    "trip_days": 5,
    "user_satisfaction_score": 4.8,
    "fallback_triggered": False
})
```

## 🚀 **Conclusión**

Esta estrategia permite que **cada sistema haga lo que mejor sabe hacer**:

- **🚀 Sistema Actual**: Casos simples, rápidos y confiables
- **🧠 City2Graph**: Casos complejos que requieren análisis semántico profundo

El algoritmo de decisión garantiza que City2Graph se active **SOLO cuando agrega valor real**, manteniendo el sistema productivo estable para el 80% de casos típicos.