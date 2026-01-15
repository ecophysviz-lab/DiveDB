# Client-Side Playback Architecture

> **Status**: Proposed  
> **Priority**: High  
> **Impact**: Eliminates server round-trips during playback, enabling smooth 60fps animation

## Problem Statement

The current playback system creates multiple server round-trips every second:

1. `dcc.Interval` fires every 1 second (server-controlled)
2. This triggers `update_playhead_from_interval` callback (server-side)
3. Server updates `playhead-time` store
4. Multiple callbacks react to `playhead-time` change (server + clientside)

This creates 3-4 round trips per tick, causing choppy/laggy playback.

## Current Architecture (Server-Dependent)

```
┌─────────────────────────────────────────────────────────────────┐
│ Every 1 second during playback:                                 │
│                                                                 │
│   dcc.Interval ──► Server (update_playhead_from_interval)       │
│        │                    │                                   │
│        │                    ▼                                   │
│        │            playhead-time store                         │
│        │                    │                                   │
│        │         ┌─────────┼─────────┐                         │
│        │         ▼         ▼         ▼                         │
│        │     Server    Server    Clientside                    │
│        │     (3D)     (video)   (slider, overlay)              │
│        │                                                        │
│   Round trips: 3-4 per tick                                    │
└─────────────────────────────────────────────────────────────────┘
```

## Proposed Client-Side Architecture

**Key insight:** All data needed for playback is already in `dcc.Store` components, which are accessible from clientside callbacks!

- `playback-timestamps` - the timestamp list
- `timeline-bounds` - current zoom range  
- `current-video-options` - available videos
- `playback-rate` - speed multiplier

```
┌─────────────────────────────────────────────────────────────────┐
│ Continuous playback (no server):                                │
│                                                                 │
│   JavaScript requestAnimationFrame / setInterval                │
│        │                                                        │
│        ▼                                                        │
│   Update playhead-time store (clientside)                       │
│        │                                                        │
│        ├──► Slider sync (clientside) ✓                         │
│        ├──► Playhead overlay (clientside) ✓                    │
│        ├──► 3D model time (NEW: clientside)                    │
│        └──► Video selection (NEW: clientside)                  │
│                                                                 │
│   Round trips: 0 per tick                                      │
└─────────────────────────────────────────────────────────────────┘
```

## Implementation Plan

### Phase 1: Optimize Existing Callbacks ✅ Partially Complete

1. **Playhead overlay** - ✅ Moved to CSS overlay (no figure re-render)
2. **Timestamp lookups** - 🔄 Replace `pd.Series` with binary search
3. **3D model update** - Move to clientside callback

### Phase 2: Client-Side Playback Manager

Replace the `dcc.Interval` + server callback with a JavaScript-based playback controller.

#### New Asset File: `assets/playback-manager.js`

```javascript
window.DiveDBPlayback = {
    isPlaying: false,
    playbackRate: 1,
    timestamps: [],
    currentTime: null,
    animationId: null,
    lastTick: null,
    
    start: function() {
        this.isPlaying = true;
        this.lastTick = performance.now();
        this.tick();
    },
    
    stop: function() {
        this.isPlaying = false;
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
    },
    
    tick: function() {
        if (!this.isPlaying) return;
        
        const now = performance.now();
        const deltaSeconds = (now - this.lastTick) / 1000;
        this.lastTick = now;
        
        // Advance playhead by rate * elapsed time
        const newTime = this.currentTime + (deltaSeconds * this.playbackRate);
        
        // Find nearest timestamp (binary search)
        this.currentTime = this.findNearestTimestamp(newTime);
        
        // Update the Dash store
        this.updatePlayheadStore(this.currentTime);
        
        // Schedule next tick (throttle to ~30fps for efficiency)
        setTimeout(() => {
            this.animationId = requestAnimationFrame(() => this.tick());
        }, 33);
    },
    
    findNearestTimestamp: function(target) {
        const ts = this.timestamps;
        if (!ts.length) return target;
        
        // Clamp to bounds
        if (target <= ts[0]) return ts[0];
        if (target >= ts[ts.length - 1]) return ts[0]; // Loop back
        
        // Binary search for O(log n) performance
        let lo = 0, hi = ts.length - 1;
        while (lo < hi) {
            const mid = Math.floor((lo + hi) / 2);
            if (ts[mid] < target) lo = mid + 1;
            else hi = mid;
        }
        
        // Check neighbors for closest
        if (lo > 0 && Math.abs(ts[lo-1] - target) < Math.abs(ts[lo] - target)) {
            return ts[lo-1];
        }
        return ts[lo];
    },
    
    updatePlayheadStore: function(time) {
        // Trigger Dash store update via hidden input
        const input = document.getElementById('playhead-update-input');
        if (input) {
            input.value = time + ':' + Date.now();
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }
};
```

### Phase 3: Clientside Callbacks

#### Play Button Toggle (Clientside)

