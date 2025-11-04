"""
Selection callbacks for dataset, deployment, and date range selection.
"""
import dash
from dash import Output, Input, State, html, callback_context, no_update
import pandas as pd
import logging


def register_selection_callbacks(app, duck_pond, immich_service):
    """Register all selection-related callbacks with the given app instance."""
    print("🔧 Registering selection callbacks...")

    @app.callback(
        Output("dataset-dropdown", "options"),
        Output("dataset-dropdown", "value"),
        Output("available-datasets", "data"),
        Output("dataset-loading-output", "children"),
        Input("url", "pathname"),
    )
    def load_datasets_on_page_load(pathname):
        """Load datasets when the page loads."""
        print("🔍 Loading datasets from data lake on page load...")
        try:
            available_datasets = duck_pond.get_all_datasets()
            print(f"📊 Found {len(available_datasets)} datasets: {available_datasets}")

            if not available_datasets:
                return (
                    [],
                    None,
                    [],
                    html.Div(
                        "No datasets found in data lake",
                        className="alert alert-warning small",
                    ),
                )

            # Create dropdown options
            dataset_options = [{"label": ds, "value": ds} for ds in available_datasets]
            default_dataset = available_datasets[0]

            success_msg = html.Div(
                [
                    html.I(className="fas fa-check-circle me-2"),
                    f"Loaded {len(available_datasets)} datasets",
                ],
                className="alert alert-success small",
            )

            return dataset_options, default_dataset, available_datasets, success_msg

        except Exception as e:
            logging.error(f"Error loading datasets: {e}", exc_info=True)
            error_msg = html.Div(
                [
                    html.Strong("Error: "),
                    str(e),
                    html.Br(),
                    html.Small("Check console for details", className="text-muted"),
                ],
                className="alert alert-danger small",
            )
            return [], None, [], error_msg

    @app.callback(
        Output("selected-dataset", "data"),
        Input("dataset-dropdown", "value"),
    )
    def update_selected_dataset(dataset):
        """Update the selected dataset store."""
        print(f"🔄 Dataset selection changed to: {dataset}")
        return dataset

    @app.callback(
        Output("available-deployments", "data"),
        Output("deployment-list-container", "children"),
        Output("deployment-loading-output", "children"),
        Input("dataset-dropdown", "value"),
        Input("trigger-initial-load", "data"),
    )
    def load_deployments_for_dataset(dataset, trigger):
        """Load deployments when a dataset is selected."""
        print(f"📊 Loading deployments for dataset: {dataset} (trigger: {trigger})")
        if not dataset:
            return (
                [],
                html.P("Select a dataset first", className="text-muted small"),
                None,
            )

        try:
            # Get all datasets and deployments, then extract deployments for selected dataset
            all_deployments = duck_pond.get_all_datasets_and_deployments()
            deployments_data = all_deployments.get(dataset, [])

            if len(deployments_data) == 0:
                return (
                    [],
                    html.P(
                        "No deployments found for this dataset",
                        className="text-muted small",
                    ),
                    None,
                )

            # Create deployment buttons
            deployment_buttons = []
            for idx, dep in enumerate(deployments_data):
                animal_id = dep["animal"]
                min_date = pd.to_datetime(dep["min_date"]).strftime("%Y-%m-%d")
                sample_count = dep["sample_count"]

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
                    id={"type": "deployment-button", "index": idx},
                    className="list-group-item list-group-item-action",
                    n_clicks=0,
                )
                deployment_buttons.append(button)

            deployment_list = html.Div(
                deployment_buttons,
                className="list-group",
            )

            return deployments_data, deployment_list, None

        except Exception as e:
            logging.error(f"Error loading deployments: {e}")
            error_msg = html.Div(
                f"Error loading deployments: {str(e)}",
                className="alert alert-danger small",
            )
            return [], error_msg, None

    @app.callback(
        Output("selected-deployment", "data"),
        Input(
            {"type": "deployment-button", "index": dash.dependencies.ALL}, "n_clicks"
        ),
        State("available-deployments", "data"),
    )
    def select_deployment(n_clicks_list, deployments_data):
        """Handle deployment selection."""
        if not callback_context.triggered or not deployments_data:
            return no_update

        if not n_clicks_list or not any(n_clicks_list):
            return no_update

        # Find which button was clicked
        triggered_id = callback_context.triggered[0]["prop_id"]

        if "deployment-button" not in triggered_id:
            return no_update

        # Extract index from triggered_id
        import json

        try:
            button_id = json.loads(triggered_id.split(".")[0])
            idx = button_id["index"]
            selected = deployments_data[idx]
            print(
                f"✅ Selected deployment: {selected['animal']} ({selected['deployment']})"
            )
            return selected
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logging.error(f"Error parsing deployment button click: {e}")
            return no_update

    @app.callback(
        Output("deployment-info-container", "style"),
        Output("deployment-info-container", "children"),
        Input("selected-deployment", "data"),
    )
    def update_deployment_info(deployment_data):
        """Display selected deployment information."""
        if not deployment_data:
            # Hide deployment info
            return {"display": "none"}, []

        # Parse dates from deployment data
        min_dt = pd.to_datetime(deployment_data["min_date"])
        max_dt = pd.to_datetime(deployment_data["max_date"])

        # Format deployment info
        info_content = html.Div(
            [
                html.Label("Selected Deployment", className="form-label fw-bold mt-3"),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Strong("Animal: "),
                                html.Span(deployment_data["animal"]),
                            ],
                            className="mb-1",
                        ),
                        html.Div(
                            [
                                html.Strong("Deployment ID: "),
                                html.Span(deployment_data["deployment"]),
                            ],
                            className="mb-1",
                        ),
                        html.Div(
                            [
                                html.Strong("Date Range: "),
                            ],
                            className="mb-1",
                        ),
                        html.Div(
                            [
                                html.Small(f"{min_dt.strftime('%Y-%m-%d %H:%M:%S')}"),
                                html.Br(),
                                html.Small(
                                    f"to {max_dt.strftime('%Y-%m-%d %H:%M:%S')}"
                                ),
                            ],
                            className="text-muted ps-3 mb-1",
                        ),
                        html.Div(
                            [
                                html.Strong("Samples: "),
                                html.Span(f"{deployment_data['sample_count']:,}"),
                            ],
                            className="mb-1",
                        ),
                    ],
                    className="small border rounded p-2 bg-light",
                ),
            ]
        )

        return {"display": "block"}, info_content

    @app.callback(
        Output("load-visualization-button", "disabled"),
        Output("selected-date-range", "data"),
        Input("selected-deployment", "data"),
    )
    def update_load_button(deployment_data):
        """Enable/disable load button based on deployment selection."""
        if not deployment_data:
            return True, None  # Button disabled

        try:
            # Use deployment's min and max dates directly
            min_dt = pd.to_datetime(deployment_data["min_date"])
            max_dt = pd.to_datetime(deployment_data["max_date"])

            date_range = {
                "start": min_dt.isoformat(),
                "end": max_dt.isoformat(),
            }

            return False, date_range  # Button enabled
        except Exception as e:
            logging.error(f"Error updating load button: {e}")
            return True, None  # Button disabled on error

    @app.callback(
        Output("graph-content", "figure"),
        Output("visualization-loading-output", "children"),
        Input("load-visualization-button", "n_clicks"),
        State("selected-dataset", "data"),
        State("selected-deployment", "data"),
        State("selected-date-range", "data"),
        prevent_initial_call=True,
    )
    def load_visualization(n_clicks, dataset, deployment_data, date_range):
        """Load and display visualization for selected deployment."""
        print(f"🔍 Callback fired - n_clicks: {n_clicks}")
        print(f"🔍 Dataset: {dataset}")
        print(f"🔍 Deployment: {deployment_data}")
        print(f"🔍 Date range: {date_range}")

        if not n_clicks or not dataset or not deployment_data or not date_range:
            print("❌ Missing required data - returning no_update")
            error_msg = html.Div(
                "Missing required data. Please select a dataset and deployment.",
                className="alert alert-danger small mt-2",
            )
            return no_update, error_msg

        print(
            f"🚀 Loading visualization for deployment: {deployment_data['deployment']}"
        )
        print(f"📅 Date range: {date_range['start']} to {date_range['end']}")

        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots

            # Get deployment info
            deployment_id = deployment_data["deployment"]
            animal_id = deployment_data["animal"]

            # Discover available labels/signals for this deployment
            view_name = duck_pond.get_view_name(dataset, "data")
            labels_query = f"""
                SELECT DISTINCT label
                FROM {view_name}
                WHERE deployment = '{deployment_id}'
                AND animal = '{animal_id}'
                AND label IS NOT NULL
                ORDER BY label
            """
            labels_df = duck_pond.conn.sql(labels_query).df()
            available_labels = labels_df["label"].tolist()

            print(f"📊 Found {len(available_labels)} total labels")

            # Define priority signal patterns (ordered by importance)
            priority_patterns = [
                "depth",
                "pressure",
                "ecg",
                "odba",
                "hr",
                "pitch",
                "roll",
                "heading",
                "accelerometer",
                "gyroscope",
                "magnetometer",
                "temperature",
                "light",
            ]

            # Filter and prioritize labels based on patterns
            prioritized_labels = []
            for pattern in priority_patterns:
                matching = [
                    label
                    for label in available_labels
                    if pattern.lower() in label.lower()
                    and label not in prioritized_labels
                ]
                prioritized_labels.extend(matching)

            # Use prioritized labels, fallback to first 10 if no matches
            labels_to_load = (
                prioritized_labels[:15] if prioritized_labels else available_labels[:10]
            )

            print(f"📊 Selected {len(labels_to_load)} priority labels: {labels_to_load}")

            if not labels_to_load:
                # No data found - return empty figure with message
                fig = go.Figure()
                fig.update_layout(
                    annotations=[
                        dict(
                            text=f"No data found for deployment {deployment_id}",
                            xref="paper",
                            yref="paper",
                            x=0.5,
                            y=0.5,
                            showarrow=False,
                            font=dict(size=16, color="red"),
                        )
                    ],
                    height=600,
                )
                error_msg = html.Div(
                    f"No labels/signals found for deployment {deployment_id}",
                    className="alert alert-warning small mt-2",
                )
                return fig, error_msg

            # Load data at a reasonable frequency (e.g., 1 Hz)
            print("📥 Loading data...")
            print(f"   Dataset: {dataset}")
            print(f"   Deployment ID: {deployment_id}")
            print(f"   Animal ID: {animal_id}")

            dff = duck_pond.get_data(
                dataset=dataset,
                deployment_ids=deployment_id,
                animal_ids=animal_id,
                date_range=(date_range["start"], date_range["end"]),
                frequency=0.1,  # 1 Hz sampling
                labels=labels_to_load,
                add_timestamp_column=True,
            )

            print(f"📦 Data loaded - Shape: {dff.shape if not dff.empty else 'EMPTY'}")
            print(f"📦 Columns: {dff.columns.tolist() if not dff.empty else 'N/A'}")

            if dff.empty:
                fig = go.Figure()
                fig.update_layout(
                    annotations=[
                        dict(
                            text="No data in selected range",
                            xref="paper",
                            yref="paper",
                            x=0.5,
                            y=0.5,
                            showarrow=False,
                            font=dict(size=16, color="orange"),
                        )
                    ],
                    height=600,
                )
                error_msg = html.Div(
                    "No data returned for the selected date range",
                    className="alert alert-warning small mt-2",
                )
                return fig, error_msg

            print(f"✓ Loaded {len(dff)} rows with {len(dff.columns)} columns")

            # Create a simple multi-subplot figure
            # Skip 'datetime' and 'timestamp' columns
            data_columns = [
                col for col in dff.columns if col not in ["datetime", "timestamp"]
            ]

            if not data_columns:
                fig = go.Figure()
                fig.update_layout(
                    annotations=[
                        dict(
                            text="No signal data to display",
                            xref="paper",
                            yref="paper",
                            x=0.5,
                            y=0.5,
                            showarrow=False,
                            font=dict(size=16, color="orange"),
                        )
                    ],
                    height=600,
                )
                error_msg = html.Div(
                    "Data loaded but no signal columns found (only datetime/timestamp)",
                    className="alert alert-warning small mt-2",
                )
                return fig, error_msg

            # Create subplots for first 10 signals
            num_plots = min(10, len(data_columns))
            fig = make_subplots(
                rows=num_plots,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.02,
                subplot_titles=data_columns[:num_plots],
            )

            # Add traces for each signal
            for idx, col in enumerate(data_columns[:num_plots], start=1):
                fig.add_trace(
                    go.Scattergl(
                        x=dff["datetime"],
                        y=dff[col],
                        mode="lines",
                        name=col,
                        showlegend=False,
                    ),
                    row=idx,
                    col=1,
                )

            # Update layout
            fig.update_layout(
                height=600 + 80 * num_plots,
                showlegend=False,
                xaxis=dict(
                    rangeslider=dict(visible=True, thickness=0.05),
                    type="date",
                ),
            )

            # Update all x-axes to show date
            fig.update_xaxes(type="date")

            print(f"✓ Created figure with {num_plots} subplots")

            success_msg = html.Div(
                [
                    html.I(className="fas fa-check-circle me-2"),
                    f"Loaded {len(dff):,} samples with {len(data_columns)} signals",
                ],
                className="alert alert-success small mt-2",
            )
            return fig, success_msg

        except Exception as e:
            logging.error(f"Error loading visualization: {e}", exc_info=True)
            import traceback

            error_traceback = traceback.format_exc()
            print("❌ EXCEPTION OCCURRED:")
            print(error_traceback)

            # Return error figure AND error message in loading output
            fig = go.Figure()
            fig.update_layout(
                annotations=[
                    dict(
                        text=f"Error loading data: {str(e)}",
                        xref="paper",
                        yref="paper",
                        x=0.5,
                        y=0.5,
                        showarrow=False,
                        font=dict(size=14, color="red"),
                    )
                ],
                height=600,
            )

            error_msg = html.Div(
                [
                    html.Strong("Error: "),
                    str(e),
                    html.Br(),
                    html.Small("Check console for details", className="text-muted"),
                ],
                className="alert alert-danger small mt-2",
            )
            return fig, error_msg

    # SIMPLE TEST CALLBACK - Proves deployment selection works
    @app.callback(
        Output("deployment-loading-output", "children", allow_duplicate=True),
        Input(
            {"type": "deployment-button", "index": dash.dependencies.ALL}, "n_clicks"
        ),
        prevent_initial_call=True,
    )
    def test_deployment_click(n_clicks_list):
        """Test if deployment button click is detected."""
        print(f"🧪 TEST CALLBACK FIRED! n_clicks: {n_clicks_list}")
        print(f"🧪 Context: {callback_context.triggered}")
        if callback_context.triggered and any(n_clicks_list or []):
            return html.Div("✅ Button clicked!", className="alert alert-success small")
        return no_update
