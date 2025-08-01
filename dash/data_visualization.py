import os
import dash
from dash import dcc, html, Output, Input, State, callback_context
import pandas as pd
from dotenv import load_dotenv
import dash_bootstrap_components as dbc

import three_js_orientation
import video_preview

from DiveDB.services.duck_pond import DuckPond
from graph_utils import plot_tag_data_interactive5

load_dotenv()
duckpond = DuckPond(os.getenv("LOCAL_DELTA_LAKE_PATH"))

app = dash.Dash(__name__, external_stylesheets=[
    dbc.themes.BOOTSTRAP,
    "/assets/styles.css"  # Custom SASS-compiled CSS
])

dff = duckpond.get_delta_data(
    animal_ids="apfo-001a",
    frequency=1,
    labels=[
        "derived_data_depth",
        "sensor_data_temperature",
        "sensor_data_light",
        "pitch",
        "roll",
        "heading",
    ],
    date_range=("2019-11-08T09:33:11+13:00", "2019-11-08T09:39:30+13:00"),
)
# Convert to UTC
dff["datetime"] = dff["datetime"].dt.tz_convert("UTC")
# convert the datetime in dff to +13 timezone
dff["datetime"] = dff["datetime"] + pd.Timedelta(hours=13)

# Convert datetime to timestamp (seconds since epoch) for slider control
dff["timestamp"] = dff["datetime"].apply(lambda x: x.timestamp())
dff["depth"] = dff["derived_data_depth"].apply(lambda x: x * -1)

# Replace the existing figure creation with a call to the new function
fig = plot_tag_data_interactive5(
    data_pkl={
        "sensor_data": {
            "light": dff[["datetime", "sensor_data_light"]],
            "temperature": dff[["datetime", "sensor_data_temperature"]],
        },
        "derived_data": {
            "prh": dff[["datetime", "pitch", "roll", "heading"]],
            "depth": dff[["datetime", "depth"]],
        },
        "sensor_info": {
            "light": {
                "channels": ["sensor_data_light"],
                "metadata": {
                    "sensor_data_light": {
                        "original_name": "Light",
                        "unit": "lux",
                    }
                },
            },
            "temperature": {
                "channels": ["sensor_data_temperature"],
                "metadata": {
                    "sensor_data_temperature": {
                        "original_name": "Temperature (imu)",
                        "unit": "°C",
                    }
                },
            },
        },
        "derived_info": {
            "depth": {
                "channels": ["depth"],
                "metadata": {
                    "depth": {
                        "original_name": "Corrected Depth",
                        "unit": "m",
                    }
                },
            },
            "prh": {
                "channels": ["pitch", "roll", "heading"],
                "metadata": {
                    "pitch": {
                        "original_name": "Pitch",
                        "unit": "°",
                    },
                    "roll": {
                        "original_name": "Roll",
                        "unit": "°",
                    },
                    "heading": {
                        "original_name": "Heading",
                        "unit": "°",
                    },
                },
            },
        },
    },
    sensors=["light", "temperature"],
)

# Set x-axis range to data range and set uirevision
fig.update_layout(
    xaxis=dict(
        range=[dff["datetime"].min(),
        dff["datetime"].max()],
    ),
    uirevision="constant",  # Maintain UI state across updates
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=-.15,
        xanchor="right",
        x=1,
    ),
    font_family="Figtree",
    title_font_family="Figtree",
    font=dict(
        family="Figtree",
        size=14,
        weight='bold',
    ),
    paper_bgcolor="rgba(0,0,0,0)",  # Transparent background
    plot_bgcolor="rgba(245,245,245,1)",  # Transparent plot
    margin=dict(l=0, r=0, t=0, b=0),
)

# Convert DataFrame to JSON
data_json = dff[["datetime", "pitch", "roll", "heading"]].to_json(orient="split")

