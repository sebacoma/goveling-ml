#!/usr/bin/env python3

import asyncio
import logging
from datetime import datetime
from utils.hybrid_optimizer_v31 import optimize_itinerary_hybrid_v31

# Configurar logging detallado
logging.basicConfig(level=logging.DEBUG)

async def debug_activity_scheduling():
    """Debug detallado de por qué solo programa 1 actividad por cluster"""
    
    places = [
        {'name': 'BLACK ANTOFAGASTA', 'lat': -23.6627773, 'lon': -70.4004961, 'type': 'restaurant', 'priority': 5},
        {'name': 'McDonalds', 'lat': -23.6449718, 'lon': -70.40338899999999, 'type': 'restaurant', 'priority': 5},
        {'name': 'Tanta - MallPlaza Antofagasta', 'lat': -23.6446295, 'lon': -70.4023929, 'type': 'restaurant', 'priority': 5}
    ]
    
    result = await optimize_itinerary_hybrid_v31(
        places=places,
        start_date=datetime(2025, 8, 4),
        end_date=datetime(2025, 8, 6),  # Solo 2 días para focus
        daily_start_hour=9,
        daily_end_hour=18
    )
    
    print("\n=== RESULTADO FINAL ===")
    for i, day in enumerate(result['days']):
        print(f"Día {i+1}: {len(day['activities'])} actividades")
        for activity in day['activities']:
            print(f"  - {activity.name} (start: {activity.start_time}, end: {activity.end_time}, duration: {activity.duration_minutes})")
        print(f"  Tiempo libre: {day['free_minutes']} minutos")

if __name__ == "__main__":
    asyncio.run(debug_activity_scheduling())
