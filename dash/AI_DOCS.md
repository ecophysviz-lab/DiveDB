# AI Agent Documentation - Dash Data Visualization

> **Purpose**: Token-efficient reference for AI agents working on the DiveDB Dash visualization dashboard.

## Quick Reference

- **Project**: Dash-based biologging data visualization dashboard for DiveDB
- **Entry Point**: `data_visualization.py` (line 206: `if __name__ == "__main__"`)
- **Tech Stack**: Dash, Plotly, DuckDB, Apache Iceberg, Notion API, Immich, plotly-resampler, dash-extensions
- **Port**: 8054 (development)
- **Key Dependencies**: `DuckPond`, `NotionORMManager`, `ImmichService`
- **Performance**: Uses `plotly-resampler` for dynamic data resampling on zoom/pan
- **Caching**: Set `DASH_USE_CACHE=true` to enable file-based caching for faster deployment loads

## Architecture Overview

### Component Flow

```
User Action → Callback → Store Update → UI Update → Next Callback
```

### State Management

- Uses `dcc.Store` components for persistent state
- Key stores: `selected-dataset`, `selected-deployment`, `playhead-time`, `is-playing`, `playback-timestamps`, `playback-rate`, `current-video-options`, `available-channels`, `selected-channels`, `figure-store`, `available-events`, `selected-events`, `channel-order-from-dom`, `arrow-key-input`
- Stores defined in `create_app_stores()` (data_visualization.py:67-120)
- `figure-store` caches `FigureResampler` objects server-side via `dash-extensions.Serverside`

### Callback Registration Order

1. Standard callbacks (`register_callbacks`) - playback, video selection
2. Selection callbacks (`register_selection_callbacks`) - dataset/deployment selection
3. Clientside callbacks (`register_clientside_callbacks`) - UI interactions (uses `allow_duplicate=True`)

## File Map

| File | Purpose | Key Exports | Lines |
|------|---------|-------------|-------|
| `data_visualization.py` | App entry point, service initialization | `app`, `server` | ~209 |
| `callbacks.py` | Server-side callbacks (playback, video, rate cycling, skip) | `register_callbacks()` | ~1008 |
| `selection_callbacks.py` | Dataset/deployment selection, events | `register_selection_callbacks()`, `DataPkl`, `generate_graph_from_channels()`, `transform_events_for_graph()` | ~1775 |
| `clientside_callbacks.py` | Client-side callbacks (fullscreen, slider sync, arrow keys) | `register_clientside_callbacks()` | ~240 |
| `graph_utils.py` | Plotly visualization utilities | `plot_tag_data_interactive()` | ~361 |
| `layout/core.py` | Main layout assembly | `create_header()`, `create_main_content()`, `create_layout()` | ~283 |
| `layout/sidebar.py` | Left/right sidebars | `create_left_sidebar()`, `create_right_sidebar()`, `create_dataset_accordion_item()` | 284 |
| `layout/timeline.py` | Footer timeline components | `create_footer()`, `create_timeline_section()` | ~840 |
| `layout/indicators.py` | Event/video indicators | `create_event_indicator()`, `create_video_indicator()` | 460 |
| `layout/modals.py` | Modal dialogs | `create_bookmark_modal()`, `create_event_modal()` | ~145 |
| `logging_config.py` | Centralized logging | `get_logger()` | 96 |
| `assets/channel-drag-drop.js` | Channel drag-and-drop reordering | `initializeDragDrop()` | ~237 |
| `assets/arrow-key-navigation.js` | Global arrow key playhead navigation | - | ~130 |
| `assets/b-key-bookmark.js` | Global B key handler for event creation | - | ~120 |
| `assets/tooltip.js` | Slider tooltip timestamp formatter | `formatTimestamp()` | ~19 |

## Module Reference

### data_visualization.py

**Purpose**: App initialization, service setup, layout creation

**Key Functions**:
- `create_app_stores(dff)` → List[dcc.Store] - Creates all dcc.Store components
- `create_layout(fig, data_json, dff, ...)` → html.Div - Assembles complete app layout

**Services Initialized**:
- `notion_manager`: NotionORMManager (lines 38-50)
- `duck_pond`: DuckPond.from_environment() (line 61)
- `immich_service`: ImmichService() (line 62)

**App Configuration**:
- Uses `DashProxy` from `dash-extensions` with `ServersideOutputTransform` for server-side caching
- External stylesheets: Bootstrap + custom SASS CSS (lines 54-56)
- Initial layout: Empty state with empty figure/dataframe (lines 152-170)

### callbacks.py

**Purpose**: Server-side callbacks for playback, video selection, UI toggles

**Key Functions**:
- `register_callbacks(app, dff, video_options, channel_options)` - Registers all standard callbacks
- `parse_video_duration(duration_str)` → float - Parses HH:MM:SS.mmm to seconds
- `parse_video_created_time(created_at_str)` → float - ISO timestamp to Unix timestamp
- `calculate_video_overlap(video, playhead_time, time_offset)` → dict - Video overlap calculation
- `find_best_overlapping_video(video_options, playhead_time, time_offset)` → dict - Selects best video

