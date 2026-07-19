"""Data-access helpers for the dashboard.

The dashboard only *reads* processed data. These helpers pull from the persisted
``weekly_training`` and ``activity_metrics`` tables (populated by
``pipeline.process_activities``), falling back to on-the-fly aggregation when the
processed tables are empty so the app still renders on a fresh database.
"""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from analytics.tss import classify_discipline
from analytics.weekly import aggregate_weekly_activity_summaries
from database.connection import create_engine_from_url
from database.models import Activity, ActivityMetrics, WeeklyTraining

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return a process-wide database engine."""
    global _engine
    if _engine is None:
        _engine = create_engine_from_url(os.getenv("DATABASE_URL", "sqlite:///endurolytics.db"))
    return _engine


def _summary_to_weekly(summary: dict[str, Any]) -> dict[str, Any]:
    """Map an in-memory weekly summary to the WeeklyTraining dict shape."""
    return {
        "week_start": summary["week_start"],
        "total_tss": summary["total_tss"],
        "bike_tss": summary["bike_tss"],
        "run_tss": summary["run_tss"],
        "swim_tss": summary["swim_tss"],
        "total_hours": round(summary["total_duration_seconds"] / 3600.0, 2),
        "run_hours": round(summary["running_duration_seconds"] / 3600.0, 2),
        "bike_hours": round(summary["cycling_duration_seconds"] / 3600.0, 2),
        "swim_hours": round(summary["swimming_duration_seconds"] / 3600.0, 2),
        "run_distance": summary["run_distance_km"],
        "bike_distance": summary["bike_distance_km"],
        "swim_distance": summary["swim_distance_km"],
        "ctl": summary["ctl"],
        "atl": summary["atl"],
        "tsb": summary["tsb"],
        "longest_run": summary["longest_run_km"],
        "longest_bike": summary["longest_bike_km"],
        "longest_swim": summary["longest_swim_km"],
    }


def get_weekly_training(engine: Engine) -> list[dict[str, Any]]:
    """Return weekly training rollups ordered by week (oldest first)."""
    with Session(engine) as session:
        rows = (
            session.query(WeeklyTraining)
            .order_by(WeeklyTraining.week_start.asc())
            .all()
        )
        if rows:
            return [row.to_dict() for row in rows]

    # Fallback: compute on the fly when nothing has been processed yet.
    return [_summary_to_weekly(s) for s in aggregate_weekly_activity_summaries(engine)]


def get_activities_with_metrics(
    engine: Engine, discipline: str | None = None, limit: int = 1000
) -> list[dict[str, Any]]:
    """Return activities joined with their metrics, newest first.

    ``discipline`` optionally filters to ``run`` / ``bike`` / ``swim``.
    """
    with Session(engine) as session:
        rows = (
            session.query(Activity, ActivityMetrics)
            .outerjoin(ActivityMetrics, Activity.activity_id == ActivityMetrics.activity_id)
            .filter(Activity.date.is_not(None))
            .order_by(Activity.date.desc())
            .limit(limit)
            .all()
        )

    results: list[dict[str, Any]] = []
    for activity, metric in rows:
        activity_discipline = (metric.discipline if metric else None) or classify_discipline(activity.sport)
        if discipline and activity_discipline != discipline:
            continue
        results.append(
            {
                "activity_id": activity.activity_id,
                "date": activity.date.date().isoformat() if activity.date else None,
                "activity_name": activity.activity_name,
                "sport": activity.sport,
                "discipline": activity_discipline,
                "duration_seconds": activity.duration_seconds,
                "distance_meters": activity.distance,
                "avg_hr": activity.avg_hr,
                "avg_power": activity.avg_power,
                "normalized_power": activity.normalized_power,
                "tss": metric.tss if metric else None,
                "intensity_factor": metric.intensity_factor if metric else None,
                "tss_method": metric.tss_method if metric else None,
            }
        )
    return results