# Define the app layout
app.layout = html.Div(
    [
        html.Div(
            [
                html.Div(
                    [],
                    className="announcement_bar"
                ),
                html.Header(
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
                                                dbc.Col(dbc.NavbarBrand("Data Visualization", className="ms-3")),
                                            ],
                                            align="center",
                                            className="g-0",
                                        ),
                                        href="/",
                                        style={"textDecoration": "none"},
                                    ),
                                    # html.A(
                                    #     "Contact Us", className="btn btn-primary btn-stroke btn-sm m-0", href="/contact"
                                    # ),
                                    dbc.DropdownMenu(
                                        children=[
                                            dbc.DropdownMenuItem("View Profile", href="#", id="view-profile"),
                                            dbc.DropdownMenuItem("Settings", href="#", id="settings"),
                                            dbc.DropdownMenuItem(divider=True),
                                            dbc.DropdownMenuItem("Sign Out", href="#", id="sign-out"),
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
                    className="main_header"
                ),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                [
                                                    html.Button(
                                                        id="left-toggle",
                                                        className="btn btn-icon-only btn-sm btn-icon-expand toggle_left",
                                                        n_clicks=0
                                                    ),
                                                    dbc.Tooltip(
                                                        "Toggle Left Sidebar",
                                                        target="left-toggle",
                                                        placement="right"
                                                    ),
                                                ],
                                                width={"size": "auto"},
                                            ),
                                            dbc.Col(
                                                [
                                                    html.P(
                                                        [
                                                            html.Strong(
                                                                [
                                                                    "Datasets",
                                                                ],
                                                            ),
                                                        ],
                                                        className="m-0",
                                                    ),
                                                ],
                                                className="sidebar_title",
                                            ),
                                        ],
                                        align="center",
                                        className="gx-2",
                                    ),
                                    className="sidebar_header"
                                ),
                                html.Div(
                                    dbc.Accordion(
                                        [
                                            dbc.AccordionItem(
                                                [
                                                    html.Div(
                                                        [
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action animal_link",
                                                            ),
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action animal_link",
                                                            ),
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action",
                                                            ),
                                                        ],
                                                        className="list-group"
                                                    ),
                                                ],
                                                title=[
                                                    html.Div([
                                                        dbc.Row(
                                                            [
                                                                dbc.Col(
                                                                     html.Div(
                                                                        [
                                                                            html.Div(
                                                                                [
                                                                                    html.Img(
                                                                                        src="/assets/images/dolphin.svg",
                                                                                    ),
                                                                                ],
                                                                                className="animal_border ratio ratio-1x1",
                                                                            ),
                                                                        ],
                                                                        className="animal_art sm",
                                                                        style={"--bs-border-color": "var(--pink)"},
                                                                    ),
                                                                    width={"size": "auto"},
                                                                ),
                                                                dbc.Col(
                                                                    [
                                                                        html.P(
                                                                            [
                                                                                html.Strong(
                                                                                    [
                                                                                        "DOLP_001",
                                                                                    ],
                                                                                ),
                                                                            ],
                                                                            className="strong m-0",
                                                                        ),
                                                                    ],
                                                                ),
                                                                dbc.Col(
                                                                ),
                                                                dbc.Col(
                                                                ),
                                                            ],
                                                            align="center",
                                                        className="gx-3",
                                                    ),
                                                ], className="w-100")
                                                ],
                                                item_id="date-accordion-1"
                                            ),
                                            dbc.AccordionItem(
                                                [
                                                    html.Div(
                                                        [
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action animal_link",
                                                            ),
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action animal_link",
                                                            ),
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action",
                                                            ),
                                                        ],
                                                        className="list-group"
                                                    ),
                                                ],
                                                title=[
                                                    html.Div([
                                                        dbc.Row(
                                                            [
                                                                dbc.Col(
                                                                     html.Div(
                                                                        [
                                                                            html.Div(
                                                                                [
                                                                                    html.Img(
                                                                                        src="/assets/images/penguin.svg",
                                                                                    ),
                                                                                ],
                                                                                className="animal_border ratio ratio-1x1",
                                                                            ),
                                                                        ],
                                                                        className="animal_art sm",
                                                                        style={"--bs-border-color": "var(--orange)"},
                                                                    ),
                                                                    width={"size": "auto"},
                                                                ),
                                                                dbc.Col(
                                                                    [
                                                                        html.P(
                                                                            [
                                                                                html.Strong(
                                                                                    [
                                                                                        "APFO_001",
                                                                                    ],
                                                                                ),
                                                                            ],
                                                                            className="strong m-0",
                                                                        ),
                                                                    ],
                                                                ),
                                                                dbc.Col(
                                                                ),
                                                                dbc.Col(
                                                                    html.Div([
                                                                        html.Span("●", className="text-success me-1"),
                                                                        html.Small("Active", className="text-muted")
                                                                    ], className="ms-auto d-flex align-items-center"),      
                                                                    width={"size": "auto"},
                                                                ),
                                                            ],
                                                            align="center",
                                                        className="gx-3",
                                                    ),
                                                ], className="w-100")
                                                ],
                                                item_id="date-accordion-2"
                                            ),
                                            
                                            dbc.AccordionItem(
                                                [
                                                    html.Div(
                                                        [
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 20, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action animal_link",
                                                            ),
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0 active",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action animal_link active",
                                                            ),
                                                            html.Div(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            "May 13, 2018",
                                                                        ],
                                                                        className="m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action",
                                                            ),
                                                        ],
                                                        className="list-group"
                                                    ),
                                                ],
                                                title=[
                                                    html.Div([
                                                        dbc.Row(
                                                            [
                                                                dbc.Col(
                                                                     html.Div(
                                                                        [
                                                                            html.Div(
                                                                                [
                                                                                    html.Img(
                                                                                        src="/assets/images/seal.svg",
                                                                                    ),
                                                                                ],
                                                                                className="animal_border ratio ratio-1x1",
                                                                            ),
                                                                        ],
                                                                        className="animal_art sm",
                                                                        style={"--bs-border-color": "var(--turquoise)"},
                                                                    ),
                                                                    width={"size": "auto"},
                                                                ),
                                                                dbc.Col(
                                                                    [
                                                                        html.P(
                                                                            [
                                                                                html.Strong(
                                                                                    [
                                                                                        "NESC_001",
                                                                                    ],
                                                                                ),
                                                                            ],
                                                                            className="strong m-0",
                                                                        ),
                                                                    ],
                                                                ),
                                                                dbc.Col(
                                                                ),
                                                            ],
                                                            align="center",
                                                        className="gx-3",
                                                    ),
                                                ], className="w-100")
                                                ],
                                                item_id="date-accordion-3"
                                            ),
                                            dbc.AccordionItem(
                                                [
                                                    html.Div(
                                                        [
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action animal_link",
                                                            ),
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action animal_link",
                                                            ),
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action",
                                                            ),
                                                        ],
                                                        className="list-group"
                                                    ),
                                                ],
                                                title=[
                                                    html.Div([
                                                        dbc.Row(
                                                            [
                                                                dbc.Col(
                                                                     html.Div(
                                                                        [
                                                                            html.Div(
                                                                                [
                                                                                    html.Img(
                                                                                        src="/assets/images/seal.svg",
                                                                                    ),
                                                                                ],
                                                                                className="animal_border ratio ratio-1x1",
                                                                            ),
                                                                        ],
                                                                        className="animal_art sm",
                                                                        style={"--bs-border-color": "var(--green)"},
                                                                    ),
                                                                    width={"size": "auto"},
                                                                ),
                                                                dbc.Col(
                                                                    [
                                                                        html.P(
                                                                            [
                                                                                html.Strong(
                                                                                    [
                                                                                        "NESC_002",
                                                                                    ],
                                                                                ),
                                                                            ],
                                                                            className="strong m-0",
                                                                        ),
                                                                    ],
                                                                ),
                                                                dbc.Col(
                                                                    
                                                                ),
                                                            ],
                                                            align="center",
                                                        className="gx-3",
                                                    ),
                                                ], className="w-100")
                                                ],
                                                item_id="date-accordion-4"
                                            ),
                                            dbc.AccordionItem(
                                                [
                                                    html.Div(
                                                        [
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action animal_link",
                                                            ),
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action animal_link",
                                                            ),
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action",
                                                            ),
                                                        ],
                                                        className="list-group"
                                                    ),
                                                ],
                                                title=[
                                                    html.Div([
                                                        dbc.Row(
                                                            [
                                                                dbc.Col(
                                                                     html.Div(
                                                                        [
                                                                            html.Div(
                                                                                [
                                                                                    html.Img(
                                                                                        src="/assets/images/seal.svg",
                                                                                    ),
                                                                                ],
                                                                                className="animal_border ratio ratio-1x1",
                                                                            ),
                                                                        ],
                                                                        className="animal_art sm",
                                                                        style={"--bs-border-color": "var(--purple)"},
                                                                    ),
                                                                    width={"size": "auto"},
                                                                ),
                                                                dbc.Col(
                                                                    [
                                                                        html.P(
                                                                            [
                                                                                html.Strong(
                                                                                    [
                                                                                        "NESC_003",
                                                                                    ],
                                                                                ),
                                                                            ],
                                                                            className="strong m-0",
                                                                        ),
                                                                    ],
                                                                ),
                                                                dbc.Col(
                                                                    
                                                                ),
                                                            ],
                                                            align="center",
                                                        className="gx-3",
                                                    ),
                                                ], className="w-100")
                                                ],
                                                item_id="date-accordion-5"
                                            ),
                                            dbc.AccordionItem(
                                                [
                                                    html.Div(
                                                        [
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action animal_link",
                                                            ),
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action animal_link",
                                                            ),
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action",
                                                            ),
                                                        ],
                                                        className="list-group"
                                                    ),
                                                ],
                                                title=[
                                                    html.Div([
                                                        dbc.Row(
                                                            [
                                                                dbc.Col(
                                                                     html.Div(
                                                                        [
                                                                            html.Div(
                                                                                [
                                                                                    html.Img(
                                                                                        src="/assets/images/turtle.svg",
                                                                                    ),
                                                                                ],
                                                                                className="animal_border ratio ratio-1x1",
                                                                            ),
                                                                        ],
                                                                        className="animal_art sm",
                                                                        style={"--bs-border-color": "var(--red)"},
                                                                    ),
                                                                    width={"size": "auto"},
                                                                ),
                                                                dbc.Col(
                                                                    [
                                                                        html.P(
                                                                            [
                                                                                html.Strong(
                                                                                    [
                                                                                        "TURL_001",
                                                                                    ],
                                                                                ),
                                                                            ],
                                                                            className="strong m-0",
                                                                        ),
                                                                    ],
                                                                ),
                                                                dbc.Col(
                                                                    
                                                                ),
                                                            ],
                                                            align="center",
                                                        className="gx-3",
                                                    ),
                                                ], className="w-100")
                                                ],
                                                item_id="date-accordion-6"
                                            ),
                                            dbc.AccordionItem(
                                                [
                                                    html.Div(
                                                        [
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action animal_link",
                                                            ),
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action animal_link",
                                                            ),
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action",
                                                            ),
                                                        ],
                                                        className="list-group"
                                                    ),
                                                ],
                                                title=[
                                                    html.Div([
                                                        dbc.Row(
                                                            [
                                                                dbc.Col(
                                                                     html.Div(
                                                                        [
                                                                            html.Div(
                                                                                [
                                                                                    html.Img(
                                                                                        src="/assets/images/turtle.svg",
                                                                                    ),
                                                                                ],
                                                                                className="animal_border ratio ratio-1x1",
                                                                            ),
                                                                        ],
                                                                        className="animal_art sm",
                                                                        style={"--bs-border-color": "var(--green)"},
                                                                    ),
                                                                    width={"size": "auto"},
                                                                ),
                                                                dbc.Col(
                                                                    [
                                                                        html.P(
                                                                            [
                                                                                html.Strong(
                                                                                    [
                                                                                        "TURL_002",
                                                                                    ],
                                                                                ),
                                                                            ],
                                                                            className="strong m-0",
                                                                        ),
                                                                    ],
                                                                ),
                                                                dbc.Col(
                                                                    
                                                                ),
                                                            ],
                                                            align="center",
                                                        className="gx-3",
                                                    ),
                                                ], className="w-100")
                                                ],
                                                item_id="date-accordion-7"
                                            ),
                                            dbc.AccordionItem(
                                                [
                                                    html.Div(
                                                        [
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action animal_link",
                                                            ),
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action animal_link",
                                                            ),
                                                            html.Button(
                                                                [
                                                                    html.P(
                                                                        [
                                                                            html.Strong(
                                                                                [
                                                                                    "April 22, 2018",
                                                                                ],
                                                                            ),
                                                                        ],
                                                                        className="strong m-0",
                                                                    ),
                                                                ],
                                                                className="list-group-item list-group-item-action",
                                                            ),
                                                        ],
                                                        className="list-group"
                                                    ),
                                                ],
                                                title=[
                                                    html.Div([
                                                        dbc.Row(
                                                            [
                                                                dbc.Col(
                                                                     html.Div(
                                                                        [
                                                                            html.Div(
                                                                                [
                                                                                    html.Img(
                                                                                        src="/assets/images/turtle.svg",
                                                                                    ),
                                                                                ],
                                                                                className="animal_border ratio ratio-1x1",
                                                                            ),
                                                                        ],
                                                                        className="animal_art sm",
                                                                        style={"--bs-border-color": "var(--pink)"},
                                                                    ),
                                                                    width={"size": "auto"},
                                                                ),
                                                                dbc.Col(
                                                                    [
                                                                        html.P(
                                                                            [
                                                                                html.Strong(
                                                                                    [
                                                                                        "TURL_003",
                                                                                    ],
                                                                                ),
                                                                            ],
                                                                            className="strong m-0",
                                                                        ),
                                                                    ],
                                                                ),
                                                                dbc.Col(
                                                                    
                                                                ),
                                                            ],
                                                            align="center",
                                                        className="gx-3",
                                                    ),
                                                ], className="w-100")
                                                ],
                                                item_id="date-accordion-8"
                                            ),
                                            
                                            
                                        ],
                                        id="sidebar-accordion",
                                        start_collapsed=True,
                                        always_open=False,
                                        flush=True,
                                    ),
                                    className="sidebar_content"
                                ),
                            ],
                            className="sidebar"
                        )
                    ],
                    className="left_sidebar"
                ),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                dcc.Graph(id="graph-content", figure=fig, responsive=True),
                                            ],
                                            className="graph-content-container",
                                        ),
                                    ],
                                    className="main_content_scroll"
                                )
                            ],
                            className="content"
                        ),
                        html.Div(
                            [],
                            className="resize-bar",
                            id="resizeHandle"
                        )
                    ],
                    className="main_content"
                ),
                html.Div(
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
                                                                    "Visuals",
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
                                                        id="right-toggle",
                                                        className="btn btn-icon-only btn-sm btn-icon-expand toggle_right",
                                                        n_clicks=0
                                                    ),
                                                    dbc.Tooltip(
                                                        "Toggle Right Sidebar",
                                                        target="right-toggle",
                                                        placement="left"
                                                    ),
                                                ],
                                                width={"size": "auto"},
                                            ),
                                        ],
                                        align="center",
                                        className="gx-2",
                                    ),
                                    className="sidebar_header xd-none"
                                ),
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                html.Div(
                                                    [
                                                        three_js_orientation.ThreeJsOrientation(
                                                            id="three-d-model",
                                                            data=data_json,
                                                            activeTime=0,
                                                            objFile="/assets/PenguinSwim.obj",
                                                            textureFile="/assets/PenguinSwim.png",
                                                            style={"width": "100%", "height": "100%"},
                                                        ),
                                                        html.Button(
                                                            [
                                                                "Expand",
                                                            ],
                                                            id="right-top-toggle",
                                                            className="btn btn-icon toggle_right_top",
                                                            n_clicks=0
                                                        ),
                                                        dbc.Tooltip(
                                                            "Expand 3D Model",
                                                            target="right-top-toggle",
                                                            placement="left"
                                                        ),
                                                    ],
                                                    className="three-d-model-container",
                                                )
                                            ],
                                            className="right_sidebar_top",
                                        ),
                                        html.Div(
                                            [
                                                html.Div(
                                                    [
                                                        video_preview.VideoPreview(
                                                            id="video-trimmer",
                                                            # Video file must be downloaded from https://figshare.com/ndownloader/files/50061327
                                                            videoSrc="/assets/2019-11-08_apfo-001a_CC-35_excerpt.mp4",
                                                            # activeTime=0,
                                                            playheadTime=dff["timestamp"].min(),
                                                            isPlaying=False,
                                                        ),
                                                        html.Button(
                                                            [
                                                                "Expand",
                                                            ],
                                                            id="right-bottom-toggle",
                                                            className="btn btn-icon toggle_right_bottom",
                                                            n_clicks=0
                                                        ),
                                                        dbc.Tooltip(
                                                            "Expand Video",
                                                            target="right-bottom-toggle",
                                                            placement= "left",
                                                        ),
                                                    ],
                                                    className="video-container"
                                                )
                                            ],
                                            className="right_sidebar_bottom"
                                        ),
                                    ],
                                    className="sidebar_content"
                                ),
                            ],
                            className="sidebar"
                        ),
                    ],
                    className="right_sidebar"
                ),
                html.Footer(
                    [
                        html.Div(
                            dbc.Container(
                                [
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                [
                                                    html.Div(
                                                        [
                                                            html.Img(
                                                                src="/assets/images/scrubber.svg",
                                                                id="scrubber-icon",
                                                            ),
                                                            dbc.Tooltip(
                                                                "Timeline Scrubber",
                                                                target="scrubber-icon",
                                                                placement="top"
                                                            ),
                                                        ],
                                                        className="icon sm",
                                                    ),
                                                ],
                                                width={"size": "auto"},
                                            ),
                                            dbc.Col(
                                                [
                                                    dcc.Slider(
                                                        id="playhead-slider",
                                                        className="playhead-slider",
                                                        min=dff["timestamp"].min(),
                                                        max=dff["timestamp"].max(),
                                                        value=dff["timestamp"].min(),
                                                        step=1,
                                                        # marks={
                                                        #     int(dff["timestamp"].min()): pd.to_datetime(dff["timestamp"].min(), unit="s").strftime("%H:%M:%S"),
                                                        #     int(dff["timestamp"].max()): pd.to_datetime(dff["timestamp"].max(), unit="s").strftime("%H:%M:%S"),
                                                        # },  # Will be populated by callback
                                                        marks=None,
                                                        
                                                        tooltip={"placement": "top", "always_visible": True, "transform": "formatTimestamp"},
                                                    ),

                                                    dbc.Row(
                                                        [
                                                            dbc.Col(
                                                                [
                                                                    html.Div(
                                                                        [
                                                                            html.P(
                                                                                [
                                                                                    pd.to_datetime(dff["timestamp"].min(), unit="s").strftime("%H:%M:%S"),
                                                                                ],
                                                                                className="xs m-0",
                                                                            ),
                                                                        ],
                                                                        className="time-start",
                                                                    ),
                                                                ],
                                                                width={"size": "auto"},
                                                            ),
                                                            dbc.Col(
                                                                [
                                                                    html.Div(
                                                                        [
                                                                            html.P(
                                                                                [
                                                                                    pd.to_datetime(dff["timestamp"].max(), unit="s").strftime("%H:%M:%S"),
                                                                                ],
                                                                                className="xs m-0",
                                                                            ),
                                                                        ],
                                                                        className="time-end",
                                                                    ),
                                                                ],
                                                                width={"size": "auto"},
                                                            ),
                                                        ],
                                                        align="center",
                                                        justify="between",
                                                        className="gx-4",
                                                    ),
                                                ],
                                                className="",
                                            ),
                                        ],
                                        align="center",
                                        className="g-4",
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                [
                                                    html.Div(
                                                        [
                                                            html.Img(
                                                                src="/assets/images/saved.svg",
                                                                id="saved-icon",
                                                            ),
                                                            dbc.Tooltip(
                                                                "Saved Timestamps",
                                                                target="saved-icon",
                                                                placement="top"
                                                            ),
                                                        ],
                                                        className="icon sm",
                                                    ),
                                                ],
                                                width={"size": "auto"},
                                            ),
                                            dbc.Col(
                                                [
                                                    html.Div(
                                                        [
                                                            html.Div(
                                                                [
                                                                    html.Button(
                                                                        [
                                                                            
                                                                        ],
                                                                        className="",
                                                                        id="saved-1",
                                                                    ),
                                                                    dbc.Tooltip(
                                                                        [
                                                                            html.Div(
                                                                                "09:33:42",
                                                                                className="timestamp"
                                                                            ),
                                                                            html.Div(
                                                                                "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
                                                                            ),
                                                                        ],
                                                                        target="saved-1",
                                                                        className="tooltip-saved",
                                                                        placement="top"
                                                                    ),
                                                                ],
                                                                className="saved_indicator",
                                                                style={
                                                                    "--start": int((dff["timestamp"].max() - dff["timestamp"].min()) * 0.075),
                                                                    "--end": int((dff["timestamp"].max() - dff["timestamp"].min()) * 0.45),
                                                                    "--length": int((dff["timestamp"].max() - dff["timestamp"].min()))
                                                                }
                                                            ),
                                                            html.Div(
                                                                [
                                                                    html.Button(
                                                                        [
                                                                            
                                                                        ],
                                                                        className="",
                                                                        id="saved-2",
                                                                    ),
                                                                    dbc.Tooltip(
                                                                        [
                                                                            html.Div(
                                                                                "09:36:42",
                                                                                className="timestamp"
                                                                            ),
                                                                            html.Div(
                                                                                "Donec nunc mi, faucibus sed vestibulum non, lacinia nec nisl. Integer volutpat odio a elit malesuada hendrerit. Maecenas nec massa urna."
                                                                            ),
                                                                        ],
                                                                        target="saved-2",
                                                                        className="tooltip-saved",
                                                                        placement="top"
                                                                    ),
                                                                ],
                                                                className="saved_indicator",
                                                                style={
                                                                    "--start": int((dff["timestamp"].max() - dff["timestamp"].min()) * 0.55),
                                                                    "--end": int((dff["timestamp"].max() - dff["timestamp"].min()) * 0.45),
                                                                    "--length": int((dff["timestamp"].max() - dff["timestamp"].min()))
                                                                }
                                                            ),
                                                            html.Div(
                                                                [
                                                                    html.Button(
                                                                        [
                                                                            
                                                                        ],
                                                                        className="",
                                                                        id="saved-3",
                                                                    ),
                                                                    dbc.Tooltip(
                                                                        [
                                                                            html.Div(
                                                                                "09:37:31",
                                                                                className="timestamp"
                                                                            ),
                                                                            html.Div(
                                                                                "Pellentesque cursus hendrerit justo, sit amet volutpat massa mattis id."
                                                                            ),
                                                                        ],
                                                                        target="saved-3",
                                                                        className="tooltip-saved",
                                                                        placement="top"
                                                                    ),
                                                                ],
                                                                className="saved_indicator",
                                                                style={
                                                                    "--start": int((dff["timestamp"].max() - dff["timestamp"].min()) * 0.675),
                                                                    "--end": int((dff["timestamp"].max() - dff["timestamp"].min()) * 0.45),
                                                                    "--length": int((dff["timestamp"].max() - dff["timestamp"].min()))
                                                                }
                                                            ),
                                                        ],
                                                        className="saved",
                                                    ),
                                                ],
                                                className="",
                                            ),
                                        ],
                                        align="center",
                                        className="g-4",
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                [
                                                    html.Div(
                                                        [
                                                            html.Img(
                                                                src="/assets/images/video.svg",
                                                                id="video-icon",
                                                            ),
                                                            dbc.Tooltip(
                                                                "Video Available",
                                                                target="video-icon",
                                                                placement="top"
                                                            ),
                                                        ],
                                                        className="icon sm",
                                                    ),
                                                ],
                                                width={"size": "auto"},
                                            ),
                                            dbc.Col(
                                                [
                                                    html.Div(
                                                        [
                                                            html.Div(
                                                                [
                                                                    html.Button(
                                                                        [
                                                                            
                                                                        ],
                                                                        className="",
                                                                        id="video-1",
                                                                    ),
                                                                    dbc.Tooltip(
                                                                        "09:33:52 - 09:36:01",
                                                                        target="video-1",
                                                                        placement="top"
                                                                    ),
                                                                ],
                                                                className="video_available_indicator",
                                                                style={
                                                                    "--start": int((dff["timestamp"].max() - dff["timestamp"].min()) * 0.1),
                                                                    "--end": int((dff["timestamp"].max() - dff["timestamp"].min()) * 0.45),
                                                                    "--length": int((dff["timestamp"].max() - dff["timestamp"].min()))
                                                                }
                                                            ),
                                                            html.Div(
                                                                [
                                                                    html.Button(
                                                                        [
                                                                            
                                                                        ],
                                                                        id="video-2",
                                                                    ),
                                                                    dbc.Tooltip(
                                                                        "09:35:40 - 09:39:11",
                                                                        target="video-2",
                                                                        placement="top"
                                                                    ),
                                                                ],
                                                                className="video_available_indicator",
                                                                style={
                                                                    "--start": int((dff["timestamp"].max() - dff["timestamp"].min()) * 0.4),
                                                                    "--end": int((dff["timestamp"].max() - dff["timestamp"].min()) * 0.95),
                                                                    "--length": int((dff["timestamp"].max() - dff["timestamp"].min()))
                                                                }
                                                            ),
                                                        ],
                                                        className="video_available",
                                                    ),
                                                ],
                                                className="",
                                            ),
                                        ],
                                        align="center",
                                        className="g-4",
                                    ),
                                ],
                                fluid=True,
                            ),
                            className="playhead-slider-container",
                        ),
                        html.Div(
                            dbc.Container(
                                [
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            html.Div(
                                                                [
                                                                    html.Div(
                                                                        [
                                                                            html.Img(
                                                                                src="/assets/images/penguin.svg",
                                                                            ),
                                                                        ],
                                                                        className="animal_border ratio ratio-1x1",
                                                                    ),
                                                                ],
                                                                className="animal_art",
                                                                style={"--bs-border-color": "var(--orange)"},
                                                            ),
                                                            width={"size": "auto"},
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                html.P(
                                                                    [
                                                                        html.Strong(
                                                                            [
                                                                                "APFO_001",
                                                                            ],
                                                                        ),
                                                                    ],
                                                                    className="strong m-0",
                                                                ),
                                                                html.P(
                                                                    [
                                                                        "November 8, 2019",
                                                                    ],
                                                                    className="sm m-0",
                                                                ),
                                                            ],
                                                        ),
                                                    ],
                                                    align="center",
                                                    justify="center",
                                                    className="h-100 gx-4",
                                                ),
                                                width={"size": "3"},
                                            ),   
                                            dbc.Col(
                                                dbc.Row(
                                                    [   
                                                        dbc.Col(
                                                            [
                                                                html.Button(
                                                                    [
                                                                        "Previous Deployment",
                                                                        html.Img(
                                                                            src="/assets/images/skip-prev-bold.svg",
                                                                        ),
                                                                    ],
                                                                    className="btn btn-icon-only btn-icon-skip-back",
                                                                    id="previous-button",
                                                                    n_clicks=0
                                                                ),
                                                                dbc.Tooltip(
                                                                    "Previous Deployment",
                                                                    target="previous-button",
                                                                    placement= "top",
                                                                ),
                                                            ],
                                                            width={"size": "auto"},
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                html.Button(
                                                                    [
                                                                        "Rewind",
                                                                        html.Img(
                                                                            src="/assets/images/rewind-bold.svg",
                                                                        ),
                                                                    ],
                                                                    className="btn btn-icon-only btn-icon-reverse",
                                                                    id="rewind-button",
                                                                    n_clicks=0
                                                                ),
                                                                dbc.Tooltip(
                                                                    "Rewind",
                                                                    target="rewind-button",
                                                                    placement= "top",
                                                                ),
                                                            ],
                                                            width={"size": "auto"},
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                html.Div(
                                                                    [
                                                                        html.Button(
                                                                            "Play", id="play-button", n_clicks=0, className="btn btn-primary btn-round btn-play btn-lg"
                                                                        ),
                                                                        dbc.Tooltip(
                                                                            "Play/Pause",
                                                                            target="play-button",
                                                                            placement="top",
                                                                        ),
                                                                    ],
                                                                    className="p-1",
                                                                ),
                                                            ],
                                                            width={"size": "auto"},
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                html.Button(
                                                                    [
                                                                        "Fast Foward",
                                                                        html.Img(
                                                                            src="/assets/images/foward-bold.svg",
                                                                        ),
                                                                    ],
                                                                    className="btn btn-icon-only btn-icon-forward",
                                                                    id="forward-button",
                                                                    n_clicks=0
                                                                ),
                                                                dbc.Tooltip(
                                                                    "Fast Foward",
                                                                    target="forward-button",
                                                                    placement= "top",
                                                                ),
                                                            ],
                                                            width={"size": "auto"},
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                html.Button(
                                                                    [
                                                                        "Next Deployment",
                                                                        html.Img(
                                                                            src="/assets/images/skip-next-bold.svg",
                                                                        ),
                                                                    ],
                                                                    className="btn btn-icon-only btn-icon-skip-forward",
                                                                    id="next-button",
                                                                    n_clicks=0
                                                                ),
                                                                dbc.Tooltip(
                                                                    "Next Deployment",
                                                                    target="next-button",
                                                                    placement= "top",
                                                                ),
                                                            ],
                                                            width={"size": "auto"},
                                                        ),
                                                    ],
                                                    align="center",
                                                    justify="center",
                                                    className="h-100 gx-2",
                                                ),
                                                width={"size": "6"},
                                            ),
                                            dbc.Col(
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            [
                                                                
                                                                dbc.Row(
                                                                    [
                                                                        dbc.Col(
                                                                            [
                                                                                html.Button(
                                                                                    [
                                                                                        "Save",
                                                                                        html.Img(
                                                                                            src="/assets/images/save.svg",
                                                                                        ),
                                                                                    ],
                                                                                    className="btn btn-icon-only btn-icon-save",
                                                                                    id="save-button",
                                                                                    n_clicks=0
                                                                                ),
                                                                                dbc.Tooltip(
                                                                                    "Bookmark Timestamp",
                                                                                    target="save-button",
                                                                                    placement= "top",
                                                                                ),
                                                                            ],
                                                                            width={"size": "auto"},
                                                                        ),
                                                                        dbc.Col(
                                                                            [
                                                                                dbc.Button(
                                                                                    [
                                                                                        "Speed",
                                                                                        html.Img(
                                                                                            src="/assets/images/speed.svg",
                                                                                        ),
                                                                                    ],
                                                                                    id="playback-rate",
                                                                                    className="btn btn-icon-only btn-icon-speed",
                                                                                ),
                                                                                dbc.Tooltip(
                                                                                    "Playback Rate",
                                                                                    target="playback-rate",
                                                                                    placement= "top",
                                                                                ),
                                                                                dbc.Popover(
                                                                                    [
                                                                                        # dbc.PopoverHeader("Playback Rate"),
                                                                                        dbc.PopoverBody(
                                                                                            [
                                                                                                dcc.Slider(
                                                                                                    id="playback-rate-slider",
                                                                                                    min=0,
                                                                                                    max=4,
                                                                                                    step=None,
                                                                                                    updatemode="drag",
                                                                                                    marks={
                                                                                                        0: "0.25x",
                                                                                                        1: "0.5x", 
                                                                                                        2: "1x",
                                                                                                        3: "1.5x",
                                                                                                        4: "2x"
                                                                                                    },
                                                                                                    value=2,
                                                                                                ),
                                                                                            ]
                                                                                        ),
                                                                                    ],
                                                                                    target="playback-rate",
                                                                                    trigger="click",
                                                                                    placement="top",
                                                                                ),
                                                                            ],
                                                                            width={"size": "4"},
                                                                        ),
                                                                        dbc.Col(
                                                                            [
                                                                                html.Button(
                                                                                    [
                                                                                        "Expand",
                                                                                        html.Img(
                                                                                            src="/assets/images/fullscreen.svg",
                                                                                        ),
                                                                                    ],
                                                                                    className="btn btn-icon-only btn-icon-fullscreen",
                                                                                    id="fullscreen-button",
                                                                                ),
                                                                                dbc.Tooltip(
                                                                                    id="fullscreen-tooltip",
                                                                                    target="fullscreen-button",
                                                                                    placement= "top",
                                                                                ),
                                                                            ],
                                                                        ),
                                                                    ],
                                                                    align="center",
                                                                    className="g-3",
                                                                ),
                                                            ],
                                                            className="d-flex justify-content-end align-items-center h-100",
                                                        ),
                                                    ],
                                                ),
                                                width={"size": "3"},
                                            ),
                                        ],
                                        className="",
                                        align="center",
                                    ),
                                ],
                                fluid=True,
                            ),
                            className="controls-container",
                        ),
                    ],
                    className="main_footer"
                )
            ],
            className="grid"
        ),
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Bookmark Timestamp")),
                dbc.ModalBody([
                    html.Div(
                        [
                            html.P(
                                "Enter a name and notes for this bookmark.",
                            ),
                            dbc.Label("Timestamp Notes", html_for="bookmark-notes"),
                            dbc.Input(type="textarea", id="bookmark-notes", placeholder="Enter notes..."),
                        ],
                        className="mb-3",
                    )
                ]),
                dbc.ModalFooter([
                    dbc.Button("Close", id="close", className="btn btn-secondary btn-sm", n_clicks=0),
                    dbc.Button("Save", id="save-bookmark-button", className="btn btn-primary btn-sm")
                ]),
            ],
            id="modal",
            is_open=False,
        ),
        dcc.Interval(
            id="interval-component",
            interval=1 * 1000,  # Base interval of 1 second
            n_intervals=0,
            disabled=True,  # Start with the interval disabled
        ),
        dcc.Store(id="playhead-time", data=dff["timestamp"].min()),
        dcc.Store(id="is-playing", data=False),
    ],
    id="main-layout",
    className="default-layout",
)