**Key Callbacks**:
- `toggle_play_pause()`: `play-button.n_clicks` → `is-playing.data`, `play-button.children`, `play-button.className`
- `cycle_playback_rate()`: `forward-button.n_clicks` + `rewind-button.n_clicks` → `playback-rate.data`, tooltip updates (cycles 0.1×→0.5×→1×→5×→10×→100×)
- `update_playback_rate_display()`: `playback-rate.data` → `playback-rate-display.children`, `playback-rate-tooltip.children`
- `skip_navigation()`: `previous-button.n_clicks` + `next-button.n_clicks` → `playhead-time.data` (skips ±10×rate seconds)
- `update_playhead_from_interval()`: `interval-component.n_intervals` + `playback-rate.data` → `playhead-time.data` (rate-aware)
- `video_selection_manager()`: `playhead-time.data` + `video-indicator.n_clicks` → `selected-video.data`, `manual-video-override.data`
- `update_video_preview()`: `playhead-time.data` + `is-playing.data` + `playback-rate.data` → `video-trimmer.playheadTime`, `video-trimmer.isPlaying`, `video-trimmer.playbackRate`
- `update_video_player()`: `selected-video.data` → `video-trimmer.videoSrc`, `video-trimmer.videoMetadata`, `video-trimmer.datasetStartTime`
- `add_new_channel()`: `add-graph-btn.n_clicks` → `graph-channel-list.children`
- `remove_channel()`: `channel-remove.n_clicks` → `graph-channel-list.children`
- Clientside callback: `update-graph-btn.n_clicks` → `channel-order-from-dom.data` (reads DOM order)
- `handle_event_modal_open()`: `bookmark-trigger.value` + `cancel-event-btn.n_clicks` → `event-modal.is_open`, `event-start-time.value`, `event-type-select.options/value`, `pending-event-time.data`
- `toggle_new_event_type_input()`: `event-type-select.value` → `new-event-type-container.style` (show/hide new event type input)

**Channel Management**:
- Channels stored as pattern-matching IDs: `{"type": "channel-select", "index": N}`
- Drag-and-drop handled by `assets/channel-drag-drop.js` (visual reordering)
- Channel order read from DOM when "Update Graph" clicked via clientside callback
- Uses `get_props()` helper to handle both dict and component objects in callbacks

### selection_callbacks.py

**Purpose**: Dataset/deployment selection, data loading, graph generation, event management

**Key Classes**:
- `DataPkl`: Wrapper for signal_data, signal_info, event_data (lines 23-70)

**Key Functions**:
- `register_selection_callbacks(app, duck_pond, immich_service)` - Registers selection callbacks
- `transform_events_for_graph(events_df)` → pd.DataFrame - Transforms DuckPond events to graph annotation format (key, datetime, duration)
- `create_data_pkl_from_dataframe(dff, group_membership)` → DataPkl - Transforms DataFrame to data_pkl structure
- `_create_data_pkl_from_groups(dff, data_columns, group_membership)` → DataPkl - Groups columns by parent group
- `generate_graph_from_channels(duck_pond, dataset, ..., events_df, selected_events)` → Tuple[fig, dff, timestamps] - Main graph generation function with optional event annotations

**Key Callbacks**:
- `load_datasets_on_page_load()`: `url.pathname` → `all-datasets-deployments.data`
- `populate_dataset_accordion()`: `all-datasets-deployments.data` → `dataset-accordion.children`
- `select_deployment_and_load_visualization()`: `deployment-button.n_clicks` → Multiple outputs:
  - `selected-deployment.data`, `selected-dataset.data`
  - `graph-content.figure`, `figure-store.data` (caches FigureResampler)
  - `is-loading-data.data`
  - `timeline-container.children`, `deployment-info-display.children`
  - `playback-timestamps.data`, `current-video-options.data`
  - `three-d-model.data`
  - Playback control button states
  - `available-channels.data`, `selected-channels.data`
  - `available-events.data`, `selected-events.data` (event types with colors)
- `update_graph_from_channels()`: `channel-order-from-dom.data` (triggered by clientside) + event selections → `graph-content.figure`, `figure-store.data`, `playback-timestamps.data`, `graph-channels.is_open`
- `populate_channel_list_from_selection()`: `selected-channels.data` + `available-events.data` → `graph-channel-list.children` (includes Events section)
- `show_loading_overlay()`: `deployment-button.n_clicks` → `loading-overlay.style`, `is-loading-data.data`
- `update_graph_on_zoom()`: `graph-content.relayoutData` + `figure-store.data` → `graph-content.figure` (plotly-resampler dynamic resampling)
- `reset_zoom_to_original()`: `reset-zoom-button.n_clicks` + `original-bounds.data` → `timeline-bounds.data`, `graph-content.figure` (resets zoom to original dataset bounds)
- `save_event()`: `save-event-btn.n_clicks` → `event-modal.is_open`, `last-event-type.data`, `available-events.data` (writes event to Iceberg via `duck_pond.write_event()`)

