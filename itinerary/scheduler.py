from typing import List, Dict, Any
from datetime import datetime, timedelta
from ml.pipeline import DurationModelPipeline
from settings import settings
import logging

def schedule_places(
    places: List[Dict[str, Any]],
    start_date: str,
    end_date: str,
    daily_start_hour: int = 9,
    daily_end_hour: int = 18
) -> Dict[str, Any]:
    """
    Programa lugares en días disponibles con predicciones ML.
    """
    logging.info(f"📅 Scheduler iniciado: {len(places)} lugares, {start_date} a {end_date}")
    
    try:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
    except ValueError:
        raise ValueError("Fechas deben estar en formato YYYY-MM-DD")
    
    if start_dt > end_dt:
        raise ValueError("Fecha de inicio debe ser anterior a fecha de fin")
    
    # Generar días disponibles
    days = []
    current_date = start_dt
    while current_date <= end_dt:
        days.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "activities": [],
            "available_hours": daily_end_hour - daily_start_hour
        })
        current_date += timedelta(days=1)
    
    if not days:
        raise ValueError("No hay días disponibles")
    
    logging.info(f"📅 {len(days)} días generados, {days[0]['available_hours']}h disponibles por día")
    
    # Inicializar pipeline ML
    ml_pipeline = DurationModelPipeline()
    
    # Enriquecer lugares con predicciones de duración
    enriched_places = []
    for i, place in enumerate(places):
        logging.info(f"🏛️ Procesando lugar {i+1}: {place.get('name', 'Sin nombre')} ({place.get('type', 'sin tipo')})")
        enriched_place = place.copy()
        
        # Predecir duración usando ML
        try:
            predicted_duration = ml_pipeline.predict(
                place_type=place.get('type', 'museum'),
                hour=12,  # Hora promedio del día
                day_of_week=start_dt.weekday()
            )
            enriched_place['predicted_duration_h'] = predicted_duration
            logging.info(f"⏱️ Duración predicha para {place['name']}: {predicted_duration:.2f}h")
        except Exception as e:
            logging.warning(f"Error prediciendo duración para {place['name']}: {e}")
            default_duration = _get_default_duration(place.get('type', 'museum'))
            enriched_place['predicted_duration_h'] = default_duration
            logging.info(f"⏱️ Duración por defecto para {place['name']}: {default_duration:.2f}h")
        
        enriched_places.append(enriched_place)
    
    logging.info(f"✅ {len(enriched_places)} lugares enriquecidos con duraciones")
    
    # Ordenar lugares por prioridad y duración
    enriched_places.sort(key=lambda x: (
        -x.get('priority', 5),  # Mayor prioridad primero
        x['predicted_duration_h']  # Luego por duración menor
    ))
    
    # Asignar lugares a días
    assigned_places = []
    unassigned_places = []
    
    logging.info(f"🎯 Iniciando asignación de {len(enriched_places)} lugares a días...")
    
    for place in enriched_places:
        duration = place['predicted_duration_h']
        logging.info(f"📍 Intentando asignar {place['name']} ({duration:.2f}h)")
        
        # Buscar día con espacio suficiente
        assigned = False
        for day_idx, day in enumerate(days):
            if day['available_hours'] >= duration:
                # Crear actividad con todos los campos necesarios
                activity = {
                    'name': place['name'],
                    'lat': place['lat'],
                    'lon': place['lon'],
                    'type': place.get('type', 'museum'),
                    'duration_h': duration,
                    'predicted_duration_h': duration
                }
                day['activities'].append(activity)
                day['available_hours'] -= duration
                assigned_places.append(place)
                assigned = True
                logging.info(f"✅ {place['name']} asignado al día {day_idx + 1} ({day['date']}). Horas restantes: {day['available_hours']:.1f}h")
                break
        
        if not assigned:
            unassigned_places.append(place)
            logging.warning(f"❌ {place['name']} NO pudo ser asignado (requiere {duration:.2f}h)")
    
    logging.info(f"📊 RESUMEN: {len(assigned_places)} asignados, {len(unassigned_places)} no asignados")
    
    # Limpiar campo temporal de días
    for day in days:
        del day['available_hours']
    
    return {
        "days": days,
        "unassigned": unassigned_places,
        "total_assigned": len(assigned_places),
        "total_unassigned": len(unassigned_places)
    }

def _get_default_duration(place_type: str) -> float:
    """Obtener duración por defecto para un tipo de lugar"""
    import json
    try:
        with open("data/default_durations.json", "r") as f:
            defaults = json.load(f)
        
        if place_type in defaults:
            if isinstance(defaults[place_type], list):
                return sum(defaults[place_type]) / len(defaults[place_type])
            return defaults[place_type]
        
        return defaults.get("_default", 1.5)
    except:
        return 1.5  # Fallback absoluto