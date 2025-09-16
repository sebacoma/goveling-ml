#!/usr/bin/env python3

import numpy as np
from sklearn.cluster import DBSCAN
import settings

def debug_clustering():
    """Debug del clustering para entender por qué faltan lugares"""
    
    # Datos exactos que envió el usuario
    places = [
        {'name': 'BLACK ANTOFAGASTA', 'lat': -23.6627773, 'lon': -70.4004961, 'type': 'restaurant', 'priority': 5},
        {'name': 'La Franchuteria', 'lat': -22.9100412, 'lon': -68.1969335, 'type': 'restaurant', 'priority': 5},
        {'name': 'McDonalds', 'lat': -23.6449718, 'lon': -70.40338899999999, 'type': 'restaurant', 'priority': 5},
        {'name': 'Tanta - MallPlaza Antofagasta', 'lat': -23.6446295, 'lon': -70.4023929, 'type': 'restaurant', 'priority': 5},
        {'name': 'Hotel Terrado Antofagasta', 'lat': -23.646929, 'lon': -70.4031467, 'type': 'accommodation', 'priority': 5}
    ]
    
    print("=== PLACES ORIGINALES ===")
    for i, p in enumerate(places):
        print(f"{i}: {p['name']} ({p['lat']}, {p['lon']}) - {p['type']}")
    
    # Filtro que hace el sistema
    pois = [p for p in places if p.get('type', '').lower() != 'accommodation']
    
    print(f"\n=== DESPUÉS DEL FILTRO (sin accommodations) ===")
    print(f"POIs para clustering: {len(pois)}")
    for i, p in enumerate(pois):
        print(f"{i}: {p['name']} ({p['lat']}, {p['lon']}) - {p['type']}")
    
    if not pois:
        print("ERROR: No hay POIs para clustering")
        return
    
    # Clustering
    coordinates = np.array([[p['lat'], p['lon']] for p in pois])
    print(f"\n=== COORDENADAS PARA CLUSTERING ===")
    for i, coord in enumerate(coordinates):
        print(f"{i}: {coord}")
    
    # Calcular distancias entre puntos
    print(f"\n=== DISTANCIAS ENTRE PUNTOS ===")
    from math import radians, cos, sin, asin, sqrt
    
    def haversine(lon1, lat1, lon2, lat2):
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371
        return c * r
    
    for i in range(len(coordinates)):
        for j in range(i+1, len(coordinates)):
            dist = haversine(coordinates[i][1], coordinates[i][0], coordinates[j][1], coordinates[j][0])
            print(f"{pois[i]['name']} <-> {pois[j]['name']}: {dist:.1f}km")
    
    # Simular clustering
    eps_km = 50  # Default desde settings
    eps_rad = eps_km / 6371.0
    min_samples = getattr(settings, 'CLUSTER_MIN_SAMPLES', 1)
    
    print(f"\n=== PARÁMETROS CLUSTERING ===")
    print(f"eps_km: {eps_km}")
    print(f"eps_rad: {eps_rad}")  
    print(f"min_samples: {min_samples}")
    
    clustering = DBSCAN(
        eps=eps_rad,
        min_samples=min_samples,
        metric='haversine'
    ).fit(np.radians(coordinates))
    
    print(f"\n=== RESULTADOS CLUSTERING ===")
    print(f"Labels: {clustering.labels_}")
    
    clusters = {}
    for i, label in enumerate(clustering.labels_):
        if label == -1:
            label = f"noise_{i}"
        
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(pois[i])
    
    print(f"\n=== CLUSTERS FINALES ===")
    for label, cluster_places in clusters.items():
        print(f"Cluster {label}: {len(cluster_places)} lugares")
        for place in cluster_places:
            print(f"  - {place['name']}")

if __name__ == "__main__":
    debug_clustering()