**Event Management**:
- Events displayed via "EVENTS" section in Manage Channels popover
- Pattern-matching IDs: `{"type": "event-checkbox", "key": event_key}`, `{"type": "event-signal", "key": event_key}`
- Point events (duration=0) → note_annotations (markers); State events → state_annotations (rectangles)

**Data Flow**:
1. Page load → Load datasets/deployments from DuckPond
2. User clicks deployment → Fetch data, generate FigureResampler graph, cache it, load videos from Immich
3. User selects channels → Update graph with selected channels, recache FigureResampler
4. User zooms/pans → plotly-resampler automatically loads appropriate resolution from cached data

### clientside_callbacks.py

**Purpose**: Client-side JavaScript callbacks for UI interactions

**Key Functions**:
- `register_clientside_callbacks(app)` - Registers all clientside callbacks

**Key Callbacks**:
- Fullscreen toggle: `fullscreen-button.n_clicks` → `fullscreen-button.className`, `fullscreen-tooltip.children`
- Playhead slider sync (bidirectional):
  - `playhead-time.data` → `playhead-slider.value`
  - `playhead-slider.value` → `playhead-time.data`
- Playhead tracking line: `playhead-time.data` → `graph-content.figure` (adds vertical line)
- Arrow key navigation: `arrow-key-input.value` → `playhead-time.data` (fixed ±0.1s steps for precise frame-by-frame navigation, works with `assets/arrow-key-navigation.js`)
- Event modal Enter key: `event-modal.is_open` → clicks `save-event-btn` (enables B → Enter quick workflow)
- Reset zoom button enable/disable: `timeline-bounds.data` + `original-bounds.data` → `reset-zoom-button.disabled` (enabled when zoomed)
- Indicator zoom sync: `timeline-bounds.data` → Updates CSS variables on `event-indicators-container` and `video-indicators-container` (repositions indicators on zoom)

**Note**: Uses `allow_duplicate=True` to avoid conflicts with server-side callbacks

**Indicator Zoom Sync Architecture**:
- Indicators store absolute timestamps as CSS variables (`--event-start-ts`, `--event-end-ts`, `--video-start-ts`, `--video-end-ts`)
- Container elements (`#event-indicators-container`, `#video-indicators-container`) provide view bounds (`--view-min`, `--view-max`)
- CSS uses calc() to position indicators relative to current view bounds
- Clientside callback updates container CSS variables when `timeline-bounds` changes, triggering instant repositioning

### graph_utils.py

**Purpose**: Plotly graph creation utilities

**Key Functions**:
- `plot_tag_data_interactive(data_pkl, signals=None, channels=None, time_range=None, note_annotations=None, state_annotations=None, zoom_start_time=None, zoom_end_time=None, plot_event_values=None, zoom_range_selector_channel=None)` → FigureResampler - Main plotting function

**Features**:
- Creates `FigureResampler` objects for performance with large datasets
- Dynamic resampling handled by `update_graph_on_zoom()` callback in `selection_callbacks.py`
- Supports sensor_data and derived_data
- Color mapping from `color_mapping.json`
- Adaptive subplot layout based on signal count

**Event Annotations**:
- `note_annotations`: Point events rendered as markers at signal's max value (matches pyologger behavior)
- `state_annotations`: State events rendered as shaded rectangles spanning full y-range
- Annotations use `signal_row` tracking to handle blank spacer row correctly
- Event markers hidden from legend (`showlegend=False`) to prevent legend overflow

### layout/core.py

**Purpose**: Main layout structure and header

**Key Functions**:
- `create_header()` → html.Header - Navbar with logo, profile dropdown
- `create_main_content(fig, channel_options=None)` → html.Div - Main graph area with channel management
- `create_empty_figure()` → go.Figure - Empty Plotly figure
- `create_empty_dataframe()` → pd.DataFrame - Empty DataFrame with datetime/timestamp columns
- `create_loading_overlay()` → html.Div - Loading overlay component

### layout/sidebar.py

**Purpose**: Left (selection) and right (visuals) sidebars

**Key Functions**:
- `create_left_sidebar()` → html.Div - Dataset accordion, channel management
- `create_right_sidebar(data_json, playhead_time, video_options, restricted_time_range)` → html.Div - 3D model, video preview, event indicators
- `create_dataset_accordion_item(dataset_name, deployments, item_id)` → dbc.AccordionItem - Single dataset accordion item with deployment buttons

**Component IDs**:
- Left sidebar: `left-sidebar`, `dataset-accordion`
- Main content: `graph-channels-toggle`, `reset-zoom-button`, `graph-content`
- Right sidebar: `right-sidebar`, `three-d-model`, `video-trimmer`

### layout/timeline.py

**Purpose**: Footer timeline with playhead controls

**Key Functions**:
- `create_footer(dff, video_options, events_df)` → html.Div - Full footer with timeline
- `create_footer_empty()` → html.Div - Empty footer (initial state)
- `create_timeline_section(dff, video_options, events_df)` → dbc.Container - Timeline slider + indicators
- `create_deployment_info_display(animal_id, deployment_date, icon_url)` → html.Div - Deployment metadata display

