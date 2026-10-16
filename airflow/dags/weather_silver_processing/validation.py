from __future__ import annotations
import math
from datetime import datetime, timezone

RANGES = {
    "temperature": (-90, 70),
    "humidity": (0, 100),
    "windSpeed": (0, 150),
    "cloudCover": (0, 100),
    "precipitationProbability": (0, 100),
}


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _parse_ts(value) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("time is missing or not a string")
    dt = datetime.fromisoformat(value) 
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def validate_payload(payload):
    if not isinstance(payload, dict):
        return None, "payload is not an object"
    data, location = payload.get("data"), payload.get("location")
    #data section exists and is a dict
    if not isinstance(data, dict):
        return None, "data section missing or not a dict"
    #location section exists and is a dict
    if not isinstance(location, dict):
        return None, "location section missing or not a dict"
    #data.values exists and is a dict
    values = data.get("values")
    if not isinstance(values, dict):
        return None, "data.values missing or not a dict"

    try:
        event_time = _parse_ts(data.get("time"))
    except ValueError as exc:
        return None, f"invalid time: {exc}"

    name = location.get("name")
    if not isinstance(name, str) or not name.strip():
        return None, "location.name missing"

    weather = {}
    #Numeric fields must be numeric (if present) & Value ranges (if field is present)
    for field, (lo, hi) in RANGES.items():
        if field not in values or values[field] is None:
            weather[field] = None
            continue
        v = values[field]
        if not _is_number(v):
            return None, f"{field} is not numeric: {v!r}"
        if not lo <= v <= hi:
            return None, f"{field}={v} out of range [{lo}, {hi}]"
        weather[field] = float(v)

    lat, lon = location.get("lat"), location.get("lon")
    return {
        "event_time": event_time,
        "location_name": name.strip(),
        "location_lat": float(lat) if _is_number(lat) else None,
        "location_lon": float(lon) if _is_number(lon) else None,
        "location_type": location.get("type") if isinstance(location.get("type"), str) else None,
        "weather": weather,
    }, None
