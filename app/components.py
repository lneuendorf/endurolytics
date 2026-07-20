"""Reusable Dash UI components styled for the brite theme."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html

from app.theme import COLORS

# Shared Plotly config: hover tooltips enabled, but no modebar, zoom, pan or
# scroll-zoom. Zoom/pan is locked via the figure layout (fixedrange + dragmode).
STATIC_GRAPH_CONFIG = {"displayModeBar": False, "scrollZoom": False, "doubleClick": False}


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
    {"label": "8 weeks", "value": 8},
    {"label": "12 weeks", "value": 12},
    {"label": "6 months", "value": 26},
    {"label": "1 year", "value": 52},
    {"label": "All time", "value": 0},
]
DEFAULT_RANGE_WEEKS = 12


def range_selector(control_id: str, default: int = DEFAULT_RANGE_WEEKS):
    """A compact dropdown for choosing how many recent weeks to show."""
    return html.Div(
        [
            html.Span("Range", className="text-muted small text-uppercase me-2", style={"letterSpacing": "0.04em"}),
            dcc.Dropdown(
                id=control_id,
                options=RANGE_OPTIONS,
                value=default,
                clearable=False,
                searchable=False,
                className="range-dropdown",
            ),
        ],
        className="d-flex align-items-center mb-3",
    )


def slice_weeks(weeks: list, n: int | None):
    """Return the most recent ``n`` weeks (or all when ``n`` is falsy)."""
    if not n or n <= 0:
        return weeks
    return weeks[-n:]


# --- Sortable tables -----------------------------------------------------
#
# Tables are rendered server-side, so sorting is done by clicking a column
# header, which updates a small ``dcc.Store`` and re-renders the rows. Sorting
# operates on the raw underlying values (not the formatted display strings) and
# always keeps rows with missing values last, regardless of direction.


def next_sort_state(columns: list[dict], current: dict | None, clicked_key: str) -> dict:
    """Return the new sort state after a header click.

    Clicking the active column flips its direction; clicking a new column sorts
    by that column using its ``default_dir`` (defaults to descending).
    """
    if current and current.get("col") == clicked_key:
        new_dir = "asc" if current.get("dir") == "desc" else "desc"
        return {"col": clicked_key, "dir": new_dir}
    column = next((c for c in columns if c["key"] == clicked_key), None)
    return {"col": clicked_key, "dir": (column or {}).get("default_dir", "desc")}


def sort_rows(rows: list[dict], columns: list[dict], sort_state: dict | None) -> list[dict]:
    """Sort ``rows`` by the active column, keeping missing values last."""
    if not sort_state:
        return rows
    column = next((c for c in columns if c["key"] == sort_state.get("col")), None)
    if column is None:
        return rows

    key_func = column["sort"]
    reverse = sort_state.get("dir") == "desc"

    keyed = [(key_func(row), row) for row in rows]
    present = [(key, row) for key, row in keyed if key is not None]
    missing = [row for key, row in keyed if key is None]
    present.sort(key=lambda pair: pair[0], reverse=reverse)
    return [row for _, row in present] + missing


def _sortable_header(columns: list[dict], sort_state: dict, sort_type: str):
    header_cells = []
    for column in columns:
        active = column["key"] == sort_state.get("col")
        if active:
            indicator = " \u25b2" if sort_state.get("dir") == "asc" else " \u25bc"
        else:
            indicator = ""
        align = "text-end" if column.get("align") == "end" else ""
        header_cells.append(
            html.Th(
                [column["label"], html.Span(indicator, className="sort-arrow")],
                id={"type": sort_type, "index": column["key"]},
                n_clicks=0,
                className=f"sortable-th {align}".strip(),
            )
        )
    return html.Thead(html.Tr(header_cells))


def sortable_table(rows: list[dict], columns: list[dict], sort_state: dict, sort_type: str):
    """Render ``rows`` as a striped table with clickable, sortable headers.

    ``rows`` should already be sorted (via :func:`sort_rows`) and, where relevant,
    paginated. Each column spec is a dict with ``key``, ``label``, ``render``
    (row -> cell) and ``sort`` (row -> comparable) plus optional ``align`` and
    ``default_dir``. ``sort_type`` namespaces the header ids for the page's
    pattern-matching callback.
    """
    body_rows = []
    for row in rows:
        cells = []
        for column in columns:
            align = "text-end" if column.get("align") == "end" else ""
            extra = column.get("cell_class", "")
            cells.append(html.Td(column["render"](row), className=f"{align} {extra}".strip()))
        body_rows.append(html.Tr(cells))

    return dbc.Table(
        [_sortable_header(columns, sort_state, sort_type), html.Tbody(body_rows)],
        striped=True,
        hover=True,
        responsive=True,
        className="align-middle mb-0",
    )

