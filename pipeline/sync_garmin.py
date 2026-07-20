from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from sqlalchemy.orm import Session, sessionmaker

from analytics.tss import classify_discipline
from database.models import Activity, ActivityMetrics, ActivityRaw
from pipeline.filter_activities import (
    find_duplicate_groups,
    is_endurance_activity,
    is_multisport_parent,
    pick_duplicate_winner,
    signal_score,
)


def _first_number(raw: dict[str, Any], *keys: str) -> float | None:
    """Return the first present, non-null key as a float (Garmin key names vary)."""
    for key in keys:
        value = raw.get(key)
        if value is not None:
            return float(value)
    return None


def _parse_start(value: Any) -> datetime | None:
    """Parse a Garmin ``startTimeGMT`` string into a naive datetime."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
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

        parsed_date = _parse_start(raw_activity.get("startTimeGMT"))

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

    def _leg_summary(self, child: Any) -> dict[str, Any] | None:
        """Flatten a multisport child leg (``get_activity`` detail) into the same
        shape as a normal activity-list summary so it can reuse the import path."""
        if not isinstance(child, dict):
            return None
        summary = child.get("summaryDTO") or {}
        type_dto = child.get("activityTypeDTO") or {}
        activity_id = child.get("activityId")
        if activity_id is None:
            return None
        return {
            "activityId": activity_id,
            "activityType": {"typeKey": type_dto.get("typeKey")},
            "activityName": child.get("activityName") or type_dto.get("typeKey"),
            "startTimeGMT": summary.get("startTimeGMT"),
            "duration": summary.get("duration"),
            "distance": summary.get("distance"),
            "averageHR": summary.get("averageHR"),
            "maxHR": summary.get("maxHR"),
            "averagePower": summary.get("averagePower"),
            "normalizedPower": summary.get("normalizedPower"),
            "elevationGain": summary.get("elevationGain"),
        }

    def _expand_multisport(self, client: Any, parent: dict[str, Any]) -> list[dict[str, Any]]:
        """Return the endurance leg summaries (swim/bike/run) of a multisport
        activity, skipping transitions. Falls back to no legs if Garmin does not
        expose child ids for the parent."""
        parent_id = str(parent.get("activityId") or "")
        if not parent_id:
            return []
        detail = client.get_activity(parent_id)
        metadata = detail.get("metadataDTO", {}) if isinstance(detail, dict) else {}
        child_ids = metadata.get("childIds") or []

        legs: list[dict[str, Any]] = []
        for child_id in child_ids:
            leg = self._leg_summary(client.get_activity(child_id))
            if leg and is_endurance_activity(leg):
                legs.append(leg)
        return legs

    def _candidate_record(self, summary: dict[str, Any]) -> dict[str, Any]:
        """Build the lightweight record used for duplicate detection."""
        activity_type = summary.get("activityType") or summary.get("sportType") or {}
        sport = (activity_type.get("typeKey") or activity_type.get("sportTypeKey") or "").lower()
        return {
            "activity_id": str(summary.get("activityId") or summary.get("activity_id") or ""),
            "discipline": classify_discipline(sport),
            "start": _parse_start(summary.get("startTimeGMT")),
            "distance": _first_number(summary, "distance"),
            "duration": _first_number(summary, "duration"),
            "signal": signal_score(
                _first_number(summary, "normPower", "normalizedPower"),
                _first_number(summary, "avgPower", "averagePower"),
                _first_number(summary, "averageHR"),
            ),
            "source": "new",
            "summary": summary,
        }

    def _existing_records(self, session: Session) -> list[dict[str, Any]]:
        """Records for already-stored activities, for cross-sync deduplication."""
        records = []
        for activity in session.query(Activity).all():
            records.append(
                {
                    "activity_id": activity.activity_id,
                    "discipline": classify_discipline(activity.sport),
                    "start": activity.date,
                    "distance": activity.distance,
                    "duration": activity.duration_seconds,
                    "signal": signal_score(
                        activity.normalized_power, activity.avg_power, activity.avg_hr
                    ),
                    "source": "db",
                }
            )
        return records

    def _delete_activity(self, session: Session, activity_id: str) -> None:
        session.query(ActivityMetrics).filter(
            ActivityMetrics.activity_id == activity_id
        ).delete(synchronize_session=False)
        session.query(Activity).filter(
            Activity.activity_id == activity_id
        ).delete(synchronize_session=False)

    def _store_candidates(
        self, session: Session, candidates: list[dict[str, Any]]
    ) -> int:
        """Persist new activities, dropping duplicate recordings of the same effort.

        Duplicates are resolved across both the incoming batch and activities
        already in the database, keeping the copy with the strongest signal.
        """
        existing_ids = {a.activity_id for a in session.query(Activity).all()}

        # Deduplicate the incoming batch by activity id first.
        batch: dict[str, dict[str, Any]] = {}
        for summary in candidates:
            record = self._candidate_record(summary)
            if record["activity_id"]:
                batch.setdefault(record["activity_id"], record)

        new_records = [r for r in batch.values() if r["activity_id"] not in existing_ids]
        records = self._existing_records(session) + new_records

        # Resolve duplicate groups: keep the winner, drop/delete the losers.
        skip_new: set[str] = set()
        for group in find_duplicate_groups(records):
            winner = pick_duplicate_winner(group)
            for record in group:
                if record["activity_id"] == winner["activity_id"]:
                    continue
                if record["source"] == "db":
                    self._delete_activity(session, record["activity_id"])
                else:
                    skip_new.add(record["activity_id"])

        imported = 0
        for record in new_records:
            if record["activity_id"] in skip_new:
                continue
            summary = record["summary"]
            session.add(self._build_activity(summary))
            session.add(
                ActivityRaw(
                    activity_id=record["activity_id"],
                    garmin_json=summary,
                    import_timestamp=datetime.utcnow(),
                )
            )
            imported += 1

        return imported

    def sync(self, client: Any, limit: int = 20) -> int:
        raw_payload = client.get_activities(start=0, limit=limit, activitytype=None)
        activities = raw_payload if isinstance(raw_payload, list) else raw_payload.get("activities", [])

        candidates: list[dict[str, Any]] = []
        for raw_activity in activities:
            if is_multisport_parent(raw_activity):
                candidates.extend(self._expand_multisport(client, raw_activity))
            elif is_endurance_activity(raw_activity):
                candidates.append(raw_activity)

        with self.session_scope() as session:
            return self._store_candidates(session, candidates)
