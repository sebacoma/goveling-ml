from typing import List, Dict, Any, Optional
from itinerary.scheduler import schedule_places
from optimizer.advanced_optimizer import AdvancedRouteOptimizer
from itinerary.lodging_recommender import pick_lodging_base

def generate_itinerary(
    places: List[Dict[str, Any]],
    start_date: str,
    end_date: str,
    daily_start_hour: int = 9,
    daily_end_hour: int = 18,
    hotel: Optional[Dict[str, Any]] = None,
    mode: str = "walk"   # "walk" o "drive"
) -> Dict[str, Any]:
    lodging = hotel if hotel else pick_lodging_base(places)
    
    # Usar el nuevo servicio de itinerarios
    from services.itinerary_service import ItineraryService
    service = ItineraryService()
    
    # Convertir a formato de request simplificado
    from models.schemas import Place, Hotel, ItineraryRequest, PlaceType, TransportMode
    from datetime import date
    
    # Mapear lugares
    mapped_places = []
    for p in places:
        try:
            place_type = PlaceType(p.get('type', 'museum'))
        except ValueError:
            place_type = PlaceType.MUSEUM
            
        mapped_places.append(Place(
            name=p['name'],
            lat=p['lat'],
            lon=p['lon'],
            type=place_type
        ))
    
    # Mapear hotel
    mapped_hotel = None
    if lodging:
        mapped_hotel = Hotel(
            name=lodging['name'],
            lat=lodging['lat'],
            lon=lodging['lon']
        )
    
    # Mapear modo de transporte
    transport_mode = TransportMode.WALK
    if mode == "drive":
        transport_mode = TransportMode.DRIVE
    elif mode == "bike":
        transport_mode = TransportMode.BIKE
    elif mode == "transit":
        transport_mode = TransportMode.TRANSIT
    
    # Crear request
    request = ItineraryRequest(
        places=mapped_places,
        start_date=date.fromisoformat(start_date),
        end_date=date.fromisoformat(end_date),
        daily_start_hour=daily_start_hour,
        daily_end_hour=daily_end_hour,
        hotel=mapped_hotel,
        transport_mode=transport_mode
    )
    
    # Generar itinerario usando el servicio avanzado
    import asyncio
    result = asyncio.run(service.generate_optimized_itinerary(request))
    
    # Convertir respuesta a formato legacy
    legacy_response = {
        "lodging": result.days[0].lodging.dict() if result.days else lodging,
        "days": [
            {
                "date": day.date,
                "activities": [
                    {
                        "place": act.place,
                        "name": act.place,
                        "start": act.start,
                        "end": act.end,
                        "duration_h": act.duration_h,
                        "lat": act.lat,
                        "lon": act.lon
                    } for act in day.activities
                ],
                "free_minutes": day.free_minutes,
                "lodging": day.lodging.dict()
            } for day in result.days
        ],
        "unassigned": [
            {
                "name": place.name,
                "lat": place.lat,
                "lon": place.lon,
                "type": place.type.value
            } for place in result.unassigned
        ]
    }
    
    return legacy_response