@app.callback(
    Output("modal", "is_open"),
    [Input("save-button", "n_clicks"), Input("close", "n_clicks")],
    [State("modal", "is_open")],
)
def toggle_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open


@app.callback(
    Output('main-layout', 'className'),
    Input('right-top-toggle', 'n_clicks'),
    Input('right-bottom-toggle', 'n_clicks'),
    Input('left-toggle', 'n_clicks'),
    Input('right-toggle', 'n_clicks'),
    State('main-layout', 'className')
)
def displayClick(right_top_clicks, right_bottom_clicks, left_clicks, right_clicks, current_className):
    if not callback_context.triggered:
        return current_className or 'default-layout'
    
    changed_id = [p['prop_id'] for p in callback_context.triggered][0]
    
    # Parse current class states
    current_classes = (current_className or 'default-layout').split() if current_className else ['default-layout']
    
    # Ensure base class is always present
    if 'default-layout' not in current_classes:
        current_classes.append('default-layout')
    
    # Determine which layout to toggle
    target_layout = None
    if 'right-top-toggle' in changed_id:
        target_layout = 'right-top-expanded'
    elif 'right-bottom-toggle' in changed_id:
        target_layout = 'right-bottom-expanded'
    elif 'left-toggle' in changed_id:
        target_layout = 'left-sidebar-hidden'
    elif 'right-toggle' in changed_id:
        target_layout = 'right-sidebar-hidden'
    
    # Toggle the specific layout class independently
    if target_layout:
        if target_layout in current_classes:
            # Remove the class (toggle off)
            current_classes.remove(target_layout)
        else:
            # Add the class (toggle on)
            current_classes.append(target_layout)
    
    return ' '.join(current_classes)


