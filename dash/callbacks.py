"""
Server-side callback functions for the DiveDB data visualization dashboard.
"""

import dash
from dash import Output, Input, State, callback_context, ALL
from datetime import datetime
import pandas as pd
from logging_config import get_logger

logger = get_logger(__name__)


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
        Output("modal", "is_open"),
        [Input("save-button", "n_clicks"), Input("close", "n_clicks")],
        [State("modal", "is_open")],
    )
    def toggle_modal(n1, n2, is_open):
        """Toggle the bookmark modal open/closed state."""
        if n1 or n2:
            return not is_open
        return is_open

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

    @app.callback(
        Output("video-trimmer", "playheadTime"),
        Output("video-trimmer", "isPlaying"),
        Output("video-trimmer", "playbackRate"),
        Input("playhead-time", "data"),
        Input("is-playing", "data"),
        Input("playback-rate", "data"),
    )
    def update_video_preview(playhead_time, is_playing, playback_rate):
        """Update the video preview component with current playhead time, playing state, and rate."""
        return playhead_time, is_playing, playback_rate or 1

    @app.callback(
        Output("three-d-model", "activeTime"),
        [Input("playhead-time", "data")],
        State("playback-timestamps", "data"),
    )
    def update_active_time(playhead_time, timestamps):
        """Update the 3D model's active time based on playhead position."""
        if not timestamps:
            raise dash.exceptions.PreventUpdate
        # Find the nearest timestamp (not index!) to the playhead time
        timestamps_series = pd.Series(timestamps)
        nearest_idx = timestamps_series.sub(playhead_time).abs().idxmin()
        # Return the actual timestamp value, not the index
        # Convert to milliseconds for JavaScript
        nearest_timestamp_seconds = timestamps[nearest_idx]
        nearest_timestamp_ms = nearest_timestamp_seconds * 1000
        return nearest_timestamp_ms

    @app.callback(
        Output("is-playing", "data"),
        Output("play-button", "children"),
        Output("play-button", "className"),
        Input("play-button", "n_clicks"),
        State("is-playing", "data"),
    )
    def toggle_play_pause(n_clicks, is_playing):
        """Toggle play/pause state and update button text and styling."""
        if n_clicks % 2 == 1:
            # Playing state - show pause button
            return True, "Pause", "btn btn-primary btn-round btn-pause btn-lg"
        else:
            # Paused state - show play button
            return False, "Play", "btn btn-primary btn-round btn-play btn-lg"

    @app.callback(Output("interval-component", "disabled"), Input("is-playing", "data"))
    def update_interval_component(is_playing):
        """Enable/disable the interval component based on play state."""
        return not is_playing  # Interval is disabled when not playing

    @app.callback(
        Output("play-button-tooltip", "children"),
        Input("is-playing", "data"),
    )
    def update_play_button_tooltip(is_playing):
        """Update play button tooltip based on playing state."""
        return "Pause" if is_playing else "Play"

    # Playback rate cycling: Forward increases rate, Rewind decreases rate
    # Available rates: 0.1, 0.5, 1, 5, 10, 100 (supports sub-second playback)
    PLAYBACK_RATES = [0.1, 0.5, 1, 5, 10, 100]

    @app.callback(
        Output("playback-rate", "data"),
        Output("rewind-button-tooltip", "children"),
        Output("forward-button-tooltip", "children"),
        Input("forward-button", "n_clicks"),
        Input("rewind-button", "n_clicks"),
        State("playback-rate", "data"),
        prevent_initial_call=True,
    )
    def cycle_playback_rate(forward_clicks, rewind_clicks, current_rate):
        """Cycle playback rate when Forward/Rewind buttons are clicked.

        Forward: Increase rate (1 → 5 → 10 → 100 → 1)
        Rewind: Decrease rate (100 → 10 → 5 → 1 → 100)
        """
        ctx = callback_context
        if not ctx.triggered:
            raise dash.exceptions.PreventUpdate

        triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # Find current rate index
        try:
            current_idx = PLAYBACK_RATES.index(current_rate)
        except ValueError:
            current_idx = 0  # Default to 1x if rate not found

        if triggered_id == "forward-button":
            # Cycle up
            new_idx = (current_idx + 1) % len(PLAYBACK_RATES)
        elif triggered_id == "rewind-button":
            # Cycle down
            new_idx = (current_idx - 1) % len(PLAYBACK_RATES)
        else:
            raise dash.exceptions.PreventUpdate

        new_rate = PLAYBACK_RATES[new_idx]
        # Format rate display: show decimal for fractional rates, integer for whole numbers
        rate_str = f"{new_rate}×" if new_rate < 1 else f"{int(new_rate)}×"
        tooltip_text = f"Speed: {rate_str}"

        logger.debug(f"Playback rate changed: {current_rate}× → {new_rate}×")
        return new_rate, tooltip_text, tooltip_text

    # Update playback rate display button when rate changes
    @app.callback(
        Output("playback-rate-display", "children"),
        Output("playback-rate-tooltip", "children"),
        Input("playback-rate", "data"),
    )
    def update_playback_rate_display(playback_rate):
        """Update the playback rate display button text and tooltip."""
        from dash import html

        rate = playback_rate or 1
        # Format rate display: show decimal for fractional rates, integer for whole numbers
        rate_str = f"{rate}×" if rate < 1 else f"{int(rate)}×"
        return [
            rate_str,
            html.Img(src="/assets/images/speed.svg"),
        ], f"Current Speed: {rate_str}"

    # Skip navigation: Previous/Next buttons jump by 10x playback rate
    @app.callback(
        Output("playhead-time", "data", allow_duplicate=True),
        Output("previous-button-tooltip", "children"),
        Output("next-button-tooltip", "children"),
        Input("previous-button", "n_clicks"),
        Input("next-button", "n_clicks"),
        State("playhead-time", "data"),
        State("playback-timestamps", "data"),
        State("playback-rate", "data"),
        prevent_initial_call=True,
    )
    def skip_navigation(
        prev_clicks, next_clicks, current_time, timestamps, playback_rate
    ):
        """Skip forward/backward by 10x playback rate seconds.

        At 1x rate: skip 10 seconds
        At 100x rate: skip 1000 seconds
        """
        ctx = callback_context
        if not ctx.triggered or not timestamps:
            raise dash.exceptions.PreventUpdate

        triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # Ensure playback_rate is valid
        playback_rate = playback_rate or 1

        # Calculate skip amount: 10x playback rate
        skip_amount = 10 * playback_rate

        # Get min/max bounds
        min_time = min(timestamps)
        max_time = max(timestamps)

        if triggered_id == "next-button":
            # Skip forward
            target_time = current_time + skip_amount
        elif triggered_id == "previous-button":
            # Skip backward
            target_time = current_time - skip_amount
        else:
            raise dash.exceptions.PreventUpdate

        # Clamp to dataset bounds
        target_time = max(min_time, min(max_time, target_time))

        # Find nearest timestamp
        timestamps_series = pd.Series(timestamps)
        nearest_idx = timestamps_series.sub(target_time).abs().idxmin()
        new_time = timestamps[nearest_idx]

        # Calculate dynamic tooltip (show actual skip amount)
        if skip_amount < 1:
            # Sub-second: show milliseconds
            skip_text = f"{int(skip_amount * 1000)}ms"
        elif skip_amount < 60:
            # Less than a minute: show seconds (handle fractional)
            skip_text = f"{skip_amount}s" if skip_amount % 1 else f"{int(skip_amount)}s"
        else:
            # Minutes and seconds
            minutes = int(skip_amount // 60)
            seconds = skip_amount % 60
            skip_text = f"{minutes}m {int(seconds)}s" if seconds else f"{minutes}m"
        prev_tooltip = f"Skip Back ({skip_text})"
        next_tooltip = f"Skip Forward ({skip_text})"

        logger.debug(
            f"Skip navigation: {current_time} → {new_time} (skip={skip_amount}s)"
        )
        return new_time, prev_tooltip, next_tooltip

    @app.callback(
        Output("playhead-time", "data"),
        Input("interval-component", "n_intervals"),
        State("is-playing", "data"),
        State("playback-timestamps", "data"),
        State("playhead-time", "data"),
        State("playback-rate", "data"),
        prevent_initial_call=True,
    )
    def update_playhead_from_interval(
        n_intervals, is_playing, timestamps, current_time, playback_rate
    ):
        """Update playhead time based on interval timer and playback rate.

        Advances playhead by playback_rate seconds per interval tick.
        Finds nearest available timestamp after time advance.
        """
        logger.debug(
            f"Interval callback fired: n_intervals={n_intervals}, is_playing={is_playing}, "
            f"timestamps_len={len(timestamps) if timestamps else 0}, current_time={current_time}, rate={playback_rate}×"
        )

        if not is_playing or not timestamps:
            logger.debug("Preventing update: not playing or no timestamps")
            raise dash.exceptions.PreventUpdate

        # Ensure playback_rate is valid
        playback_rate = playback_rate or 1

        # Advance by playback_rate seconds
        target_time = current_time + playback_rate

        # Get min/max bounds
        min_time = min(timestamps)
        max_time = max(timestamps)

        # If we've reached the end, loop back to start
        if target_time > max_time:
            new_time = min_time
        else:
            # Find the nearest timestamp to the target time
            timestamps_series = pd.Series(timestamps)
            nearest_idx = timestamps_series.sub(target_time).abs().idxmin()
            new_time = timestamps[nearest_idx]

        logger.debug(
            f"Playhead advancing: current_time={current_time}, target_time={target_time}, "
            f"new_time={new_time}, rate={playback_rate}×"
        )
        return new_time

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

    # Video selection callback using pattern-matching for dynamically created video indicators
    @app.callback(
        Output("selected-video", "data"),
        Output("manual-video-override", "data"),
        [
            Input("playhead-time", "data"),
            Input({"type": "video-indicator", "id": ALL}, "n_clicks"),
        ],
        [
            State("selected-video", "data"),
            State("manual-video-override", "data"),
            State("video-time-offset", "data"),
            State("current-video-options", "data"),
            State({"type": "video-indicator", "id": ALL}, "id"),
        ],
    )
    def video_selection_manager(
        playhead_time,
        n_clicks_list,
        selected_video,
        manual_override,
        time_offset,
        video_options,
        video_ids,
    ):
        """Manage both auto and manual video selection with proper priority."""
        if not video_options:
            raise dash.exceptions.PreventUpdate

        time_offset = time_offset or 0
        ctx = callback_context

        # Check if this was triggered by a manual click
        manual_click_triggered = False
        clicked_video = None

        for trigger in ctx.triggered:
            if "video-indicator" in trigger["prop_id"] and trigger.get("value"):
                manual_click_triggered = True
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

        if manual_click_triggered and clicked_video:
            # Manual selection - this becomes the new override
            return clicked_video, clicked_video

        elif manual_override:
            # We have a manual override active - maintain it regardless of playhead
            return manual_override, manual_override

        else:
            # Auto-selection based on playhead time with offset applied
            best_video = find_best_overlapping_video(
                video_options, playhead_time, time_offset
            )

            if best_video:
                return best_video, None  # Clear manual override
            else:
                logger.debug(
                    f"No overlapping video found (offset: {time_offset}s) - clearing selection"
                )
                return None, None  # Clear both selection and manual override

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
        if not video_options or not callback_context.triggered:
            raise dash.exceptions.PreventUpdate

        time_offset = time_offset or 0
        ctx = callback_context

        # Check if this was triggered by a video indicator click
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

                if clicked_video:
                    break

        if not clicked_video:
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
                            value=dropdown_options[0]["value"]
                            if dropdown_options
                            else "depth",
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
