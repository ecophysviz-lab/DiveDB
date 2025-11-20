"""
Selection callbacks for dataset, deployment, and date range selection.
"""

import dash
from dash import Output, Input, State, html, callback_context, no_update, ALL
import pandas as pd
import time
from logging_config import get_logger
from dash_extensions.enrich import Serverside
from layout import (
    create_dataset_accordion_item,
    create_timeline_section,
    create_deployment_info_display,
)
from graph_utils import plot_tag_data_interactive
from plotly_resampler import FigureResampler

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


def _create_data_pkl_from_groups(dff, data_columns, group_membership):
    """
    Create data_pkl structure using group_membership information.

    Groups columns by their parent group so they appear together on the same subplot.
    Preserves the order that groups were added to group_membership.
    """
    sensor_data = {}
    sensor_info = {}
    derived_data = {}
    derived_info = {}

    # Group columns by their parent group, preserving order from group_membership
    # Note: group_membership keys are in the order of labels_to_load
    groups = {}
    group_order = []  # Track the order groups are first seen
    for col, group_info in group_membership.items():
        # Only process columns that exist in the DataFrame
        if col not in data_columns:
            continue

        group_name = group_info["group"]

        if group_name not in groups:
            groups[group_name] = {
                "columns": [],
                "group_label": group_info["group_label"],
                "group_metadata": group_info["group_metadata"],
            }
            group_order.append(group_name)  # Track order
        groups[group_name]["columns"].append(col)

    # Create sensor_data/derived_data entries for each group IN ORDER
    for group_name in group_order:
        group_data = groups[group_name]
        columns = group_data["columns"]
        group_meta = group_data["group_metadata"]

        # Create DataFrame for this group
        signal_df = dff[["datetime"] + columns].copy()

        # Determine if this should go in sensor_data or derived_data
        # Use naming convention: derived_data_* goes to derived, sensor_data_* goes to sensor
        # For cleaner display, strip the prefix from the group name
        if group_name.startswith("derived_data_"):
            display_name = group_name.replace("derived_data_", "")
            target_data = derived_data
            target_info = derived_info
        elif group_name.startswith("sensor_data_"):
            display_name = group_name.replace("sensor_data_", "")
            target_data = sensor_data
            target_info = sensor_info
        else:
            # Default: use as-is and put in sensor_data
            display_name = group_name
            target_data = sensor_data
            target_info = sensor_info

        target_data[display_name] = signal_df

        # Create metadata for each channel in this group
        channel_metadata = {}
        for col in columns:
            # Try to get metadata from group_meta channels list
            col_meta = None
            if group_meta and "channels" in group_meta:
                for ch in group_meta["channels"]:
                    if ch.get("channel_id") == col or ch.get("label") == col:
                        col_meta = ch
                        break

            if col_meta:
                # Prioritize line_label (individual channel label) over other labels
                # This ensures each channel in a group gets a unique name and color
                # Fallback chain: line_label -> label -> channel_id (col)
                channel_name = (
                    col_meta.get("line_label")
                    or col_meta.get("label")
                    or col_meta.get("channel_id")
                    or col
                )
                # If channel_name is still just the raw column name, format it nicely
                if channel_name == col:
                    channel_name = col.replace("_", " ").title()

                channel_metadata[col] = {
                    "original_name": channel_name,
                    "unit": col_meta.get("y_units") or "",
                }
            else:
                # Fallback metadata - use the column name itself, formatted nicely
                channel_metadata[col] = {
                    "original_name": col.replace("_", " ").title(),
                    "unit": "",
                }

        target_info[display_name] = {
            "channels": columns,
            "metadata": channel_metadata,
        }

        # Debug: Log metadata for this group
        logger.debug(
            f"Group '{display_name}' metadata: {[(col, meta['original_name']) for col, meta in channel_metadata.items()]}"
        )

    return DataPkl(
        sensor_data=sensor_data,
        sensor_info=sensor_info,
        derived_data=derived_data,
        derived_info=derived_info,
    )


