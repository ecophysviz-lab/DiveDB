"""
Client-side callback functions for the DiveDB data visualization dashboard.
"""
from dash import Output, Input, State


def register_clientside_callbacks(app):
    """Register all client-side callbacks with the given app instance."""
    # Fullscreen toggle functionality
    app.clientside_callback(
        """
        function(n_clicks) {
            if (n_clicks && n_clicks > 0) {
                if (!document.fullscreenElement) {
                    // Enter fullscreen
                    document.documentElement.requestFullscreen().catch(err => {
                        console.log(`Error attempting to enable fullscreen: ${err.message}`);
                    });
                } else {
                    // Exit fullscreen
                    document.exitFullscreen().catch(err => {
                        console.log(`Error attempting to exit fullscreen: ${err.message}`);
                    });
                }
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("fullscreen-button", "id", allow_duplicate=True),
        [Input("fullscreen-button", "n_clicks")],
        prevent_initial_call=True,
    )

    # Update button class and content based on fullscreen state
    app.clientside_callback(
        """
        function(n_clicks) {
            // Set up fullscreen change listener if not already set
            if (!window.fullscreenListenerSet) {
                document.addEventListener('fullscreenchange', function() {
                    const button = document.getElementById('fullscreen-button');
                    const tooltip = document.getElementById('fullscreen-tooltip');
                    if (document.fullscreenElement) {
                        // In fullscreen mode - use minimize class
                        button.className = 'btn btn-icon-only btn-icon-minimize';
                        // button.innerHTML = 'Minimize';
                        if (tooltip && tooltip._tippy) {
                            tooltip._tippy.setContent('Enter Fullscreen');
                        }
                    } else {
                        // Not in fullscreen mode - use fullscreen class
                        button.className = 'btn btn-icon-only btn-icon-fullscreen';
                        // button.innerHTML = 'Expand';
                        if (tooltip && tooltip._tippy) {
                            tooltip._tippy.setContent('Exit Fullscreen');
                        }
                    }
                });
                window.fullscreenListenerSet = true;
            }

            // Return appropriate class name based on current state
            return document.fullscreenElement ?
                'btn btn-icon-only btn-icon-minimize' :
                'btn btn-icon-only btn-icon-fullscreen';
        }
        """,
        Output("fullscreen-button", "className"),
        [Input("fullscreen-button", "n_clicks")],
        prevent_initial_call=False,
    )

    # Update button text (currently commented out in original)
    app.clientside_callback(
        """
        function(n_clicks) {
            //return document.fullscreenElement ? "Minimize" : "Expand";
        }
        """,
        Output("fullscreen-button", "children"),
        [Input("fullscreen-button", "n_clicks")],
        prevent_initial_call=False,
    )

    # Update tooltip content based on fullscreen state
    app.clientside_callback(
        """
        function(n_clicks) {
            return document.fullscreenElement ? "Enter Fullscreen" : "Exit Fullscreen";
        }
        """,
        Output("fullscreen-tooltip", "children"),
        [Input("fullscreen-button", "n_clicks")],
        prevent_initial_call=False,
    )

    # Bidirectional sync between playhead-time store and playhead-slider
    # Sync playhead-time → slider (programmatic updates from interval)
    app.clientside_callback(
        """
        function(playhead_time, slider_value) {
            // Only update if playhead-time changed significantly
            // This prevents updating when slider is being manually dragged
            if (Math.abs(playhead_time - slider_value) > 0.01) {
                return playhead_time;
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("playhead-slider", "value"),
        [Input("playhead-time", "data")],
        [State("playhead-slider", "value")],
        prevent_initial_call=True,
    )

    # Sync slider → playhead-time (manual drags)
    app.clientside_callback(
        """
        function(slider_value, playhead_time) {
            // Only update if user manually changed slider
            // Check if slider value differs from current playhead-time
            if (Math.abs(slider_value - playhead_time) > 0.01) {
                return slider_value;
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("playhead-time", "data", allow_duplicate=True),
        [Input("playhead-slider", "value")],
        [State("playhead-time", "data")],
        prevent_initial_call=True,
    )

    # Playhead tracking line on graph
    # This callback draws a vertical line on the graph that follows the playhead position
    app.clientside_callback(
        """
        function(playhead_time, existing_fig) {
            // Prevent update if no valid data
            if (!playhead_time || !existing_fig) {
                return window.dash_clientside.no_update;
            }
            
            // Convert playhead timestamp (seconds) to milliseconds
            const playhead_ms = playhead_time * 1000;
            
            // Create Date object and convert to ISO string
            const playhead_date = new Date(playhead_ms);
            const playhead_iso = playhead_date.toISOString();
            
            // Clone the existing figure to avoid mutation
            const updated_fig = {...existing_fig};
            
            // Ensure layout exists
            if (!updated_fig.layout) {
                updated_fig.layout = {};
            }
            
            // Update shapes with vertical line at playhead position
            updated_fig.layout.shapes = [{
                type: 'line',
                x0: playhead_iso,
                x1: playhead_iso,
                y0: 0,
                y1: 1,
                xref: 'x',
                yref: 'paper',
                line: {
                    color: '#73a9c4',
                    width: 2,
                    dash: 'solid'
                }
            }];
            
            // Preserve UI state (zoom, pan, etc.)
            updated_fig.layout.uirevision = 'constant';
            
            return updated_fig;
        }
        """,
        Output("graph-content", "figure", allow_duplicate=True),
        [Input("playhead-time", "data")],
        [State("graph-content", "figure")],
        prevent_initial_call=True,
    )

    # Arrow key navigation (0.1s steps)
    # The arrow-key-navigation.js file updates the hidden arrow-key-input with direction
    # This callback responds to that input and updates playhead-time accordingly
    app.clientside_callback(
        """
        function(arrowInput, playhead_time, timestamps, slider_min, slider_max) {
            // Check if this is a valid arrow key input
            if (!arrowInput || arrowInput === '') {
                return window.dash_clientside.no_update;
            }
            
            // Parse the input - format is "direction:timestamp" (e.g., "1:1699123456.789")
            const parts = arrowInput.split(':');
            if (parts.length !== 2) {
                return window.dash_clientside.no_update;
            }
            
            const direction = parseInt(parts[0]);
            const inputTimestamp = parseFloat(parts[1]);
            
            // Verify this is a new input (not a stale one)
            if (isNaN(direction) || isNaN(inputTimestamp)) {
                return window.dash_clientside.no_update;
            }
            
            const STEP = 1;  // 1 second step
            
            // Get bounds
            const minTime = slider_min || (timestamps && timestamps.length > 0 ? Math.min(...timestamps) : 0);
            const maxTime = slider_max || (timestamps && timestamps.length > 0 ? Math.max(...timestamps) : Infinity);
            
            // Calculate new time
            let newTime = playhead_time + (direction * STEP);
            
            // Clamp to bounds
            newTime = Math.max(minTime, Math.min(maxTime, newTime));
            
            console.log('Arrow key navigation:', direction > 0 ? 'forward' : 'backward', 
                        playhead_time.toFixed(3), '->', newTime.toFixed(3));
            
            return newTime;
        }
        """,
        Output("playhead-time", "data", allow_duplicate=True),
        [Input("arrow-key-input", "value")],
        [
            State("playhead-time", "data"),
            State("playback-timestamps", "data"),
            State("playhead-slider", "min"),
            State("playhead-slider", "max"),
        ],
        prevent_initial_call=True,
    )
