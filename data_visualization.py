import dash
from dash import dcc, html, Output, Input, State
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import pandas as pd
import three_js_orientation
import pytz

# import DiveDB.services.duck_pond
# importlib.reload(DiveDB.services.duck_pond)
from DiveDB.services.duck_pond import DuckPond

duckpond = DuckPond()

labels = duckpond.conn.sql(
    """
    SELECT DISTINCT label
    FROM DataLake
    WHERE animal = 'oror-002'
    """
).df()

labels = sorted(
    [
        name
        for name in labels.label.to_list()
        if (name.startswith("sensor") or name.startswith("logger"))
    ]
)

app = dash.Dash(__name__)

dff = duckpond.get_delta_data(
    animal_ids="oror-002",
    frequency=1,
    labels=labels,
)

# Convert datetime to timestamp (seconds since epoch) for slider control
dff["timestamp"] = dff["datetime"].apply(lambda x: x.timestamp())

# Create the figure with subplots
fig = make_subplots(
    rows=len(dff.columns[1:-1]), cols=1, shared_xaxes=True, vertical_spacing=0.03
)
for idx, col in enumerate(dff.columns[1:-1]):  # Exclude 'timestamp' column
    fig.add_trace(
        go.Scattergl(
            x=dff["datetime"], y=dff[col], mode="lines", name=col, showlegend=True
        ),
        row=idx + 1,
        col=1,
    )

# Set x-axis range to data range and set uirevision
fig.update_layout(
    xaxis=dict(range=[dff["datetime"].min(), dff["datetime"].max()]),
    uirevision="constant",  # Maintain UI state across updates
)

dates = pd.date_range(start="2021-01-01", periods=10, freq="T")
data = {
    "pitch": [i * 5 for i in range(10)],
    "roll": [i * 3 for i in range(10)],
    "heading": [i * 10 for i in range(10)],
}
df = pd.DataFrame(data, index=dates)

# Convert DataFrame to JSON
data_json = df.to_json(orient="split")

# Define the app layout
app.layout = html.Div(
    [
        three_js_orientation.ThreeJsOrientation(
            id="three-d-model",
            data=data_json,
            activeTime="2021-01-01T00:01:00Z",
            fbxFile="/assets/6_KillerWhaleOrca_v020_HR_fast.fbx",
            style={"width": "50vw", "height": "40vw"},
        ),
        dcc.Graph(id="graph-content", figure=fig),
        html.Div(
            [
                html.Button("Play", id="play-button", n_clicks=0),
                dcc.Slider(
                    id="playhead-slider",
                    min=dff["timestamp"].min(),
                    max=dff["timestamp"].max(),
                    value=dff["timestamp"].min(),
                    marks=None,
                    tooltip={"placement": "bottom"},
                ),
                dcc.Interval(
                    id="interval-component",
                    interval=1 * 1000,  # Base interval of 1 second
                    n_intervals=0,
                    disabled=True,  # Start with the interval disabled
                ),
                dcc.Store(id="playhead-time", data=dff["timestamp"].min()),
                dcc.Store(id="is-playing", data=False),
            ]
        ),
    ]
)


@app.callback(
    Output("three-d-model", "activeTime"), [Input("interval-component", "n_intervals")]
)
def update_active_time(n_intervals):
    next_time_index = n_intervals % len(df.index)
    next_time = df.index[next_time_index]
    return next_time.tz_localize(pytz.UTC).isoformat()


# Callback to toggle play/pause state
@app.callback(
    Output("is-playing", "data"),
    Output("play-button", "children"),
    Input("play-button", "n_clicks"),
    State("is-playing", "data"),
)
def play_pause(n_clicks, is_playing):
    if n_clicks % 2 == 1:
        return True, "Pause"  # Switch to playing
    else:
        return False, "Play"  # Switch to paused


# Callback to enable/disable the interval component based on play state
@app.callback(Output("interval-component", "disabled"), Input("is-playing", "data"))
def update_interval_component(is_playing):
    return not is_playing  # Interval is disabled when not playing


# Callback to update playhead time based on interval or slider input
@app.callback(
    Output("playhead-time", "data"),
    Output("playhead-slider", "value"),
    Input("interval-component", "n_intervals"),
    Input("playhead-slider", "value"),
    State("is-playing", "data"),
    prevent_initial_call=True,
)
def update_playhead(n_intervals, slider_value, is_playing):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if trigger_id == "interval-component" and is_playing:
        # Find the current index based on the slider value
        current_idx = dff["timestamp"].sub(slider_value).abs().idxmin()
        next_idx = (
            current_idx + 5 if current_idx + 5 < len(dff) else 0
        )  # Loop back to start
        new_time = dff["timestamp"].iloc[next_idx]
        return new_time, new_time
    elif trigger_id == "playhead-slider":
        return slider_value, slider_value
    else:
        raise dash.exceptions.PreventUpdate


# Callback to update the graph with the playhead line
@app.callback(
    Output("graph-content", "figure"),
    Input("playhead-time", "data"),
    State("graph-content", "figure"),
)
def update_graph(playhead_timestamp, existing_fig):
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
            line=dict(width=2, dash="solid"),
        )
    )
    existing_fig["layout"]["uirevision"] = "constant"
    return existing_fig


if __name__ == "__main__":
    app.run_server(debug=True)
