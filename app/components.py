"""Reusable Dash UI components styled for the brite theme."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import html

from app.theme import COLORS


def stat_card(title: str, value: str, subtitle: str | None = None, accent: str = COLORS["primary"]):
    """A compact metric card with a colored accent bar."""
    body = [
        html.Div(title, className="text-muted small text-uppercase", style={"letterSpacing": "0.04em"}),
        html.Div(value, className="fw-bold", style={"fontSize": "1.75rem", "lineHeight": "1.1"}),
    ]
    if subtitle:
        body.append(html.Div(subtitle, className="text-muted small"))

    return dbc.Card(
        dbc.CardBody(body),
        className="h-100 shadow-sm",
        style={"borderLeft": f"4px solid {accent}"},
    )


def section_card(title: str, children):
    """A titled card wrapper for charts and tables."""
    return dbc.Card(
        [
            dbc.CardHeader(html.H5(title, className="mb-0")),
            dbc.CardBody(children),
        ],
        className="mb-4 shadow-sm",
    )


# Date-range spans (in weeks) for the trend pages. ``0`` means "all data".
RANGE_OPTIONS = [
    {"label": "8 wk", "value": 8},
    {"label": "12 wk", "value": 12},
    {"label": "1/2 yr", "value": 26},
    {"label": "1 yr", "value": 52},
    {"label": "All", "value": 0},
]
DEFAULT_RANGE_WEEKS = 12


def range_selector(control_id: str, default: int = DEFAULT_RANGE_WEEKS):
    """A pill-style radio group for choosing how many recent weeks to show."""
    return html.Div(
        [
            html.Span("Range", className="text-muted small text-uppercase me-2", style={"letterSpacing": "0.04em"}),
            dbc.RadioItems(
                id=control_id,
                options=RANGE_OPTIONS,
                value=default,
                inline=True,
                className="range-selector d-inline-flex",
                inputClassName="btn-check",
                labelClassName="btn btn-outline-secondary btn-sm me-2",
                labelCheckedClassName="active",
            ),
        ],
        className="d-flex align-items-center mb-3",
    )


def slice_weeks(weeks: list, n: int | None):
    """Return the most recent ``n`` weeks (or all when ``n`` is falsy)."""
    if not n or n <= 0:
        return weeks
    return weeks[-n:]