```javascript
app.clientside_callback(
    """
    function(n_clicks, timestamps, playbackRate, currentTime, minTime) {
        const mgr = window.DiveDBPlayback;
        mgr.timestamps = timestamps || [];
        mgr.playbackRate = playbackRate || 1;
        mgr.currentTime = currentTime || minTime || 0;
        
        if (n_clicks % 2 === 1) {
            mgr.start();
            return [true, 'Pause', 'btn btn-primary btn-round btn-pause btn-lg'];
        } else {
            mgr.stop();
            return [false, 'Play', 'btn btn-primary btn-round btn-play btn-lg'];
        }
    }
    """,
    [Output('is-playing', 'data'), 
     Output('play-button', 'children'), 
     Output('play-button', 'className')],
    [Input('play-button', 'n_clicks')],
    [State('playback-timestamps', 'data'), 
     State('playback-rate', 'data'), 
     State('playhead-time', 'data'),
     State('playhead-slider', 'min')]
)
```

#### 3D Model Update (Clientside)

```javascript
app.clientside_callback(
    """
    function(playhead_time, timestamps) {
        if (!playhead_time || !timestamps || !timestamps.length) {
            return window.dash_clientside.no_update;
        }
        
        // Binary search for nearest timestamp
        let lo = 0, hi = timestamps.length - 1;
        while (lo < hi) {
            const mid = Math.floor((lo + hi) / 2);
            if (timestamps[mid] < playhead_time) lo = mid + 1;
            else hi = mid;
        }
        
        const nearest = (lo > 0 && 
            Math.abs(timestamps[lo-1] - playhead_time) < Math.abs(timestamps[lo] - playhead_time))
            ? timestamps[lo-1] : timestamps[lo];
        
        return nearest * 1000;  // Convert to milliseconds
    }
    """,
    Output('three-d-model', 'activeTime'),
    [Input('playhead-time', 'data')],
    [State('playback-timestamps', 'data')]
)
```

#### Video Selection (Clientside)

```javascript
app.clientside_callback(
    """
    function(playhead_time, video_options, time_offset, manual_override) {
        // If manual override is set, maintain it
        if (manual_override) {
            return [manual_override, manual_override];
        }
        
        if (!video_options || !playhead_time) {
            return [null, null];
        }
        
        time_offset = time_offset || 0;
        
        // Find best overlapping video
        let bestVideo = null;
        let bestOverlap = Infinity;
        
        for (const video of video_options) {
            const createdAt = video.fileCreatedAt;
            if (!createdAt) continue;
            
            const startTime = new Date(createdAt).getTime() / 1000 + time_offset;
            const duration = parseDuration(video.metadata?.duration || '0');
            const endTime = startTime + duration;
            
            if (playhead_time >= startTime && playhead_time <= endTime) {
                const overlap = playhead_time - startTime;
                if (overlap < bestOverlap) {
                    bestOverlap = overlap;
                    bestVideo = video;
                }
            }
        }
        
        return [bestVideo, null];
    }
    """,
    [Output('selected-video', 'data'), Output('manual-video-override', 'data')],
    [Input('playhead-time', 'data')],
    [State('current-video-options', 'data'),
     State('video-time-offset', 'data'),
     State('manual-video-override', 'data')]
)
```

## Migration Checklist

### Phase 1: Optimize (Can Do Now)
- [x] Move playhead overlay to CSS
- [ ] Binary search for timestamp lookups
- [ ] Move 3D model update to clientside

### Phase 2: Client-Side Playback (Future)
- [ ] Create `playback-manager.js` asset
- [ ] Add hidden input for playhead updates
- [ ] Convert play/pause to clientside
- [ ] Convert interval-based updates to JS
- [ ] Remove `dcc.Interval` component

### Phase 3: Full Client-Side (Future)
- [ ] Move video selection to clientside
- [ ] Move video preview sync to clientside
- [ ] Remove server-side playback callbacks

## Performance Impact

| Metric | Current | After Phase 1 | After Phase 2 |
|--------|---------|---------------|---------------|
| Server round-trips per tick | 3-4 | 2-3 | 0 |
| Timestamp search complexity | O(n) | O(log n) | O(log n) |
| Playhead overlay render | Full figure | CSS only | CSS only |
| Max smooth playback rate | ~10x | ~50x | ~100x |

## Risks and Mitigations

1. **Store sync issues**: Clientside store updates may not trigger all callbacks
   - Mitigation: Use hidden input pattern with proper event dispatch

2. **Browser compatibility**: `requestAnimationFrame` not available in old browsers
   - Mitigation: Fallback to `setInterval`

3. **Timestamp list size**: Large datasets may have slow binary search
   - Mitigation: Pre-compute timestamp index on deployment load

## References

- [Dash Clientside Callbacks](https://dash.plotly.com/clientside-callbacks)
- [requestAnimationFrame MDN](https://developer.mozilla.org/en-US/docs/Web/API/window/requestAnimationFrame)
- [Plotly.js Performance](https://plotly.com/javascript/webgl-vs-svg/)