**Timeline Components**:
- Playhead slider: `playhead-slider` (step=0.001 for millisecond resolution, tooltip shows `YYYY-MM-DD HH:MM:SS.mmm` via `assets/tooltip.js`)
- Playback controls:
  - `previous-button`: Skip back (10× playback rate seconds)
  - `rewind-button`: Decrease playback rate (100→10→5→1→0.5→0.1)
  - `play-button`: Play/pause
  - `forward-button`: Increase playback rate (0.1→0.5→1→5→10→100)
  - `next-button`: Skip forward (10× playback rate seconds)
- Speed display: `playback-rate-display` (shows current rate, e.g., "0.5×" or "5×")
- Timeline container: `timeline-container`
- Indicator containers (for zoom-aware positioning):
  - `event-indicators-container`: Wraps event rows, provides `--view-min`/`--view-max` CSS variables
  - `video-indicators-container`: Wraps video indicators, provides `--view-min`/`--view-max` CSS variables

### layout/indicators.py

**Purpose**: Event and video indicator components for timeline

**Key Functions**:
- `create_event_indicator(event_id, tooltip_content, start_ratio, end_ratio, timestamp_min, timestamp_max, color)` → html.Div - Single event indicator
- `create_video_indicator(video_id, tooltip_content, position_data, timestamp_min, timestamp_max)` → html.Div - Single video indicator
- `create_saved_indicator(saved_id, timestamp_display, notes, start_ratio, end_ratio, timestamp_min, timestamp_max)` → html.Div - Saved bookmark indicator
- `calculate_video_timeline_position(video, timeline_start_ts, timeline_end_ts)` → dict - Calculates video position ratios
- `generate_event_indicators_row(events_df, timestamp_min, timestamp_max)` → List[html.Div] - Generates all event indicator rows
- `assign_event_colors(events_df)` → pd.DataFrame - Assigns colors to events

**CSS Variables for Zoom-Aware Positioning**:
- Indicators store absolute timestamps: `--event-start-ts`, `--event-end-ts` (events), `--video-start-ts`, `--video-end-ts` (videos)
- Position calculated via CSS: `left: calc((var(--event-start-ts) - var(--view-min)) / (var(--view-max) - var(--view-min)) * 100%)`
- View bounds (`--view-min`, `--view-max`) inherited from container elements and updated on zoom

**Note**: Avoid inline styles on buttons. Tooltips use `delay` and `autohide` params.

### layout/modals.py

**Purpose**: Modal dialogs

**Key Functions**:
- `create_bookmark_modal()` → dbc.Modal - Bookmark timestamp modal
- `create_event_modal()` → dbc.Modal - B-key event creation modal with event type dropdown, start/end time fields

**Event Modal Components**:
- `event-type-select`: Dropdown for selecting event type (populated from `available-events`)
- `new-event-type-input`: Text input for creating new event types (shown when "Create new" selected)
- `event-start-time`: Read-only display of playhead time when modal opened
- `event-end-time`: Optional end time input for duration events
- `save-event-btn`, `cancel-event-btn`: Modal action buttons

## Callback Chains

### Dataset Selection Flow

1. **Page Load** (`load_datasets_on_page_load`)
   - Trigger: `url.pathname`
   - Output: `all-datasets-deployments.data`
   - Action: Fetch all datasets/deployments from DuckPond

2. **Populate Accordion** (`populate_dataset_accordion`)
   - Trigger: `all-datasets-deployments.data`
   - Output: `dataset-accordion.children`
   - Action: Create accordion items with deployment buttons

3. **Select Deployment** (`select_deployment_and_load_visualization`)
   - Trigger: `deployment-button.n_clicks`
   - Outputs: Multiple (see selection_callbacks.py:733-752)
   - Actions:
     - Set `selected-deployment.data`, `selected-dataset.data`
     - Fetch data via `generate_graph_from_channels()`
     - Load videos from Immich
     - Generate timeline with events/videos
     - Prepare 3D model data
     - Enable playback controls

4. **Show Loading Overlay** (`show_loading_overlay`)
   - Trigger: `deployment-button.n_clicks`
   - Output: `loading-overlay.style`, `is-loading-data.data`
   - Action: Display loading overlay during data fetch

5. **Hide Loading Overlay** (`hide_loading_overlay`)
   - Trigger: `is-loading-data.data` (when False)
   - Output: `loading-overlay.style`
   - Action: Hide overlay when data loaded

### Channel Selection Flow

1. **Populate Channel List** (`populate_channel_list_from_selection`)
   - Trigger: `selected-channels.data`
   - Output: `graph-channel-list.children`
   - Action: Create CHANNELS header, channel rows, EVENTS section, Update button

2. **Add Channel** (`add_new_channel`)
   - Trigger: `add-graph-btn.n_clicks`
   - Output: `graph-channel-list.children`
   - Action: Add new channel selection row after existing channels

