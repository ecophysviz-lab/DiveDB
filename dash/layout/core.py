"""
Core layout components and main layout assembly.
"""
from dash import dcc, html
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go


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


def create_main_content(fig, channel_options=None):
    """Create the main content area with the graph."""
    # Convert channel_options to dropdown format - ONLY GROUPS
    dropdown_options = []
    if channel_options:
        for option in channel_options:
            if isinstance(option, dict):
                # Handle DuckPond channel metadata format
                kind = option.get("kind")
                # Only show groups, not individual variables
                if kind == "group":
                    # Group - use group name as value, label as display
                    group_name = option.get("group")
                    display_label = option.get("label") or group_name
                    # Note: icons are URLs and can't be displayed in Select dropdowns
                    dropdown_options.append(
                        {"label": display_label, "value": group_name}
                    )
            else:
                # Handle string format (fallback)
                dropdown_options.append(
                    {"label": str(option), "value": str(option).lower()}
                )
    else:
        # Fallback options if channel_options is None (all groups)
        dropdown_options = [
            {"label": "Depth", "value": "depth"},
            {"label": "Pitch, roll, heading", "value": "prh"},
            {"label": "Temperature", "value": "temperature"},
            {"label": "Light", "value": "light"},
        ]

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        html.P(
                                            [
                                                html.Strong(
                                                    [
                                                        "Data Channels",
                                                    ],
                                                ),
                                            ],
                                            className="m-0",
                                        ),
                                    ],
                                    className="sidebar_title",
                                ),
                                dbc.Col(
                                    [
                                        html.Button(
                                            [
                                                html.Img(
                                                    src="/assets/images/home.svg",
                                                    className="",
                                                ),
                                            ],
                                            className="btn btn-sm btn-icon-only m-0",
                                            id="reset-zoom-button",
                                            disabled=True,  # Disabled until user zooms in
                                        ),
                                        dbc.Tooltip(
                                            "Reset Zoom",
                                            target="reset-zoom-button",
                                            placement="bottom",
                                            delay={"show": 100, "hide": 0},
                                            autohide=True,
                                        ),
                                    ],
                                    width={"size": "auto"},
                                ),
                                dbc.Col(
                                    [
                                        html.Button(
                                            [
                                                html.Img(
                                                    src="/assets/images/filter.svg",
                                                    className="",
                                                ),
                                                "Manage Channels",
                                            ],
                                            className="btn btn-sm btn-icon-only m-0",
                                            id="graph-channels-toggle",
                                            disabled=True,  # Disabled until dataset is loaded
                                        ),
                                        dbc.Popover(
                                            [
                                                dbc.PopoverBody(
                                                    [
                                                        dbc.ListGroup(
                                                            [
                                                                # Empty initial state - will be populated by callback
                                                                # Contains placeholder elements with required IDs
                                                                dbc.ListGroupItem(
                                                                    html.Span(
                                                                        "Select a deployment to manage channels",
                                                                        className="text-muted",
                                                                        style={
                                                                            "fontSize": "12px"
                                                                        },
                                                                    ),
                                                                    className="py-3",
                                                                ),
                                                            ],
                                                            id="graph-channel-list",
                                                        ),
                                                    ],
                                                    className="",
                                                )
                                            ],
                                            target="graph-channels-toggle",
                                            placement="bottom-start",
                                            is_open=False,
                                            id="graph-channels",
                                        ),
                                        dbc.Tooltip(
                                            "Manage Channels",
                                            target="graph-channels-toggle",
                                            placement="right",
                                            delay={"show": 100, "hide": 0},
                                            autohide=True,
                                        ),
                                    ],
                                    width={"size": "auto"},
                                ),
                            ],
                            align="center",
                            className="gx-2",
                        ),
                        className="sidebar_header",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    dcc.Graph(
                                        id="graph-content",
                                        figure=fig,
                                        responsive=True,
                                        config={"displayModeBar": False},
                                    ),
                                    # Playhead line overlay - positioned via CSS for performance
                                    # This avoids re-rendering the entire Plotly figure on each tick
                                    html.Div(
                                        id="playhead-line-overlay",
                                        className="playhead-line-overlay",
                                    ),
                                ],
                                className="graph-content-container",
                            ),
                        ],
                        className="sidebar_content",
                    ),
                ],
                className="sidebar",
            ),
            html.Div([], className="resize-bar", id="resizeHandle"),
        ],
        className="main_content",
    )


def create_empty_figure():
    """Create an empty placeholder figure for initial load."""
    fig = go.Figure()
    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[
            dict(
                text="Select a dataset and deployment to begin",
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                xanchor="center",
                yanchor="middle",
                showarrow=False,
                font=dict(size=20, color="gray"),
            )
        ],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(245,245,245,1)",
        margin=dict(l=0, r=0, t=0, b=0),
        height=600,
    )
    return fig


def create_empty_dataframe():
    """Create a minimal empty dataframe for initial stores."""
    now = pd.Timestamp.now()
    return pd.DataFrame(
        {
            "datetime": [now, now + pd.Timedelta(seconds=1)],
            "timestamp": [now.timestamp(), (now + pd.Timedelta(seconds=1)).timestamp()],
        }
    )


def create_loading_overlay():
    """Create a full-page loading overlay with spinner."""
    return html.Div(
        [
            html.Div(
                [
                    dbc.Spinner(
                        color="primary",
                        type="border",
                        spinner_style={"width": "4rem", "height": "4rem"},
                    ),
                    html.P(
                        "Loading deployment data...",
                        className="mt-3 text-white",
                        style={"fontSize": "1.2rem"},
                    ),
                ],
                style={
                    "position": "absolute",
                    "top": "50%",
                    "left": "50%",
                    "transform": "translate(-50%, -50%)",
                    "textAlign": "center",
                    "zIndex": "10001",
                },
            ),
        ],
        id="loading-overlay",
        style={
            "position": "fixed",
            "top": "0",
            "left": "0",
            "width": "100%",
            "height": "100%",
            "backgroundColor": "rgba(0, 0, 0, 0.7)",
            "zIndex": "10000",
            "display": "none",  # Hidden by default
        },
    )
