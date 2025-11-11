# 🚨 CONFIGURACIÓN RENDER - ORTools Habilitado

## ⚙️ **Variables de Entorno CRÍTICAS para Render:**

Agregar estas variables en el dashboard de Render:

```bash
# ORTools Configuration (OBLIGATORIAS)
ENABLE_ORTOOLS=true
ORTOOLS_USER_PERCENTAGE=100
ENABLE_CITY2GRAPH=true

# Production Settings
DEBUG=false
ENABLE_CACHE=true
CACHE_TTL_SECONDS=300
MAX_CONCURRENT_REQUESTS=3
```

## 🎯 **¿Por qué es importante?**

### ❌ **Sin estas variables (comportamiento anterior):**
- Clustering hardcodeado solo para Chile
- París/Barcelona no se detectan como múltiples ciudades
- Routing subóptimo para viajes internacionales
- Complexity score siempre 0.0

### ✅ **Con estas variables (comportamiento mejorado):**
- Clustering automático mundial (París, Barcelona, Tokyo, etc.)
- Detección automática de múltiples ciudades
- ORTools optimiza rutas complejas
- Complexity score dinámico (ej: 6.75, 10.5)

## 📋 **Pasos para configurar en Render:**

1. **Ir al Dashboard de Render**
2. **Seleccionar el servicio Goveling ML**
3. **Environment → Environment Variables**
4. **Agregar las 3 variables críticas:**
   - `ENABLE_ORTOOLS=true`
   - `ORTOOLS_USER_PERCENTAGE=100` 
   - `ENABLE_CITY2GRAPH=true`
5. **Deploy automático se activará**

## 🧪 **Verificación post-deploy:**

Probar este endpoint para confirmar:
```bash
curl -X POST https://tu-app.onrender.com/city2graph/test-decision \
  -H "Content-Type: application/json" \
  -d '{
    "places": [
      {"name": "Torre Eiffel", "lat": 48.8583701, "lon": 2.2944813, "type": "point_of_interest"},
      {"name": "Sagrada Familia", "lat": 41.4036299, "lon": 2.1743558, "type": "point_of_interest"}
    ],
    "start_date": "2025-11-10",
    "end_date": "2025-11-12",
    "transport_mode": "drive"
  }'
```

**Respuesta esperada:**
```json
{
  "decision": {
    "complexity_score": 6.75,
    "factors": {
      "multi_city": {
        "cities": ["barcelona", "paris"]
      }
    }
  }
}
```

## ⚠️ **Si NO configurar las variables:**
- El sistema seguirá funcionando
- Pero solo con capacidades básicas (Chile)
- París/Barcelona no se optimizarán correctamente
- Experiencia subóptima para usuarios internacionales

---
**📅 Fecha:** 11 Nov 2025  
**🔧 Cambio:** ORTools habilitado para clustering mundial  
**👤 Configuración:** 5 minutos en dashboard Render  