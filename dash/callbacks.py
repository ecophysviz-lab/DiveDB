"""
Server-side callback functions for the DiveDB data visualization dashboard.
"""

import bisect
import dash
from dash import Output, Input, State, callback_context, ALL
from datetime import datetime
from logging_config import get_logger

logger = get_logger(__name__)


def find_nearest_timestamp(timestamps, target):
    """
    Find the nearest timestamp to the target using binary search.

    O(log n) complexity vs O(n) for pd.Series approach.

    Args:
        timestamps: Sorted list of timestamps
        target: Target timestamp to find nearest match for

    Returns:
        The timestamp from the list closest to target
    """
    if not timestamps:
        return target

    n = len(timestamps)

    # Handle edge cases
    if target <= timestamps[0]:
        return timestamps[0]
    if target >= timestamps[-1]:
        return timestamps[-1]

    # Binary search for insertion point
    idx = bisect.bisect_left(timestamps, target)

    # Check which neighbor is closer
    if idx == 0:
        return timestamps[0]
    if idx == n:
        return timestamps[-1]

    before = timestamps[idx - 1]
    after = timestamps[idx]

    if (target - before) <= (after - target):
        return before
    return after


def parse_video_duration(duration_str):
    """Parse video duration from HH:MM:SS.mmm format to total seconds."""
    if not duration_str:
        return 0
    try:
        time_parts = duration_str.split(":")
        if len(time_parts) == 3:
            hours = int(time_parts[0])
            minutes = int(time_parts[1])
            seconds = float(time_parts[2])
            return hours * 3600 + minutes * 60 + seconds
    except (ValueError, IndexError):
        pass
    return 0


def parse_video_created_time(created_at_str):
    """Parse video creation timestamp from ISO format to Unix timestamp."""
    if not created_at_str:
        return 0
    try:
        # Handle both 'Z' and '+00:00' timezone formats
        created_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        return created_dt.timestamp()
    except (ValueError, TypeError):
        return 0


def calculate_video_overlap(video, playhead_time, time_offset=0):
    """Calculate how much a video overlaps with the playhead time.

    Args:
        video: Video metadata dict
        playhead_time: Current playhead timestamp
        time_offset: Time offset in seconds to apply to video timing

    Returns:
        dict: {
            'overlaps': bool,
            'overlap_duration': float (seconds),
            'video_start': float (timestamp),
            'video_end': float (timestamp),
            'adjusted_video_start': float (timestamp),
            'adjusted_video_end': float (timestamp)
        }
    """
    original_video_start_time = parse_video_created_time(video.get("fileCreatedAt"))
    duration_seconds = parse_video_duration(
        video.get("metadata", {}).get("duration", "0")
    )
    original_video_end_time = original_video_start_time + duration_seconds

    # Apply time offset (positive offset = video appears later)
    adjusted_video_start_time = original_video_start_time + time_offset
    adjusted_video_end_time = adjusted_video_start_time + duration_seconds

    # Check if playhead falls within adjusted video timerange
    overlaps = adjusted_video_start_time <= playhead_time <= adjusted_video_end_time

    # Calculate overlap duration (for tie-breaking when multiple videos overlap)
    if overlaps:
        # For simplicity, we'll use the distance from video start as a proxy for "best match"
        # Closer to video start = better match
        overlap_duration = playhead_time - adjusted_video_start_time
    else:
        overlap_duration = 0

    return {
        "overlaps": overlaps,
        "overlap_duration": overlap_duration,
        "video_start": original_video_start_time,
        "video_end": original_video_end_time,
        "adjusted_video_start": adjusted_video_start_time,
        "adjusted_video_end": adjusted_video_end_time,
    }


def find_best_overlapping_video(video_options, playhead_time, time_offset=0):
    """Find the best video that overlaps with the playhead time.

    Args:
        video_options: List of video metadata dicts
        playhead_time: Current playhead timestamp
        time_offset: Time offset in seconds to apply to video timing

    Selection priority:
    1. Video with greatest overlap (closest to start time)
    2. If tie, return first video in list
    """
    overlapping_videos = []

    for video in video_options:
        overlap_info = calculate_video_overlap(video, playhead_time, time_offset)
        if overlap_info["overlaps"]:
            overlapping_videos.append((video, overlap_info))

    if not overlapping_videos:
        return None

    # Sort by overlap_duration (ascending - closer to start is better)
    # Then by list order (stable sort maintains original order for ties)
    overlapping_videos.sort(key=lambda x: x[1]["overlap_duration"])

    return overlapping_videos[0][0]  # Return the video (not the tuple)


