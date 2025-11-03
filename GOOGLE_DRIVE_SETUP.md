
# 📂 INSTRUCCIONES: SUBIR GRAFOS A GOOGLE DRIVE

## 🎯 PASO A PASO (Manual - Una sola vez)

### 1️⃣ Comprimir grafos localmente
```bash
# Comprimir cada grafo para reducir tamaño
cd cache/

echo "🗜️ Comprimiendo grafos..."
gzip -c chile_graph_cache.pkl > chile_graph_cache.pkl.gz          # 1.8GB → ~400MB
gzip -c chile_nodes_dict.pkl > chile_nodes_dict.pkl.gz            # 488MB → ~100MB  
gzip -c santiago_metro_walking_cache.pkl > santiago_metro_walking_cache.pkl.gz  # 365MB → ~80MB
gzip -c santiago_metro_cycling_cache.pkl > santiago_metro_cycling_cache.pkl.gz  # 323MB → ~70MB
 
echo "✅ Total comprimido: ~650MB (vs 2.98GB original)"
```

### 2️⃣ Subir a Google Drive (Web Interface)
1. **Ir a**: https://drive.google.com
2. **Crear carpeta**: "Goveling-ML-Graphs" 
3. **Subir archivos**: Arrastrar los 4 archivos .gz
4. **Compartir públicamente**: 
   - Click derecho en cada archivo → "Compartir"
   - "Cambiar a cualquier persona con el enlace"
   - "Copiar enlace"

### 3️⃣ Configurar URLs en el sistema

1. **Copia el template de configuración**:
   ```bash
   cp google_drive_config.template.json google_drive_config.json
   ```

2. **Actualiza cada FILE_ID con los IDs reales de Google Drive**:
   - Para cada archivo que subiste, toma la URL compartida
   - Extrae el FILE_ID de URLs como: `https://drive.google.com/file/d/FILE_ID/view?usp=sharing`
   - Reemplaza `REPLACE_WITH_FILE_ID` en el JSON

3. **El archivo final debe verse así**:
```json
{
  "chile_graph_cache.pkl": {
    "drive_url": "https://drive.google.com/file/d/1abc123xyz/view?usp=sharing",
    "direct_url": "https://drive.google.com/uc?id=1abc123xyz&export=download",
    "description": "Grafo principal de Chile (1.8GB → 625MB comprimido)",
    "priority": "critical"
  },
  "chile_nodes_dict.pkl": {
    "drive_url": "https://drive.google.com/file/d/2def456abc/view?usp=sharing", 
    "direct_url": "https://drive.google.com/uc?id=2def456abc&export=download",
    "description": "Diccionario de nodos Chile (488MB → 240MB comprimido)",
    "priority": "critical"
  }
  // ... resto de archivos
}
```

### 4️⃣ Extraer FILE_ID de las URLs
De la URL: `https://drive.google.com/file/d/1ABC123xyz789/view?usp=sharing`
El FILE_ID es: `1ABC123xyz789`

---

## 🚀 AUTOMATIZACIÓN (Después del setup manual)

Una vez configurado, el sistema descargará automáticamente:
```python
# En producción
router = get_chile_router()
# → Detecta grafos faltantes
# → Descarga automáticamente desde Google Drive
# → 4.7s performance en lugar de 12s
```

---

## 💡 VENTAJAS DE GOOGLE DRIVE

✅ **15GB gratuitos** (vs 2.98GB necesarios)
✅ **URLs públicas** estables  
✅ **Sin autenticación** para descarga
✅ **CDN global** de Google
✅ **Interface familiar** para gestión
✅ **Backups automáticos**

---

## 📊 COMPARACIÓN DE TAMAÑOS

| Archivo | Original | Comprimido | Reducción |
|---------|----------|------------|-----------|
| chile_graph_cache.pkl | 1.8GB | ~400MB | 78% |
| chile_nodes_dict.pkl | 488MB | ~100MB | 80% |
| santiago_metro_walking_cache.pkl | 365MB | ~80MB | 78% |
| santiago_metro_cycling_cache.pkl | 323MB | ~70MB | 78% |
| **TOTAL** | **2.98GB** | **~650MB** | **78%** |

---

## ⚡ SIGUIENTE PASO

1. **Ejecutar compresión**: `bash compress_graphs.sh`
2. **Subir a Google Drive** (manual, una vez)
3. **Actualizar configuración** con FILE_IDs
4. **Testing automático** funcionará en producción

