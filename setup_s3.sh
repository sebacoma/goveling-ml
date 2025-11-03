#!/bin/bash

# 🚀 SETUP COMPLETO: AMAZON S3 PARA GRAFOS DE CHILE
# Automatiza el proceso de configuración y upload a S3

echo "☁️ GOVELING ML - SETUP AMAZON S3"
echo "=================================="
echo ""

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Verificar dependencias
echo "📋 Verificando dependencias..."

# Verificar boto3
python3 -c "import boto3" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "   ${GREEN}✅ boto3 disponible${NC}"
else
    echo -e "   ${RED}❌ boto3 no encontrado${NC}"
    echo -e "   ${YELLOW}💡 Instalando: pip install boto3${NC}"
    pip install boto3
fi

# Verificar AWS CLI (opcional)
if command -v aws &> /dev/null; then
    echo -e "   ${GREEN}✅ AWS CLI disponible${NC}"
    aws_version=$(aws --version 2>&1 | cut -d' ' -f1)
    echo "      📦 $aws_version"
else
    echo -e "   ${YELLOW}⚠️ AWS CLI no instalado (opcional)${NC}"
    echo "      💡 Para instalar: curl 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o 'awscliv2.zip' && unzip awscliv2.zip && sudo ./aws/install"
fi

echo ""

# Verificar archivos de grafos
echo "📋 Verificando archivos de grafos..."

CACHE_FILES=(
    "cache/chile_graph_cache.pkl"
    "cache/chile_nodes_dict.pkl" 
    "cache/santiago_metro_walking_cache.pkl"
    "cache/santiago_metro_cycling_cache.pkl"
)

MISSING_FILES=()
TOTAL_SIZE=0

for file in "${CACHE_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        MISSING_FILES+=("$file")
    else
        size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null)
        TOTAL_SIZE=$((TOTAL_SIZE + size))
        size_mb=$((size / 1024 / 1024))
        echo -e "   ${GREEN}✅ $(basename "$file")${NC} (${size_mb}MB)"
    fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo -e "\n${RED}❌ Archivos faltantes:${NC}"
    printf '   %s\n' "${MISSING_FILES[@]}"
    echo ""
    echo -e "${YELLOW}💡 Genera los grafos primero ejecutando:${NC}"
    echo "   python generate_chile_multimodal.py"
    exit 1
fi

total_size_gb=$((TOTAL_SIZE / 1024 / 1024 / 1024))
total_size_mb=$((TOTAL_SIZE / 1024 / 1024))
echo -e "\n${BLUE}📊 Tamaño total: ${total_size_mb}MB (${total_size_gb}.${TOTAL_SIZE}GB)${NC}"

echo ""

# Comprimir archivos para S3
echo "🗜️ Preparando archivos para S3..."
cd cache/

compressed_size=0
for pkl_file in chile_graph_cache.pkl chile_nodes_dict.pkl santiago_metro_walking_cache.pkl santiago_metro_cycling_cache.pkl; do
    if [ ! -f "${pkl_file}.gz" ] || [ "$pkl_file" -nt "${pkl_file}.gz" ]; then
        echo "   🔄 Comprimiendo $pkl_file..."
        gzip -c "$pkl_file" > "${pkl_file}.gz"
        
        # Mostrar reducción de tamaño
        original_size=$(stat -f%z "$pkl_file" 2>/dev/null || stat -c%s "$pkl_file")
        compressed_file_size=$(stat -f%z "${pkl_file}.gz" 2>/dev/null || stat -c%s "${pkl_file}.gz")
        
        original_mb=$((original_size / 1024 / 1024))
        compressed_mb=$((compressed_file_size / 1024 / 1024))
        reduction=$(( (original_size - compressed_file_size) * 100 / original_size ))
        
        echo -e "      ${GREEN}└─ ${original_mb}MB → ${compressed_mb}MB (${reduction}% reducción)${NC}"
    else
        compressed_file_size=$(stat -f%z "${pkl_file}.gz" 2>/dev/null || stat -c%s "${pkl_file}.gz")
        echo -e "   ${GREEN}✅ $pkl_file ya comprimido${NC}"
    fi
    
    compressed_size=$((compressed_size + compressed_file_size))
done

cd ..

compressed_size_mb=$((compressed_size / 1024 / 1024))
savings=$(( (TOTAL_SIZE - compressed_size) * 100 / TOTAL_SIZE ))
echo -e "\n${BLUE}📦 Total comprimido: ${compressed_size_mb}MB (${savings}% ahorro)${NC}"

echo ""

# Crear configuración S3 si no existe
echo "📝 Configurando S3..."

