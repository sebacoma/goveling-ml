"""
🏨 Sistema de Recomendación de Hoteles - Multi-Ciudad Enhanced
Recomienda hoteles para viajes multi-ciudad con scheduling inteligente
Soporta intercity travel, multi-day stays, y accommodation orchestration
"""

import logging
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field
import math
from datetime import datetime, timedelta
from geopy.distance import geodesic

@dataclass
class HotelRecommendation:
    name: str
    lat: float
    lon: float
    type: str = "hotel"
    address: str = ""
    rating: float = 0.0
    price_range: str = "medium"  # low, medium, high
    distance_to_centroid_km: float = 0.0
    avg_distance_to_places_km: float = 0.0
    convenience_score: float = 0.0
    reasoning: str = ""
    
    # Multi-ciudad enhancements
    city: str = ""
    country: str = ""
    supports_multi_night: bool = True
    intercity_accessibility: float = 0.0  # Score for intercity travel convenience

@dataclass
class MultiCityAccommodationPlan:
    """Plan de accommodations para viaje multi-ciudad"""
    accommodations: List[Dict] = field(default_factory=list)
    total_nights: int = 0
    total_cities: int = 0
    estimated_cost: float = 0.0
    intercity_optimization: Dict = field(default_factory=dict)
    
    def add_city_accommodation(self, city: str, hotel: HotelRecommendation, 
                             nights: int, check_in_day: int):
        """Añade accommodation para una ciudad específica"""
        self.accommodations.append({
            'city': city,
            'hotel': hotel,
            'nights': nights,
            'check_in_day': check_in_day,
            'check_out_day': check_in_day + nights,
            'coordinates': (hotel.lat, hotel.lon)
        })
        
    def get_accommodation_sequence(self) -> List[str]:
        """Retorna secuencia de ciudades con accommodations"""
        return [acc['city'] for acc in sorted(self.accommodations, key=lambda x: x['check_in_day'])]

