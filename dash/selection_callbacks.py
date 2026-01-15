"""
Selection callbacks for dataset, deployment, and date range selection.
"""

import dash
from dash import Output, Input, State, html, callback_context, no_update, ALL
import pandas as pd
import time
from concurrent.futures import ThreadPoolExecutor
from logging_config import get_logger
from dash_extensions.enrich import Serverside
from layout import (
    create_dataset_accordion_item,
    create_timeline_section,
    create_deployment_info_display,
)
from layout.indicators import assign_event_colors
from graph_utils import plot_tag_data_interactive
from plotly_resampler import FigureResampler

logger = get_logger(__name__)


class DataPkl:
    """Simple class to support both attribute and dict access for data_pkl structure."""

    def __init__(self, signal_data, signal_info, event_data=None):
        self.signal_data = signal_data
        self.signal_info = signal_info
        self.event_data = event_data

    def __getitem__(self, key):
        """Support dict-style access."""
        if key == "signal_data":
            return self.signal_data
        elif key == "signal_info":
            return self.signal_info
        elif key == "event_data":
            return self.event_data
        else:
            raise KeyError(key)

    def __contains__(self, key):
        """Support 'in' operator."""
        return key in ["signal_data", "signal_info", "event_data"]


def transform_events_for_graph(events_df):
    """
    Transform events DataFrame from DuckPond format to graph annotation format.

    DuckPond format: event_key, datetime_start, datetime_end
    Graph format: key, datetime, duration

    Returns:
        pd.DataFrame with columns: key, datetime, duration (in seconds)
    """
    if events_df is None or events_df.empty:
        return None

    transformed = pd.DataFrame()
    transformed["key"] = events_df["event_key"]
    transformed["datetime"] = events_df["datetime_start"]

    # Calculate duration in seconds
    start_times = pd.to_datetime(events_df["datetime_start"])
    end_times = pd.to_datetime(events_df["datetime_end"])
    transformed["duration"] = (end_times - start_times).dt.total_seconds()

    # Keep original columns for reference
    transformed["datetime_end"] = events_df["datetime_end"]
    if "short_description" in events_df.columns:
        transformed["short_description"] = events_df["short_description"]

    return transformed