def register_callbacks(app, dff, video_options=None, channel_options=None):
    """Register all server-side callbacks with the given app instance."""

    @app.callback(
        Output("main-layout", "className"),
        Input("right-top-toggle", "n_clicks"),
        Input("right-bottom-toggle", "n_clicks"),
        Input("left-toggle", "n_clicks"),
        Input("right-toggle", "n_clicks"),
        State("main-layout", "className"),
    )
    def toggle_layout_panels(
        right_top_clicks,
        right_bottom_clicks,
        left_clicks,
        right_clicks,
        current_className,
    ):
        """Toggle various layout panels (sidebars, expanded views)."""
        if not callback_context.triggered:
            return current_className or "default-layout"

        changed_id = [p["prop_id"] for p in callback_context.triggered][0]

        # Parse current class states
        current_classes = (
            (current_className or "default-layout").split()
            if current_className
            else ["default-layout"]
        )

        # Ensure base class is always present
        if "default-layout" not in current_classes:
            current_classes.append("default-layout")

        # Determine which layout to toggle
        target_layout = None
        if "right-top-toggle" in changed_id:
            target_layout = "right-top-expanded"
        elif "right-bottom-toggle" in changed_id:
            target_layout = "right-bottom-expanded"
        elif "left-toggle" in changed_id:
            target_layout = "left-sidebar-hidden"
        elif "right-toggle" in changed_id:
            target_layout = "right-sidebar-hidden"

        # Toggle the specific layout class independently
        if target_layout:
            if target_layout in current_classes:
                # Remove the class (toggle off)
                current_classes.remove(target_layout)
            else:
                # Add the class (toggle on)
                current_classes.append(target_layout)

        return " ".join(current_classes)

    # NOTE: update_video_preview moved to clientside callback for performance
    # See clientside_callbacks.py - eliminates server round-trip on every playhead tick
    # @app.callback(
    #     Output("video-trimmer", "playheadTime"),
    #     Output("video-trimmer", "isPlaying"),
    #     Output("video-trimmer", "playbackRate"),
    #     Input("playhead-time", "data"),
    #     Input("is-playing", "data"),
    #     Input("playback-rate", "data"),
    # )
    # def update_video_preview(playhead_time, is_playing, playback_rate):
    #     """Update the video preview component with current playhead time, playing state, and rate."""
    #     return playhead_time, is_playing, playback_rate or 1

    # NOTE: 3D model update moved to clientside callback for performance
    # See clientside_callbacks.py - eliminates server round-trip on every playhead tick
    # @app.callback(
    #     Output("three-d-model", "activeTime"),
    #     [Input("playhead-time", "data")],
    #     State("playback-timestamps", "data"),
    # )
    # def update_active_time(playhead_time, timestamps):
    #     """Update the 3D model's active time based on playhead position."""
    #     if not timestamps:
    #         raise dash.exceptions.PreventUpdate
    #     # Find the nearest timestamp using O(log n) binary search
    #     nearest_timestamp_seconds = find_nearest_timestamp(timestamps, playhead_time)
    #     # Convert to milliseconds for JavaScript
    #     nearest_timestamp_ms = nearest_timestamp_seconds * 1000
    #     return nearest_timestamp_ms

    # NOTE: toggle_play_pause moved to clientside callback for performance
    # See clientside_callbacks.py - eliminates server round-trip on play/pause
    # @app.callback(
    #     Output("is-playing", "data"),
    #     Output("play-button", "children"),
    #     Output("play-button", "className"),
    #     Input("play-button", "n_clicks"),
    #     State("is-playing", "data"),
    # )
    # def toggle_play_pause(n_clicks, is_playing):
    #     """Toggle play/pause state and update button text and styling."""
    #     if n_clicks % 2 == 1:
    #         # Playing state - show pause button
    #         return True, "Pause", "btn btn-primary btn-round btn-pause btn-lg"
    #     else:
    #         # Paused state - show play button
    #         return False, "Play", "btn btn-primary btn-round btn-play btn-lg"

    # NOTE: These callbacks have been moved to clientside for zero server round-trips
    # during play/pause. See clientside_callbacks.py for the implementations.
    #
    # @app.callback(Output("interval-component", "disabled"), Input("is-playing", "data"))
    # def update_interval_component(is_playing):
    #     """Enable/disable the interval component based on play state."""
    #     return not is_playing  # Interval is disabled when not playing
    #
    # @app.callback(
    #     Output("play-button-tooltip", "children"),
    #     Input("is-playing", "data"),
    # )
    # def update_play_button_tooltip(is_playing):
    #     """Update play button tooltip based on playing state."""
    #     return "Pause" if is_playing else "Play"

    # NOTE: Playback rate cycling, skip navigation, and tooltips have been moved to
    # clientside callbacks for zero server round-trips. See clientside_callbacks.py.
    # Only the display button content remains server-side (requires html.Img component).

    # Update playback rate display button when rate changes
    # This remains server-side because it needs to create html.Img components
    # The tooltip is handled by a separate clientside callback
    @app.callback(
        Output("playback-rate-display", "children"),
        Input("playback-rate", "data"),
    )
    def update_playback_rate_display(playback_rate):
        """Update the playback rate display button text."""
        from dash import html

        rate = playback_rate or 1
        # Format rate display: show decimal for fractional rates, integer for whole numbers
        rate_str = f"{rate}×" if rate < 1 else f"{int(rate)}×"
        return [
            rate_str,
            html.Img(src="/assets/images/speed.svg"),
        ]

    # NOTE: The playhead update is now handled by a clientside callback that reads
    # from the JavaScript playback manager (window.DiveDBPlayback). This is registered
    # in clientside_callbacks.py as update_playhead_from_interval_clientside.
    # The original server-side callback is commented out below for reference.
    #
    # @app.callback(
    #     Output("playhead-time", "data"),
    #     Input("interval-component", "n_intervals"),
    #     State("is-playing", "data"),
    #     State("playback-timestamps", "data"),
    #     State("playhead-time", "data"),
    #     State("playback-rate", "data"),
    #     prevent_initial_call=True,
    # )
    # def update_playhead_from_interval(
    #     n_intervals, is_playing, timestamps, current_time, playback_rate
    # ):
    #     """Update playhead time based on interval timer and playback rate."""
    #     if not is_playing or not timestamps:
    #         raise dash.exceptions.PreventUpdate
    #     playback_rate = playback_rate or 1
    #     target_time = current_time + playback_rate
    #     min_time = timestamps[0]
    #     max_time = timestamps[-1]
    #     if target_time > max_time:
    #         new_time = min_time
    #     else:
    #         new_time = find_nearest_timestamp(timestamps, target_time)
    #     return new_time
    pass  # Placeholder to maintain code structure

    # NOTE: Slider → playhead-time sync is handled by clientside callback
    # to avoid race conditions with the interval-based playhead updates

    # TODO: Re-enable this callback after refactoring to avoid duplicate outputs
    # This conflicts with the load_visualization callback in selection_callbacks.py
    # @app.callback(
    #     Output("graph-content", "figure"),
    #     Input("playhead-time", "data"),
    #     State("graph-content", "figure"),
    # )
    # def update_graph_playhead(playhead_timestamp, existing_fig):
    #     """Update the graph with a vertical line showing current playhead position."""
    #     playhead_time = pd.to_datetime(playhead_timestamp, unit="s")
    #     existing_fig["layout"]["shapes"] = []
    #     existing_fig["layout"]["shapes"].append(
    #         dict(
    #             type="line",
    #             x0=playhead_time,
    #             x1=playhead_time,
    #             y0=0,
    #             y1=1,
    #             xref="x",
    #             yref="paper",
    #             line=dict(color="#73a9c4", width=2, dash="solid"),
    #         )
    #     )
    #     existing_fig["layout"]["uirevision"] = "constant"
    #     return existing_fig

    # Video manual selection callback using pattern-matching for video indicators
    # NOTE: Auto-selection based on playhead time is now handled by a clientside callback
    # in clientside_callbacks.py for performance. This callback only handles manual clicks.
    @app.callback(
        Output("selected-video", "data", allow_duplicate=True),
        Output("manual-video-override", "data", allow_duplicate=True),
        [
            Input({"type": "video-indicator", "id": ALL}, "n_clicks"),
        ],
        [
            State("current-video-options", "data"),
            State({"type": "video-indicator", "id": ALL}, "id"),
        ],
        prevent_initial_call=True,
    )
    def video_manual_selection(
        n_clicks_list,
        video_options,
        video_ids,
    ):
        """Handle manual video selection when user clicks a video indicator."""
        ctx = callback_context

        # Debug: Log callback entry
        logger.debug("video_manual_selection triggered:")
        logger.debug(f"  - ctx.triggered: {ctx.triggered}")
        logger.debug(f"  - n_clicks_list: {n_clicks_list}")
        logger.debug(f"  - video_ids: {video_ids}")
        logger.debug(
            f"  - video_options count: {len(video_options) if video_options else 0}"
        )

        if not video_options:
            logger.debug("  - PreventUpdate: no video_options")
            raise dash.exceptions.PreventUpdate

        # Check if this was triggered by a manual click
        clicked_video = None

        for trigger in ctx.triggered:
            if "video-indicator" in trigger["prop_id"] and trigger.get("value"):
                # Extract the clicked video ID from the trigger
                import json

                trigger_id = json.loads(trigger["prop_id"].split(".")[0])
                clicked_video_id = trigger_id["id"]

                # Find the corresponding video in video_options
                for vid in video_options:
                    if vid.get("id") == clicked_video_id:
                        clicked_video = vid
                        break

                if not clicked_video:
                    logger.warning(
                        f"No matching video found for ID: {clicked_video_id}"
                    )
                break

        if clicked_video:
            # Manual selection - set both selected video and manual override
            logger.debug(f"  - Manual selection: {clicked_video.get('filename')}")
            return clicked_video, clicked_video
        else:
            # No valid click detected
            logger.debug("  - PreventUpdate: no valid click")
            raise dash.exceptions.PreventUpdate

    @app.callback(
        Output("playhead-time", "data", allow_duplicate=True),
        Output("is-playing", "data", allow_duplicate=True),
        Output("play-button", "children", allow_duplicate=True),
        Output("play-button", "className", allow_duplicate=True),
        [
            Input({"type": "video-indicator", "id": ALL}, "n_clicks"),
        ],
        [
            State("current-video-options", "data"),
            State({"type": "video-indicator", "id": ALL}, "id"),
            State("video-time-offset", "data"),
        ],
        prevent_initial_call=True,
    )
    def jump_to_video_on_click(
        n_clicks_list,
        video_options,
        video_ids,
        time_offset,
    ):
        """Jump playhead to video start time and start playback when video indicator is clicked."""
        ctx = callback_context

        # Debug: Log callback entry
        logger.debug("jump_to_video_on_click triggered:")
        logger.debug(f"  - ctx.triggered: {ctx.triggered}")
        logger.debug(f"  - n_clicks_list: {n_clicks_list}")
        logger.debug(f"  - video_ids: {video_ids}")
        logger.debug(
            f"  - video_options count: {len(video_options) if video_options else 0}"
        )

        if not video_options or not ctx.triggered:
            logger.debug("  - PreventUpdate: no video_options or no trigger")
            raise dash.exceptions.PreventUpdate

        time_offset = time_offset or 0

        # Check if this was triggered by a video indicator click
        clicked_video = None
        for trigger in ctx.triggered:
            logger.debug(f"  - Checking trigger: {trigger}")
            if "video-indicator" in trigger["prop_id"] and trigger.get("value"):
                # Extract the clicked video ID from the trigger
                import json

                trigger_id = json.loads(trigger["prop_id"].split(".")[0])
                clicked_video_id = trigger_id["id"]
                logger.debug(
                    f"  - Extracted video ID: {clicked_video_id} (type: {type(clicked_video_id)})"
                )

                # Find the corresponding video in video_options
                video_option_ids = [vid.get("id") for vid in video_options]
                logger.debug(f"  - Available video IDs in options: {video_option_ids}")

                for vid in video_options:
                    if vid.get("id") == clicked_video_id:
                        clicked_video = vid
                        logger.debug(f"  - Found matching video: {vid.get('filename')}")
                        break

                if clicked_video:
                    break
            else:
                logger.debug(
                    "  - Trigger not a video-indicator click or value is falsy"
                )

        if not clicked_video:
            logger.debug("  - PreventUpdate: no clicked_video found")
            raise dash.exceptions.PreventUpdate

        # Calculate the video start time
        video_start_time = parse_video_created_time(clicked_video.get("fileCreatedAt"))

        # Apply time offset to get the adjusted start time
        adjusted_video_start = video_start_time + time_offset

        logger.info(
            f"Jumping to video start: {clicked_video.get('filename')} at {adjusted_video_start}"
        )

        # Return: new playhead time, playing=True, button text="Pause", button class
        return (
            adjusted_video_start,
            True,
            "Pause",
            "btn btn-primary btn-round btn-pause btn-lg",
        )

    @app.callback(
        Output("video-trimmer", "videoSrc"),
        Output("video-trimmer", "videoMetadata"),
        Output("video-trimmer", "datasetStartTime"),
        Input("selected-video", "data"),
    )
    def update_video_player(selected_video):
        """Update VideoPreview component with selected video and metadata."""
        # Always provide dataset start time for temporal alignment
        dataset_start_time = dff["timestamp"].min()

        if selected_video:
            video_url = selected_video.get("shareUrl") or selected_video.get(
                "originalUrl"
            )

            # Extract relevant metadata for temporal alignment
            video_metadata = {
                "fileCreatedAt": selected_video.get("fileCreatedAt"),
                "duration": selected_video.get("metadata", {}).get("duration"),
                "filename": selected_video.get("filename"),
            }

            return video_url, video_metadata, dataset_start_time

        return "", None, dataset_start_time

    @app.callback(
        Output("video-time-offset", "data"),
        Input("video-trimmer", "timeOffset"),
        prevent_initial_call=True,
    )
    def update_video_offset_store(time_offset):
        """Update the video time offset store when component changes."""
        return time_offset or 0

    @app.callback(
        Output("graph-channel-list", "children"),
        Input("add-graph-btn", "n_clicks"),
        State("graph-channel-list", "children"),
        State("available-channels", "data"),
        prevent_initial_call=True,
    )
    def add_new_channel(n_clicks, current_children, available_channels):
        """Add a new channel selection row when Add Graph button is clicked.

        New structure:
        - Index 0: CHANNELS header (contains "+ Add" button)
        - Indices 1 to N: Channel rows (have channel-select pattern-matching IDs)
        - Events section (after channels)
        - Last item: Update Graph button
        """
        if not n_clicks:
            raise dash.exceptions.PreventUpdate

        # Import necessary components (needed for dynamic creation)
        import dash_bootstrap_components as dbc
        from dash import html

        def get_props(obj):
            """Get props from either a dict or a Dash component."""
            if isinstance(obj, dict):
                return obj.get("props", {})
            elif hasattr(obj, "props"):
                return obj.props
            return {}

        def find_channel_select_index(child):
            """Find channel-select index in a child, if it exists. Returns None if not a channel row."""
            try:
                props = get_props(child)
                children = props.get("children")
                if children is None:
                    return None

                # Handle Row structure
                row_props = get_props(children)
                cols = row_props.get("children", [])
                if not isinstance(cols, list):
                    cols = [cols]

                for col in cols:
                    col_props = get_props(col)
                    col_children = col_props.get("children")
                    if col_children is None:
                        continue

                    # Check if this is a select with channel-select type
                    element_props = get_props(col_children)
                    element_id = element_props.get("id")
                    if (
                        isinstance(element_id, dict)
                        and element_id.get("type") == "channel-select"
                    ):
                        return element_id.get("index", 0)
            except (TypeError, AttributeError, KeyError):
                pass
            return None

        # Count existing channel rows and find the highest index
        channel_indices = []
        last_channel_position = 0  # Position after header (index 0)

        for i, child in enumerate(current_children):
            idx = find_channel_select_index(child)
            if idx is not None:
                last_channel_position = i
                channel_indices.append(idx)

        # New channel ID is max existing + 1 (or 1 if no channels)
        new_channel_id = max(channel_indices, default=0) + 1

        # Convert channel_options to dropdown format - ONLY GROUPS
        dropdown_options = []
        if available_channels:
            for option in available_channels:
                if isinstance(option, dict):
                    # Handle DuckPond channel metadata format
                    kind = option.get("kind")
                    # Only show groups, not individual variables
                    if kind == "group":
                        # Group - use group name as value, label as display
                        group_name = option.get("group")
                        display_label = option.get("label") or group_name
                        dropdown_options.append(
                            {"label": display_label, "value": group_name}
                        )
                else:
                    # Handle string format (fallback)
                    dropdown_options.append(
                        {"label": str(option), "value": str(option).lower()}
                    )
        else:
            # Fallback options if available_channels is None (all groups)
            dropdown_options = [
                {"label": "Depth", "value": "depth"},
                {"label": "Pitch, roll, heading", "value": "prh"},
                {"label": "Temperature", "value": "temperature"},
                {"label": "Light", "value": "light"},
            ]

        new_channel_row = dbc.ListGroupItem(
            dbc.Row(
                [
                    dbc.Col(
                        html.Button(
                            html.Img(
                                src="/assets/images/drag.svg",
                                className="drag-icon",
                            ),
                            className="btn btn-icon-only btn-sm",
                            id={"type": "channel-drag", "index": new_channel_id},
                        ),
                        width="auto",
                        className="drag-handle",
                    ),
                    dbc.Col(
                        dbc.Select(
                            options=dropdown_options,
                            value=(
                                dropdown_options[0]["value"]
                                if dropdown_options
                                else "depth"
                            ),
                            id={"type": "channel-select", "index": new_channel_id},
                        ),
                    ),
                    dbc.Col(
                        html.Button(
                            html.Img(
                                src="/assets/images/remove.svg",
                                className="remove-icon",
                            ),
                            className="btn btn-icon-only btn-sm",
                            id={"type": "channel-remove", "index": new_channel_id},
                            n_clicks=0,
                        ),
                        width="auto",
                    ),
                ],
                align="center",
                className="g-2",
            ),
        )

        # Insert after the last channel row
        # Structure: [header, ...channels, ...events, update_button]
        insert_position = last_channel_position + 1
        new_children = (
            current_children[:insert_position]
            + [new_channel_row]
            + current_children[insert_position:]
        )

        return new_children

    @app.callback(
        Output("graph-channel-list", "children", allow_duplicate=True),
        [Input({"type": "channel-remove", "index": ALL}, "n_clicks")],
        State("graph-channel-list", "children"),
        prevent_initial_call=True,
    )
    def remove_channel(remove_clicks, current_children):
        """Remove a channel selection row when remove button is clicked."""
        import json

        # Filter out None values and check if any button was actually clicked
        valid_clicks = [c for c in remove_clicks if c is not None and c > 0]
        if not valid_clicks:
            raise dash.exceptions.PreventUpdate

        ctx = callback_context
        if not ctx.triggered:
            raise dash.exceptions.PreventUpdate

        # Find which remove button was clicked
        clicked_button = ctx.triggered[0]["prop_id"]

        # Extract the channel ID from the button ID
        button_info = json.loads(clicked_button.split(".")[0])
        channel_to_remove = button_info["index"]

        logger.debug(f"Remove channel triggered for index: {channel_to_remove}")

        def get_props(obj):
            """Get props from either a dict or a Dash component."""
            if isinstance(obj, dict):
                return obj.get("props", {})
            elif hasattr(obj, "props"):
                return obj.props
            return {}

        def find_channel_remove_id(child):
            """Find channel-remove button ID in a child, if it exists."""
            try:
                props = get_props(child)
                children = props.get("children")
                if children is None:
                    return None

                # Handle Row structure
                row_props = get_props(children)
                cols = row_props.get("children", [])
                if not isinstance(cols, list):
                    cols = [cols]

                for col in cols:
                    col_props = get_props(col)
                    col_children = col_props.get("children")
                    if col_children is None:
                        continue

                    # Check if this is a button with channel-remove type
                    button_props = get_props(col_children)
                    button_id = button_props.get("id")
                    if (
                        isinstance(button_id, dict)
                        and button_id.get("type") == "channel-remove"
                    ):
                        return button_id
            except (TypeError, AttributeError, KeyError):
                pass
            return None

        # Count current channel rows
        channel_count = sum(
            1 for child in current_children if find_channel_remove_id(child) is not None
        )

        logger.debug(f"Current channel count: {channel_count}")

        # Don't allow removal if only one channel remains
        if channel_count <= 1:
            logger.debug("Cannot remove - only one channel remains")
            raise dash.exceptions.PreventUpdate

        # Filter out the channel to remove
        new_children = []
        for child in current_children:
            button_id = find_channel_remove_id(child)
            if button_id is not None and button_id.get("index") == channel_to_remove:
                logger.debug(f"Removing channel with index: {channel_to_remove}")
                continue  # Skip this child (remove it)
            new_children.append(child)

        logger.debug(
            f"Returning {len(new_children)} children (was {len(current_children)})"
        )
        return new_children

    # Client-side callback to handle drag and drop reordering
    app.clientside_callback(
        """
        function(children) {
            // Initialize drag and drop whenever the channel list changes
            setTimeout(function() {
                if (typeof initializeDragDrop === 'function') {
                    initializeDragDrop();
                } else {
                    // If function not loaded yet, try again
                    setTimeout(function() {
                        if (typeof initializeDragDrop === 'function') {
                            initializeDragDrop();
                        }
                    }, 500);
                }
            }, 100);
            return window.dash_clientside.no_update;
        }
        """,
        Output("graph-channel-list", "id"),  # Dummy output to trigger callback
        Input("graph-channel-list", "children"),
        prevent_initial_call=False,
    )

    # Clientside callback to read channel order from DOM when Update Graph is clicked
    # This captures the visual order after drag-drop reordering
    app.clientside_callback(
        """
        function(n_clicks) {
            if (!n_clicks) {
                return window.dash_clientside.no_update;
            }
            
            // Read channel values in their current DOM order
            const channelList = document.getElementById('graph-channel-list');
            if (!channelList) {
                return [];
            }
            
            const channelOrder = [];
            const listItems = channelList.querySelectorAll('.list-group-item');
            
            listItems.forEach((item) => {
                // Find select element (channel dropdown)
                const select = item.querySelector('select');
                if (select && select.id && select.id.includes('channel-select')) {
                    channelOrder.push(select.value);
                }
            });
            
            console.log('Read channel order from DOM:', channelOrder);
            return channelOrder;
        }
        """,
        Output("channel-order-from-dom", "data"),
        Input("update-graph-btn", "n_clicks"),
        prevent_initial_call=True,
    )

    # Clientside callback to show loading state on Update Graph button immediately
    # The server callback will restore the button when processing completes
    app.clientside_callback(
        """
        function(n_clicks) {
            if (!n_clicks) {
                return [window.dash_clientside.no_update, window.dash_clientside.no_update];
            }
            // Immediately show loading state
            return [true, "Updating..."];
        }
        """,
        Output("update-graph-btn", "disabled"),
        Output("update-graph-btn", "children"),
        Input("update-graph-btn", "n_clicks"),
        prevent_initial_call=True,
    )

    # =========================================================================
    # Event Modal Callbacks (B-key bookmark feature)
    # =========================================================================

    @app.callback(
        Output("event-modal", "is_open"),
        Output("event-start-time", "value"),
        Output("event-type-select", "options"),
        Output("event-type-select", "value"),
        Output("pending-event-time", "data"),
        Output("new-event-type-container", "style"),
        Output("new-event-type-input", "value"),
        Output("event-end-time", "value"),
        Output("event-short-description", "value"),
        Output("event-long-description", "value"),
        Input("bookmark-trigger", "value"),
        Input("save-button", "n_clicks"),  # Bookmark button in timeline
        Input("cancel-event-btn", "n_clicks"),
        State("playhead-time", "data"),
        State("last-event-type", "data"),
        State("available-events", "data"),
        State("selected-deployment", "data"),
        State("event-modal", "is_open"),
        prevent_initial_call=True,
    )
    def handle_event_modal_open(
        bookmark_trigger,
        save_button_clicks,
        cancel_clicks,
        playhead_time,
        last_event_type,
        available_events,
        selected_deployment,
        is_open,
    ):
        """Handle opening/closing the event modal on B key press, save button click, or cancel."""
        ctx = callback_context
        if not ctx.triggered:
            return (
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
            )

        triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # Handle cancel button
        if triggered_id == "cancel-event-btn":
            return (
                False,  # Close modal
                "",  # Clear start time
                dash.no_update,  # Keep options
                dash.no_update,  # Keep selected value
                None,  # Clear pending time
                {"display": "none"},  # Hide new event type input
                "",  # Clear new event type input
                "",  # Clear end time
                "",  # Clear short description
                "",  # Clear long description
            )

        # Handle B key press (bookmark-trigger) or save button click
        if (triggered_id == "bookmark-trigger" and bookmark_trigger) or (
            triggered_id == "save-button" and save_button_clicks
        ):
            # Don't open if no deployment selected
            if not selected_deployment:
                logger.warning("Cannot create event: no deployment selected")
                return (
                    dash.no_update,
                    dash.no_update,
                    dash.no_update,
                    dash.no_update,
                    dash.no_update,
                    dash.no_update,
                    dash.no_update,
                    dash.no_update,
                    dash.no_update,
                    dash.no_update,
                )

            # Build dropdown options from available events
            options = []
            if available_events:
                for event in available_events:
                    event_key = event.get("event_key", "")
                    if event_key:
                        options.append({"label": event_key, "value": event_key})

            # Add "Create new..." option at the end
            options.append(
                {"label": "➕ Create new event type...", "value": "__create_new__"}
            )

            # Determine which value to pre-select
            selected_value = None
            if last_event_type and any(
                opt["value"] == last_event_type for opt in options
            ):
                selected_value = last_event_type
            elif options and len(options) > 1:
                # Select first actual event type (not "Create new")
                selected_value = options[0]["value"]

            # Format the start time for display
            # Use utcfromtimestamp because the timestamp was created from a datetime
            # that already had the timezone offset applied (for display purposes).
            # Using fromtimestamp would incorrectly apply the server's local timezone.
            if playhead_time:
                try:
                    dt = datetime.utcfromtimestamp(playhead_time)
                    formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                except Exception:
                    formatted_time = str(playhead_time)
            else:
                formatted_time = "Unknown"

            return (
                True,  # Open modal
                formatted_time,  # Start time display
                options,  # Dropdown options
                selected_value,  # Pre-selected value
                playhead_time,  # Store pending time
                {"display": "none"},  # Hide new event type input initially
                "",  # Clear new event type input
                "",  # Clear end time
                "",  # Clear short description
                "",  # Clear long description
            )

        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
        )

    @app.callback(
        Output("new-event-type-container", "style", allow_duplicate=True),
        Input("event-type-select", "value"),
        prevent_initial_call=True,
    )
    def toggle_new_event_type_input(selected_value):
        """Show/hide the new event type input based on dropdown selection."""
        if selected_value == "__create_new__":
            return {"display": "block"}
        return {"display": "none"}

    @app.callback(
        Output("channel-order", "data"),
        Input("graph-channel-list", "children"),
        prevent_initial_call=True,
    )
    def update_channel_order(children):
        """Update the channel order store when the channel list changes."""
        if not children:
            return []

        def get_props(obj):
            """Get props from either a dict or a Dash component."""
            if isinstance(obj, dict):
                return obj.get("props", {})
            elif hasattr(obj, "props"):
                return obj.props
            return {}

        order = []
        for i, child in enumerate(children):
            try:
                props = get_props(child)
                row_children = props.get("children")
                if row_children is None:
                    continue

                row_props = get_props(row_children)
                cols = row_props.get("children", [])
                if not isinstance(cols, list):
                    cols = [cols]

                for col in cols:
                    col_props = get_props(col)
                    col_children = col_props.get("children")
                    if col_children is None:
                        continue

                    element_props = get_props(col_children)
                    element_id = element_props.get("id")

                    # Handle dict pattern-matching IDs
                    if (
                        isinstance(element_id, dict)
                        and element_id.get("type") == "channel-select"
                    ):
                        order.append(
                            {
                                "id": element_id.get("index"),
                                "index": i,
                                "value": element_props.get("value", ""),
                            }
                        )
                        break
                    # Legacy: handle string IDs (fallback)
                    elif isinstance(element_id, str) and "-select" in element_id:
                        channel_id = element_id.replace("-select", "")
                        order.append(
                            {
                                "id": channel_id,
                                "index": i,
                                "value": element_props.get("value", ""),
                            }
                        )
                        break
            except (TypeError, AttributeError, KeyError):
                continue

        return order