# Callback to update VideoPreview props
@app.callback(
    Output("video-trimmer", "playheadTime"),
    Output("video-trimmer", "isPlaying"),
    Input("playhead-time", "data"),
    Input("is-playing", "data"),
)
def update_video_preview(playhead_time, is_playing):
    return playhead_time, is_playing


@app.callback(
    Output("three-d-model", "activeTime"), [Input("playhead-slider", "value")]
)
def update_active_time(slider_value):
    # Find the nearest datetime to the slider value
    nearest_idx = dff["timestamp"].sub(slider_value).abs().idxmin()
    return nearest_idx


# Callback to toggle play/pause state
@app.callback(
    Output("is-playing", "data"),
    Output("play-button", "children"),
    Input("play-button", "n_clicks"),
    State("is-playing", "data"),
)
def play_pause(n_clicks, is_playing):
    if n_clicks % 2 == 1:
        return True, "Pause"  # Switch to playing
    else:
        return False, "Play"  # Switch to paused


# Callback to enable/disable the interval component based on play state
@app.callback(Output("interval-component", "disabled"), Input("is-playing", "data"))
def update_interval_component(is_playing):
    return not is_playing  # Interval is disabled when not playing


# Callback to update playhead time based on interval or slider input
@app.callback(
    Output("playhead-time", "data"),
    Output("playhead-slider", "value"),
    Input("interval-component", "n_intervals"),
    Input("playhead-slider", "value"),
    State("is-playing", "data"),
    prevent_initial_call=True,
)
def update_playhead(n_intervals, slider_value, is_playing):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if trigger_id == "interval-component" and is_playing:
        # Find the current index based on the slider value
        current_idx = dff["timestamp"].sub(slider_value).abs().idxmin()
        next_idx = (
            current_idx + 1 if current_idx + 1 < len(dff) else 0
        )  # Loop back to start
        new_time = dff["timestamp"].iloc[next_idx]
        return new_time, new_time
    elif trigger_id == "playhead-slider":
        return slider_value, slider_value
    else:
        raise dash.exceptions.PreventUpdate


