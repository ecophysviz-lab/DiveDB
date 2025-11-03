"""
Server-side callback functions for the DiveDB data visualization dashboard.
"""
import dash
from dash import Output, Input, State, callback_context, ALL
import pandas as pd
from datetime import datetime


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
        Input("playhead-time", "data"),
        Input("is-playing", "data"),
    )
    def update_video_preview(playhead_time, is_playing):
        """Update the video preview component with current playhead time and playing state."""
        return playhead_time, is_playing

    @app.callback(
        Output("three-d-model", "activeTime"), [Input("playhead-slider", "value")]
    )
    def update_active_time(slider_value):
        """Update the 3D model's active time based on slider position."""
        # Find the nearest datetime to the slider value
        nearest_idx = dff["timestamp"].sub(slider_value).abs().idxmin()
        return nearest_idx

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

    @app.callback(
        Output("playhead-time", "data"),
        Output("playhead-slider", "value"),
        Input("interval-component", "n_intervals"),
        Input("playhead-slider", "value"),
        State("is-playing", "data"),
        prevent_initial_call=True,
    )
    def update_playhead(n_intervals, slider_value, is_playing):
        """Update playhead time based on interval timer or manual slider input."""
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

    @app.callback(
        Output("graph-content", "figure"),
        Input("playhead-time", "data"),
        State("graph-content", "figure"),
    )
    def update_graph_playhead(playhead_timestamp, existing_fig):
        """Update the graph with a vertical line showing current playhead position."""
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
                line=dict(color="#73a9c4", width=2, dash="solid"),
            )
        )
        existing_fig["layout"]["uirevision"] = "constant"
        return existing_fig

    # Add video selection callback if video options are available
    if video_options:
        # Create inputs for all video indicators
        video_ids = [f"video-{video.get('id', 'unknown')}" for video in video_options]

        video_inputs = [Input(vid, "n_clicks") for vid in video_ids]

        @app.callback(
            Output("selected-video", "data"),
            Output("manual-video-override", "data"),
            [Input("playhead-time", "data")] + video_inputs,
            [
                State("selected-video", "data"),
                State("manual-video-override", "data"),
                State("video-time-offset", "data"),
            ],
        )
        def video_selection_manager(playhead_time, *args):
            """Manage both auto and manual video selection with proper priority."""
            # Extract states from args (manual clicks are unused but required for callback signature)
            manual_override = args[-2]  # Current manual override state
            time_offset = args[-1] or 0  # Current time offset (default to 0 if None)

            ctx = callback_context

            # Check if this was triggered by a manual click
            manual_click_triggered = False
            clicked_video = None

            for trigger in ctx.triggered:
                if trigger["prop_id"] != "playhead-time.data" and trigger.get("value"):
                    manual_click_triggered = True
                    clicked_id = trigger["prop_id"].split(".")[0]

                    # Extract video ID from button ID (format: "video-{video_id}")
                    video_button_id = clicked_id.replace("video-", "")

                    # Find the corresponding video in video_options
                    for vid in video_options:
                        if vid.get("id") == video_button_id:
                            clicked_video = vid
                            break

                    if not clicked_video:
                        print(f"⚠️ No matching video found for ID: {video_button_id}")
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
                    print(
                        f"🤖 No overlapping video found (offset: {time_offset}s) - clearing selection"
                    )
                    return None, None  # Clear both selection and manual override

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
        prevent_initial_call=True,
    )
    def add_new_channel(n_clicks, current_children):
        """Add a new channel selection row when Add Graph button is clicked."""
        if not n_clicks:
            raise dash.exceptions.PreventUpdate
        
        # Get current number of channels to create unique IDs
        channel_count = len([child for child in current_children if hasattr(child, 'props') and 
                           child.props.get('children') and 
                           child.props['children'].props.get('children') and
                           any('channel-' in str(col.props.get('children', {}).get('props', {}).get('id', '')) 
                               for col in child.props['children'].props['children'] 
                               if hasattr(col, 'props'))])
        
        new_channel_id = channel_count + 1
        
        # Import necessary components (needed for dynamic creation)
        import dash_bootstrap_components as dbc
        from dash import html
        
        # Convert channel_options to dropdown format
        dropdown_options = []
        if channel_options:
            for option in channel_options:
                if isinstance(option, dict):
                    # Handle dictionary format - check for non-None values
                    label = option.get('label') or option.get('group')
                    value = option.get('group')
                    dropdown_options.append({"label": label, "value": value})
                else:
                    # Handle string format
                    dropdown_options.append({"label": str(option), "value": str(option).lower()})
        else:
            # Fallback options if channel_options is None
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
                            value=dropdown_options[0]["value"],
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
                        ),
                        width="auto",
                    ),
                ],
                align="center",
                className="g-2",
            ),
        )
        
        # Insert the new row before the "Add Graph" button (which should be the last item)
        new_children = current_children[:-1] + [new_channel_row] + [current_children[-1]]
        
        return new_children

    @app.callback(
        Output("graph-channel-list", "children", allow_duplicate=True),
        [Input({"type": "channel-remove", "index": ALL}, "n_clicks")],
        State("graph-channel-list", "children"),
        prevent_initial_call=True,
    )
    def remove_channel(remove_clicks, current_children):
        """Remove a channel selection row when remove button is clicked."""
        if not any(remove_clicks):
            raise dash.exceptions.PreventUpdate
        
        ctx = callback_context
        if not ctx.triggered:
            raise dash.exceptions.PreventUpdate
        
        # Find which remove button was clicked
        clicked_button = ctx.triggered[0]["prop_id"]
        
        # Extract the channel ID from the button ID
        import json
        button_info = json.loads(clicked_button.split('.')[0])
        channel_to_remove = button_info["index"]
        
        # Count current channel rows (excluding the "Add Graph" button)
        channel_count = 0
        for child in current_children:
            if hasattr(child, 'props') and child.props.get('children'):
                row = child.props['children']
                if hasattr(row, 'props') and row.props.get('children'):
                    for col in row.props['children']:
                        if hasattr(col, 'props') and col.props.get('children'):
                            button = col.props['children']
                            if hasattr(button, 'props') and button.props.get('id'):
                                button_id = button.props['id']
                                if isinstance(button_id, dict) and button_id.get('type') == 'channel-remove':
                                    channel_count += 1
                                    break
        
        # Don't allow removal if only one channel remains
        if channel_count <= 1:
            raise dash.exceptions.PreventUpdate
        
        # Filter out the channel to remove by checking IDs
        new_children = []
        for child in current_children:
            should_keep = True
            if hasattr(child, 'props') and child.props.get('children'):
                row = child.props['children']
                if hasattr(row, 'props') and row.props.get('children'):
                    for col in row.props['children']:
                        if hasattr(col, 'props') and col.props.get('children'):
                            button = col.props['children']
                            if hasattr(button, 'props') and button.props.get('id'):
                                button_id = button.props['id']
                                if isinstance(button_id, dict) and button_id.get('type') == 'channel-remove' and button_id.get('index') == channel_to_remove:
                                    should_keep = False
                                    break
            
            if should_keep:
                new_children.append(child)
        
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
        prevent_initial_call=False
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
        
        order = []
        for i, child in enumerate(children):
            if hasattr(child, 'props') and child.props.get('children'):
                row = child.props['children']
                if hasattr(row, 'props') and row.props.get('children'):
                    for col in row.props['children']:
                        if hasattr(col, 'props') and col.props.get('children'):
                            element = col.props['children']
                            if hasattr(element, 'props') and element.props.get('id'):
                                element_id = element.props['id']
                                # Look for channel select elements
                                if isinstance(element_id, str) and '-select' in element_id:
                                    channel_id = element_id.replace('-select', '')
                                    order.append({
                                        'id': channel_id,
                                        'index': i,
                                        'value': element.props.get('value', '')
                                    })
                                    break
        
        return order
