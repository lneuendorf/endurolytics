"""Settings page: edit athlete thresholds and (optionally) recompute metrics."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, html, no_update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.components import section_card
from app.data import get_engine
from database.settings import get_athlete_settings, upsert_athlete_settings
from pipeline.process_activities import process_all


def _parse_int(value) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _parse_pace(text) -> float | None:
    """Parse 'mm:ss' or plain seconds into float seconds."""
    if text in (None, ""):
        return None
    text = str(text).strip()
    if not text:
        return None
    if ":" in text:
        minutes, seconds = text.split(":", 1)
        return float(int(minutes) * 60 + float(seconds))
    return float(text)


def _format_pace(seconds) -> str:
    if not seconds:
        return ""
    seconds = int(round(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


# The DB stores run threshold pace in seconds per kilometer (matching the
# analytics), but the UI presents it in minutes per mile.
_KM_PER_MILE = 1.609344


def _km_pace_to_mile(seconds_per_km) -> float | None:
    """Convert a seconds-per-km pace to seconds-per-mile for display."""
    if not seconds_per_km:
        return None
    return seconds_per_km * _KM_PER_MILE


def _mile_pace_to_km(seconds_per_mile) -> float | None:
    """Convert a seconds-per-mile pace to seconds-per-km for storage."""
    if not seconds_per_mile:
        return None
    return seconds_per_mile / _KM_PER_MILE


def _field(label, input_id, value, placeholder, input_type="number", help_text=None):
    children = [
        dbc.Label(label, html_for=input_id, className="fw-semibold"),
        dbc.Input(id=input_id, type=input_type, value=value, placeholder=placeholder),
    ]
    if help_text:
        children.append(html.Small(help_text, className="text-muted"))
    return dbc.Col(html.Div(children, className="mb-3"), md=6)


def layout(engine: Engine):
    with Session(engine) as session:
        current = get_athlete_settings(session)
        data = current.to_dict() if current else {}

    form = dbc.Form(
        [
            dbc.Row(
                [
                    _field(
                        "FTP (watts)", "settings-ftp", data.get("ftp_watts"),
                        "e.g. 250", help_text="Functional Threshold Power — bike TSS.",
                    ),
                    _field(
                        "Threshold HR (bpm)", "settings-threshold-hr", data.get("threshold_hr"),
                        "e.g. 165", help_text="Lactate threshold heart rate — HR-based TSS.",
                    ),
                ]
            ),
            dbc.Row(
                [
                    _field(
                        "Run threshold pace (min/mi)", "settings-run-pace",
                        _format_pace(_km_pace_to_mile(data.get("run_threshold_pace_seconds_per_km"))),
                        "e.g. 6:50", input_type="text",
                        help_text="Threshold pace as mm:ss per mile — run TSS.",
                    ),
                    _field(
                        "Swim CSS pace (min/100m)", "settings-swim-pace",
                        _format_pace(data.get("swim_css_pace_seconds_per_100m")),
                        "e.g. 1:35", input_type="text",
                        help_text="Critical Swim Speed as mm:ss per 100 m — swim TSS.",
                    ),
                ]
            ),
            dbc.Row(
                [
                    _field(
                        "Resting HR (bpm)", "settings-resting-hr", data.get("resting_hr"),
                        "e.g. 48", help_text="Enables HR-reserve intensity when set.",
                    ),
                    _field(
                        "Max HR (bpm)", "settings-max-hr", data.get("max_hr"),
                        "e.g. 190",
                    ),
                ]
            ),
            dbc.Switch(
                id="settings-recompute",
                label="Recompute all historical metrics after saving",
                value=True,
                className="mb-3",
            ),
            dbc.Button("Save settings", id="settings-save", color="primary", n_clicks=0),
            html.Div(id="settings-status", className="mt-3"),
        ]
    )

    return dbc.Container(
        [
            html.H1("Settings", className="mt-2 mb-2"),
            html.P(
                "Set your thresholds to switch TSS from the duration-only estimate "
                "(IF 0.70) to power / pace / heart-rate based intensity.",
                className="text-muted",
            ),
            section_card("Athlete Thresholds", form),
        ],
        fluid=True,
    )


@callback(
    Output("settings-status", "children"),
    Input("settings-save", "n_clicks"),
    State("settings-ftp", "value"),
    State("settings-run-pace", "value"),
    State("settings-swim-pace", "value"),
    State("settings-threshold-hr", "value"),
    State("settings-resting-hr", "value"),
    State("settings-max-hr", "value"),
    State("settings-recompute", "value"),
    prevent_initial_call=True,
)
def save_settings(n_clicks, ftp, run_pace, swim_pace, threshold_hr, resting_hr, max_hr, recompute):
    if not n_clicks:
        return no_update

    try:
        values = {
            "ftp_watts": _parse_int(ftp),
            "run_threshold_pace_seconds_per_km": _mile_pace_to_km(_parse_pace(run_pace)),
            "swim_css_pace_seconds_per_100m": _parse_pace(swim_pace),
            "threshold_hr": _parse_int(threshold_hr),
            "resting_hr": _parse_int(resting_hr),
            "max_hr": _parse_int(max_hr),
        }
    except (ValueError, TypeError):
        return dbc.Alert(
            "Could not parse one of the values. Use numbers, and mm:ss for paces.",
            color="danger",
        )

    engine = get_engine()
    with Session(engine) as session:
        upsert_athlete_settings(session, **values)
        session.commit()

    message = "Settings saved."
    if recompute:
        counts = process_all(engine=engine)
        message += (
            f" Recomputed {counts['activity_metrics']} activities and "
            f"{counts['weekly_training']} weekly rollups."
        )

    return dbc.Alert(message, color="success")
