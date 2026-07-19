"""Activities page: filterable activity history with training-load columns."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, ctx, dcc, html

from app.components import section_card
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


def _activity_effort_display(activity: dict) -> str:
    discipline = activity.get("discipline")
    duration_seconds = activity.get("duration_seconds") or 0
    distance_meters = activity.get("distance_meters") or 0

    if discipline == "bike":
        power = activity.get("normalized_power") or activity.get("avg_power")
        return f"{power:.0f} W" if power is not None else "-"

    if not duration_seconds or not distance_meters:
        return "-"

    if discipline == "run":
        pace_seconds_per_mile = duration_seconds / (distance_meters / 1609.344)
        return f"{_seconds_to_pace(pace_seconds_per_mile)} /mi"

    if discipline == "swim":
        pace_seconds_per_100yd = duration_seconds / (distance_meters / 91.44)
        return f"{_seconds_to_pace(pace_seconds_per_100yd)} /100yd"

    return "-"


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
    Input("activities-prev", "n_clicks"),
    Input("activities-next", "n_clicks"),
    State("activities-page", "data"),
    prevent_initial_call=True,
)
def update_page(sport_filter, prev_clicks, next_clicks, current_page):
    """Track the current page, resetting to the first page on filter change."""
    trigger = ctx.triggered_id
    current_page = current_page or 0
    if trigger == "activities-sport-filter":
        return 0
    if trigger == "activities-next":
        return current_page + 1
    if trigger == "activities-prev":
        return max(0, current_page - 1)
    return current_page


@callback(
    Output("activities-table-container", "children"),
    Output("activities-page-info", "children"),
    Output("activities-prev", "disabled"),
    Output("activities-next", "disabled"),
    Input("activities-sport-filter", "value"),
    Input("activities-page", "data"),
)
def update_activities_table(sport_filter, page):
    """Render one page of the activity table for the selected discipline."""
    engine = get_engine()
    discipline = None if sport_filter in (None, "all") else sport_filter
    activities = get_activities_with_metrics(engine, discipline=discipline, limit=1000)

    if not activities:
        return dbc.Alert("No activities found.", color="info"), "", True, True

    page = page or 0
    total = len(activities)
    total_pages = (total + _PAGE_SIZE - 1) // _PAGE_SIZE
    page = max(0, min(page, total_pages - 1))
    start = page * _PAGE_SIZE
    end = start + _PAGE_SIZE
    page_activities = activities[start:end]

    table_rows = []
    for activity in page_activities:
        distance_value, distance_unit = get_distance_display(
            activity["sport"], activity.get("distance_meters")
        )
        tss = activity.get("tss")
        intensity = activity.get("intensity_factor")

        table_rows.append(
            html.Tr(
                [
                    html.Td(activity.get("date") or "-"),
                    html.Td(activity.get("activity_name") or "-"),
                    html.Td(activity.get("sport") or "-"),
                    html.Td(seconds_to_time_string(activity.get("duration_seconds"))),
                    html.Td(f"{distance_value} {distance_unit}", className="text-end"),
                    html.Td(_activity_effort_display(activity), className="text-end"),
                    html.Td(
                        f"{activity.get('avg_hr'):.0f}" if activity.get("avg_hr") is not None else "-",
                        className="text-end",
                    ),
                    html.Td(f"{tss:.0f}" if tss is not None else "-", className="text-end"),
                    html.Td(f"{intensity:.2f}" if intensity is not None else "-", className="text-end"),
                ]
            )
        )

    header = html.Thead(
        html.Tr(
            [
                html.Th("Date"),
                html.Th("Activity Name"),
                html.Th("Sport"),
                html.Th("Duration"),
                html.Th("Distance", className="text-end"),
                html.Th("Pace / NP", className="text-end"),
                html.Th("Avg HR", className="text-end"),
                html.Th("TSS", className="text-end"),
                html.Th("IF", className="text-end"),
            ]
        )
    )

    table = dbc.Table(
        [header, html.Tbody(table_rows)],
        striped=True,
        hover=True,
        responsive=True,
        className="align-middle mb-0",
    )

    page_info = f"Showing {start + 1}\u2013{min(end, total)} of {total}"
    return table, page_info, page == 0, end >= total