# Callback to update the graph with the playhead line
@app.callback(
    Output("graph-content", "figure"),
    Input("playhead-time", "data"),
    State("graph-content", "figure"),
)
def update_graph(playhead_timestamp, existing_fig):
    playhead_time = pd.to_datetime(playhead_timestamp, unit="s")
    existing_fig["layout"]["shapes"] = []
    existing_fig["layout"]["shapes"].append(
        dict(
            type="line",
            x0=playhead_time,
            x1=playhead_time,
            y0=0,
            y1=1,
            xref="x",
            yref="paper",
            line=dict(width=2, dash="solid"),
        )
    )
    existing_fig["layout"]["uirevision"] = "constant"
    return existing_fig

# Fullscreen toggle functionality
app.clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks && n_clicks > 0) {
            if (!document.fullscreenElement) {
                // Enter fullscreen
                document.documentElement.requestFullscreen().catch(err => {
                    console.log(`Error attempting to enable fullscreen: ${err.message}`);
                });
            } else {
                // Exit fullscreen
                document.exitFullscreen().catch(err => {
                    console.log(`Error attempting to exit fullscreen: ${err.message}`);
                });
            }
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("fullscreen-button", "id", allow_duplicate=True),
    [Input("fullscreen-button", "n_clicks")],
    prevent_initial_call=True,
)

