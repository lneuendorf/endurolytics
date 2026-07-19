from __future__ import annotations

from typing import Any

INCLUDED_SPORT_KEYS = {
    # --- Swimming ---
    "lap_swimming",
    "open_water_swimming"

    # --- Cycling ---
    "cycling",
    "road_biking",
    "mountain_biking",
    "gravel_cycling",
    "indoor_cycling",
    "virtual_cycling"

    # --- Running ---
    "running",
    "trail_running",
    "treadmill_running"

    # --- Triathlon ---
    "triathlon",
    "duathlon",
    "multisport"
}

EXCLUDED_ACTIVITY_KEYS = {"walking", "strength", "yoga", "cardio"}


def _lookup_type_key(activity: dict[str, Any]) -> str | None:
    for key in ("activityType", "sportType"):
        payload = activity.get(key)
        if isinstance(payload, dict):
            type_key = payload.get("typeKey") or payload.get("sportTypeKey")
            if isinstance(type_key, str):
                return type_key.lower()
    return None


def is_endurance_activity(activity: dict[str, Any]) -> bool:
    sport_key = _lookup_type_key(activity)
    if not sport_key:
        return False
    if sport_key in EXCLUDED_ACTIVITY_KEYS:
        return False
    return sport_key in INCLUDED_SPORT_KEYS or sport_key.startswith("running") or sport_key.startswith("cycling") or sport_key.startswith("swimming")