def create_data_pkl_from_dataframe(dff, group_membership=None):
    """
    Transform a pivoted DataFrame into the data_pkl structure expected by plot_tag_data_interactive.

    Uses group_membership to organize columns by their parent group, ensuring that channels
    belonging to the same group (e.g., ax, ay, az for accelerometer) are plotted together.

    Args:
        dff: DataFrame with 'datetime' column and signal columns
        group_membership: Dict mapping each label to its group info {label: {group, group_label, group_metadata}}

    Returns:
        DataPkl: data_pkl structure with sensor_data, sensor_info, derived_data, and derived_info
    """
    # Skip 'datetime' and 'timestamp' columns
    data_columns = [col for col in dff.columns if col not in ["datetime", "timestamp"]]

    if not data_columns:
        return DataPkl(sensor_data={}, sensor_info={}, derived_data={}, derived_info={})

    # If group_membership is provided, use it to organize columns
    if group_membership:
        return _create_data_pkl_from_groups(dff, data_columns, group_membership)

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


def generate_graph_from_channels(
    duck_pond,
    dataset,
    deployment_id,
    animal_id,
    date_range,
    timezone_offset,
    selected_channels,
    selected_deployment,
    available_channels=None,
):
    """
    Fetch data and generate graph for selected channels.

    Args:
        duck_pond: DuckPond instance
        dataset: Dataset identifier
        deployment_id: Deployment identifier
        animal_id: Animal identifier
        date_range: Dict with 'start' and 'end' datetime strings
        timezone_offset: Timezone offset in hours
        selected_channels: List of channel identifiers (can be group names or individual labels)
        selected_deployment: Deployment metadata dict (for sample_count)
        available_channels: List of channel metadata from DuckPond (optional)

    Returns:
        Tuple of (fig, dff, timestamps)
    """
    import plotly.graph_objects as go

    logger.debug(f"Generating graph for channels: {selected_channels}")

    # Step 1: Expand groups to individual labels using priority patterns
    # Priority patterns for label matching (most important first)
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

    labels_to_load = []
    group_membership = {}  # Track which group each label belongs to

    if available_channels:
        # Build a lookup for groups
        channel_lookup = {}
        for channel in available_channels:
            if channel.get("kind") == "group":
                # Group - add to lookup
                channel_lookup[channel.get("group")] = channel
            elif channel.get("kind") == "variable":
                # Individual variable - add to lookup
                channel_lookup[channel.get("label")] = channel

        # Expand selected channels with priority ordering
        for selected in selected_channels:
            if selected in channel_lookup:
                channel_meta = channel_lookup[selected]
                if channel_meta.get("kind") == "group":
                    # Expand group to its individual channels, sorted by priority
                    group_channels = channel_meta.get("channels", [])

                    # Sort channels by priority pattern matching
                    def get_priority_score(ch):
                        """Return priority score (lower is higher priority)"""
                        label = (ch.get("channel_id") or ch.get("label") or "").lower()
                        for idx, pattern in enumerate(priority_patterns):
                            if pattern in label:
                                return idx
                        return len(
                            priority_patterns
                        )  # Unprioritized items go to the end

                    sorted_channels = sorted(group_channels, key=get_priority_score)

                    # Add sorted channels to labels_to_load and track group membership
                    for ch in sorted_channels:
                        label = ch.get("channel_id") or ch.get("label")
                        if label and label not in labels_to_load:
                            labels_to_load.append(label)
                            group_membership[label] = {
                                "group": selected,
                                "group_label": channel_meta.get("label") or selected,
                                "group_metadata": channel_meta,
                            }
                else:
                    # Individual label
                    label = channel_meta.get("label") or channel_meta.get("channel_id")
                    if label and label not in labels_to_load:
                        labels_to_load.append(label)
                        group_membership[label] = {
                            "group": label,
                            "group_label": channel_meta.get("y_label") or label,
                            "group_metadata": channel_meta,
                        }
            else:
                # Fallback: use as-is if not found in metadata
                if selected not in labels_to_load:
                    labels_to_load.append(selected)
                    group_membership[selected] = {
                        "group": selected,
                        "group_label": selected,
                        "group_metadata": None,
                    }
    else:
        # No metadata available - use selected_channels as-is
        labels_to_load = list(selected_channels)
        for label in labels_to_load:
            group_membership[label] = {
                "group": label,
                "group_label": label,
                "group_metadata": None,
            }

    logger.debug(f"Expanded to {len(labels_to_load)} labels: {labels_to_load}")

    # Load metadata for selected channels only (lazy loading for performance)
    logger.debug("Loading metadata for selected channels...")
    channels_metadata = duck_pond.get_channels_metadata(
        dataset=dataset, channel_ids=labels_to_load
    )
    logger.debug(f"Loaded metadata for {len(channels_metadata)} channels")

    # Enrich group_membership with metadata
    for label, metadata in channels_metadata.items():
        if label in group_membership and group_membership[label]["group_metadata"]:
            # If there's already group metadata, we might want to add channel-specific metadata
            # For now, we'll update the channels list within group_metadata if it exists
            group_meta = group_membership[label]["group_metadata"]
            if "channels" in group_meta:
                # Find the channel in the channels list and update it
                for ch in group_meta["channels"]:
                    if ch.get("channel_id") == label or ch.get("label") == label:
                        # Update with fresh metadata
                        ch.update(
                            {
                                "y_label": metadata.get("label"),
                                "y_description": metadata.get("description"),
                                "y_units": metadata.get("standardized_unit"),
                                "line_label": metadata.get("label"),
                                "color": metadata.get("color"),
                                "icon": metadata.get("icon"),
                            }
                        )

    # Step 2: Set maximum frequency cap
    # Each label will be downsampled only if it exceeds this frequency
    # Lower-frequency labels (e.g., depth at 1 Hz) stay at native resolution
    MAX_FREQUENCY_HZ = 20  # Configurable: downsample high-freq signals to this cap

    logger.debug(
        f"Using max_frequency={MAX_FREQUENCY_HZ} Hz (per-label adaptive downsampling)"
    )

    # Step 3: Load data with max frequency cap
    if not labels_to_load:
        # No labels to load - return empty figure
        fig = go.Figure()
        fig.update_layout(
            annotations=[
                dict(
                    text="No channels selected",
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
        empty_dff = pd.DataFrame({"datetime": [], "timestamp": []})
        return fig, empty_dff, []

    logger.debug("Loading data...")
    t0 = time.time()
    dff = duck_pond.get_data(
        dataset=dataset,
        deployment_ids=deployment_id,
        animal_ids=animal_id,
        date_range=(date_range["start"], date_range["end"]),
        max_frequency=MAX_FREQUENCY_HZ,  # Use new optimized parameter
        labels=labels_to_load,
        add_timestamp_column=True,
        apply_timezone_offset=timezone_offset,
        pivoted=True,
        use_cache=True,
    )
    t1 = time.time()
    logger.info(
        f"Data load time: {t1 - t0:.2f}s (using max_frequency={MAX_FREQUENCY_HZ} Hz)"
    )
    logger.debug(f"Data shape: {dff.shape if not dff.empty else 'EMPTY'}")

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
        # Return a properly structured empty dataframe with required columns
        empty_dff = pd.DataFrame({"datetime": [], "timestamp": []})
        return fig, empty_dff, []

    logger.info(f"Loaded {len(dff)} rows with {len(dff.columns)} columns")

    # Step 4: Create data_pkl structure from DataFrame
    logger.debug("Creating data_pkl structure...")
    data_pkl = create_data_pkl_from_dataframe(dff, group_membership=group_membership)

    # Determine zoom_range_selector_channel (use depth if available)
    zoom_range_selector_channel = None
    if "depth" in data_pkl["sensor_data"] or "depth" in data_pkl["derived_data"]:
        zoom_range_selector_channel = "depth"

    # Step 5: Create figure using plot_tag_data_interactive
    logger.debug("Creating figure...")
    fig = plot_tag_data_interactive(
        data_pkl=data_pkl,
        zoom_range_selector_channel=zoom_range_selector_channel,
    )

    logger.info(
        f"Created figure with {len(data_pkl['sensor_data'])} sensor groups and {len(data_pkl['derived_data'])} derived groups"
    )

    # Extract timestamps for playback
    timestamps = dff["timestamp"].tolist() if "timestamp" in dff.columns else []

    return fig, dff, timestamps


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
        Output("figure-store", "data"),
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
        # Channel management outputs
        Output("available-channels", "data"),
        Output("selected-channels", "data"),
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
                [],
                [],
            )

        if not n_clicks_list or not any(n_clicks_list):
            # Create minimal empty data JSON for 3D model
            empty_data_json = pd.DataFrame({"datetime": []}).to_json(orient="split")
            return (
                no_update,
                no_update,
                no_update,
                no_update,  # figure-store
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
                [],  # available-channels
                [],  # selected-channels
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
                [],
                [],
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
                    [],
                    [],
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

            # Fetch available channels from DuckPond (without metadata for speed)
            logger.debug("Fetching available channels...")
            available_channels = duck_pond.get_available_channels(
                dataset=dataset,
                include_metadata=True,
                pack_groups=True,
                load_metadata=False,
            )
            logger.debug(f"Found {len(available_channels)} channel options")

            # Debug: Log all available group names
            available_groups = [
                ch.get("group")
                for ch in available_channels
                if ch.get("kind") == "group"
            ]
            logger.debug(f"Available groups: {available_groups}")

            # Select default channels - prioritize groups like depth, prh, pressure, temperature, light
            # Note: We only show groups in the UI, so only select groups by default
            default_priority = ["depth", "prh", "pressure", "temperature", "light"]
            selected_channels = []

            for priority_name in default_priority:
                for channel in available_channels:
                    # Only use groups
                    if channel.get("kind") == "group":
                        group_name = channel.get("group", "")
                        # Match if priority name is in group name (handles prefixes like derived_data_depth)
                        if priority_name.lower() in group_name.lower():
                            selected_channels.append(group_name)
                            logger.debug(
                                f"Matched priority '{priority_name}' to group '{group_name}'"
                            )
                            break
                # Limit to first 5 channels
                if len(selected_channels) >= 5:
                    break

            # If no matches, use first 3 available groups
            if not selected_channels:
                logger.debug("No priority matches found, selecting first 3 groups")
                for channel in available_channels:
                    # Only use groups
                    if channel.get("kind") == "group":
                        group_name = channel.get("group")
                        selected_channels.append(group_name)
                        logger.debug(f"Added fallback group: {group_name}")
                        if len(selected_channels) >= 3:
                            break

            logger.debug(f"Default selected channels: {selected_channels}")

            # Generate graph using the new helper function
            fig, dff, timestamps = generate_graph_from_channels(
                duck_pond=duck_pond,
                dataset=dataset,
                deployment_id=deployment_id,
                animal_id=animal_id,
                date_range=date_range,
                timezone_offset=timezone_offset,
                selected_channels=selected_channels,
                selected_deployment=selected_deployment,
                available_channels=available_channels,
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
                icon_url=selected_deployment.get("icon_url", "/assets/images/seal.svg"),
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
                # Downsample to 1 Hz for 3D model performance
                model_df = model_df.resample("1S").last()
                model_data_json = model_df.to_json(orient="split")
                logger.debug(
                    f"3D model data prepared WITH orientation (downsampled to 1 Hz): {len(model_df)} rows, {model_df.shape[1]} columns"
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
                Serverside(fig),  # Cache FigureResampler for plotly-resampler
                False,
                timeline_html,
                deployment_info_html,
                timestamps,  # playback timestamps from generate_graph_from_channels
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
                available_channels,  # available-channels from DuckPond
                selected_channels,  # selected-channels (default selection)
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
                None,
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
                [],
                [],
            )

    @app.callback(
        Output("graph-content", "figure", allow_duplicate=True),
        Output(
            "figure-store", "data", allow_duplicate=True
        ),  # NEW: Cache FigureResampler
        Output("playback-timestamps", "data", allow_duplicate=True),
        Output("graph-channels", "is_open"),
        Input("update-graph-btn", "n_clicks"),
        State({"type": "channel-select", "index": ALL}, "value"),
        State("selected-dataset", "data"),
        State("selected-deployment", "data"),
        State("available-channels", "data"),
        State("all-datasets-deployments", "data"),
        prevent_initial_call=True,
    )
    def update_graph_from_channels(
        n_clicks,
        channel_values,
        dataset,
        deployment_data,
        available_channels,
        datasets_with_deployments,
    ):
        """Update graph when user clicks Update Graph button."""
        if not n_clicks or not channel_values or not dataset or not deployment_data:
            raise dash.exceptions.PreventUpdate

        logger.info(f"Updating graph with selected channels: {channel_values}")

        # Get deployment details
        deployment_id = deployment_data["deployment"]
        animal_id = deployment_data["animal"]

        # Find full deployment data for sample_count
        deployments_list = datasets_with_deployments.get(dataset, [])
        selected_deployment = None
        for dep in deployments_list:
            if dep["deployment"] == deployment_id and dep["animal"] == animal_id:
                selected_deployment = dep
                break

        if not selected_deployment:
            logger.error(f"Could not find deployment {deployment_id} in datasets")
            raise dash.exceptions.PreventUpdate

        # Get timezone offset
        timezone_offset = duck_pond.get_deployment_timezone_offset(deployment_id)

        # Build date range
        min_dt = pd.to_datetime(selected_deployment["min_date"])
        max_dt = pd.to_datetime(selected_deployment["max_date"])
        date_range = {
            "start": min_dt.isoformat(),
            "end": max_dt.isoformat(),
        }

        # Generate graph with selected channels
        fig, dff, timestamps = generate_graph_from_channels(
            duck_pond=duck_pond,
            dataset=dataset,
            deployment_id=deployment_id,
            animal_id=animal_id,
            date_range=date_range,
            timezone_offset=timezone_offset,
            selected_channels=channel_values,
            selected_deployment=selected_deployment,
            available_channels=available_channels,
        )

        logger.info(f"Graph updated successfully with {len(channel_values)} channels")
        return fig, Serverside(fig), timestamps, False

    @app.callback(
        Output("graph-channel-list", "children", allow_duplicate=True),
        Input("selected-channels", "data"),
        State("available-channels", "data"),
        prevent_initial_call=True,
    )
    def populate_channel_list_from_selection(selected_channels, available_channels):
        """Populate the channel list UI based on selected channels."""
        import dash_bootstrap_components as dbc

        logger.debug(
            f"populate_channel_list_from_selection triggered with selected_channels: {selected_channels}"
        )

        if not selected_channels:
            logger.debug("No selected channels, preventing update")
            raise dash.exceptions.PreventUpdate

        logger.debug(
            f"Populating channel list with {len(selected_channels)} channels: {selected_channels}"
        )

        # Convert available_channels to dropdown format - ONLY GROUPS
        dropdown_options = []
        if available_channels:
            for option in available_channels:
                if isinstance(option, dict):
                    kind = option.get("kind")
                    # Only show groups, not individual variables
                    if kind == "group":
                        group_name = option.get("group")
                        display_label = option.get("label") or group_name
                        # Note: icons are URLs and can't be displayed in Select dropdowns
                        dropdown_options.append(
                            {"label": display_label, "value": group_name}
                        )
        else:
            # Fallback options (all groups)
            dropdown_options = [
                {"label": "Depth", "value": "depth"},
                {"label": "Pitch, roll, heading", "value": "prh"},
                {"label": "Temperature", "value": "temperature"},
                {"label": "Light", "value": "light"},
            ]

        logger.debug(
            f"Dropdown options available: {[opt['value'] for opt in dropdown_options]}"
        )

        # Build channel rows
        channel_rows = []
        for idx, channel_value in enumerate(selected_channels, start=1):
            logger.debug(f"Creating row {idx} for channel: {channel_value}")

            # Check if channel_value exists in dropdown_options
            matching_option = next(
                (opt for opt in dropdown_options if opt["value"] == channel_value), None
            )
            if not matching_option:
                logger.warning(
                    f"Channel '{channel_value}' not found in dropdown options!"
                )

            channel_row = dbc.ListGroupItem(
                dbc.Row(
                    [
                        dbc.Col(
                            html.Button(
                                html.Img(
                                    src="/assets/images/drag.svg",
                                    className="drag-icon",
                                ),
                                className="btn btn-icon-only btn-sm",
                                id={"type": "channel-drag", "index": idx},
                            ),
                            width="auto",
                            className="drag-handle",
                        ),
                        dbc.Col(
                            dbc.Select(
                                options=dropdown_options,
                                value=channel_value,
                                id={"type": "channel-select", "index": idx},
                            ),
                        ),
                        dbc.Col(
                            html.Button(
                                html.Img(
                                    src="/assets/images/remove.svg",
                                    className="remove-icon",
                                ),
                                className="btn btn-icon-only btn-sm",
                                id={"type": "channel-remove", "index": idx},
                            ),
                            width="auto",
                        ),
                    ],
                    align="center",
                    className="g-2",
                ),
            )
            channel_rows.append(channel_row)

        # Add buttons side-by-side in one row
        buttons_row = dbc.ListGroupItem(
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Button(
                            "Add Graph",
                            color="primary",
                            className="btn-xs btn-stroke my-1 w-100",
                            id="add-graph-btn",
                        ),
                        width=3,
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Update Graph",
                            color="success",
                            className="btn-xs my-1 w-100",
                            id="update-graph-btn",
                        ),
                        width=3,
                    ),
                ],
                align="center",
                className="g-2 justify-content-end",
            ),
        )

        return channel_rows + [buttons_row]

    @app.callback(
        Output("graph-channels-toggle", "disabled"),
        Input("selected-dataset", "data"),
    )
    def toggle_manage_channels_button(selected_dataset):
        """Enable/disable the Manage Channels button based on dataset selection."""
        # Enable button when a dataset is selected, disable when None
        return selected_dataset is None

    @app.callback(
        Output("graph-channels", "is_open", allow_duplicate=True),
        Input("graph-channels-toggle", "n_clicks"),
        State("graph-channels", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_manage_channels_popover(n_clicks, is_open):
        """Toggle the Manage Channels popover open/closed when button is clicked."""
        if n_clicks:
            return not is_open
        return is_open

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

    # Handle zoom/pan events with plotly-resampler
    @app.callback(
        Output("graph-content", "figure", allow_duplicate=True),
        Input("graph-content", "relayoutData"),
        State("figure-store", "data"),  # The cached FigureResampler object
        prevent_initial_call=True,
        memoize=True,
    )
    def update_graph_on_zoom(relayoutdata: dict, fig: FigureResampler):
        """
        Handle zoom/pan events with plotly-resampler.

        When a user zooms or pans on the graph, this callback is triggered.
        The FigureResampler object cached in figure-store will automatically
        load the appropriate resolution of data for the new view range.
        """
        if fig is None:
            logger.debug("No FigureResampler in cache, skipping zoom update")
            return no_update

        if not relayoutdata:
            logger.debug("No relayout data, skipping zoom update")
            return no_update

        logger.debug(f"Zoom/pan event detected: {relayoutdata.keys()}")

        # construct_update_data_patch handles the resampling based on zoom level
        return fig.construct_update_data_patch(relayoutdata)
