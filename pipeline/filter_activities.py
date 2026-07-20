from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

INCLUDED_SPORT_KEYS = {
    # --- Swimming ---
    "lap_swimming",
    "open_water_swimming",
    "swimming",
    # --- Cycling ---
    "cycling",
    "road_biking",
    "mountain_biking",
    "gravel_cycling",
    "indoor_cycling",
    "virtual_cycling",
    # --- Running ---
    "running",
    "trail_running",
    "treadmill_running",
    "virtual_run",
}

EXCLUDED_ACTIVITY_KEYS = {
    "walking",
    "strength",
    "strength_training",
    "yoga",
    "cardio",
    "disc_golf",
    "other",
    # Multisport transitions (T1/T2) carry no meaningful training load.
    "transition",
    "transition_v2",
}

# Parent activity types that bundle several legs (swim/bike/run + transitions).
# These are decomposed into their child legs rather than imported directly.
MULTISPORT_PARENT_KEYS = {"multi_sport", "multisport", "triathlon", "duathlon"}


def _lookup_type_key(activity: dict[str, Any]) -> str | None:
    for key in ("activityType", "sportType"):
        payload = activity.get(key)
        if isinstance(payload, dict):
            type_key = payload.get("typeKey") or payload.get("sportTypeKey")
            if isinstance(type_key, str):
                return type_key.lower()
    return None


def is_multisport_parent(activity: dict[str, Any]) -> bool:
    """True if the activity is a multisport container with child legs."""
    if activity.get("isMultiSportParent"):
        return True
    if _lookup_type_key(activity) in MULTISPORT_PARENT_KEYS:
        return True
    metadata = activity.get("metadataDTO")
    if isinstance(metadata, dict) and metadata.get("childIds"):
        return True
    return False


def is_endurance_activity(activity: dict[str, Any]) -> bool:
    sport_key = _lookup_type_key(activity)
    if not sport_key:
        return False
    if sport_key in MULTISPORT_PARENT_KEYS:
        return False
    if sport_key in EXCLUDED_ACTIVITY_KEYS:
        return False
    return (
        sport_key in INCLUDED_SPORT_KEYS
        or sport_key.startswith("running")
        or sport_key.startswith("cycling")
        or sport_key.startswith("swimming")
    )


# --- Duplicate detection -------------------------------------------------

# A recording is treated as a duplicate of another when it is the same
# discipline, starts within this many seconds, and the distances agree to
# within this fraction. Requiring all three makes false matches between
# genuinely distinct workouts extremely unlikely.
DUPLICATE_START_WINDOW_SECONDS = 300  # 5 minutes
DUPLICATE_DISTANCE_TOLERANCE = 0.02  # 2 percent


def signal_score(
    normalized_power: float | None,
    avg_power: float | None,
    avg_hr: float | None,
) -> int:
    """Rank how much training-load signal a recording carries (higher = better).

    Power beats heart rate, which beats a duration-only estimate. Used to pick
    the copy to keep when the same effort was recorded on two devices.
    """
    if normalized_power or avg_power:
        return 3
    if avg_hr:
        return 2
    return 1


def _within_tolerance(a: float | None, b: float | None, tolerance: float) -> bool:
    if not a or not b:
        return False
    return abs(a - b) <= tolerance * max(a, b)


def _times_close(a: datetime | None, b: datetime | None, window_seconds: int) -> bool:
    if a is None or b is None:
        return False
    return abs((a - b).total_seconds()) <= window_seconds


def _is_duplicate(
    left: dict[str, Any],
    right: dict[str, Any],
    start_window_seconds: int,
    distance_tolerance: float,
) -> bool:
    if not left.get("discipline") or left["discipline"] != right.get("discipline"):
        return False
    if not _within_tolerance(left.get("distance"), right.get("distance"), distance_tolerance):
        return False
    return _times_close(left.get("start"), right.get("start"), start_window_seconds)


def find_duplicate_groups(
    records: Iterable[dict[str, Any]],
    start_window_seconds: int = DUPLICATE_START_WINDOW_SECONDS,
    distance_tolerance: float = DUPLICATE_DISTANCE_TOLERANCE,
) -> list[list[dict[str, Any]]]:
    """Cluster records that represent the same effort recorded more than once.

    Each input record must provide ``discipline``, ``start`` (``datetime`` or
    ``None``), and ``distance``. Returns only groups with more than one member.
    """
    groups: list[list[dict[str, Any]]] = []
    for record in records:
        if record.get("start") is None or not record.get("distance"):
            continue
        for group in groups:
            if _is_duplicate(record, group[0], start_window_seconds, distance_tolerance):
                group.append(record)
                break
        else:
            groups.append([record])
    return [group for group in groups if len(group) > 1]


def pick_duplicate_winner(group: list[dict[str, Any]]) -> dict[str, Any]:
    """Choose the copy to keep from a duplicate group.

    Prefers the richest training-load signal, then the longer/farther recording,
    with the activity id as a deterministic final tiebreak.
    """
    return max(
        group,
        key=lambda r: (
            r.get("signal", 1),
            r.get("duration") or 0,
            r.get("distance") or 0,
            str(r.get("activity_id") or ""),
        ),
    )
