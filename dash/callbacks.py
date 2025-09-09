"""
Server-side callback functions for the DiveDB data visualization dashboard.
"""
import dash
from dash import Output, Input, State, callback_context
import pandas as pd


def register_callbacks(app, dff):
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
        Input("play-button", "n_clicks"),
        State("is-playing", "data"),
    )
    def toggle_play_pause(n_clicks, is_playing):
        """Toggle play/pause state and update button text."""
        if n_clicks % 2 == 1:
            return True, "Pause"  # Switch to playing
        else:
            return False, "Play"  # Switch to paused

    @app.callback(Output("interval-component", "disabled"), Input("is-playing", "data"))
    def update_interval_component(is_playing):
        """Enable/disable the interval component based on play state."""
        return not is_playing  # Interval is disabled when not playing

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
