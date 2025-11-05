"""
Selection callbacks for dataset, deployment, and date range selection.
"""

import dash
from dash import Output, Input, State, html, callback_context, no_update
import pandas as pd
import time
from logging_config import get_logger
from layout import (
    create_dataset_accordion_item,
    create_timeline_section,
    create_deployment_info_display,
)
from graph_utils import plot_tag_data_interactive5

logger = get_logger(__name__)


class DataPkl:
    """Simple class to support both attribute and dict access for data_pkl structure."""

    def __init__(self, sensor_data, sensor_info, derived_data=None, derived_info=None):
        self.sensor_data = sensor_data
        self.sensor_info = sensor_info
        self.derived_data = derived_data or {}
        self.derived_info = derived_info or {}

    def __getitem__(self, key):
        """Support dict-style access."""
        if key == "sensor_data":
            return self.sensor_data
        elif key == "sensor_info":
            return self.sensor_info
        elif key == "derived_data":
            return self.derived_data
        elif key == "derived_info":
            return self.derived_info
        else:
            raise KeyError(key)

    def __contains__(self, key):
        """Support 'in' operator."""
        return key in ["sensor_data", "sensor_info", "derived_data", "derived_info"]


def create_data_pkl_from_dataframe(dff):
    """
    Transform a pivoted DataFrame into the data_pkl structure expected by plot_tag_data_interactive5.

    Matches the previous structure where:
    - pitch, roll, heading are grouped as "prh" in derived_data
    - depth is in derived_data
    - Other signals (light, temperature, etc.) are in sensor_data

    Args:
        dff: DataFrame with 'datetime' column and signal columns

    Returns:
        DataPkl: data_pkl structure with sensor_data, sensor_info, derived_data, and derived_info
    """
    # Skip 'datetime' and 'timestamp' columns
    data_columns = [col for col in dff.columns if col not in ["datetime", "timestamp"]]

    if not data_columns:
        return DataPkl(sensor_data={}, sensor_info={}, derived_data={}, derived_info={})

    # Define sensor signals (go in sensor_data)
    # TODO: Pull from Notion
    sensor_patterns = {
        "light": {"pattern": "light", "unit": "lux", "display_name": "Light"},
        "temperature": {
            "pattern": "temperature",
            "unit": "°C",
            "display_name": "Temperature (imu)",
        },
        "ecg": {"pattern": "ecg", "unit": "mV", "display_name": "ECG"},
        "hr": {"pattern": "hr", "unit": "bpm", "display_name": "Heart Rate"},
        "accelerometer": {
            "pattern": "accelerometer",
            "unit": "g",
            "display_name": "Accelerometer",
        },
        "gyroscope": {
            "pattern": "gyroscope",
            "unit": "deg/s",
            "display_name": "Gyroscope",
        },
        "magnetometer": {
            "pattern": "magnetometer",
            "unit": "μT",
            "display_name": "Magnetometer",
        },
        "odba": {"pattern": "odba", "unit": "g", "display_name": "ODBA"},
    }

    # Define derived signals (go in derived_data)
    # Note: depth and prh (pitch/roll/heading) are derived
    derived_patterns = {
        "depth": {"pattern": "depth", "unit": "m", "display_name": "Corrected Depth"},
        "pressure": {"pattern": "pressure", "unit": "m", "display_name": "Pressure"},
    }

    sensor_data = {}
    sensor_info = {}
    derived_data = {}
    derived_info = {}

    # Track which columns have been assigned
    assigned_columns = set()

    # First pass: Handle prh (pitch, roll, heading) - these go together in derived_data
    prh_cols = []
    for col in data_columns:
        if col.lower() in ["pitch", "roll", "heading"] and col not in assigned_columns:
            prh_cols.append(col)
            assigned_columns.add(col)

    if prh_cols:
        # Create prh DataFrame
        prh_df = dff[["datetime"] + prh_cols].copy()
        derived_data["prh"] = prh_df

        # Create metadata for prh channels
        prh_metadata = {}
        display_names = {
            "pitch": "Pitch",
            "roll": "Roll",
            "heading": "Heading",
        }
        for col in prh_cols:
            col_lower = col.lower()
            display_name = display_names.get(col_lower, col.replace("_", " ").title())
            prh_metadata[col] = {
                "original_name": display_name,
                "unit": "°",
            }

        derived_info["prh"] = {
            "channels": prh_cols,
            "metadata": prh_metadata,
        }

    # Second pass: Handle depth/pressure (go in derived_data)
    for signal_name, signal_config in derived_patterns.items():
        pattern = signal_config["pattern"]
        matching_cols = [
            col
            for col in data_columns
            if pattern.lower() in col.lower() and col not in assigned_columns
        ]

        if matching_cols:
            # Create DataFrame for this signal type
            signal_df = dff[["datetime"] + matching_cols].copy()
            derived_data[signal_name] = signal_df

            # Create metadata for channels
            channel_metadata = {}
            for col in matching_cols:
                # For single-channel signals, use signal name as metadata key if channel doesn't match
                # For multi-channel signals, use channel name as metadata key
                if len(matching_cols) == 1 and col.lower() != signal_name.lower():
                    metadata_key = signal_name
                else:
                    metadata_key = col

                channel_metadata[metadata_key] = {
                    "original_name": signal_config["display_name"],
                    "unit": signal_config["unit"],
                }

            derived_info[signal_name] = {
                "channels": matching_cols,
                "metadata": channel_metadata,
            }

            assigned_columns.update(matching_cols)

    # Third pass: Handle sensor signals (go in sensor_data)
    for signal_name, signal_config in sensor_patterns.items():
        pattern = signal_config["pattern"]
        matching_cols = [
            col
            for col in data_columns
            if pattern.lower() in col.lower() and col not in assigned_columns
        ]

        if matching_cols:
            # Create DataFrame for this signal type
            signal_df = dff[["datetime"] + matching_cols].copy()
            sensor_data[signal_name] = signal_df

            # Create metadata for channels
            # Note: metadata key should match the channel name (like in the example)
            channel_metadata = {}
            for col in matching_cols:
                # For single-channel signals, use signal name as metadata key if channel doesn't match
                # For multi-channel signals, use channel name as metadata key
                if len(matching_cols) == 1 and col.lower() != signal_name.lower():
                    metadata_key = signal_name
                else:
                    metadata_key = col

                channel_metadata[metadata_key] = {
                    "original_name": signal_config["display_name"],
                    "unit": signal_config["unit"],
                }

            sensor_info[signal_name] = {
                "channels": matching_cols,
                "metadata": channel_metadata,
            }

            assigned_columns.update(matching_cols)

    # Fourth pass: assign remaining columns to sensor_data by their base name
    remaining_cols = [col for col in data_columns if col not in assigned_columns]

    if remaining_cols:
        # Group remaining columns by their base name (before any suffix)
        other_groups = {}
        for col in remaining_cols:
            # Extract base name (everything before first underscore or use full name)
            base_name = col.split("_")[0] if "_" in col else col
            if base_name not in other_groups:
                other_groups[base_name] = []
            other_groups[base_name].append(col)

        # Create signal entries for each group in sensor_data
        for base_name, cols in other_groups.items():
            signal_df = dff[["datetime"] + cols].copy()
            sensor_data[base_name] = signal_df

            channel_metadata = {}
            for col in cols:
                display_name = col.replace("_", " ").title()
                channel_metadata[col] = {
                    "original_name": display_name,
                    "unit": "",  # No unit for unknown signals
                }

            sensor_info[base_name] = {
                "channels": cols,
                "metadata": channel_metadata,
            }

    return DataPkl(
        sensor_data=sensor_data,
        sensor_info=sensor_info,
        derived_data=derived_data,
        derived_info=derived_info,
    )


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
        Output("timeline-container", "children"),
        Output("deployment-info-display", "children"),
        Output("playback-timestamps", "data"),
        Output("current-video-options", "data"),
        Output("three-d-model", "data"),
        # Playback control buttons
        Output("previous-button", "disabled"),
        Output("rewind-button", "disabled"),
        Output("play-button", "disabled"),
        Output("forward-button", "disabled"),
        Output("next-button", "disabled"),
        Output("save-button", "disabled"),
        Output("playback-rate", "disabled"),
        Output("fullscreen-button", "disabled"),
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
            # Create minimal empty data JSON for 3D model
            empty_data_json = pd.DataFrame({"datetime": []}).to_json(orient="split")
            return (
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                [],
                empty_data_json,
                True,
                True,
                True,
                True,
                True,
                True,
                True,
                True,
            )

        if not n_clicks_list or not any(n_clicks_list):
            # Create minimal empty data JSON for 3D model
            empty_data_json = pd.DataFrame({"datetime": []}).to_json(orient="split")
            return (
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                [],
                empty_data_json,
                True,
                True,
                True,
                True,
                True,
                True,
                True,
                True,
            )

        # Find which button was clicked
        triggered_id = callback_context.triggered[0]["prop_id"]

        if "deployment-button" not in triggered_id:
            # Create minimal empty data JSON for 3D model
            empty_data_json = pd.DataFrame({"datetime": []}).to_json(orient="split")
            return (
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                [],
                empty_data_json,
                True,
                True,
                True,
                True,
                True,
                True,
                True,
                True,
            )

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
                # Create minimal empty data JSON for 3D model
                empty_data_json = pd.DataFrame({"datetime": []}).to_json(orient="split")
                return (
                    no_update,
                    no_update,
                    no_update,
                    no_update,
                    no_update,
                    no_update,
                    no_update,
                    [],
                    empty_data_json,
                    True,
                    True,
                    True,
                    True,
                    True,
                    True,
                    True,
                    True,
                )

            selected_deployment = deployments_data[idx]
            logger.info(
                f"Selected deployment: {selected_deployment['animal']} ({selected_deployment['deployment']}) from dataset {dataset}"
            )

            # Now load the visualization for this deployment
            import plotly.graph_objects as go

            deployment_id = selected_deployment["deployment"]
            animal_id = selected_deployment["animal"]

            # Get timezone offset from Notion via DuckDB
            timezone_offset = duck_pond.get_deployment_timezone_offset(deployment_id)
            logger.info(f"Deployment timezone offset: UTC{timezone_offset:+.1f}")

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
                "pitch",
                "roll",
                "temp_ext",
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
                empty_timeline = html.P(
                    "No data available for timeline",
                    className="text-muted text-center py-4",
                )
                empty_info = html.P("No deployment info", className="text-muted")
                # Create minimal empty data JSON for 3D model
                empty_data_json = pd.DataFrame({"datetime": []}).to_json(orient="split")
                return (
                    selected_deployment,
                    dataset,
                    fig,
                    False,
                    empty_timeline,
                    empty_info,
                    [],
                    [],
                    empty_data_json,
                    True,
                    True,
                    True,
                    True,
                    True,
                    True,
                    True,
                    True,
                )

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
                apply_timezone_offset=timezone_offset,
                pivoted=True,
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
                empty_timeline = html.P(
                    "No data available for timeline",
                    className="text-muted text-center py-4",
                )
                empty_info = html.P("No deployment info", className="text-muted")
                # Create minimal empty data JSON for 3D model
                empty_data_json = pd.DataFrame({"datetime": []}).to_json(orient="split")
                return (
                    selected_deployment,
                    dataset,
                    fig,
                    False,
                    empty_timeline,
                    empty_info,
                    [],
                    [],
                    empty_data_json,
                    True,
                    True,
                    True,
                    True,
                    True,
                    True,
                    True,
                    True,
                )

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
                empty_timeline = html.P(
                    "No data available for timeline",
                    className="text-muted text-center py-4",
                )
                empty_info = html.P("No deployment info", className="text-muted")
                # Prepare orientation data for 3D model (check if columns exist)
                # Important: Set datetime as index so React component can access it via dataframe.index
                if (
                    "pitch" in dff.columns
                    and "roll" in dff.columns
                    and "heading" in dff.columns
                ):
                    logger.debug(
                        f"3D model data prepared WITH orientation: {len(dff)} rows"
                    )
                    model_df = dff[["datetime", "pitch", "roll", "heading"]].set_index(
                        "datetime"
                    )
                    model_data_json = model_df.to_json(orient="split")
                else:
                    logger.debug(
                        f"3D model data prepared WITHOUT orientation: {len(dff)} rows"
                    )
                    model_df = dff[["datetime"]].set_index("datetime")
                    model_data_json = model_df.to_json(orient="split")
                return (
                    selected_deployment,
                    dataset,
                    fig,
                    False,
                    empty_timeline,
                    empty_info,
                    [],
                    [],
                    model_data_json,
                    True,
                    True,
                    True,
                    True,
                    True,
                    True,
                    True,
                    True,
                )

            # Create data_pkl structure from DataFrame
            logger.debug("Creating data_pkl structure from DataFrame...")
            data_pkl = create_data_pkl_from_dataframe(dff)

            # Determine zoom_range_selector_channel (use depth if available)
            zoom_range_selector_channel = None
            if (
                "depth" in data_pkl["sensor_data"]
                or "depth" in data_pkl["derived_data"]
            ):
                zoom_range_selector_channel = "depth"

            # Create figure using plot_tag_data_interactive5
            logger.debug("Creating figure with plot_tag_data_interactive5...")
            fig = plot_tag_data_interactive5(
                data_pkl=data_pkl,
                zoom_range_selector_channel=zoom_range_selector_channel,
            )

            logger.info(
                f"Created figure with {len(data_pkl['sensor_data'])} sensor groups and {len(data_pkl['derived_data'])} derived groups"
            )

            # Fetch events for this deployment
            logger.debug("Fetching events...")
            try:
                events_df = duck_pond.get_events(
                    dataset=dataset,
                    animal_ids=animal_id,
                    date_range=(date_range["start"], date_range["end"]),
                    apply_timezone_offset=timezone_offset,
                    add_timestamp_columns=True,
                )
                logger.debug(
                    f"Loaded {len(events_df) if not events_df.empty else 0} events"
                )
            except Exception as e:
                logger.error(f"Error fetching events: {e}")
                events_df = None

            # Fetch videos from Immich
            logger.debug("Fetching videos from Immich...")
            video_options = []
            try:
                deployment_id_for_immich = "DepID_" + selected_deployment["deployment"]
                logger.debug(
                    f"Fetching videos from Immich for deployment: {deployment_id_for_immich}"
                )
                media_result = immich_service.find_media_by_deployment_id(
                    deployment_id_for_immich, media_type="VIDEO", shared=True
                )
                video_result = immich_service.prepare_video_options_for_react(
                    media_result
                )
                video_options = video_result.get("video_options", [])
                logger.debug(f"Loaded {len(video_options)} videos")
            except Exception as e:
                logger.error(f"Error fetching videos: {e}")
                video_options = []

            # Generate timeline HTML
            timeline_html = create_timeline_section(
                dff=dff,
                video_options=video_options,
                events_df=events_df,
            )

            # Generate deployment info display
            deployment_info_html = create_deployment_info_display(
                animal_id=animal_id,
                deployment_date=selected_deployment["deployment_date"],
            )

            # Prepare orientation data for 3D model
            # Important: Set datetime as index so React component can access it via dataframe.index
            logger.debug(
                f"Checking for orientation data. Available columns: {dff.columns.tolist()}"
            )
            if (
                "pitch" in dff.columns
                and "roll" in dff.columns
                and "heading" in dff.columns
            ):
                model_df = dff[["datetime", "pitch", "roll", "heading"]].set_index(
                    "datetime"
                )
                model_data_json = model_df.to_json(orient="split")
                logger.debug(
                    f"3D model data prepared WITH orientation: {len(model_df)} rows, {model_df.shape[1]} columns"
                )
                logger.debug(f"Columns: {model_df.columns.tolist()}")
            else:
                # No orientation data - send empty structure that component will recognize
                logger.warning(
                    f"No orientation data found. Columns available: {dff.columns.tolist()}"
                )
                # Create empty dataframe with proper structure but no data
                empty_df = pd.DataFrame({"datetime": []}).set_index("datetime")
                model_data_json = empty_df.to_json(orient="split")
                logger.debug("3D model data prepared WITHOUT orientation (empty)")

            return (
                selected_deployment,
                dataset,
                fig,
                False,
                timeline_html,
                deployment_info_html,
                dff["timestamp"].tolist(),  # playback timestamps
                video_options,  # current video options
                model_data_json,  # three-d-model data
                False,  # previous-button enabled
                False,  # rewind-button enabled
                False,  # play-button enabled
                False,  # forward-button enabled
                False,  # next-button enabled
                False,  # save-button enabled
                False,  # playback-rate enabled
                False,  # fullscreen-button enabled
            )

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
            error_timeline = html.P(
                f"Error: {str(e)}", className="text-danger text-center py-4"
            )
            error_info = html.P("Error loading deployment", className="text-danger")
            # Create minimal empty data JSON for 3D model on error
            empty_data_json = pd.DataFrame({"datetime": []}).to_json(orient="split")
            return (
                no_update,
                no_update,
                fig,
                False,
                error_timeline,
                error_info,
                [],
                [],
                empty_data_json,
                True,
                True,
                True,
                True,
                True,
                True,
                True,
                True,
            )

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
