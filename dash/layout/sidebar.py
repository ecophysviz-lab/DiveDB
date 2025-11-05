"""
Sidebar components for dataset selection and visualization controls.
"""
from dash import html
import dash_bootstrap_components as dbc
import three_js_orientation
import video_preview
from logging_config import get_logger

logger = get_logger("layout")


def create_dataset_accordion_item(dataset_name, deployments, item_id):
    """Create accordion item for a dataset with deployment buttons inside."""
    # Create deployment buttons for this dataset
    deployment_buttons = []
    for idx, dep in enumerate(deployments):
        button = html.Button(
            [
                html.Div(
                    [
                        html.Strong(f"{dep['animal']}"),
                        html.Br(),
                        html.Small(f"{dep['deployment_date']}", className="text-muted"),
                        html.Br(),
                        html.Small(
                            f"{dep['sample_count']:,} samples", className="text-muted"
                        ),
                    ]
                )
            ],
            id={"type": "deployment-button", "dataset": dataset_name, "index": idx},
            className="list-group-item list-group-item-action",
            n_clicks=0,
        )
        deployment_buttons.append(button)

    return dbc.AccordionItem(
        [html.Div(deployment_buttons, className="list-group")],
        title=[
            html.Div(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                html.Img(src="/assets/images/seal.svg"),
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
                                        [html.Strong([dataset_name])],
                                        className="strong m-0",
                                    ),
                                ]
                            ),
                        ],
                        align="center",
                        className="gx-3",
                    ),
                ],
                className="w-100",
            )
        ],
        item_id=item_id,
    )


def create_left_sidebar(available_datasets=None, initial_deployments=None):
    """Create the left sidebar with accordion-based dataset/deployment selection."""
    logger.debug("Creating sidebar with accordion structure")

    return html.Div(
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
                                            n_clicks=0,
                                        ),
                                        dbc.Tooltip(
                                            "Toggle Left Sidebar",
                                            target="left-toggle",
                                            placement="right",
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
                        className="sidebar_header",
                    ),
                    html.Div(
                        [
                            dbc.Accordion(
                                id="dataset-accordion",
                                children=[],  # Will be populated by callback
                                start_collapsed=True,
                                always_open=False,
                                flush=True,
                            ),
                        ],
                        className="sidebar_content",
                    ),
                ],
                className="sidebar",
            )
        ],
        className="left_sidebar",
    )


def create_right_sidebar(
    data_json, video_min_timestamp, video_options=None, restricted_time_range=None
):
    """Create the right sidebar with 3D model and video."""
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
                                            n_clicks=0,
                                        ),
                                        dbc.Tooltip(
                                            "Toggle Right Sidebar",
                                            target="right-toggle",
                                            placement="left",
                                        ),
                                    ],
                                    width={"size": "auto"},
                                ),
                            ],
                            align="center",
                            className="gx-2",
                        ),
                        className="sidebar_header xd-none",
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
                                                style={
                                                    "width": "100%",
                                                    "height": "100%",
                                                },
                                            ),
                                            html.Button(
                                                [
                                                    "Expand",
                                                ],
                                                id="right-top-toggle",
                                                className="btn btn-icon toggle_right_top",
                                                n_clicks=0,
                                            ),
                                            dbc.Tooltip(
                                                "Expand 3D Model",
                                                target="right-top-toggle",
                                                placement="left",
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
                                                videoSrc="",  # Empty string as placeholder until proper rebuild
                                                videoMetadata=None,  # Will be populated when video is selected
                                                datasetStartTime=video_min_timestamp,
                                                playheadTime=video_min_timestamp,
                                                isPlaying=False,
                                                showControls=False,
                                            ),
                                            html.Button(
                                                [
                                                    "Expand",
                                                ],
                                                id="right-bottom-toggle",
                                                className="btn btn-icon toggle_right_bottom",
                                                n_clicks=0,
                                            ),
                                            dbc.Tooltip(
                                                "Expand Video",
                                                target="right-bottom-toggle",
                                                placement="left",
                                            ),
                                        ],
                                        className="video-container",
                                    )
                                ],
                                className="right_sidebar_bottom",
                            ),
                        ],
                        className="sidebar_content",
                    ),
                ],
                className="sidebar",
            ),
        ],
        className="right_sidebar",
    )
