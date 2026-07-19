import os
import dash_bootstrap_components as dbc
from dash import Dash, dcc, html, callback
from dash.dependencies import Input, Output

from app.data import get_engine
# Import pages at module load so their @callback definitions register with Dash
# before the server starts serving the callback dependency graph.
from app.pages import activities, glossary, overview, settings, training_load, weekly


def _brand(app: Dash):
    """Modern wordmark: gradient pulse badge + two-tone 'Endurolytics'."""
    return html.A(
        [
            html.Img(src=app.get_asset_url("logo.svg"), className="brand-logo__badge"),
            html.Span(
                [
                    html.Span("Enduro", className="brand-logo__accent"),
                    html.Span("lytics", className="brand-logo__rest"),
                ],
                className="brand-logo__wordmark",
            ),
        ],
        href="/",
        className="brand-logo navbar-brand",
    )


def create_app() -> Dash:
    """Create and configure the Dash app with multi-page support."""
    app = Dash(
        __name__,
        suppress_callback_exceptions=True,
    )

    engine = get_engine()

    app.layout = html.Div([
        dcc.Location(id="url", refresh=False),
        dbc.Navbar(
            dbc.Container(
                [
                    _brand(app),
                    dbc.Nav([
                        dbc.NavLink("Overview", href="/", active="exact"),
                        dbc.NavLink("Weekly", href="/weekly", active="exact"),
                        dbc.NavLink("Training Load", href="/training-load", active="exact"),
                        dbc.NavLink("Activities", href="/activities", active="exact"),
                        dbc.NavLink("Glossary", href="/glossary", active="exact"),
                        dbc.NavLink("Settings", href="/settings", active="exact"),
                    ], navbar=True, className="ms-auto"),
                ],
                fluid=True,
            ),
            color="dark",
            dark=True,
            className="mb-4",
        ),
        html.Div(id="page-content"),
    ])

    @app.callback(
        Output("page-content", "children"),
        Input("url", "pathname"),
    )
    def display_page(pathname):
        """Display the appropriate page based on the URL pathname."""
        if pathname == "/activities":
            return activities.layout()
        if pathname == "/weekly":
            return weekly.layout(engine)
        if pathname == "/training-load":
            return training_load.layout(engine)
        if pathname == "/glossary":
            return glossary.layout(engine)
        if pathname == "/settings":
            return settings.layout(engine)
        # Default overview page
        return overview.layout(engine)

    return app


app = create_app()
server = app.server


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)

