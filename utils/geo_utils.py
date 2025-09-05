import math
from typing import Tuple, Literal, List, Dict, Any
from settings import settings

# Constantes para mejor legibilidad
EARTH_RADIUS_KM = 6371.0
TransportMode = Literal["walk", "drive", "transit", "bike"]

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcula la distancia entre dos puntos usando la fórmula de Haversine.
    
    Args:
        lat1, lon1: Coordenadas del primer punto
        lat2, lon2: Coordenadas del segundo punto
        
    Returns:
        Distancia en kilómetros
        
    Raises:
        ValueError: Si las coordenadas están fuera del rango válido
    """
    # Validación de coordenadas
    if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90):
        raise ValueError("Latitud debe estar entre -90 y 90 grados")
    if not (-180 <= lon1 <= 180 and -180 <= lon2 <= 180):
        raise ValueError("Longitud debe estar entre -180 y 180 grados")
    
    # Caso especial: misma ubicación
    if lat1 == lat2 and lon1 == lon2:
        return 0.0
    
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    
    a = (math.sin(dphi/2)**2 + 
         math.cos(p1) * math.cos(p2) * math.sin(dlmb/2)**2)
    
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))

def estimate_travel_minutes(
    lat1: float, 
    lon1: float, 
    lat2: float, 
    lon2: float, 
    mode: TransportMode = "walk"
) -> float:
    """
    Estima el tiempo de viaje entre dos puntos.
    
    Args:
        lat1, lon1: Coordenadas origen
        lat2, lon2: Coordenadas destino  
        mode: Modo de transporte
        
    Returns:
        Tiempo estimado en minutos
    """
    # Mapeo de velocidades por modo
    speed_map = {
        "walk": settings.CITY_SPEED_KMH_WALK,
        "drive": settings.CITY_SPEED_KMH_DRIVE,
        "bike": settings.CITY_SPEED_KMH_BIKE,
        "transit": settings.CITY_SPEED_KMH_TRANSIT
    }
    
    if mode not in speed_map:
        raise ValueError(f"Modo '{mode}' no soportado. Use: {list(speed_map.keys())}")
    
    km = haversine_km(lat1, lon1, lat2, lon2)
    travel_time = (km / speed_map[mode]) * 60.0
    
    return max(settings.MIN_TRAVEL_MIN, travel_time)

def calculate_center_point(coordinates: List[Tuple[float, float]]) -> Tuple[float, float]:
    """
    Calcula el punto central geográfico de una lista de coordenadas.
    Útil para encontrar ubicación óptima de hotel.
    """
    if not coordinates:
        raise ValueError("Lista de coordenadas no puede estar vacía")
    
    # Convertir a radianes y calcular coordenadas cartesianas
    x = y = z = 0
    
    for lat, lon in coordinates:
        lat_rad, lon_rad = math.radians(lat), math.radians(lon)
        x += math.cos(lat_rad) * math.cos(lon_rad)
        y += math.cos(lat_rad) * math.sin(lon_rad)
        z += math.sin(lat_rad)
    
    # Promediar y convertir de vuelta
    total = len(coordinates)
    x, y, z = x/total, y/total, z/total
    
    central_lon = math.atan2(y, x)
    central_lat = math.atan2(z, math.sqrt(x*x + y*y))
    
    return math.degrees(central_lat), math.degrees(central_lon)

def is_within_radius(
    center_lat: float, 
    center_lon: float, 
    point_lat: float, 
    point_lon: float, 
    radius_km: float
) -> bool:
    """
    Verifica si un punto está dentro de un radio específico.
    """
    distance = haversine_km(center_lat, center_lon, point_lat, point_lon)
    return distance <= radius_km

def calculate_bounding_box(
    lat: float, 
    lon: float, 
    radius_km: float
) -> Tuple[float, float, float, float]:
    """
    Calcula una bounding box aproximada alrededor de un punto.
    
    Returns:
        (min_lat, min_lon, max_lat, max_lon)
    """
    # Aproximación rápida: 1 grado ≈ 111 km
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / (111.0 * math.cos(math.radians(lat)))
    
    return (
        lat - lat_delta,    # min_lat
        lon - lon_delta,    # min_lon  
        lat + lat_delta,    # max_lat
        lon + lon_delta     # max_lon
    )

# Funciones de conveniencia para el sistema de itinerarios
def total_route_distance(places: List[Dict[str, Any]]) -> float:
    """Calcula distancia total de una ruta secuencial."""
    if len(places) < 2:
        return 0.0
    
    total = 0.0
    for i in range(len(places) - 1):
        p1, p2 = places[i], places[i + 1]
        total += haversine_km(p1["lat"], p1["lon"], p2["lat"], p2["lon"])
    
    return total

def total_route_time(places: List[Dict[str, Any]], mode: TransportMode = "walk") -> float:
    """Calcula tiempo total de una ruta secuencial."""
    if len(places) < 2:
        return 0.0
    
    total = 0.0
    for i in range(len(places) - 1):
        p1, p2 = places[i], places[i + 1]
        total += estimate_travel_minutes(
            p1["lat"], p1["lon"], p2["lat"], p2["lon"], mode
        )
    
    return total

# Alias para compatibilidad
calculate_distance = haversine_km

def get_city_bounds(city_lat: float, city_lon: float, radius_km: float = 50.0) -> dict:
    """
    Obtiene los límites de una ciudad aproximados
    
    Args:
        city_lat: Latitud del centro de la ciudad
        city_lon: Longitud del centro de la ciudad  
        radius_km: Radio en kilómetros para definir los límites
        
    Returns:
        Dict con límites de la ciudad
    """
    min_lat, min_lon, max_lat, max_lon = calculate_bounding_box(
        city_lat, city_lon, radius_km
    )
    
    return {
        'min_lat': min_lat,
        'min_lon': min_lon,
        'max_lat': max_lat,
        'max_lon': max_lon,
        'center_lat': city_lat,
        'center_lon': city_lon,
        'radius_km': radius_km
    }
