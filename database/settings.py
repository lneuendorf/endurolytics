"""Helpers for reading and persisting athlete threshold settings.

The training-load calculations (bike/run/swim TSS, CTL, ATL, TSB) all depend on
per-athlete thresholds. This module centralizes reading and upserting the single
``athlete_settings`` row so both the pipeline and dashboard use one code path.
"""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy.orm import Session

from .connection import session_scope
from .models import AthleteSettings

DEFAULT_ATHLETE_ID = "default"

# Environment variable -> AthleteSettings field, with the parser to apply.
_ENV_FIELD_MAP: dict[str, tuple[str, type]] = {
    "ATHLETE_FTP_WATTS": ("ftp_watts", int),
    "ATHLETE_RUN_THRESHOLD_PACE_SECONDS_PER_KM": ("run_threshold_pace_seconds_per_km", float),
    "ATHLETE_SWIM_CSS_PACE_SECONDS_PER_100M": ("swim_css_pace_seconds_per_100m", float),
    "ATHLETE_MAX_HR": ("max_hr", int),
    "ATHLETE_RESTING_HR": ("resting_hr", int),
    "ATHLETE_THRESHOLD_HR": ("threshold_hr", int),
}


def get_athlete_settings(
    session: Session, athlete_id: str = DEFAULT_ATHLETE_ID
) -> AthleteSettings | None:
    """Return the settings row for ``athlete_id`` or ``None`` if not seeded yet."""
    return (
        session.query(AthleteSettings)
        .filter(AthleteSettings.athlete_id == athlete_id)
        .one_or_none()
    )


def athlete_tss_kwargs(
    session: Session, athlete_id: str = DEFAULT_ATHLETE_ID
) -> dict[str, Any]:
    """Return the threshold keyword arguments consumed by ``analytics.tss``.

    Provides a single settings-loading path shared by the weekly aggregator and
    the processing pipeline so per-activity and weekly TSS always agree.
    """
    settings = get_athlete_settings(session, athlete_id)
    if settings is None:
        return {}
    return {
        "ftp_watts": settings.ftp_watts,
        "run_threshold_pace_seconds_per_km": settings.run_threshold_pace_seconds_per_km,
        "swim_css_pace_seconds_per_100m": settings.swim_css_pace_seconds_per_100m,
        "threshold_hr": settings.threshold_hr,
        "resting_hr": settings.resting_hr,
    }


def upsert_athlete_settings(
    session: Session, athlete_id: str = DEFAULT_ATHLETE_ID, **fields: Any
) -> AthleteSettings:
    """Create or update the settings row for ``athlete_id``.

    Only keys present in ``fields`` are written; ``None`` values are ignored so a
    partial update never clobbers existing thresholds.
    """
    settings = get_athlete_settings(session, athlete_id)
    if settings is None:
        settings = AthleteSettings(athlete_id=athlete_id)
        session.add(settings)

    for key, value in fields.items():
        if value is None:
            continue
        if not hasattr(settings, key):
            raise AttributeError(f"AthleteSettings has no field '{key}'")
        setattr(settings, key, value)

    session.flush()
    return settings


def _settings_from_env() -> dict[str, Any]:
    """Read known athlete settings from environment variables."""
    values: dict[str, Any] = {}
    for env_name, (field, parser) in _ENV_FIELD_MAP.items():
        raw = os.getenv(env_name)
        if raw is None or raw == "":
            continue
        values[field] = parser(raw)
    return values


def seed_from_env(
    database_url: str | None = None, athlete_id: str = DEFAULT_ATHLETE_ID
) -> AthleteSettings:
    """Upsert athlete settings from environment variables and return the row."""
    values = _settings_from_env()
    with session_scope(database_url) as session:
        settings = upsert_athlete_settings(session, athlete_id=athlete_id, **values)
        session.expunge(settings)
        return settings


def main() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    settings = seed_from_env()
    print(f"Seeded athlete settings for '{settings.athlete_id}': {settings.to_dict()}")


if __name__ == "__main__":
    main()
