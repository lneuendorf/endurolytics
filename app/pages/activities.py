"""Activities page: filterable activity history with training-load columns."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update

from app.components import next_sort_state, section_card, sort_rows, sortable_table
from app.data import get_activities_with_metrics, get_engine
from app.utils import get_distance_display, seconds_to_time_string

_SPORT_OPTIONS = [
    {"label": "All sports", "value": "all"},
    {"label": "Run", "value": "run"},
    {"label": "Bike", "value": "bike"},
    {"label": "Swim", "value": "swim"},
]

_PAGE_SIZE = 20


def _seconds_to_pace(seconds: float | None) -> str:
    if seconds is None or seconds <= 0:
        return "-"
    total_seconds = int(round(seconds))
    return f"{total_seconds // 60}:{total_seconds % 60:02d}"


def _bike_power(activity: dict) -> float | None:
    """Normalized power (falling back to average power) for bike activities."""
    if activity.get("discipline") != "bike":
        return None
    return activity.get("normalized_power") or activity.get("avg_power")


def _run_pace_seconds(activity: dict) -> float | None:
    """Run pace in seconds per mile, or ``None`` when not a measurable run."""
    if activity.get("discipline") != "run":
        return None
    duration_seconds = activity.get("duration_seconds") or 0
    distance_meters = activity.get("distance_meters") or 0
    if not duration_seconds or not distance_meters:
        return None
    return duration_seconds / (distance_meters / 1609.344)


def _swim_pace_seconds(activity: dict) -> float | None:
    """Swim pace in seconds per 100 yards, or ``None`` when not a measurable swim."""
    if activity.get("discipline") != "swim":
        return None
    duration_seconds = activity.get("duration_seconds") or 0
    distance_meters = activity.get("distance_meters") or 0
    if not duration_seconds or not distance_meters:
        return None
    return duration_seconds / (distance_meters / 91.44)


def _np_display(activity: dict) -> str:
    power = _bike_power(activity)
    return f"{power:.0f} W" if power is not None else "-"


def _run_pace_display(activity: dict) -> str:
    seconds = _run_pace_seconds(activity)
    return f"{_seconds_to_pace(seconds)} /mi" if seconds is not None else "-"


def _swim_pace_display(activity: dict) -> str:
    seconds = _swim_pace_seconds(activity)
    return f"{_seconds_to_pace(seconds)} /100yd" if seconds is not None else "-"


def _distance_cell(activity: dict):
    distance_value, distance_unit = get_distance_display(activity["sport"], activity.get("distance_meters"))
    return f"{distance_value} {distance_unit}"


ACTIVITIES_COLUMNS = [
    {"key": "date", "label": "Date", "default_dir": "desc",
     "sort": lambda a: a.get("date"),
     "render": lambda a: a.get("date") or "-"},
    {"key": "activity_name", "label": "Activity Name", "default_dir": "asc",
     "sort": lambda a: (a.get("activity_name") or "").lower() or None,
     "render": lambda a: a.get("activity_name") or "-"},
    {"key": "sport", "label": "Sport", "default_dir": "asc",
     "sort": lambda a: (a.get("sport") or "").lower() or None,
     "render": lambda a: a.get("sport") or "-"},
    {"key": "duration_seconds", "label": "Duration", "default_dir": "desc",
     "sort": lambda a: a.get("duration_seconds"),
     "render": lambda a: seconds_to_time_string(a.get("duration_seconds"))},
    {"key": "distance_meters", "label": "Distance", "align": "end", "default_dir": "desc",
     "sort": lambda a: a.get("distance_meters"),
     "render": _distance_cell},
    {"key": "np", "label": "NP", "align": "end", "default_dir": "desc",
     "sort": _bike_power,
     "render": _np_display},
    {"key": "run_pace", "label": "Run Pace", "align": "end", "default_dir": "asc",
     "sort": _run_pace_seconds,
     "render": _run_pace_display},
    {"key": "swim_pace", "label": "Swim Pace", "align": "end", "default_dir": "asc",
     "sort": _swim_pace_seconds,
     "render": _swim_pace_display},
    {"key": "avg_hr", "label": "Avg HR", "align": "end", "default_dir": "desc",
     "sort": lambda a: a.get("avg_hr"),
     "render": lambda a: f"{a.get('avg_hr'):.0f}" if a.get("avg_hr") is not None else "-"},
    {"key": "tss", "label": "TSS", "align": "end", "default_dir": "desc",
     "sort": lambda a: a.get("tss"),
     "render": lambda a: f"{a.get('tss'):.0f}" if a.get("tss") is not None else "-"},
    {"key": "intensity_factor", "label": "IF", "align": "end", "default_dir": "desc",
     "sort": lambda a: a.get("intensity_factor"),
     "render": lambda a: f"{a.get('intensity_factor'):.2f}" if a.get("intensity_factor") is not None else "-"},
]

DEFAULT_ACTIVITIES_SORT = {"col": "date", "dir": "desc"}


def layout():
    """Return the layout for the activities page."""
    return dbc.Container(
        [
            html.H1("Activities", className="mt-2 mb-4"),
            dbc.Row(
                [
                    dbc.Col(
                        dcc.Dropdown(
                            id="activities-sport-filter",
                            options=_SPORT_OPTIONS,
                            value="all",
                            clearable=False,
                        ),
                        lg=3,
                        md=5,
                        sm=8,
                        className="mb-3",
                    ),
                ]
            ),
            dcc.Store(id="activities-page", data=0),
            dcc.Store(id="activities-sort", data=DEFAULT_ACTIVITIES_SORT),
            section_card("Activity History", html.Div(id="activities-table-container")),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Button(
                            "Previous",
                            id="activities-prev",
                            color="secondary",
                            outline=True,
                            disabled=True,
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        html.Div(id="activities-page-info", className="text-muted"),
                        className="d-flex align-items-center",
                        width="auto",
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Next",
                            id="activities-next",
                            color="secondary",
                            outline=True,
                        ),
                        width="auto",
                    ),
                ],
                className="mt-3 align-items-center g-2",
            ),
        ],
        fluid=True,
    )


@callback(
    Output("activities-page", "data"),
    Input("activities-sport-filter", "value"),
    Input("activities-sort", "data"),
    Input("activities-prev", "n_clicks"),
    Input("activities-next", "n_clicks"),
    State("activities-page", "data"),
    prevent_initial_call=True,
)
def update_page(sport_filter, sort_state, prev_clicks, next_clicks, current_page):
    """Track the current page, resetting to the first page on filter or sort change."""
    trigger = ctx.triggered_id
    current_page = current_page or 0
    if trigger in ("activities-sport-filter", "activities-sort"):
        return 0
    if trigger == "activities-next":
        return current_page + 1
    if trigger == "activities-prev":
        return max(0, current_page - 1)
    return current_page


@callback(
    Output("activities-sort", "data"),
    Input({"type": "activities-sort-col", "index": ALL}, "n_clicks"),
    State("activities-sort", "data"),
    prevent_initial_call=True,
)
def update_activities_sort(n_clicks, current):
    if not ctx.triggered or not ctx.triggered[0]["value"]:
        return no_update
    return next_sort_state(ACTIVITIES_COLUMNS, current, ctx.triggered_id["index"])


@callback(
    Output("activities-table-container", "children"),
    Output("activities-page-info", "children"),
    Output("activities-prev", "disabled"),
    Output("activities-next", "disabled"),
    Input("activities-sport-filter", "value"),
    Input("activities-page", "data"),
    Input("activities-sort", "data"),
)
def update_activities_table(sport_filter, page, sort_state):
    """Render one page of the activity table for the selected discipline."""
    engine = get_engine()
    discipline = None if sport_filter in (None, "all") else sport_filter
    activities = get_activities_with_metrics(engine, discipline=discipline, limit=1000)

    if not activities:
        return dbc.Alert("No activities found.", color="info"), "", True, True

    sort_state = sort_state or DEFAULT_ACTIVITIES_SORT
    activities = sort_rows(activities, ACTIVITIES_COLUMNS, sort_state)

    page = page or 0
    total = len(activities)
    total_pages = (total + _PAGE_SIZE - 1) // _PAGE_SIZE
    page = max(0, min(page, total_pages - 1))
    start = page * _PAGE_SIZE
    end = start + _PAGE_SIZE
    page_activities = activities[start:end]

    table = sortable_table(page_activities, ACTIVITIES_COLUMNS, sort_state, "activities-sort-col")

    page_info = f"Showing {start + 1}\u2013{min(end, total)} of {total}"
    return table, page_info, page == 0, end >= total
