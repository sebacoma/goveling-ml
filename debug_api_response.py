#!/usr/bin/env python3

import requests
import json

def debug_api_response():
    """Debug completo de la respuesta del API"""
    
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
    
    print("🔍 DEBUG: Respuesta completa del API")
    print("=" * 60)
    
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("\n📊 ESTRUCTURA COMPLETA:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
        print("\n🔍 ANÁLISIS DETALLADO:")
        print(f"• Keys principales: {list(data.keys())}")
        
        if 'optimization_metrics' in data:
            metrics = data['optimization_metrics']
            print(f"• optimization_metrics keys: {list(metrics.keys())}")
            print(f"• optimization_mode: {metrics.get('optimization_mode')}")
            print(f"• fallback_active: {metrics.get('fallback_active')}")
            print(f"• efficiency_score: {metrics.get('efficiency_score')}")
        else:
            print("❌ No hay optimization_metrics en la respuesta")
            
        if 'itinerary' in data:
            itinerary = data['itinerary'] 
            print(f"• Días en itinerary: {len(itinerary)}")
            for i, day in enumerate(itinerary):
                print(f"  Día {i+1}: {list(day.keys())}")
                print(f"    Activities: {len(day.get('activities', []))}")
                print(f"    Transfers: {len(day.get('transfers', []))}")
        else:
            print("❌ No hay itinerary en la respuesta")
            
    else:
        print(f"❌ Error: {response.json()}")

if __name__ == "__main__":
    debug_api_response()