3. **Remove Channel** (`remove_channel`)
   - Trigger: `channel-remove.n_clicks`
   - Output: `graph-channel-list.children`
   - Action: Remove channel row (minimum 1 required)

4. **Drag-Drop Reorder** (`channel-drag-drop.js`)
   - User drags channel row via drag handle
   - JavaScript visually reorders DOM elements
   - 15px dead zone prevents stuttering

5. **Read DOM Order + Button Loading** (clientside callbacks in `callbacks.py`)
   - Trigger: `update-graph-btn.n_clicks`
   - Outputs: `channel-order-from-dom.data`, `update-graph-btn.disabled`, `update-graph-btn.children`
   - Action: Read channel values from DOM in visual order; immediately set button to "Updating..." state

6. **Update Graph** (`update_graph_from_channels`)
   - Trigger: `channel-order-from-dom.data`
   - State: `timeline-bounds.data` (for zoom preservation)
   - Outputs: `graph-content.figure`, `playback-timestamps.data`, `update-graph-btn.disabled`, `update-graph-btn.children`
   - Action: Regenerate graph with channels in DOM order; preserve current zoom range via `timeline-bounds`; restore button state

### Playback Flow

1. **Toggle Play/Pause** (`toggle_play_pause`)
   - Trigger: `play-button.n_clicks`
   - Output: `is-playing.data`, `play-button.children`, `play-button.className`
   - Action: Toggle play state, update button UI

2. **Cycle Playback Rate** (`cycle_playback_rate`)
   - Trigger: `forward-button.n_clicks` or `rewind-button.n_clicks`
   - Output: `playback-rate.data`, tooltip updates
   - Action: Forward cycles up (1→5→10→100→1), Rewind cycles down

3. **Skip Navigation** (`skip_navigation`)
   - Trigger: `previous-button.n_clicks` or `next-button.n_clicks`
   - Output: `playhead-time.data`, tooltip updates
   - Action: Jump ±(10 × playback_rate) seconds

4. **Arrow Key Navigation** (clientside + `arrow-key-navigation.js`)
   - Trigger: Left/Right arrow keys → `arrow-key-input.value`
   - Output: `playhead-time.data`
   - Action: Move playhead ±0.1 seconds (fixed step for precise frame-by-frame analysis)

5. **Enable Interval** (`update_interval_component`)
   - Trigger: `is-playing.data`
   - Output: `interval-component.disabled`
   - Action: Enable/disable interval based on play state

6. **Update Playhead** (`update_playhead_from_interval`)
   - Trigger: `interval-component.n_intervals`
   - State: `playback-rate.data`
   - Output: `playhead-time.data`
   - Action: Advance playhead by `playback_rate` seconds per tick

7. **Sync Slider** (clientside)
   - Trigger: `playhead-time.data` → `playhead-slider.value`
   - Action: Update slider position

8. **Update Video** (`video_selection_manager`)
   - Trigger: `playhead-time.data`
   - Output: `selected-video.data`
   - Action: Auto-select overlapping video

9. **Update 3D Model** (`update_active_time`)
   - Trigger: `playhead-time.data`
   - Output: `three-d-model.activeTime`
   - Action: Update 3D model orientation

### B-Key Event Bookmark Flow

1. **B Key Press** (`b-key-bookmark.js`)
   - Trigger: User presses 'B' key (not in input field)
   - Action: Updates `bookmark-trigger` hidden input with timestamp

2. **Open Event Modal** (`handle_event_modal_open`)
   - Trigger: `bookmark-trigger.value`
   - State: `playhead-time.data`, `last-event-type.data`, `available-events.data`
   - Output: `event-modal.is_open`, `event-type-select.options/value`, `event-start-time.value`, `pending-event-time.data`
   - Action: Open modal, populate dropdown, auto-select last event type, display start time

3. **Toggle New Event Type** (`toggle_new_event_type_input`)
   - Trigger: `event-type-select.value`
   - Output: `new-event-type-container.style`
   - Action: Show/hide new event type input based on "Create new" selection

4. **Save Event** (`save_event`)
   - Trigger: `save-event-btn.n_clicks` (or Enter key via clientside callback)
   - State: `event-type-select.value`, `new-event-type-input.value`, `pending-event-time.data`, `event-end-time.value`, `selected-dataset.data`, `selected-deployment.data`
   - Output: `event-modal.is_open`, `last-event-type.data`, `available-events.data`
   - Action: Write event to Iceberg via `duck_pond.write_event()`, update stores, close modal

**Quick Workflow**: B → Enter (creates point event with last-used event type)

## Data Structures

### Store Schemas

