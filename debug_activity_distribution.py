#!/usr/bin/env python3

import requests
import json

def debug_activity_distribution():
    """Debug específico de por qué las actividades no se distribuyen"""
    
    url = "http://localhost:8002/api/v2/itinerary/generate-hybrid"
    
    # Caso simple para debug
    data = {
        "places": [
            {"name": "Museo Regional de Antofagasta", "lat": -23.6525, "lon": -70.398611, "type": "museum", "priority": 5},
            {"name": "Café en Isla de Pascua", "lat": -27.149, "lon": -109.433, "type": "restaurant", "priority": 5}
        ],
        "start_date": "2025-08-12",
        "end_date": "2025-08-13",
        "transport_mode": "walk"
    }
    
    print("🔍 DEBUG: ¿Por qué las actividades no se distribuyen?")
    print("=" * 60)
    
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        
        print(f"\n📊 ACTIVIDADES POR DÍA:")
        for i, day in enumerate(result.get('itinerary', [])):
            activities = day.get('places', [])  # Puede ser 'places' en lugar de 'activities'
            if not activities:
                activities = day.get('activities', [])
            
            print(f"  Día {i+1} ({day.get('date')}):")
            print(f"    Activities: {len(activities)}")
            if activities:
                for j, act in enumerate(activities):
                    print(f"      {j+1}. {act.get('name')} ({act.get('lat')}, {act.get('lng', act.get('lon'))})")
            else:
                print(f"      ❌ Sin actividades")
            
            print(f"    Transfers: {len(day.get('transfers', []))}")
            for transfer in day.get('transfers', []):
                print(f"      🚗 {transfer.get('from')} → {transfer.get('to')} ({transfer.get('mode')})")
                
            base = day.get('base')
            if base:
                print(f"    Base: {base.get('name')} ({base.get('lat')}, {base.get('lon')})")
            else:
                print(f"    ❌ Sin base")
        
        print(f"\n🎯 MÉTRICAS:")
        metrics = result.get('optimization_metrics', {})
        print(f"  total_distance_km: {metrics.get('total_distance_km')}")
        print(f"  intercity_transfers: {len(metrics.get('intercity_transfers', []))}")
        
        print(f"\n📝 RECOMENDACIONES:")
        for rec in result.get('recommendations', []):
            print(f"  • {rec}")
            
    else:
        print(f"❌ Error: {response.json()}")

if __name__ == "__main__":
    debug_activity_distribution()
