import dash
from dash import dcc, html, Output, Input, State
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import pandas as pd
import three_js_orientation
import video_preview

# import DiveDB.services.duck_pond
# importlib.reload(DiveDB.services.duck_pond)
from DiveDB.services.duck_pond import DuckPond

duckpond = DuckPond("/data/delta-2")

app = dash.Dash(__name__)

dff = duckpond.get_delta_data(
    animal_ids="oror-002",
    frequency=10,
    labels=[
        "derived_data_depth",
        "ax",
        "ay",
        "az",
        "pitch",
        "roll",
        "heading",
    ],
    date_range=["2024-01-16 18:00:00", "2024-01-16 18:10:00"],
)

ecg_dff = duckpond.get_delta_data(
    animal_ids="oror-002",
    frequency=25,
    labels="sensor_data_ecg",
    date_range=["2024-01-16 18:00:00", "2024-01-16 18:10:00"],
)
# Convert datetime to timestamp (seconds since epoch) for slider control
dff["timestamp"] = dff["datetime"].apply(lambda x: x.timestamp())


color_mapping = {
    "ecg": "#d09191",
    "broad_bandpassed_signal": "#d09191",
    "narrow_bandpassed_signal": "#e64747",
    "spike_removed_signal": "#62b5d9",
    "smoothed_signal": "#9f76ba",
    "normalized_signal": "#6c4e7f",
    "depth": "#a2bae0",
    "pressure": "#a2bae0",
    "Corrected Depth": "#476390",
    "Accelerometer X": "#6CA1C3",
    "Accelerometer Y": "#99d8b5",
    "Accelerometer Z": "#e4d596",
    "Gyroscope X [mrad/s]": "#6ca1c3",
    "Gyroscope Y [mrad/s]": "#99d8b5",
    "Gyroscope Z [mrad/s]": "#e4d596",
    "Magnetometer X [\u00b5T]": "#6ca1c3",
    "Magnetometer Y [\u00b5T]": "#99d8b5",
    "Magnetometer Z [\u00b5T]": "#e4d596",
    "Filtered Heartbeats": "#e8d6d6",
    "Exhalation Breath": "#6ca1c3",
    "field_intensity_acc": "#88ba92",
    "field_intensity_mag": "#b884a7",
    "inclination_angle": "#d99e9d",
    "field_intensity_acc2": "#957684",
    "field_intensity_mag2": "#fc9e6d",
    "inclination_angle2": "#d6e1ff",
    "Corrected Accelerometer X [m/s\u00b2]": "#6CA1C3",
    "Corrected Accelerometer Y [m/s\u00b2]": "#99d8b5",
    "Corrected Accelerometer Z [m/s\u00b2]": "#e4d596",
    "Corrected Gyroscope X [mrad/s]": "#6ca1c3",
    "Corrected Gyroscope Y [mrad/s]": "#99d8b5",
    "Corrected Gyroscope Z [mrad/s]": "#e4d596",
    "Corrected Magnetometer X [\u00b5T]": "#6ca1c3",
    "Corrected Magnetometer Y [\u00b5T]": "#99d8b5",
    "Corrected Magnetometer Z [\u00b5T]": "#e4d596",
    "Pitch": "#e6aa5c",
    "Roll": "#94b6c3",
    "Heading": "#6f5398",
    "odba": "#87c577",
    "hr": "#9aad81",
    "Depth": "#476390",
    "ax": "#c7cccf",
    "ay": "#d1b4ea",
    "az": "#ec7cca",
    "gx": "#c38b95",
    "gy": "#94f199",
    "gz": "#ab8d77",
    "Light intensity 1 [raw]": "#a5e591",
    "Temperature (imu) [\u00b0C]": "#a39fc0",
}


def generate_random_color():
    """Generate a random pastel color in HEX format."""
    import random

    def r():
        return random.randint(100, 255)

    return f"#{r():02x}{r():02x}{r():02x}"