class HotelRecommender:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Base de datos de hoteles por ciudad (expandida para multi-ciudad)
        self.hotel_database = {
            "santiago": [
                {
                    "name": "Hotel Sheraton Santiago",
                    "lat": -33.4172,
                    "lon": -70.6060,
                    "address": "Av. Santa María 1742, Providencia",
                    "rating": 4.6,
                    "price_range": "high"
                },
            {
                "name": "W Santiago",
                "lat": -33.4150,
                "lon": -70.6100,
                "address": "Isidora Goyenechea 3000, Las Condes",
                "rating": 4.7,
                "price_range": "high"
            },
            {
                "name": "Hotel Plaza San Francisco",
                "lat": -33.4372,
                "lon": -70.6506,
                "address": "Alameda 816, Santiago Centro",
                "rating": 4.5,
                "price_range": "medium"
            },
            {
                "name": "Hotel Carrera",
                "lat": -33.4378,
                "lon": -70.6511,
                "address": "Teatinos 180, Santiago Centro",
                "rating": 4.2,
                "price_range": "medium"
            },
            {
                "name": "Ibis Santiago Providencia",
                "lat": -33.4372,
                "lon": -70.6172,
                "address": "Eliodoro Yáñez 1800, Providencia",
                "rating": 4.0,
                "price_range": "low"
            },
            {
                "name": "Hotel Director Vitacura",
                "lat": -33.3890,
                "lon": -70.5950,
                "address": "Av. Vitacura 3600, Vitacura",
                "rating": 4.4,
                "price_range": "high"
            },
            {
                "name": "Hotel Magnolia Santiago Centro",
                "lat": -33.4389,
                "lon": -70.6507,
                "address": "Huérfanos 539, Santiago Centro",
                "rating": 4.1,
                "price_range": "medium"
            },
            {
                "name": "Best Western Los Condes",
                "lat": -33.4089,
                "lon": -70.5950,
                "address": "Vitacura 4873, Las Condes",
                "rating": 4.0,
                "price_range": "medium"
            },
            {
                "name": "Hotel Boutique Castillo Rojo",
                "lat": -33.4262,
                "lon": -70.6344,
                "address": "Constitución 195, Bellavista",
                "rating": 4.3,
                "price_range": "medium"
            },
            {
                "name": "Hotel NH Ciudad de Santiago",
                "lat": -33.4350,
                "lon": -70.6450,
                "address": "Av. O'Higgins 136, Santiago Centro",
                "rating": 4.2,
                "price_range": "medium"
            }
        ],
        "antofagasta": [
            {
                "name": "Hotel Terrado Antofagasta",
                "lat": -23.646929,
                "lon": -70.4031467,
                "address": "Avenida Balmaceda 2575, Antofagasta",
                "rating": 4.5,
                "price_range": "high"
            },
            {
                "name": "Hotel Antofagasta",
                "lat": -23.6500,
                "lon": -70.3977,
                "address": "Av. Grecia 1490, Antofagasta",
                "rating": 4.3,
                "price_range": "medium"
            },
            {
                "name": "Ibis Antofagasta",
                "lat": -23.6435,
                "lon": -70.3955,
                "address": "Av. Grecia 1171, Antofagasta",
                "rating": 4.0,
                "price_range": "low"
            }
        ],
        "calama": [
            {
                "name": "Hotel Diego de Almagro Calama",
                "lat": -22.4583,
                "lon": -68.9204,
                "address": "Av. Granaderos 3452, Calama",
                "rating": 4.2,
                "price_range": "medium"
            },
            {
                "name": "Park Plaza Calama",
                "lat": -22.4595,
                "lon": -68.9215,
                "address": "Av. Balmaceda 2634, Calama",
                "rating": 4.1,
                "price_range": "medium"
            }
        ],
        # Ciudades europeas para multi-ciudad
        "paris": [
            {
                "name": "Hotel Le Meurice",
                "lat": 48.8656,
                "lon": 2.3279,
                "address": "228 Rue de Rivoli, Paris",
                "rating": 4.8,
                "price_range": "high"
            },
            {
                "name": "Hotel des Grands Boulevards",
                "lat": 48.8719,
                "lon": 2.3432,
                "address": "17 Boulevard Poissonnière, Paris",
                "rating": 4.5,
                "price_range": "high"
            },
            {
                "name": "Hotel Malte Opera",
                "lat": 48.8719,
                "lon": 2.3432,
                "address": "63 Rue de Richelieu, Paris",
                "rating": 4.2,
                "price_range": "medium"
            },
            {
                "name": "Hotel ibis Paris Centre",
                "lat": 48.8566,
                "lon": 2.3522,
                "address": "35 Boulevard Saint-Marcel, Paris",
                "rating": 4.0,
                "price_range": "medium"
            }
        ],
        "amsterdam": [
            {
                "name": "Waldorf Astoria Amsterdam",
                "lat": 52.3676,
                "lon": 4.9041,
                "address": "Herengracht 542-556, Amsterdam",
                "rating": 4.7,
                "price_range": "high"
            },
            {
                "name": "Hotel V Nesplein",
                "lat": 52.3654,
                "lon": 4.8944,
                "address": "Nesplein 49, Amsterdam",
                "rating": 4.4,
                "price_range": "medium"
            },
            {
                "name": "Hotel NH Amsterdam Centre",
                "lat": 52.3702,
                "lon": 4.8952,
                "address": "Stadhouderskade 7, Amsterdam",
                "rating": 4.2,
                "price_range": "medium"
            }
        ],
        "berlin": [
            {
                "name": "Hotel Adlon Kempinski Berlin",
                "lat": 52.5163,
                "lon": 13.3777,
                "address": "Unter den Linden 77, Berlin",
                "rating": 4.8,
                "price_range": "high"
            },
            {
                "name": "Meininger Hotel Berlin Mitte",
                "lat": 52.5200,
                "lon": 13.4050,
                "address": "Hallesches Ufer 30, Berlin",
                "rating": 4.1,
                "price_range": "low"
            },
            {
                "name": "Hotel Hackescher Hof",
                "lat": 52.5243,
                "lon": 13.4015,
                "address": "Große Präsidentenstraße 8, Berlin",
                "rating": 4.3,
                "price_range": "medium"
            }
        ],
        "rome": [
            {
                "name": "Hotel de Russie",
                "lat": 41.9109,
                "lon": 12.4776,
                "address": "Via del Babuino 9, Rome",
                "rating": 4.7,
                "price_range": "high"
            },
            {
                "name": "Hotel Artemide",
                "lat": 41.9028,
                "lon": 12.4964,
                "address": "Via Nazionale 22, Rome",
                "rating": 4.4,
                "price_range": "medium"
            }
        ],
        "barcelona": [
            {
                "name": "Hotel Casa Fuster",
                "lat": 41.4036,
                "lon": 2.1540,
                "address": "Passeig de Gràcia 132, Barcelona",
                "rating": 4.6,
                "price_range": "high"
            },
            {
                "name": "Hotel Barcelona Gothic",
                "lat": 41.3851,
                "lon": 2.1734,
                "address": "Carrer Jaume I, 14, Barcelona",
                "rating": 4.2,
                "price_range": "medium"
            }
        ]
    }
    
    def haversine_km(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calcular distancia usando fórmula de Haversine"""
        R = 6371  # Radio de la Tierra en km
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def calculate_geographic_centroid(self, places: List[Dict]) -> Tuple[float, float]:
        """Calcular el centroide geográfico de los lugares"""
        if not places:
            # Default a Santiago centro si no hay lugares
            return -33.4489, -70.6693
        
        # Calcular promedio ponderado por prioridad
        total_lat = 0
        total_lon = 0
        total_weight = 0
        
        for place in places:
            weight = place.get('priority', 5)  # Usar prioridad como peso
            total_lat += place['lat'] * weight
            total_lon += place['lon'] * weight
            total_weight += weight
        
        centroid_lat = total_lat / total_weight
        centroid_lon = total_lon / total_weight
        
        self.logger.info(f"🎯 Centroide calculado: ({centroid_lat:.4f}, {centroid_lon:.4f})")
        return centroid_lat, centroid_lon
    
    def calculate_convenience_score(self, hotel: Dict, places: List[Dict], centroid: Tuple[float, float]) -> float:
        """Calcular score de conveniencia para un hotel"""
        hotel_lat, hotel_lon = hotel['lat'], hotel['lon']
        centroid_lat, centroid_lon = centroid
        
        # 1. Distancia al centroide (30% del score)
        distance_to_centroid = self.haversine_km(hotel_lat, hotel_lon, centroid_lat, centroid_lon)
        centroid_score = max(0, 1 - (distance_to_centroid / 10))  # Normalizar a 10km max
        
        # 2. Distancia promedio a todos los lugares (40% del score)
        total_distance = 0
        for place in places:
            distance = self.haversine_km(hotel_lat, hotel_lon, place['lat'], place['lon'])
            weight = place.get('priority', 5) / 10  # Normalizar prioridad
            total_distance += distance * weight
        
        avg_distance = total_distance / len(places) if places else 0
        distance_score = max(0, 1 - (avg_distance / 8))  # Normalizar a 8km max
        
        # 3. Rating del hotel (20% del score)
        rating_score = hotel.get('rating', 3.0) / 5.0
        
        # 4. Bonus por estar en zona central (10% del score)
        centro_bonus = 0
        if distance_to_centroid < 2:  # Muy cerca del centroide
            centro_bonus = 0.2
        elif distance_to_centroid < 5:  # Relativamente cerca
            centro_bonus = 0.1
        
        # Calcular score final
        final_score = (
            centroid_score * 0.3 + 
            distance_score * 0.4 + 
            rating_score * 0.2 + 
            centro_bonus * 0.1
        )
        
        return min(1.0, final_score)
    
    def determine_city(self, lat: float) -> str:
        """Determinar ciudad basado en la latitud"""
        if -23.7 <= lat <= -23.5:  # Antofagasta
            return "antofagasta"
        elif -22.5 <= lat <= -22.4:  # Calama
            return "calama"
        elif -35.0 <= lat <= -32.0:  # Santiago y alrededores
            return "santiago"
        else:  # Para ubicaciones internacionales, devolver None
            return None
    
    def _generate_synthetic_hotels(self, centroid: Tuple[float, float], places: List[Dict], price_preference: str = "medium") -> List[Dict]:
        """Generar hoteles sintéticos ubicados estratégicamente cerca del centroide de POIs"""
        lat, lon = centroid
        self.logger.info(f"🏗️ Generando hoteles sintéticos para centroide ({lat:.4f}, {lon:.4f})")
        
        # Determinar ciudad aproximada basándose en coordenadas conocidas
        city_name = self._infer_international_city(lat, lon)
        self.logger.info(f"📍 Ciudad inferida: {city_name}")
        
        # 🎯 ESTRATEGIA DE UBICACIÓN: Hotel principal en el centroide exacto
        synthetic_hotels = []
        
        # Usar hoteles realistas para la ciudad
        realistic_hotels = self._get_realistic_hotels_for_city(city_name)
        
        # Si no hay suficientes hoteles realistas, agregar genéricos
        hotel_types = realistic_hotels + [
            ("Hotel Plaza", "high"),
            ("Hotel Centro", "medium"),
            ("Hotel Boutique", "high"),
            ("Hotel Ejecutivo", "medium"),
            ("Hotel Business", "medium"),
            ("Hotel Comfort", "low")
        ]
        
        for i, (hotel_type, price_range) in enumerate(hotel_types):
            # Filtrar por preferencia de precio
            if price_preference != "any" and price_range != price_preference:
                continue
            
            if i == 0:
                # 🎯 HOTEL PRINCIPAL: Ubicado exactamente en el centroide para optimización
                hotel_lat, hotel_lon = lat, lon
                hotel_name = hotel_type  # Usar nombre realista directamente
                address = f"Centro de {city_name}"
            else:
                # Hoteles alternativos con offset pequeño
                offset_lat = lat + (i * 0.002)  # Offset más pequeño (220m aprox)
                offset_lon = lon + (i * 0.002)
                hotel_lat, hotel_lon = offset_lat, offset_lon
                hotel_name = hotel_type  # Usar nombre realista directamente
                address = f"Cerca del centro de {city_name}"
                
            synthetic_hotels.append({
                "name": hotel_name,
                "lat": hotel_lat,
                "lon": hotel_lon,
                "address": address,
                "rating": round(4.2 + (i * 0.05), 1),  # Ratings entre 4.2 y 4.4
                "price_range": price_range,
                "synthetic": True,
                "centroid_optimized": i == 0  # Marcar el hotel principal como optimizado para centroide
            })
        
        # Priorizar el hotel centroide si existe
        if synthetic_hotels:
            synthetic_hotels.sort(key=lambda h: (not h.get('centroid_optimized', False), h.get('rating', 0)))
        
        self.logger.info(f"🏨 Hoteles sintéticos generados: {len(synthetic_hotels)}")
        for i, hotel in enumerate(synthetic_hotels[:3]):
            self.logger.info(f"   {i+1}. {hotel['name']} ({hotel['lat']:.4f}, {hotel['lon']:.4f})")
        
        return synthetic_hotels[:3]  # Máximo 3 hoteles sintéticos
    
    async def _search_hotels_with_google_places(self, centroid: Tuple[float, float], price_preference: str = "any") -> List[Dict]:
        """Buscar hoteles reales usando Google Places API"""
        try:
            lat, lon = centroid
            
            # Usar GooglePlacesService para buscar hoteles/alojamientos
            from services.google_places_service import GooglePlacesService
            places_service = GooglePlacesService()
            
            # Buscar lodging/accommodation cerca del centroide - intentar múltiples tipos
            places_data = None
            
            # Intentar primero con 'lodging'
            places_data = await places_service._google_nearby_search(
                lat=lat,
                lon=lon,
                radius=5000,  # 5km radius
                types=['lodging'],
                type='lodging',
                limit=10
            )
            
            # Si no encuentra con 'lodging', intentar con 'accommodation'
            if not places_data or not places_data.get('results'):
                places_data = await places_service._google_nearby_search(
                    lat=lat,
                    lon=lon,
                    radius=8000,  # Ampliar radio a 8km
                    types=['accommodation'],
                    type='accommodation',
                    limit=10
                )
            
            hotels = []
            if places_data and places_data.get('results'):
                self.logger.info(f"🏨 Google Places devolvió {len(places_data['results'])} hoteles")
                for place in places_data['results'][:5]:  # Máximo 5 hoteles
                    location = place.get('geometry', {}).get('location', {})
                    place_lat = location.get('lat', lat)
                    place_lon = location.get('lng', lon)
                    
                    # Mapear price_level de Google Places a nuestros rangos
                    google_price_level = place.get('price_level', 2)  # Default medium
                    price_range = self._map_google_price_to_range(google_price_level)
                    
                    hotel_name = place.get('name', 'Hotel')
                    self.logger.info(f"   📍 {hotel_name} - Price level: {google_price_level} -> {price_range}")
                    
                    # Filtrar por preferencia de precio si se especifica
                    if price_preference != "any" and price_range != price_preference:
                        self.logger.info(f"   ❌ {hotel_name} filtrado por precio (quiere: {price_preference}, tiene: {price_range})")
                        continue
                    
                    self.logger.info(f"   ✅ {hotel_name} incluido")
                    
                    hotel = {
                        "name": place.get('name', 'Hotel'),
                        "lat": place_lat,
                        "lon": place_lon,
                        "address": place.get('vicinity', ''),
                        "rating": place.get('rating', 4.0),
                        "price_range": price_range,
                        "google_place_id": place.get('place_id'),
                        "synthetic": False,  # Es un hotel real de Google Places
                        "source": "google_places"
                    }
                    hotels.append(hotel)
            
            if hotels:
                self.logger.info(f"✅ Google Places encontró {len(hotels)} hoteles")
                return hotels
            else:
                self.logger.warning("❌ Google Places no encontró hoteles")
                return []  # Retornar lista vacía para activar el fallback
                
        except Exception as e:
            self.logger.error(f"Error buscando hoteles con Google Places: {e}")
            return []
    
    def _map_google_price_to_range(self, price_level: int) -> str:
        """Mapear price_level de Google Places (0-4) a nuestros rangos"""
        if price_level <= 1:
            return "low"
        elif price_level <= 2:
            return "medium" 
        else:
            return "high"
    
    def _infer_international_city(self, lat: float, lon: float) -> str:
        """Inferir ciudad internacional basándose en coordenadas"""
        # Ciudades conocidas con hoteles realistas
        international_cities = [
            # Estados Unidos - Florida
            (28.5383, -81.3792, "Orlando"),
            (25.7617, -80.1918, "Miami"),
            
            # Estados Unidos - Otras ciudades principales
            (40.7128, -74.0060, "Nueva York"),
            (34.0522, -118.2437, "Los Ángeles"),
            (41.8781, -87.6298, "Chicago"),
            
            # México
            (19.4326, -99.1332, "Ciudad de México"),
            (20.6597, -103.3496, "Guadalajara"),
            
            # Brasil
            (-23.5505, -46.6333, "São Paulo"),
            (-22.9068, -43.1729, "Río de Janeiro"),
            
            # Argentina
            (-34.6118, -58.3960, "Buenos Aires"),
            
            # Perú
            (-12.0464, -77.0428, "Lima")
        ]
        
        min_distance = float('inf')
        closest_city = "Ciudad Internacional"
        
        for city_lat, city_lon, city_name in international_cities:
            distance = ((lat - city_lat) ** 2 + (lon - city_lon) ** 2) ** 0.5
            if distance < min_distance:
                min_distance = distance
                closest_city = city_name
        
        return closest_city
    
    def _get_realistic_hotels_for_city(self, city_name: str) -> List[Tuple[str, str]]:
        """Obtener nombres de hoteles realistas por ciudad"""
        realistic_hotels = {
            "Orlando": [
                ("Grand Bohemian Orlando", "high"),
                ("Embassy Suites Orlando Downtown", "medium"),
                ("Hampton Inn & Suites Orlando Downtown", "medium"),
                ("Hilton Orlando Lake Buena Vista", "high"),
                ("Holiday Inn Express Orlando Downtown", "low")
            ],
            "Miami": [
                ("The Ritz-Carlton South Beach", "high"),
                ("Fontainebleau Miami Beach", "high"),
                ("Hampton Inn & Suites Miami Downtown", "medium"),
                ("Holiday Inn Express Miami Airport", "low"),
                ("InterContinental Miami", "high")
            ],
            "Nueva York": [
                ("The Plaza Hotel", "high"),
                ("Hampton Inn Manhattan Times Square", "medium"),
                ("Holiday Inn Express Manhattan", "low"),
                ("The Westin New York", "high"),
                ("Courtyard by Marriott Manhattan", "medium")
            ],
            "Los Ángeles": [
                ("The Beverly Hills Hotel", "high"),
                ("Hollywood Roosevelt Hotel", "medium"),
                ("Hampton Inn & Suites LAX", "medium"),
                ("Holiday Inn Express Hollywood", "low"),
                ("The Standard Downtown LA", "medium")
            ]
        }
        
        return realistic_hotels.get(city_name, [
            ("Grand Hotel Central", "high"),
            ("Plaza Hotel", "medium"),
            ("Business Hotel", "medium"),
            ("Express Inn", "low"),
            ("City Center Hotel", "medium")
        ])
    
    async def recommend_hotels(self, places: List[Dict], max_recommendations: int = 5, 
                        price_preference: str = "any") -> List[HotelRecommendation]:
        """
        Recomendar hoteles basado en ubicación de lugares
        
        Args:
            places: Lista de lugares a visitar
            max_recommendations: Número máximo de recomendaciones
            price_preference: "low", "medium", "high", "any"
        """
        if not places:
            self.logger.warning("No hay lugares para recomendar hoteles")
            return []
        
        # Calcular centroide geográfico
        centroid = self.calculate_geographic_centroid(places)
        
        # Determinar ciudad basado en el centroide
        city = self.determine_city(centroid[0])
        
        # Verificar si tenemos hoteles para esta ciudad
        if city in self.hotel_database:
            # Filtrar hoteles por preferencia de precio
            available_hotels = self.hotel_database[city]
            if price_preference != "any":
                available_hotels = [h for h in available_hotels if h['price_range'] == price_preference]
        else:
            # Para ubicaciones internacionales, usar Google Places API primero
            try:
                self.logger.info("🔍 Intentando buscar hoteles con Google Places...")
                # Ahora podemos usar await correctamente
                google_hotels = await self._search_hotels_with_google_places(centroid, price_preference)
                if google_hotels:
                    self.logger.info(f"✅ Google Places encontró {len(google_hotels)} hoteles")
                    available_hotels = google_hotels
                else:
                    self.logger.info("⚠️ Google Places no encontró hoteles, generando hoteles sintéticos...")
                    # Fallback a hoteles sintéticos si Google Places falla
                    available_hotels = self._generate_synthetic_hotels(centroid, places, price_preference)
                    self.logger.info(f"🤖 Generados {len(available_hotels)} hoteles sintéticos")
            except Exception as e:
                self.logger.warning(f"Error buscando hoteles con Google Places: {e}")
                self.logger.info("🤖 Fallback: Generando hoteles sintéticos...")
                # Fallback a hoteles sintéticos
                available_hotels = self._generate_synthetic_hotels(centroid, places, price_preference)
                self.logger.info(f"🤖 Generados {len(available_hotels)} hoteles sintéticos como fallback")
        
        # Calcular scores para cada hotel
        recommendations = []
        
        for hotel in available_hotels:
            # Calcular métricas
            distance_to_centroid = self.haversine_km(
                hotel['lat'], hotel['lon'], centroid[0], centroid[1]
            )
            
            # Calcular distancia promedio a lugares
            total_distance = 0
            for place in places:
                distance = self.haversine_km(hotel['lat'], hotel['lon'], place['lat'], place['lon'])
                total_distance += distance
            avg_distance_to_places = total_distance / len(places)
            
            # Calcular convenience score
            convenience_score = self.calculate_convenience_score(hotel, places, centroid)
            
            # Generar reasoning
            reasoning_parts = []
            if distance_to_centroid < 2:
                reasoning_parts.append("Muy cerca del centro de tus actividades")
            elif distance_to_centroid < 5:
                reasoning_parts.append("Ubicación conveniente para tus planes")
            
            if hotel['rating'] >= 4.5:
                reasoning_parts.append("Hotel de alta calidad")
            elif hotel['rating'] >= 4.0:
                reasoning_parts.append("Buena calidad y servicio")
            
            if avg_distance_to_places < 3:
                reasoning_parts.append("Fácil acceso a tus destinos")
            
            reasoning = " • ".join(reasoning_parts) if reasoning_parts else "Opción disponible en la zona"
            
            # Crear recomendación
            recommendation = HotelRecommendation(
                name=hotel['name'],
                lat=hotel['lat'],
                lon=hotel['lon'],
                type="hotel",
                address=hotel['address'],
                rating=hotel['rating'],
                price_range=hotel['price_range'],
                distance_to_centroid_km=round(distance_to_centroid, 2),
                avg_distance_to_places_km=round(avg_distance_to_places, 2),
                convenience_score=round(convenience_score, 3),
                reasoning=reasoning
            )
            
            recommendations.append(recommendation)
        
        # Ordenar por convenience score (descendente)
        recommendations.sort(key=lambda x: x.convenience_score, reverse=True)
        
        # Limitar número de recomendaciones
        recommendations = recommendations[:max_recommendations]
        
        self.logger.info(f"🏨 Generadas {len(recommendations)} recomendaciones de hoteles")
        
        return recommendations
    
    def format_recommendations_for_api(self, recommendations: List[HotelRecommendation]) -> List[Dict]:
        """Formatear recomendaciones para respuesta API"""
        return [
            {
                "name": rec.name,
                "lat": rec.lat,
                "lon": rec.lon,
                "type": rec.type,
                "address": rec.address,
                "rating": rec.rating,
                "price_range": rec.price_range,
                "distance_to_centroid_km": rec.distance_to_centroid_km,
                "avg_distance_to_places_km": rec.avg_distance_to_places_km,
                "convenience_score": rec.convenience_score,
                "reasoning": rec.reasoning,
                "recommendation_rank": i + 1,
                "selection_criteria": {
                    "based_on": "geographic_proximity_to_planned_activities",
                    "factors": [
                        "distance_to_activity_centroid",
                        "average_distance_to_all_places", 
                        "hotel_rating",
                        "central_location_bonus"
                    ],
                    "algorithm": "weighted_convenience_score"
                }
            }
            for i, rec in enumerate(recommendations)
        ]
    
    # ===== MULTI-CIUDAD ENHANCEMENTS =====
    
    def plan_multi_city_accommodations(self, cities: List[Dict], 
                                     days_per_city: Dict[str, int]) -> MultiCityAccommodationPlan:
        """
        Planifica accommodations para viaje multi-ciudad
        
        Args:
            cities: Lista de ciudades con info [{'name': str, 'pois': List[Dict], 'coordinates': Tuple}]
            days_per_city: Días por ciudad {'city_name': days}
            
        Returns:
            Plan completo de accommodations multi-ciudad
        """
        self.logger.info(f"🏨 Planificando accommodations para {len(cities)} ciudades")
        
        plan = MultiCityAccommodationPlan()
        current_day = 1
        
        for city_info in cities:
            city_name = city_info['name']
            city_pois = city_info.get('pois', [])
            city_days = days_per_city.get(city_name, 1)
            
            if city_days <= 1:
                # Solo 1 día, no necesita accommodation overnight
                continue
            
            # Encontrar mejor hotel para esta ciudad
            # Por ahora, usar búsqueda directa por ciudad para mejor precisión
            hotels = self.find_hotels_by_city_name(city_name, max_recommendations=3)
            
            if hotels:
                best_hotel = hotels[0]  # El mejor-rankeado
                
                # Mejorar información del hotel para multi-ciudad
                best_hotel.city = city_name
                best_hotel.intercity_accessibility = self._calculate_intercity_accessibility(
                    best_hotel, city_info['coordinates']
                )
                
                # Añadir al plan
                plan.add_city_accommodation(
                    city=city_name,
                    hotel=best_hotel,
                    nights=city_days - 1,  # -1 porque el último día se viaja
                    check_in_day=current_day
                )
                
                self.logger.info(f"🏨 {city_name}: {best_hotel.name} por {city_days-1} noches (días {current_day}-{current_day + city_days - 2})")
            
            current_day += city_days
        
        # Calcular estadísticas del plan
        plan.total_nights = sum(acc['nights'] for acc in plan.accommodations)
        plan.total_cities = len(plan.accommodations)
        plan.estimated_cost = self._estimate_accommodation_costs(plan)
        plan.intercity_optimization = self._analyze_intercity_logistics(plan)
        
        self.logger.info(f"✅ Plan multi-ciudad: {plan.total_nights} noches en {plan.total_cities} ciudades")
        
        return plan
    
    def find_hotels_by_city_name(self, city_name: str, max_recommendations: int = 5) -> List[HotelRecommendation]:
        """
        Encuentra hoteles por nombre de ciudad (para ciudades sin POIs específicos)
        
        Args:
            city_name: Nombre de la ciudad
            max_recommendations: Número máximo de recomendaciones
            
        Returns:
            Lista de hoteles recomendados
        """
        city_key = city_name.lower().replace(' ', '_')
        
        # Buscar en database local
        if city_key in self.hotel_database:
            hotels = self.hotel_database[city_key][:max_recommendations]
            
            recommendations = []
            for hotel in hotels:
                rec = HotelRecommendation(
                    name=hotel['name'],
                    lat=hotel['lat'],
                    lon=hotel['lon'],
                    address=hotel.get('address', ''),
                    rating=hotel.get('rating', 0.0),
                    price_range=hotel.get('price_range', 'medium'),
                    city=city_name,
                    convenience_score=hotel.get('rating', 0.0) / 5.0,  # Normalizar rating como score
                    reasoning=f"Hotel encontrado por búsqueda de ciudad: {city_name}"
                )
                recommendations.append(rec)
            
            return recommendations
        
        # Si no se encuentra, generar hotel sintético centrado en la ciudad
        return self._generate_synthetic_hotel_for_city(city_name)
    
    def optimize_accommodation_sequence(self, plan: MultiCityAccommodationPlan, 
                                      city_travel_sequence: List[str]) -> MultiCityAccommodationPlan:
        """
        Optimiza la secuencia de accommodations según el orden de viaje de ciudades
        
        Args:
            plan: Plan de accommodations original
            city_travel_sequence: Secuencia optimizada de ciudades
            
        Returns:
            Plan optimizado según secuencia de viaje
        """
        # Reordenar accommodations según secuencia de ciudades
        accommodation_map = {acc['city']: acc for acc in plan.accommodations}
        
        optimized_accommodations = []
        current_day = 1
        
        for city in city_travel_sequence:
            if city in accommodation_map:
                acc = accommodation_map[city].copy()
                acc['check_in_day'] = current_day
                acc['check_out_day'] = current_day + acc['nights']
                optimized_accommodations.append(acc)
                current_day += acc['nights'] + 1  # +1 para día de viaje
        
        # Crear plan optimizado
        optimized_plan = MultiCityAccommodationPlan(
            accommodations=optimized_accommodations,
            total_nights=plan.total_nights,
            total_cities=plan.total_cities,
            estimated_cost=plan.estimated_cost
        )
        
        return optimized_plan
    
    def _calculate_intercity_accessibility(self, hotel: HotelRecommendation, 
                                         city_coordinates: Tuple[float, float]) -> float:
        """Calcula score de accesibilidad intercity del hotel"""
        # Distancia del hotel al centro de la ciudad
        hotel_coord = (hotel.lat, hotel.lon)
        distance_to_center = geodesic(hotel_coord, city_coordinates).kilometers
        
        # Score basado en proximidad al centro (mejor para intercity travel)
        accessibility_score = max(0.0, 1.0 - (distance_to_center / 20.0))  # 20km = score 0
        
        return accessibility_score
    
    def _estimate_accommodation_costs(self, plan: MultiCityAccommodationPlan) -> float:
        """Estima costos totales de accommodations"""
        price_ranges = {
            'low': 50.0,      # USD por noche
            'medium': 120.0,
            'high': 250.0
        }
        
        total_cost = 0.0
        for acc in plan.accommodations:
            hotel = acc['hotel']
            nights = acc['nights']
            price_per_night = price_ranges.get(hotel.price_range, 120.0)
            total_cost += price_per_night * nights
        
        return total_cost
    
    def _analyze_intercity_logistics(self, plan: MultiCityAccommodationPlan) -> Dict:
        """Analiza logística intercity del plan de accommodations"""
        if len(plan.accommodations) <= 1:
            return {'complexity': 'simple', 'logistics_score': 1.0}
        
        # Calcular distancias entre hoteles consecutivos
        distances = []
        for i in range(len(plan.accommodations) - 1):
            hotel1 = plan.accommodations[i]['hotel']
            hotel2 = plan.accommodations[i + 1]['hotel']
            
            coord1 = (hotel1.lat, hotel1.lon)
            coord2 = (hotel2.lat, hotel2.lon)
            distance = geodesic(coord1, coord2).kilometers
            distances.append(distance)
        
        avg_intercity_distance = sum(distances) / len(distances) if distances else 0
        max_intercity_distance = max(distances) if distances else 0
        
        # Score logístico (distancias más cortas = mejor)
        logistics_score = max(0.1, 1.0 - (avg_intercity_distance / 1000.0))  # 1000km = score 0.1
        
        complexity = 'simple'
        if max_intercity_distance > 800:
            complexity = 'international'
        elif avg_intercity_distance > 300:
            complexity = 'intercity'
        
        return {
            'complexity': complexity,
            'logistics_score': logistics_score,
            'avg_intercity_distance_km': avg_intercity_distance,
            'max_intercity_distance_km': max_intercity_distance,
            'total_accommodation_changes': len(plan.accommodations)
        }
    
    def _generate_synthetic_hotel_for_city(self, city_name: str) -> List[HotelRecommendation]:
        """Genera hotel sintético para ciudades sin data específica"""
        # Coordenadas sintéticas básicas (esto se podría mejorar con geocoding)
        synthetic_coords = self._get_synthetic_city_coordinates(city_name)
        
        synthetic_hotel = HotelRecommendation(
            name=f"Hotel Central {city_name}",
            lat=synthetic_coords[0],
            lon=synthetic_coords[1],
            address=f"Centro de {city_name}",
            rating=4.0,  # Rating por defecto
            price_range="medium",
            city=city_name,
            convenience_score=0.7,  # Score moderado por ser sintético
            reasoning=f"Hotel sintético generado para {city_name} (sin data específica disponible)"
        )
        
        return [synthetic_hotel]
    
    def _get_synthetic_city_coordinates(self, city_name: str) -> Tuple[float, float]:
        """Retorna coordenadas sintéticas para ciudades conocidas"""
        city_coords = {
            'paris': (48.8566, 2.3522),
            'london': (51.5074, -0.1278),
            'berlin': (52.5200, 13.4050),
            'madrid': (40.4168, -3.7038),
            'rome': (41.9028, 12.4964),
            'amsterdam': (52.3676, 4.9041),
            'barcelona': (41.3851, 2.1734),
            'santiago': (-33.4489, -70.6693),
            'valparaiso': (-33.0472, -71.6127)
        }
        
        return city_coords.get(city_name.lower(), (0.0, 0.0))  # Default to equator
