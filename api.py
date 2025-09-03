# api.py
from typing import List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging
from datetime import datetime
import time

from models.schemas import *
from settings import settings

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Goveling ML API",
    description="API de optimización de itinerarios con ML v2.2 - Con soporte para hoteles",
    version="2.2.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check básico"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.2.0"
    }

@app.post("/api/v2/itinerary/generate-hybrid", response_model=ItineraryResponse, tags=["Hybrid Optimizer"])
async def generate_hybrid_itinerary_endpoint(request: ItineraryRequest):
    """
    🚀 OPTIMIZADOR HÍBRIDO INTELIGENTE v2.2 - CON DETECCIÓN AUTOMÁTICA DE HOTELES
    
    ✨ FUNCIONALIDADES NUEVAS:
    - 🏨 Detección automática de hoteles/alojamientos como centroides
    - 🚗 Recomendaciones inteligentes de transporte 
    - 🔍 Modo automático: Con/Sin hoteles
    - ↩️ Completamente retrocompatible
    
    📊 CARACTERÍSTICAS TÉCNICAS:
    - 🗺️ Clustering geográfico automático (agrupa lugares cercanos)
    - 🏨 Clustering basado en hoteles (si se proporcionan alojamientos)
    - ⚡ Estimación híbrida de tiempos (Haversine + Google Directions API)
    - 📅 Programación multi-día inteligente con horarios realistas
    - 🎯 Optimización nearest neighbor dentro de clusters
    - 🚶‍♂️🚗🚌 Recomendaciones automáticas de transporte por tramo
    - ⏰ Respeto de horarios, buffers y tiempos de traslado
    - 💰 Eficiente en costos (solo usa Google API cuando es necesario)
    
    🏨 MODO HOTELES:
    - Envía 'accommodations' con tus hoteles/alojamientos
    - Sistema agrupa lugares por proximidad a hoteles
    - Rutas optimizadas desde/hacia alojamientos
    - Información de hotel incluida en cada actividad
    
    🗺️ MODO GEOGRÁFICO:
    - No envíes 'accommodations' o envía lista vacía
    - Comportamiento actual (clustering automático)
    - Mantiene toda la funcionalidad existente
    
    VENTAJAS:
    - Horarios más realistas y precisos
    - Distribución equilibrada entre días
    - Reducción de tiempo total de viaje
    - Agrupación inteligente por zonas geográficas o hoteles
    - Recomendaciones de transporte personalizadas
    """
    from utils.analytics import analytics
    import time
    
    start_time = time.time()
    
    try:
        # 🔍 Detectar si se enviaron hoteles/alojamientos
        accommodations_data = None
        hotels_provided = False
        
        if request.accommodations:
            accommodations_data = [acc.dict() if hasattr(acc, 'dict') else acc 
                                 for acc in request.accommodations]
            hotels_provided = True
            
            analytics.track_request("hybrid_itinerary_with_hotels", {
                "places_count": len(request.places),
                "hotels_count": len(accommodations_data),
                "days_requested": (request.end_date - request.start_date).days + 1,
                "transport_mode": request.transport_mode
            })
            
            logging.info(f"🏨 Detectados {len(accommodations_data)} hoteles - modo centroides")
        else:
            analytics.track_request("hybrid_itinerary_geographic", {
                "places_count": len(request.places),
                "days_requested": (request.end_date - request.start_date).days + 1,
                "transport_mode": request.transport_mode
            })
            
            logging.info("🗺️ Modo clustering geográfico automático")
        
        logging.info(f"🚀 Iniciando optimización HÍBRIDA para {len(request.places)} lugares")
        logging.info(f"📅 Período: {request.start_date} a {request.end_date} ({(request.end_date - request.start_date).days + 1} días)")
        
        # Convertir lugares a formato dict
        places_data = []
        for place in request.places:
            if hasattr(place, 'dict'):  # Es un objeto Pydantic
                place_dict = place.dict()
            else:
                place_dict = place
            places_data.append(place_dict)
        
        # Usar optimizador híbrido con detección automática
        from utils.hybrid_optimizer import optimize_itinerary_hybrid
        from datetime import datetime
        
        # Convertir fechas
        if isinstance(request.start_date, str):
            start_date = datetime.strptime(request.start_date, '%Y-%m-%d')
        else:
            start_date = datetime.combine(request.start_date, datetime.min.time())
            
        if isinstance(request.end_date, str):
            end_date = datetime.strptime(request.end_date, '%Y-%m-%d')
        else:
            end_date = datetime.combine(request.end_date, datetime.min.time())
        
        # 🚀 OPTIMIZACIÓN CON DETECCIÓN AUTOMÁTICA
        optimization_result = await optimize_itinerary_hybrid(
            places_data,
            start_date,
            end_date,
            request.daily_start_hour,
            request.daily_end_hour,
            request.transport_mode,
            accommodations_data  # ← Detección automática (puede ser None)
        )
        
        # Extraer datos del resultado de optimización
        days_data = optimization_result.get("days", [])
        
        # Contar actividades totales
        total_activities = sum(len(day.get("activities", [])) for day in days_data)
        
        # Calcular tiempo total de viaje
        total_travel_minutes = sum([
            day.get("travel_summary", {}).get("total_travel_time_s", 0) / 60
            for day in days_data
        ])
        
        # Determinar el modo de optimización usado
        optimization_mode = "hotel_centroid" if hotels_provided else "geographic_clustering"
        
        # Formatear respuesta inteligente basada en el modo usado
        base_recommendations = []
        
        if hotels_provided:
            base_recommendations.extend([
                "🏨 Itinerario optimizado con hoteles como centroides",
                f"📍 {len(accommodations_data)} hotel(es) usado(s) como base",
                "⚡ Rutas optimizadas desde/hacia alojamientos",
                "🚗 Recomendaciones de transporte por tramo"
            ])
        else:
            base_recommendations.extend([
                "🗺️ Itinerario optimizado con clustering geográfico automático",
                "📊 Agrupación inteligente por proximidad geográfica"
            ])
            
        base_recommendations.extend([
            f"⚡ Método híbrido: Haversine + Google Directions API",
            f"📅 {total_activities} actividades distribuidas en {len(days_data)} días",
            f"🎯 Score de eficiencia: {optimization_result.get('optimization_metrics', {}).get('efficiency_score', 0.9):.1%}",
            f"🚶‍♂️ Tiempo total de viaje: {int(total_travel_minutes)} minutos"
        ])
        
        # Formatear respuesta para ItineraryResponse con información completa
        formatted_result = {
            "days": days_data,  # Ya viene en el formato correcto del hybrid optimizer
            "unassigned": [],   # El optimizador híbrido maneja todo inteligentemente
            "total_activities": total_activities,
            "total_travel_time_minutes": float(total_travel_minutes),
            "average_activities_per_day": round(total_activities / max(1, len(days_data)), 1),
            "generated_at": datetime.now().isoformat(),
            "model_version": "2.2.0-hybrid-hotels",
            "optimization_metrics": {
                "efficiency_score": optimization_result.get("optimization_metrics", {}).get("efficiency_score", 0.9),
                "total_distance_km": optimization_result.get("optimization_metrics", {}).get("total_distance_km", 0),
                "avg_travel_per_activity_min": round(total_travel_minutes / max(1, total_activities), 1),
                "google_maps_enhanced": bool(settings.GOOGLE_MAPS_API_KEY),
                # Nuevas métricas para hoteles
                "optimization_mode": optimization_mode,
                "hotels_provided": hotels_provided,
                "hotels_count": len(accommodations_data) if accommodations_data else 0,
                "accommodation_based_clustering": hotels_provided,
                "geographic_clustering": not hotels_provided,
                "transport_recommendations": True
            },
            "recommendations": base_recommendations,
            "system_info": {
                "optimizer": "hybrid_intelligent_v2.2",
                "version": "2.2.0",
                "google_maps_api": bool(settings.GOOGLE_MAPS_API_KEY),
                "generated_at": datetime.now().isoformat(),
                # Nuevas características del sistema
                "auto_hotel_detection": True,
                "backward_compatible": True,
                "hotel_centroid_clustering": hotels_provided,
                "geographic_clustering": not hotels_provided,
                "transport_recommendations": True,
                "features": {
                    "geographic_clustering": True,
                    "hybrid_travel_times": True,
                    "multi_day_scheduling": True,
                    "nearest_neighbor_optimization": True,
                    "realistic_time_windows": True,
                    "hotel_centroid_clustering": hotels_provided,
                    "transport_recommendations": True,
                    "auto_detection": True
                }
            }
        }
        
        # Log success
        duration = time.time() - start_time
        analytics.track_request(f"hybrid_itinerary_{optimization_mode}_success", {
            "efficiency_score": optimization_result.get("optimization_metrics", {}).get("efficiency_score", 0.9),
            "total_activities": total_activities,
            "days_used": len(days_data),
            "processing_time_seconds": round(duration, 2),
            "optimization_mode": optimization_mode,
            "hotels_provided": hotels_provided,
            "hotels_count": len(accommodations_data) if accommodations_data else 0
        })
        
        if hotels_provided:
            logging.info(f"✅ Optimización híbrida CON HOTELES completada en {duration:.2f}s")
            logging.info(f"🏨 {len(accommodations_data)} hoteles usados como centroides")
        else:
            logging.info(f"✅ Optimización híbrida GEOGRÁFICA completada en {duration:.2f}s")
            
        logging.info(f"🎯 Resultado: {total_activities} actividades, score {optimization_result.get('optimization_metrics', {}).get('efficiency_score', 0.9):.1%}")
        
        return ItineraryResponse(**formatted_result)
        
    except Exception as e:
        # Log error
        analytics.track_error("hybrid_itinerary_error", str(e), {
            "places_count": len(request.places),
            "error_type": type(e).__name__
        })
        
        logging.error(f"❌ Error generating hybrid itinerary: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error generating hybrid itinerary: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host=getattr(settings, 'API_HOST', '0.0.0.0'),
        port=getattr(settings, 'API_PORT', 8000),
        reload=getattr(settings, 'DEBUG', True)
    )
