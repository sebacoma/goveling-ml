# 🔌 Guía de Integración para Frontend (Lovable)

## 📡 Endpoints Disponibles

### ✅ Endpoints Activos:

1. **`POST /api/v2/itinerary/generate-hybrid`** - Endpoint principal
2. **`POST /api/v2/hotels/recommend`** - Recomendaciones de hoteles

### ❌ Endpoints Eliminados:
- ~~`/api/v2/places/search-nearby`~~ - **REDUNDANTE** (sugerencias incluidas en endpoint principal)

## 🎯 Cómo Obtener Sugerencias de Lugares

Las sugerencias de lugares están **incluidas automáticamente** en la respuesta del endpoint principal:

```json
{
  "itinerary": [
    {
      "day": 1,
      "date": "2025-10-15",
      "places": [...],
      "free_blocks": [
        {
          "start_time": 570,
          "end_time": 1080,
          "duration_minutes": 510,
          "suggestions": [
            {
              "name": "Catedral de Antofagasta",
              "lat": -23.646866,
              "lon": -70.397463,
              "type": "tourist_attraction",
              "rating": 4.6,
              "eta_minutes": 4,
              "reason": "Google Places: 4.6⭐, 4min caminando",
              "synthetic": false,
              "source": "google_places",
              "place_id": "ChIJ8QzAxhfVr5YRfA0-5NCPHec",
              "vicinity": "José de San Martín 2634, Antofagasta",
              "user_ratings_total": 80,
              "distance_km": 0.4,
              "price_level": null
            }
          ],
          "note": "Sugerencias para 8h de tiempo libre (3 lugares reales de alta calidad)"
        }
      ]
    }
  ]
}
```

## 💡 Implementación Recomendada para Frontend:

```typescript
// 1. Llamar solo al endpoint principal
const response = await fetch('/api/v2/itinerary/generate-hybrid', {
  method: 'POST',
  body: JSON.stringify(payload)
});

const data = await response.json();

// 2. Extraer sugerencias de free_blocks
data.itinerary.forEach(day => {
  day.free_blocks?.forEach(freeBlock => {
    const suggestions = freeBlock.suggestions;
    // Usar las sugerencias directamente
    suggestions.forEach(place => {
      console.log(`${place.name} (${place.rating}⭐) - ${place.eta_minutes}min`);
    });
  });
});
```

## ✅ Ventajas de este Enfoque:

1. **🚀 Más Eficiente**: Una sola llamada API
2. **🎯 Contextual**: Sugerencias específicas para tiempo libre disponible
3. **🕐 Temporal**: Considera horarios y duración de bloques libres
4. **📍 Geográfico**: Basado en ubicación actual del itinerario
5. **⭐ Calidad**: Pre-filtradas por rating y relevancia

## 🔄 Migración desde el Endpoint Anterior:

Si anteriormente usabas `/api/v2/places/search-nearby`, simplemente:

1. **Elimina** las llamadas a ese endpoint
2. **Usa** las sugerencias de `free_blocks`
3. **Disfruta** de mejor rendimiento y contexto

## 📊 Campos Disponibles en Sugerencias:

- `name`: Nombre del lugar
- `lat`/`lon`: Coordenadas
- `type`: Tipo de lugar (restaurant, tourist_attraction, etc.)
- `rating`: Calificación (1-5)
- `eta_minutes`: Tiempo estimado para llegar
- `reason`: Explicación de por qué se sugiere
- `source`: Fuente de datos (google_places)
- `distance_km`: Distancia en kilómetros
- `user_ratings_total`: Número de reseñas
- `price_level`: Nivel de precios (0-4)