def plot_tag_data_interactive5(
    data_pkl,
    sensors=None,
    derived_data_signals=None,
    channels=None,
    time_range=None,
    note_annotations=None,
    zoom_start_time=None,
    zoom_end_time=None,
    plot_event_values=None,
    zoom_range_selector_channel=None,
):
    """
    Function to plot tag data interactively using Plotly with optional initial zooming into a specific time range.
    Includes both sensor_data and derived_data.
    """
    # Default sensor and derived data order
    default_order = [
        "ecg",
        "pressure",
        "accelerometer",
        "magnetometer",
        "gyroscope",
        "prh",
        "temperature",
        "light",
    ]

    # Determine the sensors and derived data to plot
    if sensors is None:
        sensors = list(data_pkl["sensor_data"].keys())

    if derived_data_signals is None:
        derived_data_signals = list(data_pkl["derived_data"].keys())

    # Combine sensors and derived data
    signals = sensors + derived_data_signals

    # Sort signals with the range selector signal on top if specified
    if zoom_range_selector_channel and zoom_range_selector_channel in signals:
        signals_sorted = [zoom_range_selector_channel] + [
            s for s in signals if s != zoom_range_selector_channel
        ]
    else:
        signals_sorted = sorted(
            signals,
            key=lambda x: (
                default_order.index(x)
                if x in default_order
                else len(default_order) + signals.index(x)
            ),
        )

    # Add subplots: One row per signal, plus extra row for the blank plot and event values if needed
    extra_rows = len(plot_event_values) if plot_event_values else 0
    total_rows = len(signals_sorted) + extra_rows + 1  # +1 for the blank plot
    fig = make_subplots(
        rows=total_rows, cols=1, shared_xaxes=True, vertical_spacing=0.03
    )

    row_counter = 1

    def plot_signal_data(signal, signal_data, signal_info):
        """General function to handle plotting both sensor and derived data."""
        # Determine the channels to plot for the current signal
        if channels is None or signal not in channels:
            signal_channels = signal_info["channels"]
        else:
            signal_channels = channels[signal]

        # Filter data to the specified time range
        if time_range:
            start_time, end_time = time_range
            signal_data_filtered = signal_data[
                (signal_data["datetime"] >= start_time)
                & (signal_data["datetime"] <= end_time)
            ]
        else:
            signal_data_filtered = signal_data

        for channel in signal_channels:
            if channel in signal_data_filtered.columns:
                x_data = signal_data_filtered["datetime"]
                y_data = signal_data_filtered[channel]

                # Set labels and line properties
                original_name = (
                    signal_info["metadata"]
                    .get(channel, {})
                    .get("original_name", channel)
                )
                unit = signal_info["metadata"].get(channel, {}).get("unit", "")
                y_label = f"{original_name} [{unit}]" if unit else original_name
                color = color_mapping.get(original_name, generate_random_color())
                color_mapping[original_name] = color

                fig.add_trace(
                    go.Scatter(
                        x=x_data,
                        y=y_data,
                        mode="lines",
                        name=y_label,
                        line=dict(color=color),
                    ),
                    row=row_counter,
                    col=1,
                )

    # Iterate through both sensor data and derived data and plot
    for signal in signals_sorted:
        if signal in data_pkl["sensor_data"]:
            signal_data = data_pkl["sensor_data"][signal]
            signal_info = data_pkl["sensor_info"][signal]

            plot_signal_data(signal, signal_data, signal_info)

            if row_counter == 1:  # Right after the first plot
                # Add blank plot with height of 200 pixels after the first plot
                fig.add_trace(
                    go.Scatter(x=[], y=[], mode="markers", showlegend=False),
                    row=row_counter + 1,
                    col=1,
                )
                fig.update_yaxes(
                    showticklabels=False, row=row_counter + 1, col=1
                )  # Hide tick labels
                fig.update_xaxes(
                    showticklabels=False, row=row_counter + 1, col=1
                )  # Hide tick labels
                row_counter += 1  # Skip to the next row after the blank plot

        elif signal in data_pkl["derived_data"]:
            signal_data = data_pkl["derived_data"][signal]
            signal_info = data_pkl["derived_info"][signal]

            plot_signal_data(signal, signal_data, signal_info)

            if row_counter == 1:  # Right after the first plot
                # Add blank plot with height of 200 pixels after the first plot
                fig.add_trace(
                    go.Scatter(x=[], y=[], mode="markers", showlegend=False),
                    row=row_counter + 1,
                    col=1,
                )
                fig.update_yaxes(
                    showticklabels=False, row=row_counter + 1, col=1
                )  # Hide tick labels
                fig.update_xaxes(
                    showticklabels=False, row=row_counter + 1, col=1
                )  # Hide tick labels
                row_counter += 1  # Skip to the next row after the blank plot

        # Plot note annotations if available
        if note_annotations:
            plotted_annotations = set()
            y_offsets = {}

            for note_type, note_params in note_annotations.items():
                note_channel = note_params["sensor"]
                signal_data, signal_info = (
                    (
                        data_pkl["sensor_data"].get(signal),
                        data_pkl["sensor_info"].get(signal),
                    )
                    if signal in data_pkl["sensor_data"]
                    else (
                        data_pkl["derived_data"].get(signal),
                        data_pkl["derived_info"].get(signal),
                    )
                )

                if signal_data is not None and note_channel in signal_data.columns:
                    filtered_notes = data_pkl["event_data"][
                        (data_pkl["event_data"]["key"] == note_type)
                        & (data_pkl["event_data"]["datetime"] >= time_range[0])
                        & (data_pkl["event_data"]["datetime"] <= time_range[1])
                    ]

                    if not filtered_notes.empty:
                        symbol = note_params.get("symbol", "circle")
                        color = note_params.get("color", "rgba(128, 128, 128, 0.5)")
                        y_fixed = (2 / 3) * signal_data[note_channel].max()

                        scatter_x, scatter_y = [], []
                        for dt in filtered_notes["datetime"]:
                            y_current = y_offsets.get(dt, y_fixed)
                            scatter_x.append(dt)
                            scatter_y.append(y_current)
                            y_offsets[dt] = y_current + 0.15 * y_fixed

                        fig.add_trace(
                            go.Scatter(
                                x=scatter_x,
                                y=scatter_y,
                                mode="markers",
                                marker=dict(symbol=symbol, color=color, size=10),
                                name=note_type,
                                opacity=0.5,
                                showlegend=(note_type not in plotted_annotations),
                            ),
                            row=row_counter,
                            col=1,
                        )
                        plotted_annotations.add(note_type)

        # Update y-axis label for each subplot
        if row_counter == 2:
            # Align the title of the blank plot (row 2) with the first plot (row 1)
            fig.update_yaxes(title_text=signal, row=1, col=1)
        else:
            # Keep the title where it is for the other rows
            fig.update_yaxes(title_text=signal, row=row_counter, col=1)
        row_counter += 1

    # Add event values as separate subplots
    if plot_event_values:
        for event_type in plot_event_values:
            event_data = data_pkl["event_data"][
                data_pkl["event_data"]["key"] == event_type
            ]
            if not event_data.empty:
                fig.add_trace(
                    go.Scatter(
                        x=event_data["datetime"],
                        y=[1] * len(event_data),
                        mode="markers",
                        name=f"{event_type} events",
                    ),
                    row=row_counter,
                    col=1,
                )
                fig.update_yaxes(
                    title_text=f"{event_type} events", row=row_counter, col=1
                )
                row_counter += 1

    # Apply zoom and configure rangeslider for the bottom subplot
    if zoom_start_time and zoom_end_time:
        fig.update_xaxes(range=[zoom_start_time, zoom_end_time])

    # Configure shared x-axis and rangeslider at the bottom
    fig.update_layout(
        title="Tag Data Visualization",
        xaxis=dict(
            rangeselector=dict(
                buttons=[
                    dict(count=30, label="30s", step="second", stepmode="backward"),
                    dict(count=5, label="5m", step="minute", stepmode="backward"),
                    dict(count=10, label="10m", step="minute", stepmode="backward"),
                    dict(count=30, label="30m", step="minute", stepmode="backward"),
                    dict(count=1, label="1h", step="hour", stepmode="backward"),
                    dict(count=12, label="12h", step="hour", stepmode="backward"),
                    dict(step="all", label="All"),
                ]
            ),
            rangeslider=dict(visible=True, thickness=0.15),
            type="date",
        ),
        height=600 + 50 * (len(signals_sorted) + extra_rows),
        showlegend=True,
    )

    return fig


