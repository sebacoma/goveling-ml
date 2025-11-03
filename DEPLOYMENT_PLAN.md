# 🚀 DEPLOYMENT PLAN - Goveling ML Production

## 📋 **ARCHIVOS PARA PRODUCCIÓN**

### ✅ **ESENCIALES (Mantener)**
```
📂 CORE FILES
├── api.py                    # Main FastAPI application 
├── settings.py               # Configuration management
├── requirements.txt          # Dependencies
├── FRONTEND_API_GUIDE.md     # Documentation for frontend team
└── README.md                 # Project overview

📂 MODELS/
├── schemas.py               # Pydantic models
└── (other model files)

📂 SERVICES/
├── google_places_service.py
├── hotel_recommender.py
├── multi_city_optimizer_simple.py
├── city_clustering_service.py
├── hybrid_city2graph_service.py
├── ortools_monitoring.py
└── (all service files)

📂 UTILS/
├── logging_config.py
├── performance_cache.py
├── hybrid_optimizer_v31.py
├── geo_utils.py
├── geographic_validator.py
├── hybrid_routing_service.py
└── (essential utility files)

📂 DATA CACHES/
├── cache/                   # Runtime cache (2.5GB Chile graphs)
├── city2graph_cache/
└── city2graph_real_cache/
```

---

## ❌ **ARCHIVOS A ELIMINAR (No necesarios en producción)**

### 🧪 **Testing Files**
```bash
# Remove all test files
rm test_*.py
rm -rf tests/
rm analyze_*.py
rm example_*.py
rm verify_*.py
rm generate_*.py
```

### 📝 **Duplicate Documentation**
```bash
# Keep only essential docs
rm MULTIMODAL_COMPLETADO.md
rm SISTEMA_MULTIMODAL_COMPLETADO.md
# Keep: FRONTEND_API_GUIDE.md and README.md
```

### 🗑️ **Development Cache Backups**
```bash
# Remove backup caches
rm -rf cache_backup/
rm -rf __pycache__/
```

---

## 🏗️ **PRODUCTION STRUCTURE**

### **Final Production Files:**
```
goveling-ml-production/
├── api.py                 # 🚀 Main application
├── settings.py            # ⚙️ Configuration  
├── requirements.txt       # 📦 Dependencies
├── deploy.sh              # 🔧 Deployment script
├── README.md              # 📖 Essential docs
├── FRONTEND_API_GUIDE.md  # 📋 Frontend integration
│
├── models/                # 📊 Data models
│   ├── schemas.py
│   └── ...
│
├── services/              # 🎯 Core services  
│   ├── google_places_service.py
│   ├── hotel_recommender.py
│   ├── hybrid_city2graph_service.py
│   ├── ortools_monitoring.py
│   └── ...
│
├── utils/                 # 🛠️ Utilities
│   ├── hybrid_optimizer_v31.py
│   ├── hybrid_routing_service.py
│   ├── performance_cache.py
│   ├── logging_config.py
│   └── ...
│
└── cache/                 # 💾 Runtime data
    ├── (Chile 2.5GB graphs)
    └── (Dynamic cache files)
```

---

## 🔧 **PRODUCTION DEPLOYMENT SCRIPT**

### **Environment Variables Required:**
```bash
# Core API Settings
export API_HOST=0.0.0.0
export API_PORT=${PORT:-8000}
export DEBUG=false

# Performance Optimization  
export ENABLE_CACHE=true
export CACHE_TTL_SECONDS=300
export MAX_CONCURRENT_REQUESTS=3

# Google Services (Required)
export GOOGLE_MAPS_API_KEY=your_api_key_here
export GOOGLE_PLACES_API_KEY=your_api_key_here

# Optional: OR-Tools (Recommended)
export ENABLE_ORTOOLS=true
export ORTOOLS_USER_PERCENTAGE=100
export ORTOOLS_TIMEOUT_SECONDS=30

# Optional: External APIs
export OSRM_SERVER_URL=http://router.project-osrm.org
```

### **Deployment Commands:**
```bash
# 1. Install dependencies
pip install --no-cache-dir -r requirements.txt

# 2. Clean Python cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null

# 3. Start production server
uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
```

---

## 📊 **PRODUCTION FEATURES**

### **API Endpoints Ready:**
- ✅ `/itinerary/multimodal` - Universal itinerary generation  
- ✅ `/health` - System health check
- ✅ `/health/multimodal` - Multimodal system health
- ✅ `/performance/stats` - Performance monitoring

### **Performance Characteristics:**
- 🇨🇱 **Chile**: ~5s response time (optimized graphs)
- 🌍 **International**: ~12s response time (fallback routing)
- 💾 **Memory**: ~500MB base + 2.5GB Chile cache (lazy loaded)
- 🔄 **Fallback**: OSRM → Google → Euclidean routing

### **Production Features:**
- ✅ **Lazy Loading**: Chile graphs loaded on first request
- ✅ **Circuit Breakers**: Robust error handling
- ✅ **Performance Caching**: 5-minute response cache
- ✅ **Global Support**: Works worldwide with intelligent fallbacks
- ✅ **Cost Optimization**: OSRM (free) prioritized over Google

---

## 🎯 **DEPLOYMENT PLATFORMS**

### **Render.com (Recommended)**
```bash
# Build Command: 
pip install -r requirements.txt

# Start Command:
uvicorn api:app --host 0.0.0.0 --port $PORT
```

### **Railway/Vercel/Heroku**
```bash
# All support the same uvicorn start command
# Ensure environment variables are properly set
```

---

## ✅ **POST-DEPLOYMENT VERIFICATION**

### **Health Checks:**
```bash
# Basic health
curl https://your-domain.com/health

# Multimodal system health  
curl https://your-domain.com/health/multimodal

# Test Chile optimization
curl -X POST https://your-domain.com/itinerary/multimodal \
  -H "Content-Type: application/json" \
  -d '{"places": [{"name": "Plaza de Armas", "lat": -33.4378, "lng": -70.6504, "visit_duration_minutes": 45}], "start_time": "10:00", "available_time_hours": 6, "transportation_mode": "walk"}'

# Test international fallback
curl -X POST https://your-domain.com/itinerary/multimodal \
  -H "Content-Type: application/json" \
  -d '{"places": [{"name": "Times Square", "lat": 40.7580, "lng": -73.9855, "visit_duration_minutes": 60}], "start_time": "09:00", "available_time_hours": 8, "transportation_mode": "walk"}'
```

---

## 🚨 **CRITICAL REQUIREMENTS**

### **Must Have:**
1. **GOOGLE_MAPS_API_KEY** - Essential for routing
2. **Memory**: Minimum 1GB RAM for Chile graphs
3. **Persistent Storage**: 3GB for cache files

### **Recommended:**
1. **OR-Tools enabled** for optimal performance
2. **Multiple workers** for high concurrency (if supported)
3. **CDN/Cache layer** for static assets

---

**Status**: ✅ Ready for Production Deployment 🚀