| Store ID | Type | Purpose | Example Value |
|----------|------|---------|---------------|
| `selected-dataset` | str | Current dataset name | `"nesc-adult-hi-monk-seal_dive-imu_SR-MB"` |
| `selected-deployment` | dict | Current deployment metadata | `{"deployment": "2019-11-08_apfo-001", "animal": "apfo-001a", ...}` |
| `all-datasets-deployments` | dict | All datasets with deployments | `{"dataset1": [deployment1, ...], ...}` |
| `playhead-time` | float | Current playhead timestamp (Unix seconds) | `1573228800.0` |
| `is-playing` | bool | Playback state | `True` |
| `playback-rate` | float | Playback speed multiplier (0.1, 0.5, 1, 5, 10, or 100) | `1` |
| `playback-timestamps` | List[float] | All available timestamps | `[1573228800.0, 1573228801.0, ...]` |
| `arrow-key-input` | str | Hidden input for arrow key events (direction:timestamp) | `"1:1699123456789"` |
| `selected-video` | dict | Currently selected video | `{"id": "...", "shareUrl": "...", ...}` |
| `manual-video-override` | dict | Manual video selection override | `{"id": "...", ...}` |
| `video-time-offset` | float | Video time offset in seconds | `0.0` |
| `current-video-options` | List[dict] | Available videos for current deployment | `[{...}, ...]` |
| `available-channels` | List[dict] | Channel metadata from DuckPond | `[{"kind": "group", "group": "depth", ...}, ...]` |
| `selected-channels` | List[str] | User-selected channel groups | `["depth", "prh", "temperature"]` |
| `channel-order` | List[dict] | Channel display order (from children) | `[{"id": 1, "index": 0, "value": "depth"}, ...]` |
| `channel-order-from-dom` | List[str] | Channel values in DOM order (for drag-drop) | `["depth", "prh", "temperature"]` |
| `is-loading-data` | bool | Data loading state | `False` |
| `selected-timezone` | float | Timezone offset in hours | `-10.0` |
| `figure-store` | FigureResampler | Server-side cached FigureResampler object | (cached via `Serverside()`) |
| `available-events` | List[dict] | Event types for current deployment | `[{"event_key": "dive", "color": "#3498db", "is_point_event": False, "count": 50}, ...]` |
| `selected-events` | List[dict] | User event selections | `[{"event_key": "dive", "signal": "depth", "enabled": True}, ...]` |
| `timeline-bounds` | dict | Current zoom range (used to preserve zoom on graph updates) | `{"min": 1573228800.0, "max": 1573232400.0}` |
| `original-bounds` | dict | Original dataset bounds (persists for reset zoom) | `{"min": 1573228800.0, "max": 1573232400.0}` |
| `bookmark-trigger` | str | Hidden input for B key events (triggers event modal) | `"open:1699123456789"` |
| `last-event-type` | str | Last used event type for auto-fill | `"breath"` |
| `pending-event-time` | float | Playhead time captured when event modal opens | `1573228800.0` |

### data_pkl Structure

```python
DataPkl(
    signal_data={
        "depth": pd.DataFrame(columns=["datetime", "depth"]),
        "temperature": pd.DataFrame(columns=["datetime", "temp_ext"]),
        "prh": pd.DataFrame(columns=["datetime", "pitch", "roll", "heading"]),
        ...
    },
    signal_info={
        "depth": {
            "channels": ["depth"],
            "metadata": {"depth": {"original_name": "Depth", "unit": "m"}}
        },
        "prh": {
            "channels": ["pitch", "roll", "heading"],
            "metadata": {...}
        },
        ...
    },
    event_data=pd.DataFrame(columns=["key", "datetime", "duration", "datetime_end", "short_description"])  # Optional
)
```

**Access**: Supports both attribute (`data_pkl.signal_data`) and dict (`data_pkl["signal_data"]`) access

**Event Data Format**: Transformed from DuckPond format (`event_key`, `datetime_start`, `datetime_end`) via `transform_events_for_graph()`

### Deployment Metadata Structure

```python
{
    "deployment": "2019-11-08_apfo-001",
    "animal": "apfo-001a",
    "deployment_date": "2019-11-08",
    "min_date": "2019-11-08T00:00:00",
    "max_date": "2019-11-08T23:59:59",
    "sample_count": 1000000,
    "icon_url": "/assets/images/penguin.svg"
}
```

### Video Options Structure

```python
{
    "id": "video-uuid",
    "filename": "video.mp4",
    "shareUrl": "https://...",
    "originalUrl": "https://...",
    "fileCreatedAt": "2019-11-08T12:00:00Z",
    "metadata": {
        "duration": "00:05:30.123"
    }
}
```

## Custom Components

### ThreeJsOrientation

**Location**: `three_js_orientation/three_js_orientation/ThreeJsOrientation.py`

**Props**:
- `id` (string, optional)
- `activeTime` (number, required) - Timestamp in milliseconds
- `data` (string, required) - JSON string with orientation data (pitch, roll, heading)
- `modelFile` (string, default="/assets/PenguinSwim.obj") - Path to 3D model file (supports .obj, .glb, .gltf, .fbx)
- `textureFile` (string, optional) - Path to texture file (mainly for OBJ)

**Supported 3D Formats**:
- `.obj` - OBJ format (uses OBJLoader)
- `.glb`/`.gltf` - glTF/GLB format (uses GLTFLoader)
- `.fbx` - FBX format (uses FBXLoader)

