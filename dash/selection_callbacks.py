"""
Selection callbacks for dataset, deployment, and date range selection.
"""

import dash
from dash import Output, Input, State, html, callback_context, no_update
import pandas as pd
import time
from logging_config import get_logger
from layout import create_dataset_accordion_item

logger = get_logger(__name__)


def register_selection_callbacks(app, duck_pond, immich_service):
    """Register all selection-related callbacks with the given app instance."""
    logger.debug("Registering selection callbacks...")

    @app.callback(
        Output("all-datasets-deployments", "data"),
        Input("url", "pathname"),
    )
    def load_datasets_on_page_load(pathname):
        """Load all datasets and their deployments when the page loads."""
        logger.info("Loading datasets and deployments from data lake on page load...")
        try:
            all_datasets_and_deployments = duck_pond.get_all_datasets_and_deployments()
            logger.debug(
                f"Found {len(all_datasets_and_deployments)} datasets with deployments"
            )

            return all_datasets_and_deployments

        except Exception as e:
            logger.error(f"Error loading datasets and deployments: {e}", exc_info=True)
            return {}

    @app.callback(
        Output("dataset-accordion", "children"),
        Input("all-datasets-deployments", "data"),
    )
    def populate_dataset_accordion(datasets_with_deployments):
        """Populate the accordion with datasets and their deployments."""
        if not datasets_with_deployments:
            return [
                html.Div(
                    "No datasets found in data lake",
                    className="alert alert-warning small m-3",
                )
            ]

        logger.debug(
            f"Populating accordion with {len(datasets_with_deployments)} datasets"
        )

        accordion_items = []
        for idx, (dataset_name, deployments) in enumerate(
            datasets_with_deployments.items()
        ):
            if deployments:  # Only create accordion items for datasets with deployments
                accordion_item = create_dataset_accordion_item(
                    dataset_name=dataset_name,
                    deployments=deployments,
                    item_id=f"dataset-accordion-{idx}",
                )
                accordion_items.append(accordion_item)

        if not accordion_items:
            return [
                html.Div(
                    "No deployments found in any dataset",
                    className="alert alert-warning small m-3",
                )
            ]

        logger.debug(f"Created {len(accordion_items)} accordion items")
        return accordion_items

    @app.callback(
        Output("selected-deployment", "data"),
        Output("selected-dataset", "data"),
        Output("graph-content", "figure"),
        Output("is-loading-data", "data"),
        Input(
            {
                "type": "deployment-button",
                "dataset": dash.dependencies.ALL,
                "index": dash.dependencies.ALL,
            },
            "n_clicks",
        ),
        State("all-datasets-deployments", "data"),
        prevent_initial_call=True,
    )
    def select_deployment_and_load_visualization(
        n_clicks_list, datasets_with_deployments
    ):
        """Handle deployment selection and automatically load visualization."""
        if not callback_context.triggered or not datasets_with_deployments:
            return no_update, no_update, no_update, no_update

        if not n_clicks_list or not any(n_clicks_list):
            return no_update, no_update, no_update, no_update

        # Find which button was clicked
        triggered_id = callback_context.triggered[0]["prop_id"]

        if "deployment-button" not in triggered_id:
            return no_update, no_update, no_update, no_update

        # Extract dataset and index from triggered_id
        import json

        try:
            button_id = json.loads(triggered_id.split(".")[0])
            dataset = button_id["dataset"]
            idx = button_id["index"]

            # Get deployments for the selected dataset
            deployments_data = datasets_with_deployments.get(dataset, [])
            if not deployments_data or idx >= len(deployments_data):
                logger.error(f"Invalid deployment index {idx} for dataset {dataset}")
                return no_update, no_update, no_update, no_update

            selected_deployment = deployments_data[idx]
            logger.info(
                f"Selected deployment: {selected_deployment['animal']} ({selected_deployment['deployment']}) from dataset {dataset}"
            )

            # Now load the visualization for this deployment
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots

            deployment_id = selected_deployment["deployment"]
            animal_id = selected_deployment["animal"]

            # Use deployment's min and max dates directly
            min_dt = pd.to_datetime(selected_deployment["min_date"])
            max_dt = pd.to_datetime(selected_deployment["max_date"])
            date_range = {
                "start": min_dt.isoformat(),
                "end": max_dt.isoformat(),
            }

            logger.info(f"Loading visualization for deployment: {deployment_id}")
            logger.debug(f"Date range: {date_range['start']} to {date_range['end']}")

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

            logger.debug(f"Found {len(available_labels)} total labels")

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

            logger.debug(
                f"Selected {len(labels_to_load)} priority labels: {labels_to_load}"
            )

            # Adaptive frequency adjustment based on data volume
            MAX_TARGET_ROWS = 100_000  # Configurable target
            time_span_seconds = (
                pd.to_datetime(date_range["end"]) - pd.to_datetime(date_range["start"])
            ).total_seconds()

            # Validate inputs before calculation
            if time_span_seconds <= 0:
                time_span_seconds = 1  # Prevent division by zero

            # Step 1: Quick metadata-based estimate
            sample_count = selected_deployment.get("sample_count", 0)
            rough_estimate = sample_count * len(labels_to_load)

            # Step 2: Get precise count if rough estimate is high
            if rough_estimate > MAX_TARGET_ROWS * 5:  # 5x threshold for detailed check
                logger.debug(
                    f"High data volume detected (rough: {rough_estimate:,}), getting precise estimate..."
                )
                t0 = time.time()
                estimated_rows = duck_pond.estimate_data_size(
                    dataset=dataset,
                    labels=labels_to_load,
                    deployment_ids=deployment_id,
                    animal_ids=animal_id,
                    date_range=(date_range["start"], date_range["end"]),
                )
                t1 = time.time()
                logger.debug(f"Time taken: {t1 - t0:.2f} seconds")
                logger.debug(f"Precise estimate: {estimated_rows:,} rows")
            else:
                estimated_rows = rough_estimate
                logger.debug(f"Estimated rows (from metadata): {estimated_rows:,}")

            # Step 3: Calculate adjusted frequency if needed
            if estimated_rows == 0:
                # No data available, skip adjustment
                adjusted_frequency = 0.1
            elif estimated_rows > MAX_TARGET_ROWS:
                # Calculate native sample rate
                native_sample_rate = (
                    estimated_rows / (len(labels_to_load) * time_span_seconds)
                    if time_span_seconds > 0
                    else 1.0
                )

                # Calculate target frequency to hit row limit
                adjusted_frequency = (
                    MAX_TARGET_ROWS / (len(labels_to_load) * time_span_seconds)
                    if time_span_seconds > 0
                    else 0.1
                )

                # No minimum limit as per requirements
                downsample_factor = (
                    native_sample_rate / adjusted_frequency
                    if adjusted_frequency > 0
                    else 1.0
                )

                logger.info(
                    f"Downsampling: {native_sample_rate:.2f} Hz → {adjusted_frequency:.4f} Hz ({downsample_factor:.1f}x reduction)"
                )
            else:
                adjusted_frequency = 0.1  # Use default frequency
                logger.debug(
                    f"Data volume within limits, using default frequency: {adjusted_frequency} Hz"
                )

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
                return selected_deployment, dataset, fig, False

            # Load data at adjusted frequency
            logger.debug("Loading data...")
            t0 = time.time()
            dff = duck_pond.get_data(
                dataset=dataset,
                deployment_ids=deployment_id,
                animal_ids=animal_id,
                date_range=(date_range["start"], date_range["end"]),
                frequency=adjusted_frequency,
                labels=labels_to_load,
                add_timestamp_column=True,
            )
            t1 = time.time()
            logger.debug(f"Time taken: {t1 - t0:.2f} seconds")
            logger.debug(
                f"Data loaded - Shape: {dff.shape if not dff.empty else 'EMPTY'}"
            )

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
                return selected_deployment, dataset, fig, False

            logger.info(f"Loaded {len(dff)} rows with {len(dff.columns)} columns")

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
                return selected_deployment, dataset, fig, False

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
            for idx_col, col in enumerate(data_columns[:num_plots], start=1):
                fig.add_trace(
                    go.Scattergl(
                        x=dff["datetime"],
                        y=dff[col],
                        mode="lines",
                        name=col,
                        showlegend=False,
                    ),
                    row=idx_col,
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

            logger.info(f"Created figure with {num_plots} subplots")

            return selected_deployment, dataset, fig, False

        except Exception as e:
            logger.error(f"Error loading visualization: {e}", exc_info=True)

            # Return error figure
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
            return no_update, no_update, fig, False

    @app.callback(
        Output("loading-overlay", "style"),
        Output("is-loading-data", "data", allow_duplicate=True),
        Input(
            {
                "type": "deployment-button",
                "dataset": dash.dependencies.ALL,
                "index": dash.dependencies.ALL,
            },
            "n_clicks",
        ),
        prevent_initial_call=True,
    )
    def show_loading_overlay(n_clicks_list):
        """Show loading overlay when deployment button is clicked."""
        if not callback_context.triggered:
            return no_update, no_update

        if not n_clicks_list or not any(n_clicks_list):
            return no_update, no_update

        # Find which button was clicked
        triggered_id = callback_context.triggered[0]["prop_id"]

        if "deployment-button" not in triggered_id:
            return no_update, no_update

        # Show the overlay
        style = {
            "position": "fixed",
            "top": "0",
            "left": "0",
            "width": "100%",
            "height": "100%",
            "backgroundColor": "rgba(0, 0, 0, 0.7)",
            "zIndex": "10000",
            "display": "block",
        }
        return style, True

    @app.callback(
        Output("loading-overlay", "style", allow_duplicate=True),
        Input("is-loading-data", "data"),
        prevent_initial_call=True,
    )
    def hide_loading_overlay(is_loading):
        """Hide loading overlay when data loading is complete."""
        if is_loading:
            return no_update

        # Hide the overlay
        style = {
            "position": "fixed",
            "top": "0",
            "left": "0",
            "width": "100%",
            "height": "100%",
            "backgroundColor": "rgba(0, 0, 0, 0.7)",
            "zIndex": "10000",
            "display": "none",
        }
        return style
