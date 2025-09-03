from typing import List, Dict, Any

def pick_lodging_base(places: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not places:
        return {"name": "Base", "lat": 0.0, "lon": 0.0}
    lat = sum(p["lat"] for p in places) / len(places)
    lon = sum(p["lon"] for p in places) / len(places)
    return {"name": "Lodging Base (auto)", "lat": lat, "lon": lon}