**Dynamic Model Loading**:
The model file URL is fetched dynamically from Notion Asset DB when a deployment is selected:
- Lookup chain: Animal → Asset DB → Best-3D-model property
- Falls back to `/assets/PenguinSwim.obj` if no model found

**Usage**:
```python
three_js_orientation.ThreeJsOrientation(
    id="three-d-model",
    activeTime=1573228800000,  # milliseconds
    data=model_df.to_json(orient="split"),
    modelFile="/assets/PenguinSwim.obj"  # Default, overridden by callback
)
```

**Data Format**: DataFrame with datetime index and columns: `pitch`, `roll`, `heading`

### VideoPreview

**Location**: `video_preview/video_preview/VideoPreview.py`

**Props**:
- `id` (string, optional)
- `videoSrc` (string, optional) - Video URL
- `videoMetadata` (dict, optional) - `{"fileCreatedAt": "...", "duration": "...", "filename": "..."}`
- `datasetStartTime` (number, optional) - Dataset start timestamp (Unix seconds)
- `playheadTime` (number, optional) - Current playhead time (Unix seconds)
- `isPlaying` (bool, default False) - Playback state
- `timeOffset` (number, default 0) - Time offset in seconds
- `showControls` (bool, default True) - Show video controls

**Usage**:
```python
video_preview.VideoPreview(
    id="video-trimmer",
    videoSrc="https://...",
    videoMetadata={"fileCreatedAt": "...", "duration": "..."},
    datasetStartTime=1573228800.0,
    playheadTime=1573228800.0,
    isPlaying=False
)
```

## Integration Points

### DuckPond Service

**Location**: `DiveDB/services/duck_pond.py`

**Key Methods Used**:
- `get_all_datasets_and_deployments(use_cache)` → dict - Returns all datasets with deployments (5-min TTL)
- `get_available_channels(dataset, include_metadata, pack_groups, load_metadata, use_cache)` → List[dict] - Returns channel metadata (1-hour TTL)
- `get_channels_metadata(dataset, channel_ids)` → dict - Returns metadata for specific channels
- `get_data(dataset, deployment_ids, animal_ids, date_range, frequency, labels, add_timestamp_column, apply_timezone_offset, pivoted, use_cache)` → pd.DataFrame - Fetches data (1-day TTL)
- `get_events(dataset, animal_ids, date_range, apply_timezone_offset, add_timestamp_columns, use_cache)` → pd.DataFrame - Fetches events (5-min TTL)
- `get_deployment_timezone_offset(deployment_id, use_cache)` → float - Returns timezone offset in hours (1-hour TTL)
- `get_3d_model_for_animal(animal_id, use_cache)` → dict - Returns 3D model info from Notion (1-hour TTL)
- `estimate_data_size(dataset, labels, deployment_ids, animal_ids, date_range)` → int - Estimates row count

**Caching**: All methods with `use_cache` parameter support file-based caching via `DiveDB/services/utils/cache_utils.py`. Enable with `DASH_USE_CACHE=true` environment variable.

**Initialization**: `DuckPond.from_environment(notion_manager=notion_manager)` (data_visualization.py:61)

### NotionORM Service

**Location**: `DiveDB/services/notion_orm.py`

**Purpose**: Metadata management (animals, deployments, recordings, loggers)

**Initialization**: `NotionORMManager(token, db_map)` (data_visualization.py:38-50)

**Database Maps**:
- Deployment DB, Recording DB, Logger DB, Animal DB, Asset DB, Dataset DB, Signal DB, Standardized Channel DB

### ImmichService

**Location**: `DiveDB/services/immich_service.py`

**Key Methods Used**:
- `find_media_by_deployment_id(deployment_id, media_type, shared, use_cache)` → dict - Finds videos/images by deployment (1-hour TTL)
- `prepare_video_options_for_react(media_result)` → dict - Formats video data for React components

**Caching**: Supports file-based caching via `use_cache` parameter. Enable with `DASH_USE_CACHE=true`.

**Initialization**: `ImmichService()` (data_visualization.py:62)

**Environment Variables**: `IMMICH_API_KEY`, `IMMICH_BASE_URL`

## Common Patterns

### Adding a New Callback

1. Define callback function in appropriate module:
   - Playback/video: `callbacks.py`
   - Selection/data loading: `selection_callbacks.py`
   - UI interactions: `clientside_callbacks.py`

2. Register in registration function:
   ```python
   @app.callback(
       Output("component-id", "prop"),
       Input("trigger-id", "prop"),
       State("state-id", "prop")
   )
   def my_callback(trigger_value, state_value):
       # Implementation
       return output_value
   ```

3. Call registration function in `data_visualization.py` (lines 175-182)

### Adding a New Graph Channel

1. Channel metadata comes from DuckPond (`available-channels` store)
2. User clicks "+ Add" in CHANNELS header → `add_new_channel()` adds row
3. User selects channel via `channel-select` dropdown
4. User can drag-drop to reorder (visual only until Update Graph clicked)
5. User clicks "Update Graph" → clientside reads DOM order → `update_graph_from_channels()` regenerates

