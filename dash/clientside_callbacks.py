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

    # =========================================================================
    # Play/Pause Toggle with Client-Side Playback Manager
    # =========================================================================
    # This callback controls the DiveDBPlayback manager for smooth playback.
    # The playback manager uses requestAnimationFrame instead of server round-trips.
    app.clientside_callback(
        """
        function(n_clicks, timestamps, playbackRate, currentTime, sliderMin) {
            // Get the playback manager
            const mgr = window.DiveDBPlayback;
            if (!mgr) {
                // Fallback to simple toggle if manager not loaded
                if (n_clicks % 2 === 1) {
                    return [true, 'Pause', 'btn btn-primary btn-round btn-pause btn-lg'];
                } else {
                    return [false, 'Play', 'btn btn-primary btn-round btn-play btn-lg'];
                }
            }
            
            // Toggle based on n_clicks parity
            if (n_clicks % 2 === 1) {
                // Starting playback - initialize and start the manager
                mgr.init(
                    timestamps || [],
                    playbackRate || 1,
                    currentTime || sliderMin || 0
                );
                mgr.start();
                return [true, 'Pause', 'btn btn-primary btn-round btn-pause btn-lg'];
            } else {
                // Stopping playback
                mgr.stop();
                return [false, 'Play', 'btn btn-primary btn-round btn-play btn-lg'];
            }
        }
        """,
        [
            Output("is-playing", "data"),
            Output("play-button", "children"),
            Output("play-button", "className"),
        ],
        [Input("play-button", "n_clicks")],
        [
            State("playback-timestamps", "data"),
            State("playback-rate", "data"),
            State("playhead-time", "data"),
            State("playhead-slider", "min"),
        ],
        prevent_initial_call=False,
    )

    # =========================================================================
    # Interval Enable/Disable (moved from server-side for zero round-trips)
    # =========================================================================
    # Enable the interval when playing, disable when paused.
    app.clientside_callback(
        """
        function(is_playing) {
            // Interval is disabled when NOT playing
            return !is_playing;
        }
        """,
        Output("interval-component", "disabled"),
        [Input("is-playing", "data")],
        prevent_initial_call=False,
    )

    # =========================================================================
    # Play Button Tooltip (moved from server-side for zero round-trips)
    # =========================================================================
    # Update tooltip text based on playing state and current playback rate.
    app.clientside_callback(
        """
        function(is_playing, playback_rate) {
            const rate = playback_rate || 1;
            const rateStr = rate < 1 ? rate + '×' : Math.floor(rate) + '×';
            const action = is_playing ? 'Pause' : 'Play';
            return action + ' (' + rateStr + ')';
        }
        """,
        Output("play-button-tooltip", "children"),
        [Input("is-playing", "data"), Input("playback-rate", "data")],
    )

    # =========================================================================
    # Playback Rate Cycling (moved from server-side for zero round-trips)
    # =========================================================================
    # Forward button cycles up: 0.1 → 0.5 → 1 → 5 → 10 → 100 → 0.1
    # Rewind button cycles down: 100 → 10 → 5 → 1 → 0.5 → 0.1 → 100
    # Tooltips are updated by a separate callback that reacts to playback-rate changes
    app.clientside_callback(
        """
        function(forward_clicks, rewind_clicks, current_rate) {
            const RATES = [0.1, 0.5, 1, 5, 10, 100];
            
            // Determine which button was clicked
            const ctx = window.dash_clientside.callback_context;
            if (!ctx || !ctx.triggered || ctx.triggered.length === 0) {
                return window.dash_clientside.no_update;
            }
            
            const triggeredId = ctx.triggered[0].prop_id.split('.')[0];
            
            // Find current rate index
            let currentIdx = RATES.indexOf(current_rate);
            if (currentIdx === -1) currentIdx = 2; // Default to 1x
            
            let newIdx;
            if (triggeredId === 'forward-button') {
                newIdx = (currentIdx + 1) % RATES.length;
            } else if (triggeredId === 'rewind-button') {
                newIdx = (currentIdx - 1 + RATES.length) % RATES.length;
            } else {
                return window.dash_clientside.no_update;
            }
            
            return RATES[newIdx];
        }
        """,
        Output("playback-rate", "data"),
        [
            Input("forward-button", "n_clicks"),
            Input("rewind-button", "n_clicks"),
        ],
        [State("playback-rate", "data")],
        prevent_initial_call=True,
    )

    # =========================================================================
    # Playback Rate Tooltip (clientside - shows current speed)
    # =========================================================================
    # Separate from the display update so tooltip is fully clientside
    app.clientside_callback(
        """
        function(playbackRate) {
            const rate = playbackRate || 1;
            const rateStr = rate < 1 ? rate + '×' : Math.floor(rate) + '×';
            return 'Current Speed: ' + rateStr;
        }
        """,
        Output("playback-rate-tooltip", "children"),
        [Input("playback-rate", "data")],
    )

    # =========================================================================
    # Rewind/Forward Tooltips Sync (show NEXT speed based on current rate)
    # =========================================================================
    # This keeps tooltips updated when rate changes from any source
    app.clientside_callback(
        """
        function(playbackRate) {
            const RATES = [0.1, 0.5, 1, 5, 10, 100];
            const rate = playbackRate || 1;
            
            let currentIdx = RATES.indexOf(rate);
            if (currentIdx === -1) currentIdx = 2; // Default to 1x
            
            const nextSlowerIdx = (currentIdx - 1 + RATES.length) % RATES.length;
            const nextFasterIdx = (currentIdx + 1) % RATES.length;
            const nextSlower = RATES[nextSlowerIdx];
            const nextFaster = RATES[nextFasterIdx];
            
            const slowerStr = nextSlower < 1 ? nextSlower + '×' : Math.floor(nextSlower) + '×';
            const fasterStr = nextFaster < 1 ? nextFaster + '×' : Math.floor(nextFaster) + '×';
            
            return ['Slower: ' + slowerStr, 'Faster: ' + fasterStr];
        }
        """,
        [
            Output("rewind-button-tooltip", "children", allow_duplicate=True),
            Output("forward-button-tooltip", "children", allow_duplicate=True),
        ],
        [Input("playback-rate", "data")],
        prevent_initial_call=False,
    )

    # =========================================================================
    # Skip Navigation (moved from server-side for zero round-trips)
    # =========================================================================
    # Previous/Next buttons skip by 10x playback rate seconds
    app.clientside_callback(
        """
        function(prev_clicks, next_clicks, current_time, timestamps, playback_rate) {
            // Determine which button was clicked
            const ctx = window.dash_clientside.callback_context;
            if (!ctx || !ctx.triggered || ctx.triggered.length === 0 || !timestamps || timestamps.length === 0) {
                return [window.dash_clientside.no_update, window.dash_clientside.no_update, window.dash_clientside.no_update];
            }
            
            const triggeredId = ctx.triggered[0].prop_id.split('.')[0];
            const rate = playback_rate || 1;
            const skipAmount = 10 * rate;
            
            const minTime = timestamps[0];
            const maxTime = timestamps[timestamps.length - 1];
            
            let targetTime;
            if (triggeredId === 'next-button') {
                targetTime = current_time + skipAmount;
            } else if (triggeredId === 'previous-button') {
                targetTime = current_time - skipAmount;
            } else {
                return [window.dash_clientside.no_update, window.dash_clientside.no_update, window.dash_clientside.no_update];
            }
            
            // Clamp to bounds
            targetTime = Math.max(minTime, Math.min(maxTime, targetTime));
            
            // Binary search for nearest timestamp
            function findNearest(ts, target) {
                if (ts.length === 0) return target;
                if (target <= ts[0]) return ts[0];
                if (target >= ts[ts.length - 1]) return ts[ts.length - 1];
                
                let lo = 0, hi = ts.length - 1;
                while (lo < hi) {
                    const mid = Math.floor((lo + hi) / 2);
                    if (ts[mid] < target) lo = mid + 1;
                    else hi = mid;
                }
                
                if (lo === 0) return ts[0];
                const before = ts[lo - 1];
                const after = ts[lo];
                return (target - before) <= (after - target) ? before : after;
            }
            
            const newTime = findNearest(timestamps, targetTime);
            
            // Format tooltip text
            let skipText;
            if (skipAmount < 1) {
                skipText = Math.floor(skipAmount * 1000) + 'ms';
            } else if (skipAmount < 60) {
                skipText = (skipAmount % 1 === 0) ? Math.floor(skipAmount) + 's' : skipAmount + 's';
            } else {
                const minutes = Math.floor(skipAmount / 60);
                const seconds = skipAmount % 60;
                skipText = seconds ? minutes + 'm ' + Math.floor(seconds) + 's' : minutes + 'm';
            }
            
            return [newTime, 'Skip Back (' + skipText + ')', 'Skip Forward (' + skipText + ')'];
        }
        """,
        [
            Output("playhead-time", "data", allow_duplicate=True),
            Output("previous-button-tooltip", "children"),
            Output("next-button-tooltip", "children"),
        ],
        [
            Input("previous-button", "n_clicks"),
            Input("next-button", "n_clicks"),
        ],
        [
            State("playhead-time", "data"),
            State("playback-timestamps", "data"),
            State("playback-rate", "data"),
        ],
        prevent_initial_call=True,
    )

    # =========================================================================
    # Playhead Update from Client-Side Playback Manager (Interval-Triggered)
    # =========================================================================
    # This clientside callback is triggered by dcc.Interval and reads the current
    # playhead time from the JavaScript playback manager (window.DiveDBPlayback).
    # This hybrid approach gives us:
    # - Smooth timing from the JS requestAnimationFrame-based playback manager
    # - Reliable Dash callback triggering from dcc.Interval
    app.clientside_callback(
        """
        function(n_intervals, is_playing) {
            // Only update if playing
            if (!is_playing) {
                return window.dash_clientside.no_update;
            }
            
            // Read current time from playback manager
            const mgr = window.DiveDBPlayback;
            if (!mgr || mgr.currentTime === null || mgr.currentTime === undefined) {
                return window.dash_clientside.no_update;
            }
            
            return mgr.currentTime;
        }
        """,
        Output("playhead-time", "data"),
        [Input("interval-component", "n_intervals")],
        [State("is-playing", "data")],
        prevent_initial_call=True,
    )

    # =========================================================================
    # Playback Rate Sync to Manager
    # =========================================================================
    # When playback rate changes, sync it to the playback manager.
    app.clientside_callback(
        """
        function(playbackRate) {
            const mgr = window.DiveDBPlayback;
            if (mgr && mgr.isPlaying) {
                mgr.setPlaybackRate(playbackRate || 1);
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("playback-rate", "data", allow_duplicate=True),
        [Input("playback-rate", "data")],
        prevent_initial_call=True,
    )

    # =========================================================================
    # Playhead Time Sync to Manager
    # =========================================================================
    # When playhead-time changes from any source (skip buttons, arrow keys, etc.),
    # sync it to the playback manager so it knows the current position.
    # This prevents the manager from jumping back to an old position after a skip.
    app.clientside_callback(
        """
        function(playheadTime) {
            const mgr = window.DiveDBPlayback;
            if (mgr) {
                mgr.syncTime(playheadTime);
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("playhead-time", "data", allow_duplicate=True),
        [Input("playhead-time", "data")],
        prevent_initial_call=True,
    )

    # =========================================================================
    # Video Preview Updates (moved from server-side for performance)
    # =========================================================================
    # This eliminates a server round-trip on every playhead tick
    app.clientside_callback(
        """
        function(playhead_time, is_playing, playback_rate) {
            // Pass through values to video component
            // playback_rate defaults to 1 if not set
            return [playhead_time, is_playing, playback_rate || 1];
        }
        """,
        [
            Output("video-trimmer", "playheadTime"),
            Output("video-trimmer", "isPlaying"),
            Output("video-trimmer", "playbackRate"),
        ],
        [
            Input("playhead-time", "data"),
            Input("is-playing", "data"),
            Input("playback-rate", "data"),
        ],
        prevent_initial_call=False,
    )

    # =========================================================================
    # Video Auto-Selection (moved from server-side for performance)
    # =========================================================================
    # This handles automatic video selection when playhead moves into a video's
    # time range. Manual click handling stays on the server.
    # This eliminates a server round-trip on every playhead tick during playback.
    # IMPORTANT: We check if the video is already selected to avoid unnecessary
    # updates that would trigger the server-side update_video_player callback.
    app.clientside_callback(
        """
        function(playhead_time, manual_override, video_options, time_offset, current_selected) {
            // Helper: Parse video duration from HH:MM:SS.mmm format to seconds
            function parseVideoDuration(durationStr) {
                if (!durationStr) return 0;
                try {
                    const parts = durationStr.split(':');
                    if (parts.length === 3) {
                        const hours = parseInt(parts[0]);
                        const minutes = parseInt(parts[1]);
                        const seconds = parseFloat(parts[2]);
                        return hours * 3600 + minutes * 60 + seconds;
                    }
                } catch (e) {
                    console.error('Error parsing video duration:', e);
                }
                return 0;
            }

            // Helper: Parse ISO timestamp to Unix seconds
            function parseVideoCreatedTime(createdAtStr) {
                if (!createdAtStr) return 0;
                try {
                    return new Date(createdAtStr).getTime() / 1000;
                } catch (e) {
                    return 0;
                }
            }

            // Helper: Find best overlapping video
            function findBestOverlappingVideo(videos, playheadTime, offset) {
                let overlappingVideos = [];
                
                for (const video of videos) {
                    const videoStart = parseVideoCreatedTime(video.fileCreatedAt) + offset;
                    const duration = parseVideoDuration(video.metadata?.duration || '0');
                    const videoEnd = videoStart + duration;
                    
                    if (playheadTime >= videoStart && playheadTime <= videoEnd) {
                        const overlapDuration = playheadTime - videoStart;
                        overlappingVideos.push({video, overlapDuration});
                    }
                }
                
                if (overlappingVideos.length === 0) return null;
                
                // Sort by overlap duration (ascending - closer to start is better)
                overlappingVideos.sort((a, b) => a.overlapDuration - b.overlapDuration);
                return overlappingVideos[0].video;
            }

            // If manual override is active, don't change anything
            if (manual_override) {
                return [window.dash_clientside.no_update, window.dash_clientside.no_update];
            }

            // No video options available
            if (!video_options || video_options.length === 0) {
                return [window.dash_clientside.no_update, window.dash_clientside.no_update];
            }

            const offset = time_offset || 0;
            const bestVideo = findBestOverlappingVideo(video_options, playhead_time, offset);

            // Check if the video is already selected (compare by id)
            // This prevents unnecessary updates that would trigger server callbacks
            if (bestVideo && current_selected && bestVideo.id === current_selected.id) {
                // Same video already selected - no update needed
                return [window.dash_clientside.no_update, window.dash_clientside.no_update];
            }
            
            // Check for null → null case (no video selected, no video found)
            if (!bestVideo && !current_selected) {
                return [window.dash_clientside.no_update, window.dash_clientside.no_update];
            }

            if (bestVideo) {
                // Found overlapping video - select it, clear manual override
                return [bestVideo, null];
            } else {
                // No overlapping video - clear selection and manual override
                return [null, null];
            }
        }
        """,
        [
            Output("selected-video", "data", allow_duplicate=True),
            Output("manual-video-override", "data", allow_duplicate=True),
        ],
        [Input("playhead-time", "data")],
        [
            State("manual-video-override", "data"),
            State("current-video-options", "data"),
            State("video-time-offset", "data"),
            State(
                "selected-video", "data"
            ),  # Check current selection to avoid redundant updates
        ],
        prevent_initial_call=True,
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
    # Also syncs with the playback manager so it knows the new position
    app.clientside_callback(
        """
        function(slider_value, playhead_time) {
            // Only update if user manually changed slider
            // Check if slider value differs from current playhead-time
            if (Math.abs(slider_value - playhead_time) > 0.01) {
                // Sync with playback manager if it exists
                const mgr = window.DiveDBPlayback;
                if (mgr) {
                    mgr.syncTime(slider_value);
                }
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

    # Playhead tracking line overlay (CSS-based for performance)
    # This callback updates a CSS overlay instead of the Plotly figure
    # This avoids expensive figure re-renders on every playhead tick
    app.clientside_callback(
        """
        function(playhead_time, timeline_bounds) {
            // Prevent update if no valid data
            if (!playhead_time || !timeline_bounds || 
                timeline_bounds.min === null || timeline_bounds.max === null) {
                console.log('Playhead overlay: missing data', {playhead_time, timeline_bounds});
                return { display: 'none' };
            }
            
            // Get the Plotly graph element - need to find the actual plotly div inside
            const graphContainer = document.getElementById('graph-content');
            if (!graphContainer) {
                console.log('Playhead overlay: graph-content not found');
                return { display: 'none' };
            }
            
            // The actual Plotly div might be a child element with _fullLayout
            // In Dash, the graph component wraps the plotly div
            let graphDiv = graphContainer;
            if (!graphDiv._fullLayout) {
                // Try to find the inner plotly div
                graphDiv = graphContainer.querySelector('.js-plotly-plot') || 
                           graphContainer.querySelector('[class*="plotly"]') ||
                           graphContainer;
            }
            
            if (!graphDiv._fullLayout) {
                console.log('Playhead overlay: _fullLayout not found');
                return { display: 'none' };
            }
            
            // Get the actual plot area dimensions from Plotly's internal layout
            const layout = graphDiv._fullLayout;
            const plotArea = layout._size;  // Contains l (left), r (right), t (top), b (bottom)
            
            if (!plotArea) {
                console.log('Playhead overlay: _size not found in layout');
                return { display: 'none' };
            }
            
            // Calculate position as percentage of the timeline range
            const range = timeline_bounds.max - timeline_bounds.min;
            if (range <= 0) {
                return { display: 'none' };
            }
            
            const pct = (playhead_time - timeline_bounds.min) / range;
            
            // Clamp to valid range (0-1)
            if (pct < 0 || pct > 1) {
                return { display: 'none' };
            }
            
            // Calculate pixel position within the plot area
            // plotArea.l = left margin, plotArea.r = right margin
            const containerWidth = graphDiv.clientWidth || graphContainer.clientWidth;
            const plotWidth = containerWidth - plotArea.l - plotArea.r;
            const leftPx = plotArea.l + (pct * plotWidth);
            
            return {
                display: 'block',
                left: leftPx + 'px',
                top: plotArea.t + 'px',
                height: 'calc(100% - ' + (plotArea.t + plotArea.b) + 'px)'
            };
        }
        """,
        Output("playhead-line-overlay", "style"),
        [Input("playhead-time", "data"), Input("timeline-bounds", "data")],
        prevent_initial_call=True,
    )

    # 3D Model time update (clientside for performance)
    # This eliminates a server round-trip on every playhead tick
    # Throttled: only updates when playhead moves >= 0.5s to avoid expensive
    # Three.js re-renders on every 100ms interval tick during playback.
    app.clientside_callback(
        """
        function(playhead_time, timestamps) {
            if (!playhead_time || !timestamps || timestamps.length === 0) {
                return window.dash_clientside.no_update;
            }

            // Throttle: skip update if time changed less than 0.25s since last render
            var lastT = window._divedb_lastModelTime;
            if (lastT !== undefined && Math.abs(playhead_time - lastT) < 0.25) {
                return window.dash_clientside.no_update;
            }

            var target = playhead_time;
            var ts = timestamps;
            var n = ts.length;

            if (target <= ts[0]) {
                window._divedb_lastModelTime = ts[0];
                return ts[0] * 1000;
            }
            if (target >= ts[n - 1]) {
                window._divedb_lastModelTime = ts[n - 1];
                return ts[n - 1] * 1000;
            }

            var lo = 0, hi = n - 1;
            while (lo < hi) {
                var mid = Math.floor((lo + hi) / 2);
                if (ts[mid] < target) lo = mid + 1;
                else hi = mid;
            }

            var nearest;
            if (lo === 0) nearest = ts[0];
            else {
                var before = ts[lo - 1];
                var after = ts[lo];
                nearest = (target - before) <= (after - target) ? before : after;
            }

            window._divedb_lastModelTime = nearest;
            return nearest * 1000;
        }
        """,
        Output("three-d-model", "activeTime"),
        [Input("playhead-time", "data")],
        [State("playback-timestamps", "data")],
        prevent_initial_call=True,
    )

    # Arrow key navigation (absolute time pass-through)
    # The arrow-key-navigation.js file computes the new playhead timestamp and writes
    # "absoluteTime:uniqueTimestamp" to arrow-key-input. This callback only forwards
    # that absolute time to playhead-time to avoid stale State race conditions.
    app.clientside_callback(
        """
        function(arrowInput) {
            // Check if this is a valid arrow key input
            if (!arrowInput || arrowInput === '') {
                return window.dash_clientside.no_update;
            }

            // Parse the input - format is "absoluteTime:timestamp"
            const parts = arrowInput.split(':');
            if (parts.length !== 2) {
                return window.dash_clientside.no_update;
            }

            const absoluteTime = parseFloat(parts[0]);
            const inputTimestamp = parseFloat(parts[1]);

            // Verify this is a new input (not a stale one)
            if (isNaN(absoluteTime) || isNaN(inputTimestamp)) {
                return window.dash_clientside.no_update;
            }

            return absoluteTime;
        }
        """,
        Output("playhead-time", "data", allow_duplicate=True),
        [Input("arrow-key-input", "value")],
        prevent_initial_call=True,
    )

    # =========================================================================
    # Timeline Zoom Sync Callbacks
    # =========================================================================

    # Update timeline bounds directly on the client when graph zoom changes.
    # This avoids a server round-trip and keeps playhead/slider in sync with zoom immediately.
    app.clientside_callback(
        """
        function(relayoutdata, original_bounds) {
            if (!relayoutdata) {
                return window.dash_clientside.no_update;
            }

            const markPlayheadStale = () => {
                const overlay = document.getElementById('playhead-line-overlay');
                if (!overlay) {
                    return;
                }
                overlay.classList.add('stale');

                if (window._playheadStaleTimeout) {
                    clearTimeout(window._playheadStaleTimeout);
                }
                window._playheadStaleTimeout = setTimeout(function() {
                    const currentOverlay = document.getElementById('playhead-line-overlay');
                    if (currentOverlay) {
                        currentOverlay.classList.remove('stale');
                    }
                    window._playheadStaleTimeout = null;
                }, 3000);
            };

            const hasRange =
                relayoutdata.hasOwnProperty('xaxis.range[0]') &&
                relayoutdata.hasOwnProperty('xaxis.range[1]');
            const isReset =
                relayoutdata.hasOwnProperty('xaxis.autorange') ||
                relayoutdata.hasOwnProperty('xaxis.showspikes');

            if (!hasRange && !isReset) {
                return window.dash_clientside.no_update;
            }

            markPlayheadStale();

            if (isReset) {
                if (!original_bounds || original_bounds.min === null || original_bounds.max === null) {
                    return window.dash_clientside.no_update;
                }
                return {min: original_bounds.min, max: original_bounds.max};
            }

            const x0 = relayoutdata['xaxis.range[0]'];
            const x1 = relayoutdata['xaxis.range[1]'];

            const toUnixSeconds = (value) => {
                if (typeof value === 'number') {
                    return value;
                }
                if (typeof value !== 'string') {
                    return null;
                }

                const hasTimezone = /([zZ]|[+-]\\d{2}:\\d{2})$/.test(value);
                const isoValue = hasTimezone ? value : value + 'Z';
                const parsedMs = Date.parse(isoValue);
                if (!Number.isFinite(parsedMs)) {
                    return null;
                }
                return parsedMs / 1000;
            };

            const newMin = toUnixSeconds(x0);
            const newMax = toUnixSeconds(x1);
            if (newMin === null || newMax === null || newMax <= newMin) {
                return window.dash_clientside.no_update;
            }

            return {min: newMin, max: newMax};
        }
        """,
        Output("timeline-bounds", "data", allow_duplicate=True),
        Input("graph-content", "relayoutData"),
        State("original-bounds", "data"),
        prevent_initial_call=True,
    )

    # Update slider bounds when timeline-bounds changes (from graph zoom)
    app.clientside_callback(
        """
        function(bounds) {
            if (!bounds || bounds.min === null || bounds.max === null) {
                return [window.dash_clientside.no_update, window.dash_clientside.no_update];
            }
            console.log('Updating slider bounds:', bounds.min, '-', bounds.max);
            return [bounds.min, bounds.max];
        }
        """,
        Output("playhead-slider", "min"),
        Output("playhead-slider", "max"),
        Input("timeline-bounds", "data"),
        prevent_initial_call=True,
    )

    # Update time labels when timeline-bounds changes
    app.clientside_callback(
        """
        function(bounds) {
            if (!bounds || bounds.min === null || bounds.max === null) {
                return [window.dash_clientside.no_update, window.dash_clientside.no_update];
            }

            // Format timestamps as HH:MM:SS
            const formatTime = (ts) => {
                const date = new Date(ts * 1000);
                const hours = String(date.getUTCHours()).padStart(2, '0');
                const minutes = String(date.getUTCMinutes()).padStart(2, '0');
                const seconds = String(date.getUTCSeconds()).padStart(2, '0');
                return hours + ':' + minutes + ':' + seconds;
            };

            const startLabel = formatTime(bounds.min);
            const endLabel = formatTime(bounds.max);

            console.log('Updating time labels:', startLabel, '-', endLabel);
            return [startLabel, endLabel];
        }
        """,
        Output("timeline-start-label", "children"),
        Output("timeline-end-label", "children"),
        Input("timeline-bounds", "data"),
        prevent_initial_call=True,
    )

    # Clear stale playhead affordance when the graph figure finishes updating.
    app.clientside_callback(
        """
        function(figure) {
            if (!figure) {
                return window.dash_clientside.no_update;
            }

            const overlay = document.getElementById('playhead-line-overlay');
            if (overlay) {
                overlay.classList.remove('stale');
            }

            if (window._playheadStaleTimeout) {
                clearTimeout(window._playheadStaleTimeout);
                window._playheadStaleTimeout = null;
            }

            return window.dash_clientside.no_update;
        }
        """,
        Output("timeline-container", "className", allow_duplicate=True),
        Input("graph-content", "figure"),
        prevent_initial_call=True,
    )

    # Clamp playhead to zoomed range when bounds change
    # If playhead is outside the new bounds, jump to the start of the zoomed range
    app.clientside_callback(
        """
        function(bounds, playhead_time) {
            if (!bounds || bounds.min === null || bounds.max === null) {
                return window.dash_clientside.no_update;
            }

            // Check if playhead is outside the new bounds
            if (playhead_time < bounds.min || playhead_time > bounds.max) {
                console.log('Playhead outside zoomed range, jumping to start:',
                            playhead_time, '->', bounds.min);
                return bounds.min;
            }

            // Playhead is within bounds, no change needed
            return window.dash_clientside.no_update;
        }
        """,
        Output("playhead-time", "data", allow_duplicate=True),
        Input("timeline-bounds", "data"),
        State("playhead-time", "data"),
        prevent_initial_call=True,
    )

    # =========================================================================
    # Reset Zoom Button Enable/Disable
    # =========================================================================
    # Enable the reset zoom button when user has zoomed (timeline-bounds differs from original-bounds)
    app.clientside_callback(
        """
        function(timeline_bounds, original_bounds) {
            // If either is null/undefined, keep button disabled
            if (!timeline_bounds || !original_bounds) {
                return true;  // disabled
            }
            
            // Compare bounds with small tolerance for floating point comparison
            const tolerance = 0.001;
            const minDiff = Math.abs(timeline_bounds.min - original_bounds.min);
            const maxDiff = Math.abs(timeline_bounds.max - original_bounds.max);
            
            // If bounds are different, enable the button (return false for disabled)
            const isZoomed = minDiff > tolerance || maxDiff > tolerance;
            
            console.log('Reset zoom button:', isZoomed ? 'enabled (user has zoomed)' : 'disabled (at original bounds)');
            return !isZoomed;  // disabled = !isZoomed
        }
        """,
        Output("reset-zoom-button", "disabled"),
        Input("timeline-bounds", "data"),
        State("original-bounds", "data"),
        prevent_initial_call=True,
    )

    # =========================================================================
    # Event and Video Indicator Zoom Sync
    # =========================================================================
    # Update CSS variables on indicator containers when timeline-bounds changes
    # This repositions event and video indicators to match the zoomed view
    # Uses direct DOM manipulation since the containers may not exist initially
    app.clientside_callback(
        """
        function(bounds) {
            if (!bounds || bounds.min === null || bounds.max === null) {
                return window.dash_clientside.no_update;
            }
            
            // Update event indicators container CSS variables
            const eventContainer = document.getElementById('event-indicators-container');
            if (eventContainer) {
                eventContainer.style.setProperty('--view-min', bounds.min);
                eventContainer.style.setProperty('--view-max', bounds.max);
            }
            
            // Update video indicators container CSS variables
            const videoContainer = document.getElementById('video-indicators-container');
            if (videoContainer) {
                videoContainer.style.setProperty('--view-min', bounds.min);
                videoContainer.style.setProperty('--view-max', bounds.max);
            }
            
            console.log('Updated indicator container bounds:', bounds.min, '-', bounds.max);
            
            // Return no_update - we're modifying DOM directly
            // timeline-container is used as a dummy output since it always exists
            return window.dash_clientside.no_update;
        }
        """,
        Output("timeline-container", "className", allow_duplicate=True),
        Input("timeline-bounds", "data"),
        prevent_initial_call=True,
    )

    # =========================================================================
    # Event Modal Enter Key Submission (B-key bookmark feature)
    # =========================================================================
    # This clientside callback clicks the save button when Enter is pressed
    # in the event modal, enabling the quick B -> Enter workflow
    app.clientside_callback(
        """
        function(is_open) {
            if (!is_open) {
                // Modal closed, remove any existing listener
                if (window._eventModalKeyHandler) {
                    document.removeEventListener('keydown', window._eventModalKeyHandler);
                    window._eventModalKeyHandler = null;
                }
                return window.dash_clientside.no_update;
            }

            // Modal is open, set up Enter key listener
            if (!window._eventModalKeyHandler) {
                window._eventModalKeyHandler = function(e) {
                    // Only handle Enter key
                    if (e.key !== 'Enter') return;
                    
                    // Don't trigger if user is in the end-time input (allow multiline)
                    const activeEl = document.activeElement;
                    if (activeEl && activeEl.id === 'event-end-time') {
                        return;
                    }
                    
                    // Don't trigger if in the new event type input with empty value
                    if (activeEl && activeEl.id === 'new-event-type-input') {
                        if (!activeEl.value || !activeEl.value.trim()) {
                            return;  // Don't submit with empty new event type
                        }
                    }
                    
                    // Find and click the save button
                    const saveBtn = document.getElementById('save-event-btn');
                    if (saveBtn) {
                        e.preventDefault();
                        saveBtn.click();
                        console.log('Enter key triggered event save');
                    }
                };
                document.addEventListener('keydown', window._eventModalKeyHandler);
            }

            return window.dash_clientside.no_update;
        }
        """,
        Output("event-modal", "id"),  # Dummy output
        Input("event-modal", "is_open"),
        prevent_initial_call=True,
    )

    # =========================================================================
    # Layout Panel Toggles (moved from server-side for zero round-trips)
    # =========================================================================
    # Toggles CSS classes on main-layout to show/hide sidebars and expand panels.
    app.clientside_callback(
        """
        function(rightTopClicks, rightBottomClicks, leftClicks, rightClicks, currentClassName) {
            const ctx = window.dash_clientside.callback_context;
            if (!ctx || !ctx.triggered || ctx.triggered.length === 0) {
                return currentClassName || 'default-layout';
            }

            const classes = (currentClassName || 'default-layout').split(' ').filter(Boolean);
            if (!classes.includes('default-layout')) {
                classes.push('default-layout');
            }

            const triggeredId = ctx.triggered[0].prop_id.split('.')[0];
            const targetMap = {
                'right-top-toggle': 'right-top-expanded',
                'right-bottom-toggle': 'right-bottom-expanded',
                'left-toggle': 'left-sidebar-hidden',
                'right-toggle': 'right-sidebar-hidden'
            };
            const target = targetMap[triggeredId];
            if (target) {
                const idx = classes.indexOf(target);
                if (idx >= 0) {
                    classes.splice(idx, 1);
                } else {
                    classes.push(target);
                }
            }

            return classes.join(' ');
        }
        """,
        Output("main-layout", "className"),
        Input("right-top-toggle", "n_clicks"),
        Input("right-bottom-toggle", "n_clicks"),
        Input("left-toggle", "n_clicks"),
        Input("right-toggle", "n_clicks"),
        State("main-layout", "className"),
        prevent_initial_call=False,
    )

    # =========================================================================
    # Video Time Offset Store (moved from server-side for zero round-trips)
    # =========================================================================
    app.clientside_callback(
        """
        function(timeOffset) {
            return timeOffset || 0;
        }
        """,
        Output("video-time-offset", "data"),
        Input("video-trimmer", "timeOffset"),
        prevent_initial_call=True,
    )

    # =========================================================================
    # New Event Type Input Show/Hide (moved from server-side for zero round-trips)
    # =========================================================================
    app.clientside_callback(
        """
        function(selectedValue) {
            return selectedValue === '__create_new__'
                ? {display: 'block'}
                : {display: 'none'};
        }
        """,
        Output("new-event-type-container", "style", allow_duplicate=True),
        Input("event-type-select", "value"),
        prevent_initial_call=True,
    )

    # =========================================================================
    # Manage Channels Button Enable/Disable (moved from server-side)
    # =========================================================================
    app.clientside_callback(
        """
        function(selectedDataset) {
            return selectedDataset === null || selectedDataset === undefined;
        }
        """,
        Output("graph-channels-toggle", "disabled"),
        Input("selected-dataset", "data"),
        prevent_initial_call=False,
    )

    # =========================================================================
    # Manage Channels Popover Toggle (moved from server-side)
    # =========================================================================
    app.clientside_callback(
        """
        function(n_clicks, isOpen) {
            if (!n_clicks) {
                return window.dash_clientside.no_update;
            }
            return !isOpen;
        }
        """,
        Output("graph-channels", "is_open", allow_duplicate=True),
        Input("graph-channels-toggle", "n_clicks"),
        State("graph-channels", "is_open"),
        prevent_initial_call=True,
    )

    # =========================================================================
    # Hide Loading Overlay (moved from server-side for zero round-trips)
    # =========================================================================
    # show_loading_overlay stays server-side (uses pattern-matching ALL inputs).
    app.clientside_callback(
        """
        function(isLoading) {
            if (isLoading) {
                return window.dash_clientside.no_update;
            }
            return {
                position: 'fixed',
                top: '0',
                left: '0',
                width: '100%',
                height: '100%',
                backgroundColor: 'rgba(0, 0, 0, 0.7)',
                zIndex: '10000',
                display: 'none'
            };
        }
        """,
        Output("loading-overlay", "style", allow_duplicate=True),
        Input("is-loading-data", "data"),
        prevent_initial_call=True,
    )

    # =========================================================================
    # Playback Rate Display Text (moved from server-side for zero round-trips)
    # =========================================================================
    # The html.Img is now static in layout (timeline.py). This callback only
    # updates the text span, so it no longer needs to create html.Img server-side.
    app.clientside_callback(
        """
        function(playbackRate) {
            const rate = playbackRate || 1;
            return rate < 1 ? rate + '\u00d7' : Math.floor(rate) + '\u00d7';
        }
        """,
        Output("playback-rate-text", "children"),
        Input("playback-rate", "data"),
        prevent_initial_call=False,
    )

    # =========================================================================
    # Video Player Update (moved from server-side for zero round-trips)
    # =========================================================================
    # Fires when selected-video changes (auto-selection or manual timeline click).
    # Uses playback-timestamps[0] for datasetStartTime instead of the server-side
    # dff closure, which captured an empty DataFrame at startup anyway.
    app.clientside_callback(
        """
        function(selectedVideo, timestamps) {
            const datasetStartTime = (timestamps && timestamps.length > 0)
                ? timestamps[0]
                : null;

            if (!selectedVideo) {
                return ['', null, datasetStartTime];
            }

            const videoSrc = selectedVideo.shareUrl || selectedVideo.originalUrl || '';
            const videoMetadata = {
                fileCreatedAt: selectedVideo.fileCreatedAt || null,
                duration: (selectedVideo.metadata && selectedVideo.metadata.duration)
                    ? selectedVideo.metadata.duration
                    : null,
                filename: selectedVideo.filename || null
            };

            return [videoSrc, videoMetadata, datasetStartTime];
        }
        """,
        Output("video-trimmer", "videoSrc"),
        Output("video-trimmer", "videoMetadata"),
        Output("video-trimmer", "datasetStartTime"),
        Input("selected-video", "data"),
        State("playback-timestamps", "data"),
        prevent_initial_call=False,
    )

    # =========================================================================
    # Event Modal Open/Close (moved from server-side for zero round-trips)
    # =========================================================================
    # Handles B-key press, save-button click, and cancel. All data is available
    # in client stores: available-events, playhead-time, last-event-type,
    # selected-deployment. Timestamp formatting uses UTC methods to match the
    # Python datetime.utcfromtimestamp() behavior.
    app.clientside_callback(
        """
        function(
            bookmarkTrigger, saveButtonClicks, cancelClicks,
            playheadTime, lastEventType, availableEvents, selectedDeployment
        ) {
            const nu = window.dash_clientside.no_update;
            const noChange = [nu, nu, nu, nu, nu, nu, nu, nu, nu, nu];

            const ctx = window.dash_clientside.callback_context;
            if (!ctx || !ctx.triggered || ctx.triggered.length === 0) {
                return noChange;
            }

            const triggeredId = ctx.triggered[0].prop_id.split('.')[0];

            // Handle cancel
            if (triggeredId === 'cancel-event-btn') {
                return [
                    false,          // close modal
                    '',             // clear start time
                    nu,             // keep options
                    nu,             // keep selected value
                    null,           // clear pending time
                    {display: 'none'},  // hide new event type input
                    '',             // clear new event type input
                    '',             // clear end time
                    '',             // clear short description
                    ''              // clear long description
                ];
            }

            // Handle B-key or save-button
            const isBookmark = triggeredId === 'bookmark-trigger' && bookmarkTrigger;
            const isSaveButton = triggeredId === 'save-button' && saveButtonClicks;

            if (!isBookmark && !isSaveButton) {
                return noChange;
            }

            // Guard: no deployment selected
            if (!selectedDeployment) {
                return noChange;
            }

            // Build dropdown options from available events
            const options = [];
            if (availableEvents) {
                for (const ev of availableEvents) {
                    const key = ev.event_key || '';
                    if (key) {
                        options.push({label: key, value: key});
                    }
                }
            }
            options.push({label: '\\u2795 Create new event type...', value: '__create_new__'});

            // Determine pre-selected value
            let selectedValue = null;
            if (lastEventType && options.some(o => o.value === lastEventType)) {
                selectedValue = lastEventType;
            } else if (options.length > 1) {
                selectedValue = options[0].value;
            }

            // Format timestamp as "YYYY-MM-DD HH:MM:SS.mmm" using UTC
            let formattedTime = 'Unknown';
            if (playheadTime) {
                try {
                    const d = new Date(playheadTime * 1000);
                    const pad2 = n => String(n).padStart(2, '0');
                    const ms = String(d.getUTCMilliseconds()).padStart(3, '0');
                    formattedTime = d.getUTCFullYear() + '-'
                        + pad2(d.getUTCMonth() + 1) + '-'
                        + pad2(d.getUTCDate()) + ' '
                        + pad2(d.getUTCHours()) + ':'
                        + pad2(d.getUTCMinutes()) + ':'
                        + pad2(d.getUTCSeconds()) + '.'
                        + ms;
                } catch(e) {
                    formattedTime = String(playheadTime);
                }
            }

            return [
                true,               // open modal
                formattedTime,      // start time display
                options,            // dropdown options
                selectedValue,      // pre-selected value
                playheadTime,       // store pending time
                {display: 'none'},  // hide new event type input initially
                '',                 // clear new event type input
                '',                 // clear end time
                '',                 // clear short description
                ''                  // clear long description
            ];
        }
        """,
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
        Input("save-button", "n_clicks"),
        Input("cancel-event-btn", "n_clicks"),
        State("playhead-time", "data"),
        State("last-event-type", "data"),
        State("available-events", "data"),
        State("selected-deployment", "data"),
        prevent_initial_call=True,
    )
