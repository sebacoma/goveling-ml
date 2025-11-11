#!/bin/bash
# 🚀 RENDER.COM PRODUCTION DEPLOYMENT - Goveling ML Multimodal API

echo "🚀 INICIANDO DEPLOYMENT PARA RENDER.COM..."
echo "=========================================="

# Production environment variables
export DEBUG=false
export ENABLE_CACHE=true
export CACHE_TTL_SECONDS=300
export MAX_CONCURRENT_REQUESTS=3

# ORTools Configuration (CRITICAL for optimal performance)
export ENABLE_ORTOOLS=true
export ORTOOLS_USER_PERCENTAGE=100
export ENABLE_CITY2GRAPH=true

# Render-specific optimizations
export API_HOST=0.0.0.0
export API_PORT=${PORT:-8000}

# Install production dependencies
echo "📦 Instalando dependencias optimizadas para Render..."
pip install --no-cache-dir -r requirements.txt

# Clean Python cache and artifacts  
echo "🧹 Limpiando cache y artefactos..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

# Verify critical production files
echo "🔍 Verificando archivos críticos para producción..."
critical_files=("api.py" "settings.py" "requirements.txt")
for file in "${critical_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ ERROR CRÍTICO: $file no encontrado"
        echo "   Archivo requerido para el funcionamiento del sistema"
        exit 1
    fi
done

# Check essential directories
echo "📂 Verificando estructura de directorios esenciales..."
essential_dirs=("models" "services" "utils")
for dir in "${essential_dirs[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "⚠️ WARNING: Directorio $dir no encontrado"
    fi
done

# Verify multimodal cache exists
if [ -d "cache" ]; then
    cache_size=$(du -sh cache 2>/dev/null | cut -f1)
    echo "💾 Cache multimodal encontrado: $cache_size"
else
    echo "⚠️ WARNING: Cache multimodal no encontrado - se creará dinámicamente"
fi

# Environment validation
echo "⚙️ Validando configuración de entorno..."
if [ -z "$GOOGLE_MAPS_API_KEY" ] && [ -z "$GOOGLE_PLACES_API_KEY" ]; then
    echo "⚠️ WARNING: Google API Keys no configuradas"
    echo "   Algunas funciones de routing pueden fallar sin estas keys"
    echo "   Configurar: GOOGLE_MAPS_API_KEY y GOOGLE_PLACES_API_KEY"
fi

# Memory recommendations
echo "💾 Recomendaciones de memoria para Render:"
echo "   Mínimo: 1GB RAM (funcionalidad básica)"
echo "   Recomendado: 2GB+ RAM (cache completo Chile)"

echo ""
echo "✅ DEPLOYMENT RENDER.COM PREPARADO"
echo "=================================="
echo ""
echo "🎯 CONFIGURACIÓN DE PRODUCCIÓN:"
echo "   ✅ Cache habilitado (5 min TTL)"
echo "   ✅ Logging optimizado para producción"  
echo "   ✅ Requests paralelos limitados a 3"
echo "   ✅ Debug mode deshabilitado"
echo "   ✅ API configurada para 0.0.0.0:$API_PORT"
echo ""
echo "🚀 COMANDO DE INICIO RENDER:"
echo "   uvicorn api:app --host 0.0.0.0 --port \$PORT"
echo ""
echo "📊 ENDPOINTS DISPONIBLES:"
echo "   POST /itinerary/multimodal (Principal)"
echo "   GET /health (Health check básico)"
echo "   GET /health/multimodal (Sistema multimodal)"
echo ""
echo "📋 DOCUMENTACIÓN FRONTEND:"
echo "   Ver: FRONTEND_API_GUIDE.md"
echo ""
echo "⚡ PERFORMANCE ESPERADA:"
echo "   🇨🇱 Chile: ~5s (optimizado)"
echo "   🌍 Internacional: ~12s (fallback)"