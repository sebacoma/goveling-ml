"""
🔍 Diagnóstico detallado del optimizador con routing gratuito
Verificar paso a paso qué está pasando
"""

import asyncio
import logging
from datetime import datetime, timedelta
from utils.hybrid_optimizer_v31 import HybridOptimizerV31

# Configurar logging para ver detalles
logging.basicConfig(level=logging.INFO)

async def detailed_diagnosis():
    """Diagnóstico paso a paso del optimizador"""
    
    print("🔍 DIAGNÓSTICO DETALLADO")
    print("=" * 50)
    
    # Crear instancia del optimizador
    optimizer = HybridOptimizerV31()
    print("✅ Optimizador creado")
    print(f"   🔌 Routing service: {type(optimizer.routing_service).__name__}")
    
    # Lugares de ejemplo
    places = [
        {
            'name': 'Plaza de Armas',
            'lat': -33.4489,
            'lon': -70.6693,
            'place_type': 'tourist_attraction',
            'rating': 4.2
        },
        {
            'name': 'Cerro San Cristóbal',
            'lat': -33.4378, 
            'lon': -70.6504,
            'place_type': 'tourist_attraction',
            'rating': 4.5
        }
    ]
    
    print(f"\n📍 Lugares a procesar: {len(places)}")
    for i, place in enumerate(places, 1):
        print(f"   {i}. {place['name']} ({place['lat']}, {place['lon']})")
    
    # Test 1: Clustering
    print(f"\n🗺️ PASO 1: Clustering")
    try:
        clusters = optimizer.cluster_pois(places)
        print(f"   ✅ Clusters generados: {len(clusters)}")
        for i, cluster in enumerate(clusters, 1):
            print(f"      Cluster {i}: {len(cluster.places)} lugares")
            for place in cluster.places:
                print(f"         - {place['name']}")
    except Exception as e:
        print(f"   ❌ Error en clustering: {e}")
        return
    
    # Test 2: Routing directo
    print(f"\n🚗 PASO 2: Test routing directo")
    origin = (places[0]['lat'], places[0]['lon'])
    destination = (places[1]['lat'], places[1]['lon'])
    
    try:
        eta_info = await optimizer.routing_service.eta_between(
            origin, destination, 'walk'
        )
        print(f"   ✅ Routing exitoso:")
        print(f"      📏 Distancia: {eta_info['distance_km']:.2f} km")
        print(f"      ⏱️ Duración: {eta_info['duration_minutes']:.1f} min")
        print(f"      🔌 Fuente: {eta_info.get('source', 'unknown')}")
    except Exception as e:
        print(f"   ❌ Error en routing: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 3: Asignación de home base
    print(f"\n🏨 PASO 3: Asignación home base")
    try:
        clusters_with_base = await optimizer.assign_home_base_to_clusters(clusters)
        print(f"   ✅ Home bases asignadas")
        for i, cluster in enumerate(clusters_with_base, 1):
            base = cluster.home_base
            if base:
                print(f"      Cluster {i}: {base.get('name', 'Sin nombre')}")
            else:
                print(f"      Cluster {i}: Sin home base")
    except Exception as e:
        print(f"   ❌ Error en home base: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 4: Optimización completa con fechas válidas
    print(f"\n📅 PASO 4: Optimización completa")
    start_date = datetime.now() + timedelta(days=1)  # Mañana
    end_date = start_date + timedelta(days=1)  # Un día
    
    print(f"   📅 Fecha inicio: {start_date}")
    print(f"   📅 Fecha fin: {end_date}")
    print(f"   📊 Duración: {(end_date - start_date).days} días")
    
    try:
        from utils.hybrid_optimizer_v31 import optimize_itinerary_hybrid_v31
        
        result = await optimize_itinerary_hybrid_v31(
            places=places,
            start_date=start_date,
            end_date=end_date,
            daily_start_hour=9,
            daily_end_hour=18,
            transport_mode='walk'
        )
        
        print(f"   ✅ Optimización completada")
        print(f"   📊 Días generados: {len(result.get('daily_plans', []))}")
        
        # Analizar resultado detallado
        daily_plans = result.get('daily_plans', [])
        for i, day in enumerate(daily_plans, 1):
            print(f"\n      📅 Día {i}: {day.get('date', 'Sin fecha')}")
            activities = day.get('activities', [])
            print(f"         🎯 Actividades: {len(activities)}")
            
            for j, activity in enumerate(activities, 1):
                act_type = activity.get('type', 'unknown')
                if act_type == 'activity':
                    print(f"            {j}. 🎯 {activity.get('name', 'Sin nombre')}")
                elif act_type == 'transfer':
                    duration = activity.get('duration_minutes', 0)
                    distance = activity.get('distance_km', 0)
                    print(f"            {j}. 🚗 Transfer: {duration:.0f}min, {distance:.1f}km")
        
        # Verificar métricas
        metrics = result.get('execution_metrics', {})
        if metrics:
            print(f"\n   📊 Métricas:")
            for key, value in metrics.items():
                print(f"      {key}: {value}")
        
    except Exception as e:
        print(f"   ❌ Error en optimización completa: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n🎉 Diagnóstico completado")

if __name__ == "__main__":
    asyncio.run(detailed_diagnosis())