**Manage Channels Popover Structure**:
- CHANNELS header with "+ Add" link
- Channel rows (drag handle, dropdown, remove button)
- EVENTS section with checkboxes and signal dropdowns
- "Update Graph" button at bottom

### Adding Events to Graphs

1. Events loaded from DuckPond during deployment selection → `available-events` store
2. User enables events via checkboxes in "EVENTS" section of Manage Channels popover
3. User selects target signal for each event type via dropdown
4. On "Update Graph", callback collects event selections via pattern-matching IDs
5. `generate_graph_from_channels()` builds `note_annotations`/`state_annotations` dicts
6. `plot_tag_data_interactive()` renders events on specified subplots
7. Point events (duration=0): markers at signal max; State events: shaded rectangles

### Plotly-Resampler Pattern

**Overview**: Uses `plotly-resampler` with `dash-extensions` for automatic data resampling on zoom/pan

**Implementation**:
1. `graph_utils.py` creates `FigureResampler` objects (not standard `go.Figure`)
2. Callbacks that generate graphs cache the `FigureResampler` via `Serverside(fig)`
3. `update_graph_on_zoom()` callback listens to `relayoutData` and calls `fig.construct_update_data_patch()`
4. All high-resolution data loaded once; resampler dynamically adjusts resolution based on zoom level

**Key Points**:
- App uses `DashProxy` instead of `dash.Dash` (required for `Serverside` caching)
- `figure-store` holds cached `FigureResampler` per session
- No manual high-res button needed - automatic on zoom/pan
- `memoize=True` on zoom callback prevents redundant updates

### Adding a New Layout Section

1. Create component function in appropriate `layout/` module
2. Import in `layout/__init__.py`
3. Add to `create_layout()` in `data_visualization.py` or appropriate layout function
4. Add any required stores in `create_app_stores()`
5. Create callbacks to update the section

### Data Loading Pattern

1. User selects deployment → `select_deployment_and_load_visualization()` triggered
2. Show loading overlay → `show_loading_overlay()`
3. Fetch channels → `duck_pond.get_available_channels()`
4. Select default channels → Priority-based selection (depth, prh, pressure, temperature, light)
5. Generate graph → `generate_graph_from_channels()`
   - Expand groups to labels
   - Estimate data size
   - Adjust frequency if needed (downsampling)
   - Load data from DuckPond
   - Create data_pkl structure
   - Generate FigureResampler object (contains all high-res data in memory)
6. Cache FigureResampler → Store via `Serverside(fig)` in `figure-store`
7. Load videos → `immich_service.find_media_by_deployment_id()`
8. Load events → `duck_pond.get_events()`
9. Generate timeline → `create_timeline_section()`
10. Hide loading overlay → `hide_loading_overlay()`
11. User zooms/pans → `update_graph_on_zoom()` automatically resamples from cached data

### Styling Updates

**SASS**: `dash/assets/sass/_app.scss` → Compile with `npm run build-css` before testing

**Timeline Indicators**: Use CSS variables (`--start`, `--end`, `--length`) for positioning. Don't use inline styles on indicator buttons.

## Maintenance Guidelines

### When to Update This Documentation

- **New Files**: Add entry to File Map table
- **New Callbacks**: Document in Module Reference → Key Callbacks section
- **New Data Stores**: Add to Store Schemas table
- **New Integration Points**: Add to Integration Points section
- **Architecture Changes**: Update Architecture Overview section
- **New Patterns**: Add to Common Patterns section

### Documentation Standards

1. **Keep it Token-Efficient**:
   - Use tables for structured data
   - Use bullet lists over prose
   - Function signatures only, no implementation details
   - Reference file paths and line numbers, not code
   - High-level architecture, not low-level implementation

2. **What to Include**:
   - File purposes and key exports
   - Function signatures and return types
   - Callback chains and data flow
   - Integration points and service methods
   - Important architectural decisions

3. **What to Exclude**:
   - Implementation details (how functions work internally)
   - Code examples (except for data structures)
   - Step-by-step procedures
   - CSS/styling specifics (mention file location only)
   - Detailed parameter explanations

4. **Front-Load Important Info**:
   - Quick Reference at top
   - Most common patterns first
   - Detailed reference sections follow

### Update Checklist

When making changes, check if documentation needs updates:

- [ ] New callback added → Add to Module Reference (signature only)
- [ ] New store added → Add to Store Schemas table
- [ ] New file created → Add to File Map table
- [ ] Function signature changed → Update Module Reference
- [ ] Data structure changed → Update Data Structures section
- [ ] Integration point changed → Update Integration Points
- [ ] New major pattern → Add to Common Patterns (high-level only)
- [ ] SASS changes → Note location, compile command if new

**Remember**: Document "what" and "where", not "how". Keep entries under 2 lines.

### Version Tracking

- Document major architectural changes
- Note breaking changes in callback signatures
- Track changes to data structures
- Maintain compatibility notes for external integrations

