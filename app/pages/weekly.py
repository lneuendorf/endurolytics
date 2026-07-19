"""Weekly page: per-week sport breakdown and longest sessions."""

from __future__ import annotations

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html
from sqlalchemy.engine import Engine

from app.components import (
    DEFAULT_RANGE_WEEKS,
    STATIC_GRAPH_CONFIG,
    range_selector,
    section_card,
    slice_weeks,
)
from app.data import get_engine, get_weekly_training
from app.theme import SPORT_COLORS, make_figure
from app.utils import meters_to_miles, meters_to_yards


def _tss_by_sport_figure(weeks: list[dict]) -> go.Figure:
    labels = [w["week_start"] for w in weeks]
    traces = [
        go.Bar(name="Run", x=labels, y=[w["run_tss"] or 0 for w in weeks], marker_color=SPORT_COLORS["run"]),
        go.Bar(name="Bike", x=labels, y=[w["bike_tss"] or 0 for w in weeks], marker_color=SPORT_COLORS["bike"]),
        go.Bar(name="Swim", x=labels, y=[w["swim_tss"] or 0 for w in weeks], marker_color=SPORT_COLORS["swim"]),
    ]
    fig = make_figure(traces, height=360)
    fig.update_layout(barmode="stack", yaxis_title="TSS", xaxis_title="Week")
    return fig


def _km_to_miles(distance_km: float | None) -> float:
    return meters_to_miles((distance_km or 0) * 1000)


def _km_to_yards(distance_km: float | None) -> float:
    return meters_to_yards((distance_km or 0) * 1000)


def _weekly_table(weeks: list[dict]):
    header = html.Thead(
        html.Tr(
            [
                html.Th("Week"),
                html.Th("Total TSS", className="text-end"),
                html.Th("Run TSS", className="text-end"),
                html.Th("Bike TSS", className="text-end"),
                html.Th("Swim TSS", className="text-end"),
                html.Th("Hours", className="text-end"),
                html.Th("Run Total", className="text-end"),
                html.Th("Bike Total", className="text-end"),
                html.Th("Swim Total", className="text-end"),
            ]
        )
    )

    rows = []
    for week in reversed(weeks):  # newest first
        rows.append(
            html.Tr(
                [
                    html.Td(week["week_start"]),
                    html.Td(f"{week.get('total_tss') or 0:.0f}", className="text-end fw-semibold"),
                    html.Td(f"{week.get('run_tss') or 0:.0f}", className="text-end"),
                    html.Td(f"{week.get('bike_tss') or 0:.0f}", className="text-end"),
                    html.Td(f"{week.get('swim_tss') or 0:.0f}", className="text-end"),
                    html.Td(f"{week.get('total_hours') or 0:.1f}", className="text-end"),
                    html.Td(f"{_km_to_miles(week.get('run_distance')):.1f} mi", className="text-end"),
                    html.Td(f"{_km_to_miles(week.get('bike_distance')):.1f} mi", className="text-end"),
                    html.Td(f"{_km_to_yards(week.get('swim_distance')):.0f} yd", className="text-end"),
                ]
            )
        )

    return dbc.Table(
        [header, html.Tbody(rows)],
        striped=True,
        hover=True,
        responsive=True,
        className="align-middle mb-0",
    )


def layout(engine: Engine):
    weeks = get_weekly_training(engine)

    if not weeks:
        return dbc.Container(
            [
                html.H1("Weekly", className="mt-2 mb-4"),
                dbc.Alert("No training data yet. Run the sync to import activities.", color="info"),
            ],
            fluid=True,
        )

    return dbc.Container(
        [
            html.H1("Weekly", className="mt-2 mb-4"),
            range_selector("weekly-range"),
            html.Div(id="weekly-content"),
        ],
        fluid=True,
    )


@callback(
    Output("weekly-content", "children"),
    Input("weekly-range", "value"),
)
def update_weekly_content(range_weeks):
    weeks = get_weekly_training(get_engine())
    if not weeks:
        return dbc.Alert("No training data yet.", color="info")
    weeks = slice_weeks(weeks, range_weeks if range_weeks is not None else DEFAULT_RANGE_WEEKS)
    return [
        section_card("Weekly TSS by Sport", dcc.Graph(figure=_tss_by_sport_figure(weeks), config=STATIC_GRAPH_CONFIG)),
        section_card("Weekly Detail", _weekly_table(weeks)),
    ]
