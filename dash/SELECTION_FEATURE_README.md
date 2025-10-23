# Dynamic Dataset & Deployment Selection Feature

## Project Goal

Transform the Dash data visualization dashboard from a hard-coded single-deployment viewer into a **dynamic single-page web application** where users can:

1. **Select a dataset** from available datasets in the data lake
2. **Choose a deployment** from that dataset
3. **Load the visualization** with the deployment's full date range

This enables flexible exploration of any deployment in any dataset without code changes. The deployment's start and end dates (from the database) are used as the source of truth - no manual date selection needed.

## Architecture Overview

### File Structure (Refactored)

We broke up the monolithic `layout.py` file into organized modules:

```
dash/
├── data_visualization.py          # Main app entry point
├── callbacks.py                   # Standard callbacks (playback, video selection)
├── clientside_callbacks.py        # Client-side callbacks (fullscreen, etc.)
├── selection_callbacks.py         # NEW: Dataset/deployment selection logic
└── layout/
    ├── __init__.py
    ├── core.py                    # Main layout structure
    ├── sidebar.py                 # Left sidebar with selection controls
    ├── timeline.py                # Footer with playhead controls
    ├── indicators.py              # Event and video indicators
    └── modals.py                  # Modal dialogs
```

### Data Flow

```
User Action → Callback → Store Update → UI Update → Next Callback
```

**Example Flow:**
1. User selects dataset → `update_selected_dataset` → `selected-dataset` store
2. Dataset change → `load_deployments_for_dataset` → populates deployment list
3. User clicks deployment → `select_deployment` → `selected-deployment` store
4. Deployment selected → `update_deployment_info` → shows deployment details and enables button
5. `update_load_button` → automatically sets date range from deployment min/max dates
6. User clicks button → `load_visualization` → fetches data & updates graph

## Current Status: ✅ BASIC FUNCTIONALITY WORKING

### ✅ What's Working

