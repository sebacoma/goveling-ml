# 🎯 ENDPOINTS PARA FRONTEND - GOVELING ML

## 📍 Endpoint Principal Multimodal (RECOMENDADO)

### `POST /itinerary/multimodal`

**Este es el endpoint más avanzado que debe usar tu frontend** para generar itinerarios completos con lugares.

**URL**: `https://your-api-domain.com/itinerary/multimodal`

#### � Request Body:
```json
{
  "places": [
    {
      "id": "opcional_uuid",
      "name": "Plaza de Armas",
      "lat": -33.4372,
      "lon": -70.6506,
      "type": "tourist_attraction",
      "priority": 8,
      "min_duration_hours": 1.5,
      "rating": 4.5,
      "address": "Plaza de Armas, Santiago, Chile",
      "google_place_id": "ChIJ..."
    },
    {
      "name": "Mercado Central",
      "lat": -33.4333,
      "lon": -70.6500,
      "type": "food",
      "priority": 7,
      "min_duration_hours": 2.0
    }
  ],
  "start_date": "2025-01-15",
  "end_date": "2025-01-17",
  "transport_mode": "drive",
  "daily_start_hour": 9,
  "daily_end_hour": 18,
  "max_walking_distance_km": 15.0,
  "max_daily_activities": 6,
  "preferences": {
    "culture_weight": 0.8,
    "nature_weight": 0.6,
    "food_weight": 0.9
  },
  "accommodations": []
}
```

### ✅ Campos Obligatorios:
- `places[].name` (string)
- `places[].lat` (float, -90 a 90)
- `places[].lon` (float, -180 a 180)
- `start_date` (string: "YYYY-MM-DD")
- `end_date` (string: "YYYY-MM-DD")

### 🔧 Campos Opcionales:
- `transport_mode`: "walk" | "drive" | "transit" | "bike" (default: "walk")
- `daily_start_hour`: 6-12 (default: 9)
- `daily_end_hour`: 15-23 (default: 18)
- `max_walking_distance_km`: 1-50 (default: 15.0)
- `max_daily_activities`: 1-10 (default: 6)
- `places[].type`: PlaceType enum (default: "point_of_interest")
- `places[].priority`: 1-10 (default: 5)
- `places[].min_duration_hours`: 0.5-8 (calculado automáticamente)

### 🆕 NUEVAS FUNCIONALIDADES (Dic 2025)

#### 1. Horarios Personalizados por Día (`custom_schedules`)
Permite definir horarios específicos para días particulares, sobrescribiendo los horarios por defecto:

```json
{
  "places": [...],
  "start_date": "2025-11-10",
  "end_date": "2025-11-12",
  "daily_start_hour": 9,
  "daily_end_hour": 18,
  "custom_schedules": [
    {
      "date": "2025-11-10",
      "start_hour": 11,
      "end_hour": 18
    },
    {
      "date": "2025-11-12",
      "start_hour": 9,
      "end_hour": 15
    }
  ]
}
```

**Casos de uso:**
- Primer día con llegada tarde
- Último día con salida temprano
- Días con eventos específicos que reducen tiempo disponible
- Flexibilidad según preferencias del usuario

#### 2. Información de Horarios en Respuesta

**Horarios por Día (`schedule_info`):**
Cada día ahora incluye información sobre su configuración horaria:

```json
{
  "day": 1,
  "date": "2025-11-10",
  "schedule_info": {
    "start_hour": 11,
    "end_hour": 18,
    "available_hours": 7,
    "custom_schedule": true
  },
  "places": [...]
}
```

**Horarios por Actividad (`arrival_time` y `departure_time`):**
Cada lugar ahora incluye horarios específicos en formato HH:MM:

```json
{
  "id": "uuid",
  "name": "Torre Eiffel",
  "arrival_time": "09:37",
  "departure_time": "11:07",
  "duration_minutes": 90,
  "order": 1
}
```

**Beneficios para el Frontend:**
- Mostrar timeline visual del día
- Sincronizar con calendarios
- Notificaciones basadas en horarios
- Mejor experiencia de usuario

#### ✅ Response:
```json
{
  "itinerary": [
    {
      "day": 1,
      "date": "2025-01-15",
      "activities": [
        {
          "place": "Plaza de Armas",
          "start": "09:00",
          "end": "10:30",
          "duration_h": 1.5,
          "lat": -33.4372,
          "lon": -70.6506,
          "type": "tourist_attraction",
          "name": "Plaza de Armas",
          "category": "attraction",
          "priority": 8
        }
      ],
      "travel_summary": {
        "total_distance_km": 12.5,
        "total_travel_time_minutes": 45,
        "transport_modes": ["drive"]
      }
    }
  ],
  "optimization_metrics": {
    "total_distance_km": 45.2,
    "total_travel_time_hours": 2.1,
    "optimization_mode": "multimodal_hybrid_v31",
    "multimodal_router_stats": {
      "routes_calculated": 15,
      "avg_calculation_time_ms": 180,
      "precision_mode": "high"
    }
  },
  "recommendations": [
    "Itinerario optimizado usando rutas reales de Chile",
    "Considera reservar con anticipación en temporada alta"
  ]
}
```

