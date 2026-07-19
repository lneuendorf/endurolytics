from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database.models import Activity, ActivityRaw
from pipeline.filter_activities import is_endurance_activity


def _first_number(raw: dict[str, Any], *keys: str) -> float | None:
    """Return the first present, non-null key as a float (Garmin key names vary)."""
    for key in keys:
        value = raw.get(key)
        if value is not None:
            return float(value)
    return None


class GarminSyncService:
    def __init__(self, engine: Any):
        self.engine = engine
        self.session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _build_activity(self, raw_activity: dict[str, Any]) -> Activity:
        activity_id = str(raw_activity.get("activityId") or raw_activity.get("activity_id") or "")
        if not activity_id:
            raise ValueError("Garmin activity is missing an activityId")

        activity_type = raw_activity.get("activityType") or raw_activity.get("sportType") or {}
        sport_key = (activity_type.get("typeKey") or activity_type.get("sportTypeKey") or "").lower()

        start_time = raw_activity.get("startTimeGMT")
        parsed_date = None
        if isinstance(start_time, str):
            try:
                parsed_date = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            except ValueError:
                parsed_date = None

        return Activity(
            activity_id=activity_id,
            date=parsed_date,
            activity_name=raw_activity.get("activityName"),
            sport=sport_key,
            subsport=activity_type.get("typeKey") or activity_type.get("sportTypeKey"),
            duration_seconds=int(raw_activity.get("duration") or 0) if raw_activity.get("duration") is not None else None,
            distance=float(raw_activity.get("distance") or 0) if raw_activity.get("distance") is not None else None,
            avg_hr=float(raw_activity.get("averageHR") or 0) if raw_activity.get("averageHR") is not None else None,
            max_hr=float(raw_activity.get("maxHR") or 0) if raw_activity.get("maxHR") is not None else None,
            avg_power=_first_number(raw_activity, "avgPower", "averagePower"),
            normalized_power=_first_number(raw_activity, "normPower", "normalizedPower"),
            pace=float(raw_activity.get("averagePace") or 0) if raw_activity.get("averagePace") is not None else None,
            elevation_gain=float(raw_activity.get("elevationGain") or 0) if raw_activity.get("elevationGain") is not None else None,
            source_data=json.dumps(raw_activity),
        )

    def sync(self, client: Any, limit: int = 20) -> int:
        raw_payload = client.get_activities(start=0, limit=limit, activitytype=None)
        activities = raw_payload if isinstance(raw_payload, list) else raw_payload.get("activities", [])

        imported = 0
        with self.session_scope() as session:
            for raw_activity in activities:
                if not is_endurance_activity(raw_activity):
                    continue

                activity_id = str(raw_activity.get("activityId") or raw_activity.get("activity_id") or "")
                if not activity_id:
                    continue

                existing = session.query(Activity).filter(Activity.activity_id == activity_id).first()
                if existing:
                    continue

                activity = self._build_activity(raw_activity)
                session.add(activity)
                session.add(
                    ActivityRaw(
                        activity_id=activity_id,
                        garmin_json=raw_activity,
                        import_timestamp=datetime.utcnow(),
                    )
                )
                imported += 1

        return imported