# Update button class and content based on fullscreen state
app.clientside_callback(
    """
    function(n_clicks) {
        // Set up fullscreen change listener if not already set
        if (!window.fullscreenListenerSet) {
            document.addEventListener('fullscreenchange', function() {
                const button = document.getElementById('fullscreen-button');
                const tooltip = document.getElementById('fullscreen-tooltip');
                
                if (document.fullscreenElement) {
                    // In fullscreen mode - use minimize class
                    button.className = 'btn btn-icon-only btn-icon-minimize';
                    // button.innerHTML = 'Minimize';
                    if (tooltip && tooltip._tippy) {
                        tooltip._tippy.setContent('Enter Fullscreen');
                    }
                } else {
                    // Not in fullscreen mode - use fullscreen class
                    button.className = 'btn btn-icon-only btn-icon-fullscreen';
                    // button.innerHTML = 'Expand';
                    if (tooltip && tooltip._tippy) {
                        tooltip._tippy.setContent('Exit Fullscreen');
                    }
                }
            });
            window.fullscreenListenerSet = true;
        }
        
        // Return appropriate class name based on current state
        return document.fullscreenElement ? 
            'btn btn-icon-only btn-icon-minimize' : 
            'btn btn-icon-only btn-icon-fullscreen';
    }
    """,
    Output("fullscreen-button", "className"),
    [Input("fullscreen-button", "n_clicks")],
    prevent_initial_call=False,
)

# Update button text
app.clientside_callback(
    """
    function(n_clicks) {
        //return document.fullscreenElement ? "Minimize" : "Expand";
    }
    """,
    Output("fullscreen-button", "children"),
    [Input("fullscreen-button", "n_clicks")],
    prevent_initial_call=False,
)

# Update tooltip content based on fullscreen state
app.clientside_callback(
    """
    function(n_clicks) {
        return document.fullscreenElement ? "Enter Fullscreen" : "Exit Fullscreen";
    }
    """,
    Output("fullscreen-tooltip", "children"),
    [Input("fullscreen-button", "n_clicks")],
    prevent_initial_call=False,
)


if __name__ == "__main__":
    app.run(debug=True)
