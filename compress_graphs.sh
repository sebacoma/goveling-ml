#!/bin/bash
# 🗜️ COMPRIMIR GRAFOS PARA GOOGLE DRIVE
# Generado automáticamente - 2025-11-02T22:25:59.031863

echo "🗜️ COMPRIMIENDO GRAFOS DE CHILE PARA GOOGLE DRIVE"
echo "================================================="

cd cache/

# Verificar que existen los archivos
missing_files=0

for file in chile_graph_cache.pkl chile_nodes_dict.pkl santiago_metro_walking_cache.pkl santiago_metro_cycling_cache.pkl; do
    if [ ! -f "$file" ]; then
        echo "❌ Archivo faltante: $file"
        missing_files=$((missing_files + 1))
    fi
done

if [ $missing_files -gt 0 ]; then
    echo "❌ Faltan $missing_files archivos. Generar cache primero."
    exit 1
fi

echo "📊 Tamaños originales:"
du -sh *.pkl | head -4

echo ""
echo "🗜️ Comprimiendo archivos..."

# Comprimir cada archivo con estadísticas
for file in chile_graph_cache.pkl chile_nodes_dict.pkl santiago_metro_walking_cache.pkl santiago_metro_cycling_cache.pkl; do
    echo "   📦 Comprimiendo $file..."
    gzip -c "$file" > "${file}.gz"
    
    original_size=$(du -sh "$file" | cut -f1)
    compressed_size=$(du -sh "${file}.gz" | cut -f1)
    echo "   ✅ $file: $original_size → $compressed_size"
done

echo ""
echo "📊 Archivos comprimidos listos:"
du -sh *.pkl.gz

echo ""
echo "✅ COMPRESIÓN COMPLETADA"
echo "======================="
echo ""
echo "📋 SIGUIENTE PASO:"
echo "1. Subir archivos *.pkl.gz a Google Drive"
echo "2. Configurar como públicos"
echo "3. Copiar FILE_IDs al archivo de configuración"
echo ""
echo "📂 Archivos para subir:"
ls -la *.pkl.gz
