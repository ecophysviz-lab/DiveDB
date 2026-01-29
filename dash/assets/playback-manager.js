/**
 * Client-Side Playback Manager for DiveDB
 * 
 * This module handles playback timing entirely in the browser using requestAnimationFrame,
 * eliminating server round-trips during playback for smooth, responsive animation.
 * 
 * Architecture:
 * - Uses requestAnimationFrame for smooth timing
 * - Throttles updates to ~30fps for efficiency
 * - Communicates with Dash via hidden input (playhead-update-input)
 * - Supports variable playback rates (0.1x to 100x)
 * - Binary search for O(log n) timestamp lookup
 */

(function() {
    'use strict';

    window.DiveDBPlayback = {
        // State
        isPlaying: false,
        playbackRate: 1,
        timestamps: [],
        currentTime: null,
        minTime: null,
        maxTime: null,
        
        // Internal timing
        animationId: null,
        lastTickTime: null,
        
        // Throttling: limit updates to ~30fps (33ms between updates)
        TICK_INTERVAL_MS: 33,
        lastUpdateTime: 0,

        /**
         * Initialize the playback manager with data from Dash stores.
         * Called when play is clicked.
         */
        init: function(timestamps, playbackRate, currentTime) {
            this.timestamps = timestamps || [];
            this.playbackRate = playbackRate || 1;
            this.currentTime = currentTime;
            
            if (this.timestamps.length > 0) {
                this.minTime = this.timestamps[0];
                this.maxTime = this.timestamps[this.timestamps.length - 1];
            } else {
                this.minTime = 0;
                this.maxTime = 0;
            }
        },

        /**
         * Start playback.
         */
        start: function() {
            if (this.isPlaying) return;
            
            this.isPlaying = true;
            this.lastTickTime = performance.now();
            this.lastUpdateTime = 0;
            this.tick();
        },

        /**
         * Stop playback.
         */
        stop: function() {
            this.isPlaying = false;
            
            if (this.animationId) {
                cancelAnimationFrame(this.animationId);
                this.animationId = null;
            }
        },

        /**
         * Update playback rate while playing.
         */
        setPlaybackRate: function(rate) {
            this.playbackRate = rate || 1;
        },

        /**
         * Main tick function - called by requestAnimationFrame.
         */
        tick: function() {
            if (!this.isPlaying) return;

            const now = performance.now();
            
            // Throttle updates to TICK_INTERVAL_MS
            if (now - this.lastUpdateTime < this.TICK_INTERVAL_MS) {
                this.animationId = requestAnimationFrame(() => this.tick());
                return;
            }

            // Calculate elapsed time since last tick
            const deltaMs = now - this.lastTickTime;
            this.lastTickTime = now;
            this.lastUpdateTime = now;

            // Convert to seconds and apply playback rate
            const deltaSeconds = (deltaMs / 1000) * this.playbackRate;
            
            // Advance playhead
            let newTime = this.currentTime + deltaSeconds;

            // Handle bounds - loop back to start if past end
            if (newTime > this.maxTime) {
                newTime = this.minTime;
            } else if (newTime < this.minTime) {
                newTime = this.minTime;
            }

            // Find nearest timestamp using binary search
            if (this.timestamps.length > 0) {
                newTime = this.findNearestTimestamp(newTime);
            }

            // Only update if time actually changed
            if (newTime !== this.currentTime) {
                this.currentTime = newTime;
                // NOTE: We no longer call updatePlayheadStore() directly.
                // Instead, dcc.Interval polls this.currentTime every 100ms
                // and a clientside callback updates the Dash store.
            }

            // Schedule next tick
            this.animationId = requestAnimationFrame(() => this.tick());
        },

        /**
         * Binary search to find nearest timestamp - O(log n) complexity.
         */
        findNearestTimestamp: function(target) {
            const ts = this.timestamps;
            const n = ts.length;
            
            if (n === 0) return target;
            
            // Handle edge cases
            if (target <= ts[0]) return ts[0];
            if (target >= ts[n - 1]) return ts[n - 1];

            // Binary search for insertion point
            let lo = 0, hi = n - 1;
            while (lo < hi) {
                const mid = Math.floor((lo + hi) / 2);
                if (ts[mid] < target) {
                    lo = mid + 1;
                } else {
                    hi = mid;
                }
            }

            // Check which neighbor is closer
            if (lo === 0) return ts[0];
            
            const before = ts[lo - 1];
            const after = ts[lo];
            
            return (target - before) <= (after - target) ? before : after;
        },

        /**
         * Update the Dash playhead-time store via hidden input.
         * The hidden input triggers a clientside callback that updates the store.
         * 
         * NOTE: React hijacks the native value setter, so we must use the native
         * HTMLInputElement.prototype.value setter to trigger React's change detection.
         */
        updatePlayheadStore: function(time) {
            // NOTE: This method is no longer used - kept for reference.
            // Dash interval polling is more reliable than direct DOM manipulation.
            const input = document.getElementById('playhead-update-input');
            if (!input) {
                return;
            }
            
            // Format: "timestamp:epoch" to ensure each update is unique
            const newValue = time + ':' + Date.now();
            
            // React hijacks the value property, so we need to use the native setter
            // to properly trigger React's change detection system
            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            ).set;
            nativeInputValueSetter.call(input, newValue);
            
            // Dispatch input event to trigger React and Dash callbacks
            const inputEvent = new Event('input', { bubbles: true });
            input.dispatchEvent(inputEvent);
        },

        /**
         * Sync current time from external source (e.g., slider drag).
         * Called when user manually changes playhead position.
         */
        syncTime: function(time) {
            this.currentTime = time;
        }
    };
})();
