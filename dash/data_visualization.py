import os
import dash
from dash import dcc, html, Output, Input, State
import pandas as pd
from dotenv import load_dotenv

import three_js_orientation
import video_preview

from DiveDB.services.duck_pond import DuckPond
from graph_utils import plot_tag_data_interactive5

load_dotenv()
duckpond = DuckPond(os.getenv("HOST_DELTA_LAKE_PATH"))

app = dash.Dash(__name__)

dff = duckpond.get_delta_data(
    animal_ids="apfo-001a",
    frequency=1,
    labels=[
        "derived_data_depth",
        "sensor_data_temperature",
        "sensor_data_light",
        "pitch",
        "roll",
        "heading",
    ],
    date_range=("2019-11-08T09:33:11+13:00", "2019-11-08T09:39:30+13:00"),
)
# Convert to UTC
dff["datetime"] = dff["datetime"].dt.tz_localize("UTC")
# convert the datetime in dff to +13 timezone
dff["datetime"] = dff["datetime"] + pd.Timedelta(hours=13)

# Convert datetime to timestamp (seconds since epoch) for slider control
dff["timestamp"] = dff["datetime"].apply(lambda x: x.timestamp())
dff["depth"] = dff["derived_data_depth"].apply(lambda x: x * -1)

# Replace the existing figure creation with a call to the new function
fig = plot_tag_data_interactive5(
    data_pkl={
        "sensor_data": {
            "light": dff[["datetime", "sensor_data_light"]],
            "temperature": dff[["datetime", "sensor_data_temperature"]],
        },
        "derived_data": {
            "prh": dff[["datetime", "pitch", "roll", "heading"]],
            "depth": dff[["datetime", "depth"]],
        },
        "sensor_info": {
            "light": {
                "channels": ["sensor_data_light"],
                "metadata": {
                    "sensor_data_light": {
                        "original_name": "Light",
                        "unit": "lux",
                    }
                },
            },
            "temperature": {
                "channels": ["sensor_data_temperature"],
                "metadata": {
                    "sensor_data_temperature": {
                        "original_name": "Temperature (imu)",
                        "unit": "°C",
                    }
                },
            },
        },
        "derived_info": {
            "depth": {
                "channels": ["depth"],
                "metadata": {
                    "depth": {
                        "original_name": "Corrected Depth",
                        "unit": "m",
                    }
                },
            },
            "prh": {
                "channels": ["pitch", "roll", "heading"],
                "metadata": {
                    "pitch": {
                        "original_name": "Pitch",
                        "unit": "°",
                    },
                    "roll": {
                        "original_name": "Roll",
                        "unit": "°",
                    },
                    "heading": {
                        "original_name": "Heading",
                        "unit": "°",
                    },
                },
            },
        },
    },
    sensors=["light", "temperature"],
)

# Set x-axis range to data range and set uirevision
fig.update_layout(
    xaxis=dict(range=[dff["datetime"].min(), dff["datetime"].max()]),
    uirevision="constant",  # Maintain UI state across updates
)

# Convert DataFrame to JSON
data_json = dff[["datetime", "pitch", "roll", "heading"]].to_json(orient="split")

# Define the app layout
app.layout = html.Div(
    [
        html.Div(
            [
                three_js_orientation.ThreeJsOrientation(
                    id="three-d-model",
                    data=data_json,
                    activeTime=0,
                    objFile="/assets/PenguinSwim.obj",
                    textureFile="/assets/PenguinSwim.png",
                    style={"width": "50vw", "height": "40vw"},
                ),
                video_preview.VideoPreview(
                    id="video-trimmer",
                    # Video file must be downloaded from https://figshare.com/ndownloader/files/50061327
                    videoSrc="/assets/fixed_video_output_00001_excerpt.mp4",
                    # activeTime=0,
                    playheadTime=dff["timestamp"].min(),
                    isPlaying=False,
                    style={"width": "50vw", "height": "40vw"},
                ),
            ],
            style={"display": "flex"},
        ),
        html.Div(
            "Playhead Control",
            style={
                "margin-top": "32px",
                "margin-right": "10px",
                "font-weight": "bold",
                "font-family": "sans-serif",
            },
        ),
        html.Div(
            [
                html.Button(
                    "Play", id="play-button", n_clicks=0, style={"margin-right": "10px"}
                ),
                html.Div(
                    dcc.Slider(
                        id="playhead-slider",
                        min=dff["timestamp"].min(),
                        max=dff["timestamp"].max(),
                        value=dff["timestamp"].min(),
                        marks=None,
                        tooltip={"placement": "bottom"},
                    ),
                    style={
                        "flex": "1",
                        "align-items": "center",
                        "margin-top": "25px",
                        "margin-right": "180px",
                    },
                ),
            ],
            style={"display": "flex", "align-items": "center", "width": "100%"},
        ),
        dcc.Interval(
            id="interval-component",
            interval=1 * 1000,  # Base interval of 1 second
            n_intervals=0,
            disabled=True,  # Start with the interval disabled
        ),
        dcc.Store(id="playhead-time", data=dff["timestamp"].min()),
        dcc.Store(id="is-playing", data=False),
        dcc.Graph(id="graph-content", figure=fig),
    ]
)


# Callback to update VideoPreview props
@app.callback(
    Output("video-trimmer", "playheadTime"),
    Output("video-trimmer", "isPlaying"),
    Input("playhead-time", "data"),
    Input("is-playing", "data"),
)
def update_video_preview(playhead_time, is_playing):
    return playhead_time, is_playing


@app.callback(
    Output("three-d-model", "activeTime"), [Input("playhead-slider", "value")]
)
def update_active_time(slider_value):
    # Find the nearest datetime to the slider value
    nearest_idx = dff["timestamp"].sub(slider_value).abs().idxmin()
    return nearest_idx


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
            current_idx + 1 if current_idx + 1 < len(dff) else 0
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
