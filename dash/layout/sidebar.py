"""
Sidebar components for dataset selection and visualization controls.
"""
from dash import dcc, html
import dash_bootstrap_components as dbc
import pandas as pd
import three_js_orientation
import video_preview


def create_left_sidebar(available_datasets=None, initial_deployments=None):
    """Create the left sidebar with dynamic dataset/deployment selection."""
    # Prepare dataset options
    dataset_options = []
    default_dataset = None
    if available_datasets:
        dataset_options = [{"label": ds, "value": ds} for ds in available_datasets]
        default_dataset = available_datasets[0] if available_datasets else None

    # Prepare initial deployment list
    initial_deployment_ui = html.P(
        "Select a dataset first", className="text-muted small"
    )
    if initial_deployments:
        deployment_buttons = []
        for idx, dep in enumerate(initial_deployments):
            animal_id = dep["animal"]
            min_date = pd.to_datetime(dep["min_date"]).strftime("%Y-%m-%d")
            sample_count = dep["sample_count"]

            button_id = {"type": "deployment-button", "index": idx}
            print(f"🔘 Creating deployment button {idx}: {button_id}")

            button = html.Button(
                [
                    html.Div(
                        [
                            html.Strong(f"{animal_id}"),
                            html.Br(),
                            html.Small(f"{min_date}", className="text-muted"),
                            html.Br(),
                            html.Small(
                                f"{sample_count:,} samples", className="text-muted"
                            ),
                        ]
                    ),
                ],
                id=button_id,
                className="list-group-item list-group-item-action",
                n_clicks=0,
            )
            deployment_buttons.append(button)

        initial_deployment_ui = html.Div(
            deployment_buttons,
            className="list-group",
        )

    print(
        f"🏗️ Creating sidebar with {len(dataset_options)} dataset options, {len(initial_deployments) if initial_deployments else 0} deployments"
    )

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
                                                        "Data Selection",
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
                            # Dataset Selection Section
                            html.Div(
                                [
                                    html.Label(
                                        "Dataset",
                                        className="form-label fw-bold mt-3",
                                    ),
                                    dcc.Dropdown(
                                        id="dataset-dropdown",
                                        options=dataset_options,
                                        value=default_dataset,
                                        placeholder="Select a dataset...",
                                        className="mb-3",
                                        clearable=False,
                                    ),
                                    dcc.Loading(
                                        id="dataset-loading",
                                        type="circle",
                                        children=html.Div(id="dataset-loading-output"),
                                    ),
                                ],
                                className="px-3",
                            ),
                            # Deployment Selection Section
                            html.Div(
                                [
                                    html.Label(
                                        "Deployment",
                                        className="form-label fw-bold mt-3",
                                    ),
                                    html.Div(
                                        id="deployment-list-container",
                                        children=[initial_deployment_ui],
                                        className="mb-3",
                                    ),
                                    dcc.Loading(
                                        id="deployment-loading",
                                        type="circle",
                                        children=html.Div(
                                            id="deployment-loading-output"
                                        ),
                                    ),
                                ],
                                className="px-3",
                            ),
                            # Deployment info section (shows selected deployment details)
                            html.Div(
                                id="deployment-info-container",
                                children=[],
                                className="px-3 mb-3",
                                style={
                                    "display": "none"
                                },  # Hidden until deployment selected
                            ),
                            # Load Button
                            html.Div(
                                [
                                    dbc.Button(
                                        "Load Visualization",
                                        id="load-visualization-button",
                                        color="primary",
                                        size="lg",
                                        disabled=True,
                                        className="w-100",
                                    ),
                                ],
                                className="px-3 py-3",
                            ),
                            # Loading overlay for data fetch
                            dcc.Loading(
                                id="visualization-loading",
                                type="default",
                                fullscreen=True,
                                children=html.Div(id="visualization-loading-output"),
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
