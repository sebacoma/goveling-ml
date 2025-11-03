#!/usr/bin/env python3
"""
🌍 Validador geográfico para el endpoint multimodal
"""

def validate_geographic_scope(places):
    """
    Validar si los lugares están dentro de un ámbito geográfico razonable
    """
    import math
    
    def haversine_distance(lat1, lon1, lat2, lon2):
        """Calcular distancia haversine entre dos puntos"""
        R = 6371  # Radio de la Tierra en km
        
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    # Límites geográficos de Chile (aproximados)
    CHILE_BOUNDS = {
        'north': -17.5,    # Arica
        'south': -56.0,    # Cabo de Hornos  
        'west': -81.0,     # Isla de Pascua
        'east': -66.0      # Frontera con Argentina
    }
    
    places_in_chile = []
    places_outside_chile = []
    max_distance = 0
    
    for place in places:
        lat = place.get('lat', 0)
        lon = place.get('lon', 0)
        
        # Verificar si está en Chile
        is_in_chile = (
            CHILE_BOUNDS['south'] <= lat <= CHILE_BOUNDS['north'] and
            CHILE_BOUNDS['west'] <= lon <= CHILE_BOUNDS['east']
        )
        
        if is_in_chile:
            places_in_chile.append(place)
        else:
            places_outside_chile.append(place)
    
    # Calcular distancia máxima entre lugares
    for i, place1 in enumerate(places):
        for place2 in places[i+1:]:
            dist = haversine_distance(
                place1.get('lat', 0), place1.get('lon', 0),
                place2.get('lat', 0), place2.get('lon', 0)
            )
            max_distance = max(max_distance, dist)
    
    return {
        'places_in_chile': len(places_in_chile),
        'places_outside_chile': len(places_outside_chile),
        'max_distance_km': max_distance,
        'is_chile_focused': len(places_outside_chile) == 0,
        'is_mixed_geography': len(places_in_chile) > 0 and len(places_outside_chile) > 0,
        'is_international_trip': len(places_in_chile) == 0,
        'warning_needed': max_distance > 5000,  # Más de 5000km
        'chile_places': places_in_chile,
        'international_places': places_outside_chile
    }

# Test del validador
if __name__ == "__main__":
    # Test con lugares internacionales
    test_places = [
        {"name": "Times Square", "lat": 40.7589, "lon": -73.9851},
        {"name": "Torre Eiffel", "lat": 48.8584, "lon": 2.2945},
        {"name": "Plaza de Armas Santiago", "lat": -33.4372, "lon": -70.6506}
    ]
    
    result = validate_geographic_scope(test_places)
    
    print("🌍 Validación Geográfica")
    print("========================")
    print(f"📍 Lugares en Chile: {result['places_in_chile']}")
    print(f"🌎 Lugares internacionales: {result['places_outside_chile']}")
    print(f"📏 Distancia máxima: {result['max_distance_km']:.0f}km")
    print(f"⚠️  Necesita advertencia: {result['warning_needed']}")
    
    if result['is_chile_focused']:
        print("✅ Itinerario enfocado en Chile - Óptimo para sistema multimodal")
    elif result['is_mixed_geography']:
        print("⚠️  Itinerario mixto - Funcionará pero con limitaciones")
    elif result['is_international_trip']:
        print("🌍 Itinerario completamente internacional - Usará servicios globales")
    
    print(f"\n🔧 Lugares en Chile:")
    for place in result['chile_places']:
        print(f"   • {place['name']}")
    
    print(f"\n🌎 Lugares internacionales:")
    for place in result['international_places']:
        print(f"   • {place['name']}")