if [ ! -f "s3_config.json" ]; then
    if [ -f "s3_config.template.json" ]; then
        echo "   📄 Creando s3_config.json desde template..."
        cp s3_config.template.json s3_config.json
        echo -e "   ${YELLOW}⚠️ NECESITAS actualizar s3_config.json con:${NC}"
        echo "      • Tu bucket name real"
        echo "      • Tus credenciales AWS"
        echo "      • Región preferida"
    else
        echo -e "   ${RED}❌ Template no encontrado: s3_config.template.json${NC}"
        exit 1
    fi
else
    echo -e "   ${GREEN}✅ s3_config.json ya existe${NC}"
fi

echo ""

# Verificar configuración S3
echo "🔍 Verificando configuración S3..."

python3 -c "
import json
import sys

try:
    with open('s3_config.json', 'r') as f:
        config = json.load(f)
    
    # Verificar campos requeridos
    required = ['bucket_name', 'region', 'files']
    missing = [field for field in required if field not in config]
    
    if missing:
        print(f'❌ Campos faltantes en s3_config.json: {missing}')
        sys.exit(1)
    
    # Verificar credenciales
    has_keys = 'aws_access_key_id' in config and 'aws_secret_access_key' in config
    has_env = 'AWS_ACCESS_KEY_ID' in __import__('os').environ
    
    if config['aws_access_key_id'] == 'YOUR_ACCESS_KEY_ID':
        print('⚠️ Necesitas actualizar las credenciales AWS en s3_config.json')
        if not has_env:
            print('💡 O configura variables de entorno: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY')
            sys.exit(1)
    
    print(f'✅ Configuración válida: bucket={config[\"bucket_name\"]}, region={config[\"region\"]}')
    print(f'📁 Archivos configurados: {len(config[\"files\"])}')
    
except Exception as e:
    print(f'❌ Error verificando configuración: {e}')
    sys.exit(1)
" 

config_status=$?

echo ""

if [ $config_status -eq 0 ]; then
    echo -e "${GREEN}🎯 CONFIGURACIÓN LISTA PARA S3${NC}"
    echo ""
    echo "🚀 PRÓXIMOS PASOS:"
    echo "=================="
    echo ""
    echo "1️⃣ CONFIGURAR CREDENCIALES AWS:"
    echo "   Opción A - Variables de entorno:"
    echo "   export AWS_ACCESS_KEY_ID='your-access-key'"
    echo "   export AWS_SECRET_ACCESS_KEY='your-secret-key'"
    echo ""
    echo "   Opción B - Actualizar s3_config.json con credenciales reales"
    echo ""
    echo "   Opción C - AWS CLI (recomendado):"
    echo "   aws configure"
    echo ""
    echo "2️⃣ CREAR BUCKET S3:"
    echo "   aws s3 mb s3://your-bucket-name --region us-east-1"
    echo ""
    echo "3️⃣ SUBIR GRAFOS AUTOMÁTICAMENTE:"
    echo "   python3 utils/s3_graphs_manager.py"
    echo "   # Elegir opción 3: 'Subir todos los grafos a S3'"
    echo ""
    echo "4️⃣ PROBAR DESCARGA:"
    echo "   python3 utils/s3_graphs_manager.py"
    echo "   # Elegir opción 2: 'Descargar todos los grafos desde S3'"
    echo ""
    echo "5️⃣ PROBAR API:"
    echo "   python3 api.py"
    echo "   # Endpoint /multimodal/chile funcionará con cache S3"
    echo ""
    echo -e "${BLUE}💡 Ventajas S3 vs Google Drive:${NC}"
    echo "   ⚡ Más rápido (CDN global Amazon)"
    echo "   🔒 Más seguro (IAM policies)"
    echo "   📊 Mejor para producción"
    echo "   🔄 Versionado automático"
    echo "   💰 Costo muy bajo (~\$0.02/GB/mes)"
else
    echo -e "${RED}🔧 CONFIGURACIÓN PENDIENTE${NC}"
    echo ""
    echo "📝 PASOS PARA COMPLETAR:"
    echo "========================"
    echo ""
    echo "1. Edita s3_config.json:"
    echo "   • bucket_name: Nombre único de tu bucket"
    echo "   • aws_access_key_id: Tu Access Key ID"
    echo "   • aws_secret_access_key: Tu Secret Access Key"
    echo "   • region: Región AWS preferida (ej: us-east-1)"
    echo ""
    echo "2. Crea el bucket en AWS:"
    echo "   https://console.aws.amazon.com/s3/"
    echo ""
    echo "3. Ejecuta nuevamente: ./setup_s3.sh"
fi

echo ""
echo -e "${GREEN}🎉 Setup S3 completado!${NC}"
echo -e "${BLUE}📖 Documentación completa: S3_SETUP.md${NC}"