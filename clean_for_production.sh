#!/bin/bash
# 🧹 CLEAN_FOR_PRODUCTION.sh - Limpieza automática para deployment

echo "🧹 INICIANDO LIMPIEZA PARA PRODUCCIÓN..."
echo "======================================"

# Backup original structure
echo "📋 Creando backup del proyecto original..."
cp -r . ../goveling-ml-backup-$(date +%Y%m%d-%H%M%S) 2>/dev/null || echo "⚠️ No se pudo crear backup"

# Remove all test files
echo "🗑️ Eliminando archivos de testing..."
rm -f test_*.py
rm -f analyze_*.py  
rm -f example_*.py
rm -f verify_*.py
rm -f generate_*.py

# Remove test directories
echo "🗑️ Eliminando directorios de testing..."
rm -rf tests/

# Remove duplicate documentation
echo "📄 Limpiando documentación duplicada..."
rm -f MULTIMODAL_COMPLETADO.md
rm -f SISTEMA_MULTIMODAL_COMPLETADO.md

# Remove cache backups  
echo "💾 Limpiando backups de cache..."
rm -rf cache_backup/

# Remove Python cache
echo "🐍 Limpiando cache de Python..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

# Create production requirements (optimized)
echo "📦 Optimizando requirements.txt..."
cat > requirements_production.txt << 'EOF'
# PRODUCTION REQUIREMENTS - Goveling ML Multimodal API

# Core Framework (Essential)
fastapi>=0.104.0
uvicorn>=0.24.0
pydantic>=2.5.0
pydantic-settings>=2.1.0

# HTTP Clients (Essential)  
httpx>=0.25.0
aiohttp>=3.9.0

# Environment & Config (Essential)
python-dotenv>=1.0.0
typing-extensions>=4.8.0

# Core Data Processing (Essential)
pandas>=1.5.0
numpy>=1.24.0
geopy>=2.3.0

# Location Services (Essential)
overpy>=0.6

# Routing & Optimization (Multimodal Core)
networkx>=3.0
scipy>=1.10.0

# Optional: ML & Advanced Features (if used)
scikit-learn>=1.2.0
joblib>=1.2.0

# Optional: OR-Tools (Recommended for performance)
# ortools>=9.0
EOF

# Create optimized deployment script
echo "🚀 Creando script de deployment optimizado..."
cat > deploy_production.sh << 'EOF'
#!/bin/bash
# 🚀 PRODUCTION DEPLOYMENT - Goveling ML Multimodal API

echo "🚀 INICIANDO DEPLOYMENT DE PRODUCCIÓN..."
echo "======================================="

# Set production environment
export DEBUG=false
export ENABLE_CACHE=true
export CACHE_TTL_SECONDS=300
export MAX_CONCURRENT_REQUESTS=3

# Install production dependencies
echo "📦 Instalando dependencias de producción..."
pip install --no-cache-dir -r requirements.txt

# Verify critical files
echo "🔍 Verificando archivos críticos..."
critical_files=("api.py" "settings.py" "requirements.txt")
for file in "${critical_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ ERROR: $file no encontrado"
        exit 1
    fi
done

# Clean Python artifacts
echo "🧹 Limpiando artefactos de Python..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

# Verify essential environment variables
echo "⚙️ Verificando variables de entorno esenciales..."
if [ -z "$GOOGLE_MAPS_API_KEY" ] && [ -z "$GOOGLE_PLACES_API_KEY" ]; then
    echo "⚠️ WARNING: Google API keys no configuradas. Algunas funciones pueden fallar."
fi

# Memory check
echo "💾 Verificando memoria disponible..."
available_memory=$(free -m 2>/dev/null | grep '^Mem:' | awk '{print $7}' || echo "unknown")
if [ "$available_memory" != "unknown" ] && [ "$available_memory" -lt 1024 ]; then
    echo "⚠️ WARNING: Memoria disponible < 1GB. Chile graphs requieren ~2.5GB."
fi

echo "✅ DEPLOYMENT PREPARADO"
echo "======================="
echo "🎯 Para ejecutar: uvicorn api:app --host 0.0.0.0 --port \${PORT:-8000}"
echo "📊 Endpoints disponibles:"
echo "   - POST /itinerary/multimodal (Principal)"
echo "   - GET /health (Health check)"
echo "   - GET /health/multimodal (Sistema multimodal)"
echo "📋 Documentación: FRONTEND_API_GUIDE.md"
EOF

chmod +x deploy_production.sh

# Show final structure
echo ""
echo "✅ LIMPIEZA COMPLETADA"
echo "======================"
echo ""
echo "📂 ESTRUCTURA FINAL DE PRODUCCIÓN:"
find . -name "*.py" -o -name "*.md" -o -name "*.txt" -o -name "*.sh" | grep -v __pycache__ | sort

echo ""
echo "📊 ESTADÍSTICAS:"
total_files=$(find . -type f | grep -v __pycache__ | wc -l)
python_files=$(find . -name "*.py" | wc -l)
echo "   📁 Total archivos: $total_files"
echo "   🐍 Archivos Python: $python_files" 

echo ""
echo "🚀 SIGUIENTE PASO:"
echo "   Ejecutar: ./deploy_production.sh"
echo ""
echo "📋 ARCHIVOS ESENCIALES MANTENIDOS:"
echo "   ✅ api.py (Aplicación principal)"
echo "   ✅ settings.py (Configuración)"
echo "   ✅ requirements.txt (Dependencias)"
echo "   ✅ FRONTEND_API_GUIDE.md (Docs frontend)"
echo "   ✅ models/ services/ utils/ (Core system)"
echo "   ✅ cache/ (Graphs multimodales)"
echo ""
echo "❌ ARCHIVOS ELIMINADOS:"
echo "   🧪 test_*.py (Testing innecesario)"
echo "   📊 analyze_*.py (Análisis desarrollo)"  
echo "   📝 Documentación duplicada"
echo "   💾 Cache backups"
echo ""