calibration_acc = pd.DataFrame(
    {
        "datetime": dff["datetime"],
        "ax": dff["ax"],
        "ay": dff["ay"],
        "az": dff["az"],
    }
)

prh = pd.DataFrame(
    {
        "datetime": dff["datetime"],
        "pitch": dff["pitch"],
        "roll": dff["roll"],
        "heading": dff["heading"],
    }
)

depth_dff = pd.DataFrame(
    {
        "datetime": dff["datetime"],
        "depth": dff["derived_data_depth"].apply(lambda x: x * -1),
    }
)


# Replace the existing figure creation with a call to the new function
fig = plot_tag_data_interactive5(
    data_pkl={
        "sensor_data": {
            "ecg": ecg_dff[["datetime", "sensor_data_ecg"]].rename(
                columns={"sensor_data_ecg": "ecg"}
            ),
        },
        "derived_data": {
            "depth": depth_dff,
            "accelerometer": calibration_acc,
            "prh": prh,
        },
        "sensor_info": {
            "ecg": {
                "channels": ["ecg"],
                "metadata": {
                    "original_name": "ecg",
                    "ecg": {
                        "unit": "mV",
                    },
                },
            },
        },
        "derived_info": {
            "depth": {
                "channels": ["depth"],
                "metadata": {
                    "depth": {
                        "original_name": "Depth",
                        "unit": "m",
                    }
                },
            },
            "accelerometer": {
                "channels": ["ax", "ay", "az"],
                "metadata": {
                    "ax": {
                        "original_name": "Accelerometer X",
                        "unit": "m/s^2",
                        "sensor": "accelerometer",
                    },
                    "ay": {
                        "original_name": "Accelerometer Y",
                        "unit": "m/s^2",
                        "sensor": "accelerometer",
                    },
                    "az": {
                        "original_name": "Accelerometer Z",
                        "unit": "m/s^2",
                        "sensor": "accelerometer",
                    },
                },
                "derived_from_sensors": ["accelerometer"],
                "transformation_log": ["estimated_offset_triaxial"],
            },
            "prh": {
                "channels": ["pitch", "roll", "heading"],
                "metadata": {
                    "pitch": {
                        "original_name": "Pitch",
                        "unit": "degrees",
                        "sensor": "accelerometer",
                    },
                    "roll": {
                        "original_name": "Roll",
                        "unit": "degrees",
                        "sensor": "accelerometer",
                    },
                    "heading": {
                        "original_name": "Heading",
                        "unit": "degrees",
                        "sensor": "magnetometer",
                    },
                },
                "derived_from_sensors": ["accelerometer", "magnetometer"],
                "transformation_log": ["calculated_pitch_roll_heading"],
            },
        },
    },
    sensors=["ecg"],
    zoom_range_selector_channel="depth",
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
                    fbxFile="/assets/6_KillerWhaleOrca_v020_HR_fast.fbx",
                    style={
                        "width": "50vw",
                        "height": "40vw",
                        "display": "flex",
                        "justify-content": "center",
                        "align-items": "center",
                        "flex-direction": "column",
                    },
                ),
                video_preview.VideoPreview(
                    id="video-trimmer",
                    videoSrc="/assets/fixed_video_output.mp4",
                    playheadTime=0,
                    isPlaying=False,  # New prop to control playback
                    style={
                        "width": "50vw",
                        "height": "43vw",
                        "display": "flex",
                        "justify-content": "center",
                        "align-items": "center",
                        "flex-direction": "column",
                    },
                ),
            ],
            style={"display": "flex"},
        ),
        html.Div(
            [
                html.Button("Play", id="play-button", n_clicks=0),
                html.Div(
                    [
                        dcc.Slider(
                            id="playhead-slider",
                            min=dff["timestamp"].min(),
                            max=dff["timestamp"].max(),
                            value=dff["timestamp"].min(),
                            marks=None,
                            tooltip={"placement": "bottom"},
                        ),
                    ],
                    style={"width": "75vw"},
                ),
                dcc.Interval(
                    id="interval-component",
                    interval=1 * 1000,  # Base interval of 1 second
                    n_intervals=0,
                    disabled=True,  # Start with the interval disabled
                ),
                dcc.Store(id="playhead-time", data=dff["timestamp"].min()),
                dcc.Store(id="is-playing", data=False),
            ],
            style={"display": "flex", "align-items": "center"},
        ),
        dcc.Graph(id="graph-content", figure=fig),
    ]
)


# Update the playhead time for both components and control video playback
@app.callback(
    Output("three-d-model", "activeTime"),
    Output("video-trimmer", "playheadTime"),
    Output("video-trimmer", "isPlaying"),  # New output for video playback
    [Input("playhead-slider", "value")],
    [State("is-playing", "data")],
)
def update_active_time(slider_value, is_playing):
    # Find the nearest datetime to the slider value
    nearest_idx = dff["timestamp"].sub(slider_value).abs().idxmin()
    number_of_seconds = (
        dff["timestamp"].iloc[nearest_idx] - dff["timestamp"].iloc[0] - 30
    )
    return nearest_idx, number_of_seconds, is_playing  # Ensure playheadTime is updated


# Callback to toggle play/pause state and control video playback
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
