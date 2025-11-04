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

    # TODO: Re-enable playhead visualization once duplicate callback issue is resolved
    # For now, playhead updates are disabled to avoid conflicts with load_visualization callback
