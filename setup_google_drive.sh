#!/bin/bash

# 🚀 SETUP COMPLETO: GOOGLE DRIVE PARA GRAFOS DE CHILE
# Automatiza el proceso de configuración para subir grafos a Google Drive

echo "🎯 GOVELING ML - SETUP GOOGLE DRIVE"
echo "=================================="
echo ""

# Verificar archivos necesarios
echo "📋 Verificando archivos..."

CACHE_FILES=(
    "cache/chile_graph_cache.pkl"
    "cache/chile_nodes_dict.pkl" 
    "cache/santiago_metro_walking_cache.pkl"
    "cache/santiago_metro_cycling_cache.pkl"
)

MISSING_FILES=()

for file in "${CACHE_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo "❌ Archivos faltantes:"
    printf '%s\n' "${MISSING_FILES[@]}"
    echo ""
    echo "💡 Genera los grafos primero ejecutando:"
    echo "   python generate_chile_multimodal.py"
    exit 1
fi

echo "✅ Todos los archivos encontrados"
echo ""

# Comprimir archivos
echo "🗜️ Comprimiendo grafos para Google Drive..."
cd cache/

for pkl_file in chile_graph_cache.pkl chile_nodes_dict.pkl santiago_metro_walking_cache.pkl santiago_metro_cycling_cache.pkl; do
    if [ ! -f "${pkl_file}.gz" ] || [ "$pkl_file" -nt "${pkl_file}.gz" ]; then
        echo "   Comprimiendo $pkl_file..."
        gzip -c "$pkl_file" > "${pkl_file}.gz"
        
        # Mostrar reducción de tamaño
        original_size=$(du -h "$pkl_file" | cut -f1)
        compressed_size=$(du -h "${pkl_file}.gz" | cut -f1)
        echo "   └─ $original_size → $compressed_size"
    else
        echo "   ✅ $pkl_file ya está comprimido"
    fi
done

cd ..

echo ""
echo "📦 Archivos listos para subir:"
echo "   1. cache/chile_graph_cache.pkl.gz"
echo "   2. cache/chile_nodes_dict.pkl.gz"  
echo "   3. cache/santiago_metro_walking_cache.pkl.gz"
echo "   4. cache/santiago_metro_cycling_cache.pkl.gz"

# Calcular tamaño total
total_size=$(du -ch cache/*.pkl.gz 2>/dev/null | grep total | cut -f1)
echo "   📊 Total comprimido: $total_size"
echo ""

# Crear config template si no existe
if [ ! -f "google_drive_config.json" ]; then
    if [ -f "google_drive_config.template.json" ]; then
        echo "📝 Creando google_drive_config.json desde template..."
        cp google_drive_config.template.json google_drive_config.json
        echo "✅ Archivo creado. Necesitas actualizarlo con los FILE_IDs reales."
    else
        echo "❌ Template no encontrado: google_drive_config.template.json"
        exit 1
    fi
else
    echo "📝 google_drive_config.json ya existe"
fi

echo ""
echo "🎯 PRÓXIMOS PASOS:"
echo "=================="
echo ""
echo "1️⃣ SUBIR A GOOGLE DRIVE (Manual):"
echo "   • Ir a: https://drive.google.com"
echo "   • Crear carpeta: 'Goveling-ML-Graphs'"
echo "   • Subir los 4 archivos .gz de cache/"
echo "   • Para cada archivo: Click derecho → Compartir → 'Cualquiera con el enlace'"
echo ""
echo "2️⃣ CONFIGURAR IDs:"
echo "   • Editar: google_drive_config.json"
echo "   • Reemplazar cada 'REPLACE_WITH_FILE_ID' con el ID real"
echo "   • Ejemplo: https://drive.google.com/file/d/1abc123xyz/view → usar '1abc123xyz'"
echo ""
echo "3️⃣ PROBAR EL SISTEMA:"
echo "   • python test_google_drive_download.py"
echo "   • python api.py → Probar endpoint /multimodal/chile"
echo ""
echo "💡 Documentación completa en: GOOGLE_DRIVE_SETUP.md"
echo ""
echo "🎉 Setup completado! Los grafos seguirán funcionando localmente mientras configuras Google Drive."