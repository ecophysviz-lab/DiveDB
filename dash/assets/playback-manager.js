/**
 * DiveDB Client-Side Playback Manager
 * 
 * Eliminates server round-trips during playback by managing the playback loop
 * entirely in JavaScript using requestAnimationFrame.
 * 
 * Architecture:
 * - Maintains playback state (isPlaying, currentTime, rate) in JavaScript
 * - Uses requestAnimationFrame for smooth 60fps updates
 * - Communicates with Dash via hidden input element (playhead-update-input)
 * - Binary search for O(log n) timestamp lookup
 */

window.DiveDBPlayback = {
    // Playback state
    isPlaying: false,
    playbackRate: 1,
    timestamps: [],
    currentTime: null,
    minTime: null,
    maxTime: null,
    
    // Animation state
    animationId: null,
    lastTick: null,
    
    // Throttle settings (target ~30fps for efficiency, can go up to 60fps)
    targetFPS: 30,
    frameInterval: 1000 / 30,  // ~33ms between frames
    lastFrameTime: 0,
    
    /**
     * Initialize the playback manager with timestamps and current state
     */
    init: function(timestamps, currentTime, playbackRate) {
        this.timestamps = timestamps || [];
        this.currentTime = currentTime;
        this.playbackRate = playbackRate || 1;
        
        if (this.timestamps.length > 0) {
            this.minTime = this.timestamps[0];
            this.maxTime = this.timestamps[this.timestamps.length - 1];
        }
        
        console.log('[PlaybackManager] Initialized:', {
            timestampCount: this.timestamps.length,
            currentTime: this.currentTime,
            playbackRate: this.playbackRate,
            minTime: this.minTime,
            maxTime: this.maxTime
        });
    },
    
    /**
     * Update playback rate (called when user changes speed)
     */
    setRate: function(rate) {
        this.playbackRate = rate || 1;
        console.log('[PlaybackManager] Rate changed to:', this.playbackRate + '×');
    },
    
    /**
     * Update timestamps (called when deployment changes or graph updates)
     */
    setTimestamps: function(timestamps) {
        this.timestamps = timestamps || [];
        if (this.timestamps.length > 0) {
            this.minTime = this.timestamps[0];
            this.maxTime = this.timestamps[this.timestamps.length - 1];
        }
        console.log('[PlaybackManager] Timestamps updated:', this.timestamps.length);
    },
    
    /**
     * Update current time (called when user drags slider or clicks timeline)
     */
    setCurrentTime: function(time) {
        this.currentTime = time;
    },
    
    /**
     * Start playback
     */
    start: function() {
        if (this.isPlaying) {
            console.log('[PlaybackManager] Already playing, ignoring start');
            return;
        }
        
        // Verify the hidden input exists before starting
        const input = document.getElementById('playhead-update-input');
        if (!input) {
            console.error('[PlaybackManager] CANNOT START: playhead-update-input element not found in DOM!');
            return;
        }
        
        this.isPlaying = true;
        this.lastTick = performance.now();
        this.lastFrameTime = this.lastTick;
        this._updateCount = 0;
        
        console.log('[PlaybackManager] Starting playback at', this.currentTime, 'rate:', this.playbackRate + '×');
        console.log('[PlaybackManager] Input element found:', input.id);
        
        // Use bound tick to ensure 'this' context is preserved
        const self = this;
        const boundTick = function() { self.tick(); };
        
        // Start the tick loop
        this.animationId = requestAnimationFrame(boundTick);
    },
    
    /**
     * Stop playback
     */
    stop: function() {
        this.isPlaying = false;
        
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
        
        console.log('[PlaybackManager] Stopped playback at', this.currentTime);
    },
    
    /**
     * Main playback tick - called on each animation frame
     */
    tick: function() {
        // Capture 'this' for use in callbacks
        const self = this;
        
        if (!self.isPlaying) {
            console.log('[PlaybackManager] tick: not playing, stopping');
            return;
        }
        
        const now = performance.now();
        
        // Throttle to target FPS for efficiency
        const elapsed = now - self.lastFrameTime;
        if (elapsed < self.frameInterval) {
            // Schedule next tick without processing
            self.animationId = requestAnimationFrame(function() { self.tick(); });
            return;
        }
        
        // Calculate actual time delta since last tick
        const deltaSeconds = (now - self.lastTick) / 1000;
        self.lastTick = now;
        self.lastFrameTime = now;
        
        // Advance playhead by rate * elapsed time
        const newTime = self.currentTime + (deltaSeconds * self.playbackRate);
        
        // Check bounds and loop if needed
        if (self.maxTime && newTime > self.maxTime) {
            // Loop back to start
            self.currentTime = self.minTime || 0;
            console.log('[PlaybackManager] Looped back to start');
        } else {
            // Find nearest timestamp using binary search
            self.currentTime = self.findNearestTimestamp(newTime);
        }
        
        // Update the Dash store via hidden input
        self.updatePlayheadStore(self.currentTime);
        
        // Schedule next tick
        self.animationId = requestAnimationFrame(function() { self.tick(); });
    },
    
    /**
     * Find nearest timestamp using binary search - O(log n)
     */
    findNearestTimestamp: function(target) {
        const ts = this.timestamps;
        
        if (!ts || ts.length === 0) {
            return target;
        }
        
        const n = ts.length;
        
        // Handle edge cases
        if (target <= ts[0]) {
            return ts[0];
        }
        if (target >= ts[n - 1]) {
            return ts[n - 1];
        }
        
        // Binary search for insertion point
        let lo = 0;
        let hi = n - 1;
        
        while (lo < hi) {
            const mid = Math.floor((lo + hi) / 2);
            if (ts[mid] < target) {
                lo = mid + 1;
            } else {
                hi = mid;
            }
        }
        
        // Check which neighbor is closer
        if (lo === 0) {
            return ts[0];
        }
        if (lo === n) {
            return ts[n - 1];
        }
        
        const before = ts[lo - 1];
        const after = ts[lo];
        
        if ((target - before) <= (after - target)) {
            return before;
        }
        return after;
    },
    
    /**
     * Update the Dash playhead-time store via hidden input
     * The input value change triggers a clientside callback
     * 
     * Uses the same React/Dash integration technique as arrow-key-navigation.js
     */
    updatePlayheadStore: function(time) {
        const input = document.getElementById('playhead-update-input');
        if (!input) {
            console.error('[PlaybackManager] playhead-update-input element NOT FOUND!');
            return;
        }
        
        // Use timestamp|counter format to ensure each update is unique
        // Using | as delimiter since : appears in decimal timestamps
        const newValue = time + '|' + Date.now();
        
        // Debug: log every ~1 second (every 30th frame at 30fps)
        if (!this._updateCount) this._updateCount = 0;
        this._updateCount++;
        if (this._updateCount % 30 === 1) {
            console.log('[PlaybackManager] Updating playhead:', time.toFixed(3));
        }
        
        // Try to find the React component and use setProps directly
        // This is the most reliable way to trigger Dash callbacks
        const reactKey = Object.keys(input).find(function(key) {
            return key.startsWith('__reactFiber$') || key.startsWith('__reactInternalInstance$');
        });
        
        if (reactKey) {
            try {
                var fiber = input[reactKey];
                // Traverse up to find the component with setProps
                while (fiber) {
                    if (fiber.memoizedProps && typeof fiber.memoizedProps.setProps === 'function') {
                        // Found the Dash component - update the value
                        fiber.memoizedProps.setProps({ value: newValue });
                        return;
                    }
                    fiber = fiber.return;
                }
            } catch (err) {
                console.warn('[PlaybackManager] Could not update via React fiber:', err);
            }
        }
        
        // Fallback: use native input value setter and dispatch events
        try {
            // Set the value using native setter (bypasses React's synthetic events)
            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            ).set;
            nativeInputValueSetter.call(input, newValue);
            
            // Dispatch input event to trigger React's onChange
            input.dispatchEvent(new Event('input', { bubbles: true }));
            
            // Also dispatch change event as backup
            input.dispatchEvent(new Event('change', { bubbles: true }));
        } catch (err) {
            console.warn('[PlaybackManager] Fallback input update failed:', err);
        }
    },
    
    /**
     * Get current playback state (for debugging)
     */
    getState: function() {
        return {
            isPlaying: this.isPlaying,
            currentTime: this.currentTime,
            playbackRate: this.playbackRate,
            timestampCount: this.timestamps.length,
            minTime: this.minTime,
            maxTime: this.maxTime
        };
    }
};

// Log that the playback manager is loaded
console.log('[PlaybackManager] Module loaded and ready');
