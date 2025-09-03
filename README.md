# 🚀 Goveling ML API - Sistema Híbrido de Optimización de Itinerarios

**API Inteligente de Optimización de Itinerarios de Viaje con Machine Learning y Detección Automática de Hoteles**

## ✨ **Características Principales**

### 🎯 **Sistema Híbrido v2.2**
- **🏨 Detección Automática de Hoteles**: Usa alojamientos como centroides inteligentes
- **🗺️ Clustering Geográfico**: Fallback automático por proximidad
- **🚗 Recomendaciones de Transporte**: Sugiere modo óptimo por tramo  
- **⚡ Método Híbrido**: Haversine + Google Directions API
- **🎯 100% Eficiencia**: Scores perfectos en ambos modos

### 🤖 **Machine Learning**
- **Modelo Entrenado**: MAE 0.307h (±18 min precisión)
- **R² Score**: 0.741 
- **Características**: 15+ variables predictivas
- **Actualización**: Automática con nuevos datos

### 🔧 **Tecnologías**
- **FastAPI 2.x**: Framework moderno y rápido
- **Pydantic**: Validación automática de datos
- **scikit-learn**: Machine learning
- **Google Maps API**: Rutas y tiempos reales
- **Async/Await**: Rendimiento optimizado

## � **Endpoints Principales**

### 🏨 **Optimizador Híbrido** (Recomendado)
```
POST /api/v2/itinerary/generate-hybrid
```

**Con Hoteles:**
```json
{
  "places": [
    {
      "name": "Plaza Colón",
      "lat": -23.6509,
      "lon": -70.4018,
      "type": "monument",
      "priority": 6
    }
  ],
  "accommodations": [
    {
      "name": "Hotel Centro",
      "lat": -23.6509,
      "lon": -70.4018,
      "address": "Centro Ciudad"
    }
  ],
  "start_date": "2025-08-15",
  "end_date": "2025-08-16",
  "transport_mode": "walk"
}
```

**Sin Hoteles (Automático):**
```json
{
  "places": [...],
  "start_date": "2025-08-15",
  "end_date": "2025-08-16",
  "transport_mode": "walk"
}
```

## 🚀 **Despliegue en Vercel**

### **1. Configuración**
```bash
# Variables de entorno requeridas
GOOGLE_MAPS_API_KEY=tu_api_key
```

### **2. Despliegue**
```bash
vercel --prod
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
