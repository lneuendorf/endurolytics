"""Training Load page: CTL / ATL / TSB trends over time."""

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
from app.theme import COLORS, LOAD_COLORS, make_figure


def _fitness_fatigue_figure(weeks: list[dict]) -> go.Figure:
    labels = [w["week_start"] for w in weeks]
    traces = [
        go.Scatter(
            name="CTL (Fitness)", x=labels, y=[w["ctl"] or 0 for w in weeks],
            mode="lines+markers", line={"color": LOAD_COLORS["ctl"], "width": 3},
            fill="tozeroy", fillcolor="rgba(97, 188, 255, 0.12)",
        ),
        go.Scatter(
            name="ATL (Fatigue)", x=labels, y=[w["atl"] or 0 for w in weeks],
            mode="lines+markers", line={"color": LOAD_COLORS["atl"], "width": 2, "dash": "dot"},
        ),
    ]
    fig = make_figure(traces, height=380)
    fig.update_layout(yaxis_title="Load", xaxis_title="Week")
    return fig


def _form_figure(weeks: list[dict]) -> go.Figure:
    labels = [w["week_start"] for w in weeks]
    values = [w["tsb"] or 0 for w in weeks]
    colors = [COLORS["green"] if v >= 0 else COLORS["red"] for v in values]
    traces = [go.Bar(name="TSB (Form)", x=labels, y=values, marker_color=colors)]
    fig = make_figure(traces, height=320, hovermode="x")
    fig.update_layout(yaxis_title="TSB", xaxis_title="Week", showlegend=False)
    return fig


def layout(engine: Engine):
    weeks = get_weekly_training(engine)

    if not weeks:
        return dbc.Container(
            [
                html.H1("Training Load", className="mt-2 mb-4"),
                dbc.Alert("No training data yet. Run the sync to import activities.", color="info"),
            ],
            fluid=True,
        )

    return dbc.Container(
        [
            html.H1("Training Load", className="mt-2 mb-4"),
            html.P(
                "CTL tracks long-term fitness (42-day load), ATL short-term fatigue "
                "(7-day load), and TSB their balance — positive means fresh, negative "
                "means fatigued.",
                className="text-muted",
            ),
            range_selector("training-load-range"),
            html.Div(id="training-load-content"),
        ],
        fluid=True,
    )


@callback(
    Output("training-load-content", "children"),
    Input("training-load-range", "value"),
)
def update_training_load_content(range_weeks):
    weeks = get_weekly_training(get_engine())
    if not weeks:
        return dbc.Alert("No training data yet.", color="info")
    weeks = slice_weeks(weeks, range_weeks if range_weeks is not None else DEFAULT_RANGE_WEEKS)
    return [
        section_card("Fitness & Fatigue", dcc.Graph(figure=_fitness_fatigue_figure(weeks), config=STATIC_GRAPH_CONFIG)),
        section_card("Form (TSB)", dcc.Graph(figure=_form_figure(weeks), config=STATIC_GRAPH_CONFIG)),
    ]
