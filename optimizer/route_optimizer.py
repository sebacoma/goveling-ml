from typing import List, Dict, Any
from datetime import datetime, timedelta
from utils.geo_utils import haversine_km, estimate_travel_minutes
from settings import settings

def _fmt_time(hour_float: float) -> str:
    h = int(hour_float); m = int(round((hour_float - h) * 60))
    return f"{h:02d}:{m:02d}"

def _add_hours(time_str: str, duration_h: float) -> str:
    base = datetime.strptime(time_str, "%H:%M")
    return (base + timedelta(hours=duration_h)).strftime("%H:%M")

def order_day_by_nn(start_point: Dict[str, float], activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    remain = activities[:]
    ordered = []
    cur_lat, cur_lon = start_point["lat"], start_point["lon"]
    while remain:
        nxt = min(remain, key=lambda a: haversine_km(cur_lat, cur_lon, a["lat"], a["lon"]))
        ordered.append(nxt)
        cur_lat, cur_lon = nxt["lat"], nxt["lon"]
        remain.remove(nxt)
    return ordered

def reflow_times(
    activities: List[Dict[str, Any]],
    start_point: Dict[str, float],
    day_start_hour: int = settings.BUSINESS_START_H,
    day_end_hour: int = settings.BUSINESS_END_H,
    mode: str = "walk"
) -> List[Dict[str, Any]]:
    cur = float(day_start_hour)
    out = []
    prev_lat, prev_lon = start_point["lat"], start_point["lon"]

    for a in activities:
        # traslado desde el punto previo
        tmin = estimate_travel_minutes(prev_lat, prev_lon, a["lat"], a["lon"], mode=mode)
        cur += tmin / 60.0

        dur = float(a["duration_h"])
        if cur + dur > day_end_hour:
            break

        start = _fmt_time(cur)
        end   = _add_hours(start, dur)
        out.append({**a, "start": start, "end": end})

        cur += dur
        prev_lat, prev_lon = a["lat"], a["lon"]

    return out
