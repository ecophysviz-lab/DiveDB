"""
Core layout components and main layout assembly.
"""
from dash import dcc, html
import dash_bootstrap_components as dbc

from .sidebar import create_left_sidebar, create_right_sidebar
from .timeline import create_footer
from .modals import create_bookmark_modal


def create_header():
    """Create the main header/navbar component."""
    return html.Header(
        [
            dbc.Navbar(
                dbc.Container(
                    [
                        html.A(
                            dbc.Row(
                                [
                                    dbc.Col(
                                        html.Img(
                                            src="/assets/images/divedb_logo.png",
                                        ),
                                        className="logo",
                                    ),
                                    dbc.Col(
                                        dbc.NavbarBrand(
                                            "Data Visualization",
                                            className="ms-3",
                                        )
                                    ),
                                ],
                                align="center",
                                className="g-0",
                            ),
                            href="/",
                            style={"textDecoration": "none"},
                        ),
                        dbc.DropdownMenu(
                            children=[
                                dbc.DropdownMenuItem(
                                    "View Profile",
                                    href="#",
                                    id="view-profile",
                                ),
                                dbc.DropdownMenuItem(
                                    "Settings", href="#", id="settings"
                                ),
                                dbc.DropdownMenuItem(divider=True),
                                dbc.DropdownMenuItem(
                                    "Sign Out", href="#", id="sign-out"
                                ),
                            ],
                            toggle_class_name="btn btn-icon-only btn-icon-profile btn-lg",
                            id="profile-dropdown",
                            direction="down",
                            align_end=True,
                        ),
                        dbc.NavbarToggler(id="navbar-toggler", n_clicks=0),
                    ]
                ),
                color="dark",
                dark=True,
            )
        ],
        className="main_header",
    )


def create_main_content(fig):
    """Create the main content area with the graph."""
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    dcc.Graph(
                                        id="graph-content",
                                        figure=fig,
                                        responsive=True,
                                    ),
                                ],
                                className="graph-content-container",
                            ),
                        ],
                        className="main_content_scroll",
                    )
                ],
                className="content",
            ),
            html.Div([], className="resize-bar", id="resizeHandle"),
        ],
        className="main_content",
    )


def create_app_stores(dff, initial_deployments=None):
    """Create the dcc.Store and dcc.Interval components."""
    return [
        # Location for triggering callbacks on page load
        dcc.Location(id="url", refresh=False),
        # Existing stores for playback
        dcc.Interval(
            id="interval-component",
            interval=1 * 1000,  # Base interval of 1 second
            n_intervals=0,
            disabled=True,  # Start with the interval disabled
        ),
        dcc.Store(id="playhead-time", data=dff["timestamp"].min()),
        dcc.Store(id="is-playing", data=False),
        dcc.Store(id="selected-video", data=None),  # Store for selected video data
        dcc.Store(
            id="manual-video-override", data=None
        ),  # Store for sticky manual selection
        dcc.Store(
            id="video-time-offset", data=0
        ),  # Store for video timeline offset in seconds
        # New stores for dataset/deployment selection
        dcc.Store(id="selected-dataset", data=None),
        dcc.Store(id="selected-deployment", data=None),
        dcc.Store(
            id="trigger-initial-load", data=True
        ),  # Trigger callbacks on page load
        dcc.Store(id="selected-date-range", data=None),
        dcc.Store(id="selected-timezone", data=0),
        dcc.Store(id="available-deployments", data=initial_deployments or []),
        dcc.Store(id="deployment-date-ranges", data={}),
        dcc.Store(id="visualization-loaded", data=False),
        dcc.Store(id="loading-state", data={"stage": "idle", "message": ""}),
        # Store for passing duck_pond reference (will be populated by app)
        dcc.Store(id="duck-pond-config", data=None),
    ]


def create_layout(
    fig,
    data_json,
    dff,
    video_options=None,
    restricted_time_range=None,
    events_df=None,
    available_datasets=None,
    initial_deployments=None,
):
    """Create the complete app layout."""
    return html.Div(
        [
            html.Div(
                [
                    html.Div([], className="announcement_bar"),
                    create_header(),
                    create_left_sidebar(
                        available_datasets=available_datasets,
                        initial_deployments=initial_deployments,
                    ),
                    create_main_content(fig),
                    create_right_sidebar(
                        data_json,
                        dff["timestamp"].min(),
                        video_options=video_options,
                        restricted_time_range=restricted_time_range,
                    ),
                    create_footer(
                        dff, video_options=video_options, events_df=events_df
                    ),
                ],
                className="grid",
            ),
            create_bookmark_modal(),
            *create_app_stores(dff, initial_deployments=initial_deployments),
        ],
        id="main-layout",
        className="default-layout",
    )