1. **Initial data loading** - Datasets and deployments load on app startup
2. **Dataset dropdown** - Displays available datasets
3. **Deployment list** - Shows deployments with metadata (animal ID, date, sample count)
4. **Deployment selection** - Click detection works and stores deployment data
5. **Deployment info display** - Shows selected deployment details (animal, dates, sample count)
6. **Load button** - Enables when deployment is selected (uses deployment's date range automatically)
7. **Data visualization loading** - Successfully loads and displays deployment data! ✨
8. **File organization** - Successfully modularized the codebase

### ⚠️ What's Not Yet Implemented

**The following features are not yet integrated but can be added incrementally:**

- **3D model synchronization** - Three.js orientation model needs data updates
- **Video player integration** - Video loading and sync with timeline
- **Playback controls** - Play/pause and timeline scrubbing
- **Event indicators** - Display of event markers on timeline
- **Advanced graph features** - From the original `plot_tag_data_interactive5` function

### 🎯 Current Implementation

The `load_visualization` callback now successfully loads data using a **simplified approach**:

**What it does:**
1. Queries available data labels for the selected deployment
2. Uses `duck_pond.get_data()` with `frequency=1` to get resampled DataFrame
3. Creates a multi-subplot Plotly figure with up to 10 signal traces
4. Uses `Scattergl` for efficient rendering of time-series data
5. Includes a range slider for easy navigation

**Key simplifications:**
- Uses direct DataFrame plotting instead of complex `data_pkl` structure
- Loads first 20 labels at 1 Hz for quick initial display
- Creates simple subplots instead of the full `plot_tag_data_interactive5` layout
- No conflicts with existing callbacks (no other callback controls `graph-content.figure`)

## Key Lessons Learned

### 1. **Dash Callback Rules are Strict**

- **ONE callback per output** - Dash does not allow multiple callbacks to control the same component property
- `allow_duplicate=True` exists but is complex and order-dependent
- **Solution:** Design callbacks to output to different properties or use intermediate stores

### 2. **Initial Data Loading Challenges**

Dash callbacks only fire when inputs **change**, not when they're initialized. We tried multiple approaches:

❌ **Failed Approaches:**
- `Input("url", "pathname")` - Doesn't fire reliably on initial load
- `Input("initial-load-interval", "n_intervals")` - Timing issues
- `Input("app-loaded", "data")` with `data=True` - Never changes, so never fires
- `prevent_initial_call=False` - Inconsistent behavior

✅ **Working Solution:**
- Load data directly in `data_visualization.py` at app startup
- Pass initial data to `create_layout()` as arguments
- Populate UI components during initial rendering
- Callbacks only handle *changes* after initial load

### 3. **Pattern-Matching Callbacks Work, But...**

```python
Input({"type": "deployment-button", "index": dash.dependencies.ALL}, "n_clicks")
```

This works great for dynamically generated buttons, but:
- Must be registered before any matching components exist
- Debug carefully - silent failures are common
- Use clear print statements to trace execution

### 4. **Multiple App Instances = Chaos**

We discovered **two instances** of the app running simultaneously, causing:
- Duplicate callback registrations
- Confusing error messages
- Inconsistent behavior

**Always check:** `ps aux | grep data_visualization` before debugging!

### 5. **Callback Registration Order Matters**

When using `allow_duplicate=True`, the **primary** callback (without the flag) must be registered before secondary callbacks (with the flag). We changed:

```python
# WRONG ORDER (causes issues)
register_clientside_callbacks(app)      # Has allow_duplicate
register_selection_callbacks(app)       # Primary outputs

# CORRECT ORDER
register_selection_callbacks(app)       # Primary outputs first
register_clientside_callbacks(app)      # Duplicates second
```

## Next Steps to Enhance the Feature

### Step 1: Test the Basic Flow ✅ READY TO TEST

The core workflow is now implemented:
1. Select dataset → loads deployments ✅
2. Click deployment → shows deployment info and enables load button ✅
3. Click "Load Visualization" → fetches and displays data ✅

**To test:**
```bash
cd dash
python data_visualization.py
```
Then navigate to http://localhost:8054

### Step 2: Add More Advanced Visualization Features

**Priority enhancements:**
1. **Allow signal selection** - Let users choose which signals to display
2. **Adjustable sampling rate** - Control frequency parameter
3. **Use `plot_tag_data_interactive5`** - Switch to the full-featured plotting function
4. **Event overlays** - Query and display events on the timeline
5. **Improve subplot layout** - Match original dashboard aesthetics

### Step 3: Integrate Video and 3D Model

These components need data updates from the loaded deployment:
1. **Video player** - Load videos from Immich for the deployment date range
2. **3D orientation model** - Update with orientation data
3. **Synchronize playback** - Connect timeline to video and 3D model

### Step 4: Re-enable Playback Controls

Currently the playback system exists but isn't connected to the new loading flow:
- Connect playhead slider to loaded data range
- Update playhead line on graph (currently commented out)
- Sync play/pause with video and 3D model

### Step 5: Polish & Testing

**Error handling improvements:**
- Better loading indicators (currently uses fullscreen loading)
- Informative error messages for common issues
- Handle edge cases (no data, invalid date ranges, etc.)

**User experience:**
- Add deployment search/filter for long lists
- Remember last selected dataset
- Add export/download data functionality
- Performance optimization for large deployments

## Code Snippets Reference

### Working "Back to Basics" Test Callback

This simple callback proves the pattern-matching works:

```python
@app.callback(
    Output("deployment-loading-output", "children", allow_duplicate=True),
    Input({"type": "deployment-button", "index": dash.dependencies.ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def test_deployment_click(n_clicks_list):
    """Test if deployment button click is detected."""
    if callback_context.triggered and any(n_clicks_list or []):
        return html.Div("✅ Button clicked!", className="alert alert-success small")
    return no_update
```

### Initial Data Loading Pattern

```python
# In data_visualization.py
print("🔍 Loading datasets from data lake...")
available_datasets = duck_pond.get_all_datasets()

initial_deployments = []
if available_datasets:
    default_dataset = available_datasets[0]
    # Query deployments for default dataset
    view_name = duck_pond.get_view_name(default_dataset, "data")
    query = f"""
        SELECT DISTINCT deployment, animal, 
               MIN(datetime) as min_date, 
               MAX(datetime) as max_date,
               COUNT(*) as sample_count
        FROM {view_name}
        WHERE deployment IS NOT NULL AND animal IS NOT NULL
        GROUP BY deployment, animal
        ORDER BY min_date DESC
    """
    deployments_df = duck_pond.conn.sql(query).df()
    initial_deployments = deployments_df.to_dict('records')

# Pass to layout
app.layout = create_layout(
    available_datasets=available_datasets,
    initial_deployments=initial_deployments,
    # ... other args
)
```

## Debug Tips

### Check for Multiple Running Processes
```bash
ps aux | grep "python.*data_visualization"
# Kill all: pkill -f "python.*data_visualization.py"
```

### Enable Callback Tracing
Add print statements at the start of each callback:
```python
def my_callback(...):
    print(f"🎯 my_callback fired: {locals()}")
```

### Check Browser Console
All Dash errors appear in browser console (F12). Look for:
- "Duplicate callback outputs"
- Component not found errors
- Callback execution traces

### Verify Callback Registration
In `data_visualization.py`:
```python
print("🚀 Starting callback registration...")
register_callbacks(...)
print("✓ Callbacks registered")
```

## Resources

- [Dash Callback Documentation](https://dash.plotly.com/basic-callbacks)
- [Pattern-Matching Callbacks](https://dash.plotly.com/pattern-matching-callbacks)
- [Dash Store Component](https://dash.plotly.com/dash-core-components/store)
- [DuckDB SQL Reference](https://duckdb.org/docs/sql/introduction)

---

## Recent Changes (2025-10-23)

### Phase 1: Simplified Date Selection ✅ Complete
- **Removed manual date/time selection UI** - No more date pickers or time inputs
- **Removed timezone selection** - Can be added back if needed
- Deployment's `min_date` and `max_date` from database are now the source of truth
- Simplified workflow: Select dataset → Select deployment → Load (3 steps instead of 5)

### Phase 2: Basic Visualization Loading ✅ Complete
- **Enabled `load_visualization` callback** - No callback conflicts!
- **Simple but functional approach** - Uses `duck_pond.get_data(frequency=1)` for direct DataFrame loading
- **Multi-subplot display** - Shows up to 10 signals with shared x-axis and range slider
- **Robust error handling** - Clear error messages for no data, query failures, etc.
- **Print statements for debugging** - Easy to trace data loading process

### Updated Callbacks
- `update_date_range_controls` → `update_deployment_info`: Displays deployment details
- `update_load_button`: Enables button when deployment selected, auto-populates date range
- `load_visualization`: NEW - Loads and displays deployment data in graph

**Last Updated:** 2025-10-23  
**Status:** ✅ Core visualization feature working!  
**Next Action:** Test the app and iterate on enhancements

