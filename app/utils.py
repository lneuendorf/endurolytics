"""Utility functions for the Dash app."""

from typing import Optional


def meters_to_miles(meters: Optional[float]) -> float:
    """Convert meters to miles."""
    if meters is None or meters == 0:
        return 0.0
    return round(meters / 1609.34, 2)


def meters_to_yards(meters: Optional[float]) -> float:
    """Convert meters to yards."""
    if meters is None or meters == 0:
        return 0.0
    return round(meters / 0.9144, 2)


def seconds_to_time_string(seconds: Optional[int]) -> str:
    """Convert seconds to HH:MM:SS format."""
    if seconds is None or seconds == 0:
        return "0:00"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def get_distance_display(sport: Optional[str], distance_meters: Optional[float]) -> tuple[float, str]:
    """
    Get distance in appropriate units based on sport.

    Swims (any swim discipline, e.g. lap_swimming / open_water_swimming) are shown
    in yards; running and cycling in miles.

    Returns:
        Tuple of (distance_value, unit_string)
    """
    is_swim = bool(sport) and "swim" in sport.lower()

    if distance_meters is None or distance_meters == 0:
        return (0.0, "yd" if is_swim else "mi")

    if is_swim:
        return (meters_to_yards(distance_meters), "yd")
    # Running and cycling use miles
    return (meters_to_miles(distance_meters), "mi")