def _create_data_pkl_from_groups(dff, data_columns, group_membership):
    """
    Create data_pkl structure using group_membership information.

    Groups columns by their parent group so they appear together on the same subplot.
    Preserves the order that groups were added to group_membership.
    """
    signal_data = {}
    signal_info = {}

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

    # Create signal_data entries for each group IN ORDER
    for group_name in group_order:
        group_data = groups[group_name]
        columns = group_data["columns"]
        group_meta = group_data["group_metadata"]

        # Create DataFrame for this group
        signal_df = dff[["datetime"] + columns].copy()

        # Strip signal_data_ prefix if present for cleaner display
        if group_name.startswith("signal_data_"):
            display_name = group_name.replace("signal_data_", "")
        else:
            display_name = group_name

        signal_data[display_name] = signal_df

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

        signal_info[display_name] = {
            "channels": columns,
            "metadata": channel_metadata,
        }

        # Debug: Log metadata for this group
        logger.debug(
            f"Group '{display_name}' metadata: {[(col, meta['original_name']) for col, meta in channel_metadata.items()]}"
        )

    return DataPkl(
        signal_data=signal_data,
        signal_info=signal_info,
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
        DataPkl: data_pkl structure with signal_data and signal_info
    """
    # Skip 'datetime' and 'timestamp' columns
    data_columns = [col for col in dff.columns if col not in ["datetime", "timestamp"]]

    if not data_columns:
        return DataPkl(signal_data={}, signal_info={})

    # If group_membership is provided, use it to organize columns
    if group_membership:
        return _create_data_pkl_from_groups(dff, data_columns, group_membership)

    # Define signal patterns
    # TODO: Pull from Notion
    signal_patterns = {
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
        "depth": {"pattern": "depth", "unit": "m", "display_name": "Corrected Depth"},
        "pressure": {"pattern": "pressure", "unit": "m", "display_name": "Pressure"},
    }

    signal_data = {}
    signal_info = {}

    # Track which columns have been assigned
    assigned_columns = set()

    # First pass: Handle prh (pitch, roll, heading) - these go together
    prh_cols = []
    for col in data_columns:
        if col.lower() in ["pitch", "roll", "heading"] and col not in assigned_columns:
            prh_cols.append(col)
            assigned_columns.add(col)

    if prh_cols:
        # Create prh DataFrame
        prh_df = dff[["datetime"] + prh_cols].copy()
        signal_data["prh"] = prh_df

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

        signal_info["prh"] = {
            "channels": prh_cols,
            "metadata": prh_metadata,
        }

    # Second pass: Handle all other signal patterns
    for signal_name, signal_config in signal_patterns.items():
        pattern = signal_config["pattern"]
        matching_cols = [
            col
            for col in data_columns
            if pattern.lower() in col.lower() and col not in assigned_columns
        ]

        if matching_cols:
            # Create DataFrame for this signal type
            signal_df = dff[["datetime"] + matching_cols].copy()
            signal_data[signal_name] = signal_df

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

            signal_info[signal_name] = {
                "channels": matching_cols,
                "metadata": channel_metadata,
            }

            assigned_columns.update(matching_cols)

    # Third pass: assign remaining columns by their base name
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

        # Create signal entries for each group
        for base_name, cols in other_groups.items():
            signal_df = dff[["datetime"] + cols].copy()
            signal_data[base_name] = signal_df

            channel_metadata = {}
            for col in cols:
                display_name = col.replace("_", " ").title()
                channel_metadata[col] = {
                    "original_name": display_name,
                    "unit": "",  # No unit for unknown signals
                }

            signal_info[base_name] = {
                "channels": cols,
                "metadata": channel_metadata,
            }

    return DataPkl(
        signal_data=signal_data,
        signal_info=signal_info,
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
    events_df=None,
    selected_events=None,
    zoom_range=None,
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
        events_df: DataFrame with events from DuckPond (optional)
        selected_events: List of event selection dicts [{event_key, signal, enabled}, ...] (optional)
        zoom_range: Dict with 'min' and 'max' timestamps (Unix seconds) for preserving zoom state (optional)

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

    # Step 4b: Add event data if available
    transformed_events = None
    if events_df is not None and not events_df.empty:
        transformed_events = transform_events_for_graph(events_df)
        # Update data_pkl with event_data
        data_pkl.event_data = transformed_events
        logger.debug(f"Added {len(transformed_events)} events to data_pkl")

    # Determine zoom_range_selector_channel (use depth if available)
    zoom_range_selector_channel = None
    if "depth" in data_pkl["signal_data"]:
        zoom_range_selector_channel = "depth"

    # Step 5: Build annotation dicts from selected_events
    note_annotations = {}
    state_annotations = {}

    if selected_events and transformed_events is not None:
        # Get event colors for consistent styling
        event_colors = assign_event_colors(events_df) if events_df is not None else {}

        for event_selection in selected_events:
            if not event_selection.get("enabled", False):
                continue

            event_key = event_selection.get("event_key")
            target_signal = event_selection.get("signal")

            if not event_key or not target_signal:
                continue

            # Check if this is a point event or state event
            event_rows = transformed_events[transformed_events["key"] == event_key]
            if event_rows.empty:
                continue

            # Point event: duration is 0 (datetime_start == datetime_end)
            is_point_event = (event_rows["duration"] == 0).all()
            event_color = event_colors.get(event_key, "#95a5a6")

            if is_point_event:
                # Add to note_annotations (point events as markers)
                note_annotations[event_key] = {
                    "signal": target_signal,
                    "symbol": "circle",
                    "color": event_color,
                }
                logger.debug(
                    f"Added point annotation for '{event_key}' on signal '{target_signal}'"
                )
            else:
                # Add to state_annotations (state events as rectangles)
                state_annotations[event_key] = {
                    "signal": target_signal,
                    "color": f"rgba({int(event_color[1:3], 16)}, {int(event_color[3:5], 16)}, {int(event_color[5:7], 16)}, 0.3)",
                }
                logger.debug(
                    f"Added state annotation for '{event_key}' on signal '{target_signal}'"
                )

    # Step 6: Create figure using plot_tag_data_interactive
    logger.debug("Creating figure...")

    # Convert zoom_range timestamps to datetime for Plotly
    zoom_start_time = None
    zoom_end_time = None
    if zoom_range and zoom_range.get("min") and zoom_range.get("max"):
        zoom_start_time = pd.to_datetime(zoom_range["min"], unit="s")
        zoom_end_time = pd.to_datetime(zoom_range["max"], unit="s")
        logger.debug(f"Preserving zoom range: {zoom_start_time} to {zoom_end_time}")

    fig = plot_tag_data_interactive(
        data_pkl=data_pkl,
        zoom_range_selector_channel=zoom_range_selector_channel,
        note_annotations=note_annotations if note_annotations else None,
        state_annotations=state_annotations if state_annotations else None,
        zoom_start_time=zoom_start_time,
        zoom_end_time=zoom_end_time,
    )

    logger.info(f"Created figure with {len(data_pkl['signal_data'])} signal groups")

    # If we have a zoom range, resample the data server-side for correct resolution
    # This is necessary because FigureResampler initially samples for full data range
    if zoom_start_time is not None and zoom_end_time is not None:
        logger.debug("Applying server-side resampling for zoom range...")
        try:
            # Create synthetic relayout data matching what Plotly sends on zoom
            # With subplots, each has its own xaxis (xaxis, xaxis2, xaxis3, etc.)
            # We need to include all of them to trigger resampling for all traces
            zoom_start_iso = zoom_start_time.isoformat()
            zoom_end_iso = zoom_end_time.isoformat()

            # Find all x-axes that actually exist in the figure layout
            relayout_data = {}
            layout_keys = (
                list(fig.layout.to_plotly_json().keys())
                if hasattr(fig.layout, "to_plotly_json")
                else []
            )

            for key in layout_keys:
                if key.startswith("xaxis"):
                    relayout_data[f"{key}.range[0]"] = zoom_start_iso
                    relayout_data[f"{key}.range[1]"] = zoom_end_iso

            # Fallback if no axes found
            if not relayout_data:
                relayout_data = {
                    "xaxis.range[0]": zoom_start_iso,
                    "xaxis.range[1]": zoom_end_iso,
                }

            logger.debug(
                f"Calling _construct_update_data with range: {zoom_start_iso} to {zoom_end_iso} ({len(relayout_data) // 2} axes)"
            )

            # Get resampled trace data for the zoom range
            # Note: _construct_update_data is the internal method (construct_update_data_patch is for Dash patches)
            trace_updates = fig._construct_update_data(relayout_data)

            logger.debug(
                f"_construct_update_data returned {len(trace_updates) if trace_updates else 0} updates"
            )

            # Apply the trace updates to the figure
            if trace_updates:
                for update in trace_updates:
                    trace_idx = update.get("index")
                    if trace_idx is not None and trace_idx < len(fig.data):
                        # Update the trace's x and y data
                        if "x" in update:
                            fig.data[trace_idx].x = update["x"]
                        if "y" in update:
                            fig.data[trace_idx].y = update["y"]
                logger.debug(
                    f"Applied {len(trace_updates)} trace updates for zoom resampling"
                )
            else:
                logger.warning("construct_update_data returned no updates")
        except Exception as e:
            logger.warning(f"Server-side resampling failed: {e}", exc_info=True)

    # Extract timestamps for playback
    timestamps = dff["timestamp"].tolist() if "timestamp" in dff.columns else []

    return fig, dff, timestamps


def _fetch_videos_async(
    immich_service, deployment_id: str, use_cache: bool = False
) -> list:
    """
    Fetch videos from Immich in a background thread.

    This function is designed to run in a ThreadPoolExecutor while
    DuckDB operations proceed on the main thread.
    """
    try:
        deployment_id_for_immich = "DepID_" + deployment_id
        logger.debug(f"[Thread] Fetching videos for: {deployment_id_for_immich}")

        media_result = immich_service.find_media_by_deployment_id(
            deployment_id_for_immich,
            media_type="VIDEO",
            shared=True,
            use_cache=use_cache,
        )
        video_result = immich_service.prepare_video_options_for_react(media_result)

        video_options = video_result.get("video_options", [])
        logger.debug(f"[Thread] Loaded {len(video_options)} videos")
        return video_options
    except Exception as e:
        logger.error(f"[Thread] Error fetching videos: {e}")
        return []


def register_selection_callbacks(app, duck_pond, immich_service, use_cache=False):
    """Register all selection-related callbacks with the given app instance.

    Args:
        app: Dash app instance
        duck_pond: DuckPond service instance
        immich_service: ImmichService instance
        use_cache: If True, enable caching for service calls (default: False)
    """
    logger.debug(f"Registering selection callbacks (use_cache={use_cache})...")

    @app.callback(
        Output("all-datasets-deployments", "data"),
        Input("url", "pathname"),
    )
    def load_datasets_on_page_load(pathname):
        """Load all datasets and their deployments when the page loads."""
        logger.info("Loading datasets and deployments from data lake on page load...")
        try:
            all_datasets_and_deployments = duck_pond.get_all_datasets_and_deployments(
                use_cache=use_cache
            )
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
        Output("three-d-model", "modelFile"),  # Dynamic 3D model from Notion
        Output("three-d-model", "textureFile"),  # Dynamic texture from Notion
        # Playback control buttons
        Output("previous-button", "disabled"),
        Output("rewind-button", "disabled"),
        Output("play-button", "disabled"),
        Output("forward-button", "disabled"),
        Output("next-button", "disabled"),
        Output("save-button", "disabled"),
        Output("playback-rate-display", "disabled"),
        Output("fullscreen-button", "disabled"),
        # Channel management outputs
        Output("available-channels", "data"),
        Output("selected-channels", "data"),
        # Event management outputs
        Output("available-events", "data"),
        Output("selected-events", "data"),
        # Timeline bounds output (for zoom sync)
        Output("timeline-bounds", "data"),
        # Original bounds output (for reset zoom)
        Output("original-bounds", "data"),
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
        default_model_file = ""  # Empty = no model initially
        default_texture_file = ""  # Empty = no texture initially

        if not callback_context.triggered or not datasets_with_deployments:
            # No trigger or no data - preserve existing state
            raise dash.exceptions.PreventUpdate

        if not n_clicks_list or not any(n_clicks_list):
            # No clicks - preserve existing state
            raise dash.exceptions.PreventUpdate

        # Find which button was clicked
        triggered_id = callback_context.triggered[0]["prop_id"]

        if "deployment-button" not in triggered_id:
            # Not a deployment button click - preserve existing state
            raise dash.exceptions.PreventUpdate

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
                raise dash.exceptions.PreventUpdate

            selected_deployment = deployments_data[idx]
            logger.info(
                f"Selected deployment: {selected_deployment['animal']} ({selected_deployment['deployment']}) from dataset {dataset}"
            )

            # Now load the visualization for this deployment
            import plotly.graph_objects as go

            deployment_id = selected_deployment["deployment"]
            animal_id = selected_deployment["animal"]

            # Start video fetch immediately in background thread
            # This runs in parallel with DuckDB operations below
            with ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="immich"
            ) as executor:
                video_future = executor.submit(
                    _fetch_videos_async,
                    immich_service,
                    selected_deployment["deployment"],
                    use_cache,
                )

                # Continue with DuckDB operations (sequential, share connection)
                # Get timezone offset from Notion via DuckDB
                timezone_offset = duck_pond.get_deployment_timezone_offset(
                    deployment_id, use_cache=use_cache
                )
                logger.info(f"Deployment timezone offset: UTC{timezone_offset:+.1f}")

                # Use deployment's min and max dates directly
                min_dt = pd.to_datetime(selected_deployment["min_date"])
                max_dt = pd.to_datetime(selected_deployment["max_date"])
                date_range = {
                    "start": min_dt.isoformat(),
                    "end": max_dt.isoformat(),
                }

                logger.info(f"Loading visualization for deployment: {deployment_id}")
                logger.debug(
                    f"Date range: {date_range['start']} to {date_range['end']}"
                )

                # Fetch available channels from DuckPond (with caching for faster repeat loads)
                logger.debug("Fetching available channels...")
                available_channels = duck_pond.get_available_channels(
                    dataset=dataset,
                    include_metadata=True,
                    pack_groups=True,
                    load_metadata=False,
                    use_cache=use_cache,
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
                        use_cache=use_cache,
                    )
                    logger.debug(
                        f"Loaded {len(events_df) if not events_df.empty else 0} events"
                    )
                except Exception as e:
                    logger.error(f"Error fetching events: {e}")
                    events_df = None

                # Join video results at the end (blocks only if still running)
                logger.debug("Waiting for video fetch to complete...")
                try:
                    video_options = video_future.result(timeout=30)
                except Exception as e:
                    logger.error(f"Video fetch failed or timed out: {e}")
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
                model_df = model_df.resample("1s").last()
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

            # Get 3D model file URL from Notion (Animal→Asset→Best-3D-model)
            model_info = duck_pond.get_3d_model_for_animal(
                animal_id, use_cache=use_cache
            )
            model_file_url = (
                model_info.get("model_url") or ""
            )  # Empty string = no model
            texture_file_url = (
                model_info.get("texture_url") or ""
            )  # Empty string = no texture
            logger.info(
                f"3D model for animal '{animal_id}': {model_info.get('model_filename', 'none')} ({model_info.get('filetype', 'none')})"
                + (
                    f" with texture {model_info.get('texture_filename')}"
                    if model_info.get("texture_url")
                    else ""
                )
            )

            # Extract available event types from events_df
            available_events = []
            selected_events = []
            if events_df is not None and not events_df.empty:
                # Get unique event types and assign colors
                event_colors = assign_event_colors(events_df)
                unique_event_keys = events_df["event_key"].unique().tolist()

                # Determine default signal (first selected channel)
                default_signal = selected_channels[0] if selected_channels else "depth"

                for event_key in unique_event_keys:
                    # Determine if this is a point or state event
                    event_rows = events_df[events_df["event_key"] == event_key]
                    is_point_event = (
                        event_rows["datetime_start"] == event_rows["datetime_end"]
                    ).all()

                    available_events.append(
                        {
                            "event_key": event_key,
                            "color": event_colors.get(event_key, "#95a5a6"),
                            "is_point_event": is_point_event,
                            "count": len(event_rows),
                        }
                    )
                    # Initialize selected_events with all events unchecked
                    selected_events.append(
                        {
                            "event_key": event_key,
                            "signal": default_signal,
                            "enabled": False,
                        }
                    )

                logger.debug(
                    f"Found {len(available_events)} unique event types: {unique_event_keys}"
                )

            # Calculate initial timeline bounds from timestamps
            initial_bounds = (
                {"min": timestamps[0], "max": timestamps[-1]} if timestamps else None
            )

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
                model_file_url,  # three-d-model modelFile (from Notion)
                texture_file_url,  # three-d-model textureFile (from Notion)
                False,  # previous-button enabled
                False,  # rewind-button enabled
                False,  # play-button enabled
                False,  # forward-button enabled
                False,  # next-button enabled
                False,  # save-button enabled
                False,  # playback-rate-display enabled
                False,  # fullscreen-button enabled
                available_channels,  # available-channels from DuckPond
                selected_channels,  # selected-channels (default selection)
                available_events,  # available-events (event types for this deployment)
                selected_events,  # selected-events (all unchecked by default)
                initial_bounds,  # timeline-bounds (initial full range)
                initial_bounds,  # original-bounds (persists for reset zoom)
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
                default_model_file,  # modelFile - use default on error
                default_texture_file,  # textureFile - use default on error
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
                [],  # available-events
                [],  # selected-events
                None,  # timeline-bounds
                None,  # original-bounds
            )

    @app.callback(
        Output("graph-content", "figure", allow_duplicate=True),
        Output(
            "figure-store", "data", allow_duplicate=True
        ),  # NEW: Cache FigureResampler
        Output("playback-timestamps", "data", allow_duplicate=True),
        Output("graph-channels", "is_open"),
        Output("update-graph-btn", "disabled", allow_duplicate=True),
        Output("update-graph-btn", "children", allow_duplicate=True),
        Input("channel-order-from-dom", "data"),  # Triggered by clientside callback
        Input("event-refresh-trigger", "data"),  # Triggered after event creation
        State({"type": "event-checkbox", "key": ALL}, "value"),
        State({"type": "event-checkbox", "key": ALL}, "id"),
        State({"type": "event-signal", "key": ALL}, "value"),
        State({"type": "event-signal", "key": ALL}, "id"),
        State("selected-dataset", "data"),
        State("selected-deployment", "data"),
        State("available-channels", "data"),
        State("all-datasets-deployments", "data"),
        State("timeline-bounds", "data"),
        State("selected-channels", "data"),  # For event refresh: use current channels
        prevent_initial_call=True,
    )
    def update_graph_from_channels(
        channel_values_from_dom,  # From DOM order store (Update Graph button)
        event_refresh_trigger,  # Counter incremented after event creation
        event_checkbox_values,
        event_checkbox_ids,
        event_signal_values,
        event_signal_ids,
        dataset,
        deployment_data,
        available_channels,
        datasets_with_deployments,
        timeline_bounds,
        selected_channels_state,  # Current selected channels (for event refresh)
    ):
        """Update graph when user clicks Update Graph button or after event creation.

        Channel values come from channel-order-from-dom store which is populated
        by a clientside callback reading the visual DOM order (supports drag-drop reorder).
        When triggered by event-refresh-trigger, uses selected-channels state instead.
        """
        # Determine what triggered this callback
        ctx = dash.callback_context
        triggered_id = (
            ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None
        )

        # Choose channel values based on trigger source
        if triggered_id == "event-refresh-trigger":
            # Event refresh: use current selected channels from state
            channel_values = selected_channels_state
            logger.info("Graph refresh triggered by event creation")
        else:
            # Update Graph button: use DOM order
            channel_values = channel_values_from_dom

        if not channel_values or not dataset or not deployment_data:
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

        # Get timezone offset (with caching for repeated graph updates)
        timezone_offset = duck_pond.get_deployment_timezone_offset(
            deployment_id, use_cache=use_cache
        )

        # Build date range
        min_dt = pd.to_datetime(selected_deployment["min_date"])
        max_dt = pd.to_datetime(selected_deployment["max_date"])
        date_range = {
            "start": min_dt.isoformat(),
            "end": max_dt.isoformat(),
        }

        # Build selected_events from UI inputs
        selected_events = []
        if event_checkbox_ids and event_signal_ids:
            # Build lookup for signal values by event_key
            signal_lookup = {}
            for sig_id, sig_value in zip(event_signal_ids, event_signal_values):
                if isinstance(sig_id, dict):
                    signal_lookup[sig_id.get("key")] = sig_value

            # Build selected_events list
            for checkbox_id, checkbox_value in zip(
                event_checkbox_ids, event_checkbox_values
            ):
                if isinstance(checkbox_id, dict):
                    event_key = checkbox_id.get("key")
                    selected_events.append(
                        {
                            "event_key": event_key,
                            "signal": signal_lookup.get(
                                event_key, channel_values[0] if channel_values else ""
                            ),
                            "enabled": bool(checkbox_value),
                        }
                    )

        # Check if any events are enabled
        enabled_events = [ev for ev in selected_events if ev.get("enabled")]
        logger.debug(f"Enabled events: {[ev['event_key'] for ev in enabled_events]}")

        # Fetch events if any are enabled (with caching)
        events_df = None
        if enabled_events:
            try:
                events_df = duck_pond.get_events(
                    dataset=dataset,
                    animal_ids=animal_id,
                    date_range=(date_range["start"], date_range["end"]),
                    apply_timezone_offset=timezone_offset,
                    add_timestamp_columns=True,
                    use_cache=use_cache,
                )
                logger.debug(
                    f"Loaded {len(events_df) if events_df is not None and not events_df.empty else 0} events for graph"
                )
            except Exception as e:
                logger.error(f"Error fetching events for graph update: {e}")
                events_df = None

        # Generate graph with selected channels and events
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
            events_df=events_df,
            selected_events=selected_events,
            zoom_range=timeline_bounds,
        )

        logger.info(f"Graph updated successfully with {len(channel_values)} channels")
        # Return: fig, cached fig, timestamps, close popover, enable button, restore button text
        return fig, Serverside(fig), timestamps, False, False, "Update Graph"

    @app.callback(
        Output("graph-channel-list", "children", allow_duplicate=True),
        Input("selected-channels", "data"),
        State("available-channels", "data"),
        State("available-events", "data"),
        State("selected-events", "data"),
        prevent_initial_call=True,
    )
    def populate_channel_list_from_selection(
        selected_channels, available_channels, available_events, selected_events
    ):
        """Populate the channel list UI based on selected channels and events."""
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

        # CHANNELS header with "+ Add" link
        channels_header = dbc.ListGroupItem(
            dbc.Row(
                [
                    dbc.Col(
                        html.Span(
                            "CHANNELS",
                            className="fw-bold",
                            style={
                                "textTransform": "uppercase",
                                "letterSpacing": "0.05em",
                                "fontSize": "11px",
                                "color": "white",
                            },
                        ),
                    ),
                    dbc.Col(
                        html.Button(
                            "+ Add",
                            id="add-graph-btn",
                            n_clicks=0,
                            className="btn-link",
                            style={
                                "fontSize": "11px",
                                "textDecoration": "none",
                            },
                        ),
                        width="auto",
                    ),
                ],
                align="center",
                className="g-2",
            ),
            className="py-2",
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
                                n_clicks=0,
                            ),
                            width="auto",
                        ),
                    ],
                    align="center",
                    className="g-2",
                ),
            )
            channel_rows.append(channel_row)

        # Build events section
        events_section = []
        if available_events:
            # Create signal dropdown options from currently selected channels
            # Use shorter display labels for the dropdown
            signal_options = []
            for ch in selected_channels:
                # Create shorter label by removing common prefixes
                short_label = ch.replace("signal_data_", "").replace(
                    "derived_data_", ""
                )
                signal_options.append({"label": short_label, "value": ch})

            # Build a lookup for selected events state
            selected_events_lookup = {}
            if selected_events:
                for ev in selected_events:
                    selected_events_lookup[ev["event_key"]] = ev

            # Events section header with helper text
            events_header = dbc.ListGroupItem(
                html.Div(
                    [
                        html.Span(
                            "EVENTS",
                            className="fw-bold",
                            style={
                                "textTransform": "uppercase",
                                "letterSpacing": "0.05em",
                                "fontSize": "11px",
                                "color": "white",
                            },
                        )
                    ]
                ),
                className="py-2 border-top mt-2",
            )
            events_section.append(events_header)

            # Create row for each event type
            for event_info in available_events:
                event_key = event_info["event_key"]
                event_color = event_info.get("color", "#95a5a6")
                event_count = event_info.get("count", 0)
                is_point = event_info.get("is_point_event", True)
                event_type_label = "point" if is_point else "state"

                # Get current selection state for this event
                event_selection = selected_events_lookup.get(
                    event_key,
                    {
                        "enabled": False,
                        "signal": selected_channels[0] if selected_channels else "",
                    },
                )

                # Truncate long event names
                display_name = (
                    event_key[:20] + "..." if len(event_key) > 20 else event_key
                )

                event_row = dbc.ListGroupItem(
                    [
                        # First row: checkbox + event name
                        dbc.Row(
                            [
                                dbc.Col(
                                    dbc.Checkbox(
                                        id={"type": "event-checkbox", "key": event_key},
                                        value=event_selection.get("enabled", False),
                                    ),
                                    width="auto",
                                    className="pe-0",
                                ),
                                dbc.Col(
                                    html.Div(
                                        [
                                            html.Span(
                                                "●",
                                                style={
                                                    "color": event_color,
                                                    "marginRight": "6px",
                                                },
                                            ),
                                            html.Span(
                                                display_name,
                                                title=f"{event_key} ({event_count} {event_type_label} events)",
                                                style={
                                                    "fontWeight": "500",
                                                    "color": "white",
                                                },
                                            ),
                                            html.Span(
                                                f" ({event_count})",
                                                className="text-muted",
                                                style={
                                                    "fontSize": "11px",
                                                    "paddingLeft": "4px",
                                                },
                                            ),
                                        ],
                                        style={
                                            "display": "flex",
                                            "alignItems": "center",
                                        },
                                    ),
                                    className="ps-1",
                                ),
                            ],
                            align="center",
                            className="g-0",
                        ),
                        # Second row: signal selector (only show if enabled)
                        html.Div(
                            dbc.Row(
                                [
                                    dbc.Col(
                                        html.Span(
                                            "Show on:",
                                            className="text-muted",
                                            style={"fontSize": "11px"},
                                        ),
                                        width="auto",
                                        className="pe-2",
                                    ),
                                    dbc.Col(
                                        dbc.Select(
                                            id={
                                                "type": "event-signal",
                                                "key": event_key,
                                            },
                                            options=signal_options,
                                            value=event_selection.get(
                                                "signal",
                                                selected_channels[0]
                                                if selected_channels
                                                else "",
                                            ),
                                            size="sm",
                                        ),
                                    ),
                                ],
                                align="center",
                                className="g-0 mt-1 ps-4",
                            ),
                        ),
                    ],
                    className="py-2",
                )
                events_section.append(event_row)
        else:
            # No events available message
            events_section.append(
                dbc.ListGroupItem(
                    html.Div(
                        [
                            html.Span(
                                "EVENTS",
                                className="fw-bold d-block mb-1",
                                style={
                                    "textTransform": "uppercase",
                                    "letterSpacing": "0.05em",
                                    "fontSize": "11px",
                                },
                            ),
                            html.Span(
                                "No events available for this deployment",
                                className="text-muted fst-italic",
                                style={"fontSize": "12px"},
                            ),
                        ]
                    ),
                    className="py-2 border-top mt-2",
                )
            )

        # Update Graph button at the bottom (applies to both channels and events)
        update_button_row = dbc.ListGroupItem(
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Button(
                            "Update Graph",
                            color="success",
                            className="btn-xs w-100",
                            id="update-graph-btn",
                        ),
                    ),
                ],
                align="center",
                className="g-2",
            ),
            className="border-top mt-2 pt-3",
        )

        return [channels_header] + channel_rows + events_section + [update_button_row]

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

    # Update timeline bounds when user zooms on graph
    @app.callback(
        Output("timeline-bounds", "data", allow_duplicate=True),
        Input("graph-content", "relayoutData"),
        State("playback-timestamps", "data"),
        prevent_initial_call=True,
    )
    def update_timeline_bounds_on_zoom(relayoutdata, timestamps):
        """Update timeline bounds when user zooms on the graph."""
        from datetime import datetime, timezone

        if not relayoutdata or not timestamps:
            raise dash.exceptions.PreventUpdate

        # Get original bounds for reset detection
        min_ts = min(timestamps)
        max_ts = max(timestamps)

        # Check for zoom reset (autorange or "All" button)
        if relayoutdata.get("xaxis.autorange") or relayoutdata.get("xaxis.showspikes"):
            # Reset to original bounds
            logger.debug("Zoom reset detected, restoring original timeline bounds")
            return {"min": min_ts, "max": max_ts}

        # Extract zoom range from relayoutData
        # Plotly sends ISO date strings like "2019-11-08T12:00:00.000" or with "Z" suffix
        x0 = relayoutdata.get("xaxis.range[0]")
        x1 = relayoutdata.get("xaxis.range[1]")

        if x0 is None or x1 is None:
            raise dash.exceptions.PreventUpdate

        # Convert ISO strings to Unix timestamps
        try:
            if isinstance(x0, str):
                # Remove 'Z' suffix if present for consistent parsing
                x0_clean = x0.replace("Z", "")
                x1_clean = x1.replace("Z", "")

                # Parse as datetime (may be naive or aware)
                dt0 = datetime.fromisoformat(x0_clean)
                dt1 = datetime.fromisoformat(x1_clean)

                # If naive (no timezone), treat as UTC to match Plotly's behavior
                if dt0.tzinfo is None:
                    dt0 = dt0.replace(tzinfo=timezone.utc)
                if dt1.tzinfo is None:
                    dt1 = dt1.replace(tzinfo=timezone.utc)

                new_min = dt0.timestamp()
                new_max = dt1.timestamp()
            else:
                # Already numeric (shouldn't happen with date axes, but just in case)
                new_min = float(x0)
                new_max = float(x1)

            logger.debug(
                f"Timeline bounds updated: {new_min:.2f} - {new_max:.2f} "
                f"(range: {(new_max - new_min) / 3600:.2f} hours)"
            )
            return {"min": new_min, "max": new_max}

        except Exception as e:
            logger.warning(f"Failed to parse zoom range: {e}")
            raise dash.exceptions.PreventUpdate

    # =========================================================================
    # Reset Zoom Callback (Home button)
    # =========================================================================

    @app.callback(
        Output("timeline-bounds", "data", allow_duplicate=True),
        Output("graph-content", "figure", allow_duplicate=True),
        Output("figure-store", "data", allow_duplicate=True),
        Output("playback-timestamps", "data", allow_duplicate=True),
        Input("reset-zoom-button", "n_clicks"),
        State("selected-channels", "data"),
        State("selected-dataset", "data"),
        State("selected-deployment", "data"),
        State("available-channels", "data"),
        State("all-datasets-deployments", "data"),
        prevent_initial_call=True,
    )
    def reset_zoom_to_original(
        n_clicks,
        selected_channels,
        dataset,
        deployment_data,
        available_channels,
        datasets_with_deployments,
    ):
        """Reset graph zoom by regenerating the graph with full dataset bounds from DuckPond."""
        if not n_clicks:
            raise dash.exceptions.PreventUpdate

        if not selected_channels or not dataset or not deployment_data:
            logger.warning("Cannot reset zoom: missing channel/dataset/deployment data")
            raise dash.exceptions.PreventUpdate

        try:
            # Get deployment details
            deployment_id = deployment_data["deployment"]
            animal_id = deployment_data["animal"]

            # Find full deployment data for sample_count and date range
            deployments_list = datasets_with_deployments.get(dataset, [])
            selected_deployment = None
            for dep in deployments_list:
                if dep["deployment"] == deployment_id and dep["animal"] == animal_id:
                    selected_deployment = dep
                    break

            if not selected_deployment:
                logger.error(f"Could not find deployment {deployment_id} in datasets")
                raise dash.exceptions.PreventUpdate

            # Get timezone offset from DuckPond (with caching)
            timezone_offset = duck_pond.get_deployment_timezone_offset(
                deployment_id, use_cache=use_cache
            )

            # Build date range from deployment metadata (from DuckPond)
            min_dt = pd.to_datetime(selected_deployment["min_date"])
            max_dt = pd.to_datetime(selected_deployment["max_date"])
            date_range = {
                "start": min_dt.isoformat(),
                "end": max_dt.isoformat(),
            }

            logger.info(
                f"Regenerating graph with full dataset bounds: {date_range['start']} to {date_range['end']}"
            )

            # Regenerate the graph with NO zoom range (full dataset)
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
                events_df=None,  # Skip events for simple reset
                selected_events=[],  # No event overlays
                zoom_range=None,  # No zoom - show full range
            )

            # Calculate original bounds from timestamps
            original_bounds = (
                {"min": timestamps[0], "max": timestamps[-1]} if timestamps else None
            )

            logger.info("Graph regenerated successfully with full dataset bounds")

            return (
                original_bounds,  # Reset timeline-bounds to full range
                fig,  # New figure
                Serverside(fig),  # Cache the new FigureResampler
                timestamps,  # Updated timestamps
            )

        except Exception as e:
            logger.error(f"Error regenerating graph: {e}", exc_info=True)
            raise dash.exceptions.PreventUpdate

    # =========================================================================
    # Event Save Callback (B-key bookmark feature)
    # =========================================================================

    @app.callback(
        Output("event-modal", "is_open", allow_duplicate=True),
        Output("last-event-type", "data"),
        Output("available-events", "data", allow_duplicate=True),
        Output("event-refresh-trigger", "data"),  # Trigger graph refresh
        Output("event-toast", "is_open"),  # Show success toast
        Output("event-toast", "children"),  # Toast message
        Input("save-event-btn", "n_clicks"),
        State("event-type-select", "value"),
        State("new-event-type-input", "value"),
        State("pending-event-time", "data"),
        State("event-end-time", "value"),
        State("event-short-description", "value"),
        State("event-long-description", "value"),
        State("selected-dataset", "data"),
        State("selected-deployment", "data"),
        State("available-events", "data"),
        State("event-refresh-trigger", "data"),  # Current trigger value
        prevent_initial_call=True,
    )
    def save_event(
        n_clicks,
        event_type_value,
        new_event_type,
        pending_time,
        end_time_str,
        short_description,
        long_description,
        selected_dataset,
        selected_deployment,
        available_events,
        current_refresh_trigger,
    ):
        """Save an event to the Iceberg events table."""
        if not n_clicks:
            raise dash.exceptions.PreventUpdate

        # Validate required data
        if not selected_dataset or not selected_deployment:
            logger.warning("Cannot save event: no dataset or deployment selected")
            raise dash.exceptions.PreventUpdate

        if not pending_time:
            logger.warning("Cannot save event: no pending time")
            raise dash.exceptions.PreventUpdate

        # Determine the event key
        if event_type_value == "__create_new__":
            if not new_event_type or not new_event_type.strip():
                logger.warning("Cannot save event: new event type name is empty")
                raise dash.exceptions.PreventUpdate
            event_key = new_event_type.strip()
        else:
            if not event_type_value:
                logger.warning("Cannot save event: no event type selected")
                raise dash.exceptions.PreventUpdate
            event_key = event_type_value

        # Parse start time
        # Use utcfromtimestamp because the timestamp was created from a datetime
        # that already had the timezone offset applied (for display purposes).
        # Using fromtimestamp would incorrectly apply the server's local timezone.
        try:
            datetime_start = pd.Timestamp.utcfromtimestamp(pending_time)
        except Exception as e:
            logger.error(f"Failed to parse start time: {e}")
            raise dash.exceptions.PreventUpdate

        # Parse end time (if provided)
        datetime_end = None
        if end_time_str and end_time_str.strip():
            try:
                # Try parsing as a datetime string
                datetime_end = pd.to_datetime(end_time_str.strip())
            except Exception as e:
                logger.warning(f"Failed to parse end time '{end_time_str}': {e}")
                # Continue with point event

        # Get deployment and animal info
        deployment_id = selected_deployment.get("deployment", "")
        animal_id = selected_deployment.get("animal", "")

        if not deployment_id or not animal_id:
            logger.error("Missing deployment or animal ID")
            raise dash.exceptions.PreventUpdate

        # Get timezone offset to convert from local display time back to UTC
        # The playhead-time is in local time (after timezone offset was applied for display)
        # We need to subtract the offset to get back to UTC for storage in Iceberg
        try:
            timezone_offset = duck_pond.get_deployment_timezone_offset(
                deployment_id, use_cache=use_cache
            )
            datetime_start = datetime_start - pd.Timedelta(hours=timezone_offset)
            if datetime_end is not None:
                datetime_end = datetime_end - pd.Timedelta(hours=timezone_offset)
            logger.debug(
                f"Converted to UTC: {datetime_start} (timezone offset: {timezone_offset:+.1f}h)"
            )
        except Exception as e:
            logger.warning(f"Could not get timezone offset, storing as-is: {e}")

        # Write the event to Iceberg
        try:
            duck_pond.write_event(
                dataset=selected_dataset,
                deployment=deployment_id,
                animal=animal_id,
                event_key=event_key,
                datetime_start=datetime_start,
                datetime_end=datetime_end,
                short_description=short_description if short_description else None,
                long_description=long_description if long_description else None,
            )
            logger.info(
                f"Successfully created event '{event_key}' at {datetime_start} (UTC)"
            )
        except Exception as e:
            logger.error(f"Failed to write event to Iceberg: {e}")
            raise dash.exceptions.PreventUpdate

        # Update available_events if this is a new event type
        updated_events = available_events or []
        if not any(e.get("event_key") == event_key for e in updated_events):
            # Add the new event type
            new_event = {
                "event_key": event_key,
                "color": "#808080",  # Default gray color
                "is_point_event": datetime_end is None,
                "count": 1,
            }
            updated_events = updated_events + [new_event]
            logger.info(f"Added new event type '{event_key}' to available events")

        # Increment refresh trigger to cause graph update
        new_refresh_trigger = (current_refresh_trigger or 0) + 1

        # Format success message for toast
        toast_message = f"Event '{event_key}' saved successfully"

        return (
            False,  # Close modal
            event_key,  # Update last-event-type for next use
            updated_events,  # Update available-events
            new_refresh_trigger,  # Trigger graph refresh to show new event
            True,  # Show success toast
            toast_message,  # Toast message content
        )