---

## 🔄 Endpoints Alternativos

### `POST /create_itinerary` (Endpoint Original)
- Funciona igual que `/itinerary/multimodal`
- Menos optimizado para Chile específicamente
- Usa para compatibilidad con código existente

### `POST /api/v2/itinerary/generate-hybrid` (Híbrido Avanzado)  
- Optimizador híbrido V31
- Misma estructura de request/response
- Análisis semántico adicional

---

## 🌎 Tipos de Lugares Soportados

```typescript
enum PlaceType {
  // Comida & Bebida
  RESTAURANT = "restaurant",
  CAFE = "cafe", 
  BAR = "bar",
  FOOD = "food",
  
  // Atracciones & Cultura
  ATTRACTION = "attraction",
  TOURIST_ATTRACTION = "tourist_attraction", 
  MUSEUM = "museum",
  MONUMENT = "monument",
  CHURCH = "church",
  ART_GALLERY = "art_gallery",
  
  // Naturaleza & Outdoor
  PARK = "park",
  BEACH = "beach",
  VIEWPOINT = "viewpoint", 
  NATURAL_FEATURE = "natural_feature",
  ZOO = "zoo",
  
  // Shopping & Entretenimiento
  SHOPPING = "shopping",
  SHOPPING_MALL = "shopping_mall",
  STORE = "store", 
  MOVIE_THEATER = "movie_theater",
  NIGHT_CLUB = "night_club",
  
  // Alojamiento
  LODGING = "lodging",
  ACCOMMODATION = "accommodation",
  
  // General
  POINT_OF_INTEREST = "point_of_interest",
  ESTABLISHMENT = "establishment"
}
```

---

## � URL Base

### Producción (Render):
```
https://tu-app.onrender.com/itinerary/multimodal
```

### Desarrollo Local:
```
http://localhost:8000/itinerary/multimodal
```

---

## 💡 Tips para el Frontend

1. **Validación Local**: Valida lat/lon antes de enviar
2. **Timeout**: Usa timeout de 60-120 segundos para requests complejos
3. **Cache**: Considera cachear responses por combinación de places+dates
4. **Fallback**: Si `/multimodal` falla, usa `/create_itinerary` como fallback
5. **Progress**: Muestra loading spinner - el procesamiento puede tomar 10-30 segundos

---

## 🔍 Health Check

### `GET /health/multimodal`
Verifica que el sistema multimodal esté funcionando:

```json
{
  "status": "healthy",
  "multimodal_router": "available",
  "chile_graphs_loaded": true,
  "version": "v3.1"
}
```

### Ejemplo completo cURL:
```bash
curl -X POST "https://tu-app.onrender.com/itinerary/multimodal" \
  -H "Content-Type: application/json" \
  -d '{
    "places": [
      {
        "name": "Plaza de Armas",
        "lat": -33.4372,
        "lon": -70.6506,
        "type": "tourist_attraction",
        "priority": 8
      },
      {
        "name": "Cerro San Cristóbal", 
        "lat": -33.4267,
        "lon": -70.6333,
        "type": "viewpoint",
        "priority": 9
      }
    ],
    "start_date": "2025-01-15",
    "end_date": "2025-01-16",
    "transport_mode": "drive",
    "daily_start_hour": 9,
    "daily_end_hour": 17
  }'
```

## 🛡️ Manejo de Errores

### Error 422 (Validación):
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "places", 0, "lat"],
      "msg": "Field required"
    }
  ]
}
```

### Error 500 (Interno):
```json
{
  "detail": "Error interno del servidor",
  "error_code": "OPTIMIZATION_FAILED"
}
      "loc": ["body", "places"],
      "msg": "ensure this value has at least 1 items",
      "type": "value_error"
    }
  ]
}
```

### **Server Errors (500):**
```json
{
  "detail": "Internal server error during itinerary generation"
}
```

---

## 📊 **System Architecture**

```
Frontend Request
    ↓
/itinerary/multimodal (Universal Endpoint)
    ↓
Geographic Detection
    ↓
Chile? → ChileMultiModalRouter (2.5GB Cached Graphs)
    ↓
International? → HybridRoutingService
    ↓
OSRM (Free) → Google Maps (Backup) → Euclidean (Fallback)
    ↓
Optimized Itinerary Response
```

### **Routing Intelligence:**
- **Urban Routes (<50km)**: OSRM → Google → Mathematical
- **Intercity Routes (>50km)**: Google → OSRM → Mathematical  
- **Always Available**: Euclidean distance calculations

---

## ✅ **Best Practices**

1. **Always provide realistic `visit_duration_minutes`**
2. **Use appropriate `transportation_mode` for location**
3. **Handle both optimized (Chile) and fallback (international) responses**
4. **Implement timeout handling (15+ seconds for complex routes)**
5. **Check `recommendations.optimization_used` for system performance**

---

## 🔧 **Testing**

The system has been validated with:
- ✅ **Chile locations**: Santiago, Valparaíso, Antofagasta
- ✅ **International**: NYC, London, Tokyo  
- ✅ **Mixed scenarios**: Chile + International combined
- ✅ **Edge cases**: Single location, unreachable places

**System Status**: Production Ready 🚀