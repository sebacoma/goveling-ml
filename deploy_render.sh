#!/bin/bash
# deploy_render.sh - Deploy optimizado para Render

echo "🚀 Preparando deploy optimizado para Render..."

# Variables de entorno para producción
export DEBUG=false
export ENABLE_CACHE=true
export CACHE_TTL_SECONDS=300
export MAX_CONCURRENT_REQUESTS=3

# Instalar dependencias optimizadas
echo "📦 Instalando dependencias..."
pip install --no-cache-dir -r requirements.txt

# Limpiar caché Python
echo "🧹 Limpiando cachés..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

# Verificar archivos críticos
echo "🔍 Verificando archivos..."
if [ ! -f "api.py" ]; then
    echo "❌ ERROR: api.py no encontrado"
    exit 1
fi

if [ ! -f "requirements.txt" ]; then
    echo "❌ ERROR: requirements.txt no encontrado"
    exit 1
fi

echo "✅ Deploy preparado. Archivos optimizados:"
echo "   - Caché habilitado (5 min TTL)"
echo "   - Logging optimizado para producción"
echo "   - Google API caché implementado"
echo "   - Requests paralelos limitados a 3"
echo "   - Debug deshabilitado"

echo "🎯 Para ejecutar: uvicorn api:app --host 0.0.0.0 --port \$PORT"