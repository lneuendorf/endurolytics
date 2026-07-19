"""Overview page: current fitness/fatigue/form and recent weekly load."""

from __future__ import annotations

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html
from sqlalchemy.engine import Engine

from app.components import (
    DEFAULT_RANGE_WEEKS,
    range_selector,
    section_card,
    slice_weeks,
    stat_card,
)
from app.data import get_engine, get_weekly_training
from app.theme import COLORS, LOAD_COLORS, SPORT_COLORS, make_figure


def _tsb_accent(tsb: float) -> str:
    if tsb > 5:
        return COLORS["green"]
    if tsb < -10:
        return COLORS["red"]
    return COLORS["yellow"]


def _weekly_tss_figure(weeks: list[dict]) -> go.Figure:
    weeks_labels = [w["week_start"] for w in weeks]
    traces = [
        go.Bar(name="Run", x=weeks_labels, y=[w["run_tss"] or 0 for w in weeks], marker_color=SPORT_COLORS["run"]),
        go.Bar(name="Bike", x=weeks_labels, y=[w["bike_tss"] or 0 for w in weeks], marker_color=SPORT_COLORS["bike"]),
        go.Bar(name="Swim", x=weeks_labels, y=[w["swim_tss"] or 0 for w in weeks], marker_color=SPORT_COLORS["swim"]),
    ]
    fig = make_figure(traces, height=340)
    fig.update_layout(barmode="stack", yaxis_title="TSS", xaxis_title="Week")
    return fig


def _weekly_hours_figure(weeks: list[dict]) -> go.Figure:
    weeks_labels = [w["week_start"] for w in weeks]
    traces = [
        go.Bar(name="Run", x=weeks_labels, y=[w["run_hours"] or 0 for w in weeks], marker_color=SPORT_COLORS["run"]),
        go.Bar(name="Bike", x=weeks_labels, y=[w["bike_hours"] or 0 for w in weeks], marker_color=SPORT_COLORS["bike"]),
        go.Bar(name="Swim", x=weeks_labels, y=[w["swim_hours"] or 0 for w in weeks], marker_color=SPORT_COLORS["swim"]),
    ]
    fig = make_figure(traces, height=340)
    fig.update_layout(barmode="stack", yaxis_title="Hours", xaxis_title="Week")
    return fig


def _load_figure(weeks: list[dict]) -> go.Figure:
    weeks_labels = [w["week_start"] for w in weeks]
    traces = [
        go.Scatter(
            name="CTL (Fitness)", x=weeks_labels, y=[w["ctl"] or 0 for w in weeks],
            mode="lines+markers", line={"color": LOAD_COLORS["ctl"], "width": 3},
        ),
        go.Scatter(
            name="ATL (Fatigue)", x=weeks_labels, y=[w["atl"] or 0 for w in weeks],
            mode="lines+markers", line={"color": LOAD_COLORS["atl"], "width": 2, "dash": "dot"},
        ),
    ]
    fig = make_figure(traces, height=340)
    fig.update_layout(yaxis_title="Load", xaxis_title="Week")
    return fig


def layout(engine: Engine):
    weeks = get_weekly_training(engine)

    if not weeks:
        return dbc.Container(
            [
                html.H1("Overview", className="mt-2 mb-4"),
                dbc.Alert(
                    "No training data yet. Run the sync to import activities.",
                    color="info",
                ),
            ],
            fluid=True,
        )

    latest = weeks[-1]
    tsb = latest.get("tsb") or 0.0

    cards = dbc.Row(
        [
            dbc.Col(stat_card("Fitness (CTL)", f"{latest.get('ctl') or 0:.0f}", "42-day load", LOAD_COLORS["ctl"]), lg=2, md=4, sm=6, className="mb-3"),
            dbc.Col(stat_card("Fatigue (ATL)", f"{latest.get('atl') or 0:.0f}", "7-day load", LOAD_COLORS["atl"]), lg=2, md=4, sm=6, className="mb-3"),
            dbc.Col(stat_card("Form (TSB)", f"{tsb:+.0f}", "fitness − fatigue", _tsb_accent(tsb)), lg=2, md=4, sm=6, className="mb-3"),
            dbc.Col(stat_card("This Week TSS", f"{latest.get('total_tss') or 0:.0f}", latest["week_start"], COLORS["primary"]), lg=3, md=6, sm=6, className="mb-3"),
            dbc.Col(stat_card("This Week Hours", f"{latest.get('total_hours') or 0:.1f}", "training time", COLORS["teal"]), lg=3, md=6, sm=6, className="mb-3"),
        ],
        className="g-3",
    )

    return dbc.Container(
        [
            html.H1("Overview", className="mt-2 mb-4"),
            cards,
            range_selector("overview-range"),
            html.Div(id="overview-charts"),
        ],
        fluid=True,
    )


def _charts(weeks: list[dict]):
    return [
        dbc.Row(
            [
                dbc.Col(section_card("Weekly TSS by Sport", dcc.Graph(figure=_weekly_tss_figure(weeks), config={"displayModeBar": False})), lg=6),
                dbc.Col(section_card("Weekly Hours by Sport", dcc.Graph(figure=_weekly_hours_figure(weeks), config={"displayModeBar": False})), lg=6),
            ]
        ),
        dbc.Row(
            [
                dbc.Col(section_card("Fitness & Fatigue Trend", dcc.Graph(figure=_load_figure(weeks), config={"displayModeBar": False})), lg=12),
            ]
        ),
    ]


@callback(
    Output("overview-charts", "children"),
    Input("overview-range", "value"),
)
def update_overview_charts(range_weeks):
    weeks = get_weekly_training(get_engine())
    if not weeks:
        return dbc.Alert("No training data yet.", color="info")
    return _charts(slice_weeks(weeks, range_weeks if range_weeks is not None else DEFAULT_RANGE_WEEKS))
