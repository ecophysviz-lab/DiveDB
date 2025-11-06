import plotly.graph_objs as go
from plotly.subplots import make_subplots
from plotly_resampler import FigureResampler, register_plotly_resampler
import json
import os
import numpy as np

register_plotly_resampler(mode="auto")


with open(os.path.join(os.path.dirname(__file__), "color_mapping.json"), "r") as f:
    color_mapping = json.load(f)


def generate_random_color():
    """Generate a random pastel color in HEX format."""
    import random

    def r():
        return random.randint(100, 255)

    return f"#{r():02x}{r():02x}{r():02x}"


def plot_tag_data_interactive(
    data_pkl,
    sensors=None,
    derived_data_signals=None,
    channels=None,
    time_range=None,
    note_annotations=None,
    state_annotations=None,
    zoom_start_time=None,
    zoom_end_time=None,
    plot_event_values=None,
    zoom_range_selector_channel=None,
):
    """
    Function to plot tag data interactively using Plotly with optional initial zooming into a specific time range.
    Includes both sensor_data and derived_data.
    """

    # Determine the sensors and derived data to plot
    if sensors is None:
        sensors = list(data_pkl.sensor_data.keys())

    if derived_data_signals is None and "derived_data" in data_pkl:
        derived_data_signals = list(data_pkl["derived_data"].keys())

    # Combine sensors and derived data
    signals = sensors + derived_data_signals

    # Preserve user order, only move range selector signal to top if specified
    if zoom_range_selector_channel and zoom_range_selector_channel in signals:
        signals_sorted = [zoom_range_selector_channel] + [
            s for s in signals if s != zoom_range_selector_channel
        ]
    else:
        # Maintain the exact order from the input
        signals_sorted = signals

    # Add subplots: One row per signal, plus extra row for the blank plot and event values if needed
    extra_rows = len(plot_event_values) if plot_event_values else 0
    total_rows = len(signals_sorted) + extra_rows + 1  # +1 for the blank plot
    fig = FigureResampler(
        make_subplots(rows=total_rows, cols=1, shared_xaxes=True, vertical_spacing=0.03)
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
                x_data = np.ascontiguousarray(
                    signal_data_filtered["datetime"].to_numpy()
                )
                y_data = np.ascontiguousarray(signal_data_filtered[channel].to_numpy())

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
                        mode="lines",
                        name=y_label,
                        line=dict(color=color),
                        connectgaps=True,
                    ),
                    hf_x=x_data,
                    hf_y=y_data,
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
                # Check if the annotation applies to the current signal
                if signal != note_params.get("signal"):
                    continue  # Skip annotations not tied to this signal

                # Get signal data
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

                if signal_data is not None and signal_info is not None:
                    # Use the first channel of this signal for positioning
                    if "channels" in signal_info and signal_info["channels"]:
                        first_channel = signal_info["channels"][0]
                    else:
                        continue  # Skip if no channels available

                    if first_channel not in signal_data.columns:
                        continue  # Skip if channel not in data

                    # Filter by time range if provided
                    if time_range:
                        filtered_notes = data_pkl["event_data"][
                            (data_pkl["event_data"]["key"] == note_type)
                            & (data_pkl["event_data"]["datetime"] >= time_range[0])
                            & (data_pkl["event_data"]["datetime"] <= time_range[1])
                        ]
                    else:
                        filtered_notes = data_pkl["event_data"][
                            data_pkl["event_data"]["key"] == note_type
                        ]

                    if not filtered_notes.empty:
                        symbol = note_params.get("symbol", "circle")
                        color = note_params.get("color", "rgba(128, 128, 128, 0.5)")
                        y_fixed = (2 / 3) * signal_data[first_channel].max()

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

        # Plot State Events (Rectangles for Continuous Events)
        if state_annotations:
            for event_type, event_params in state_annotations.items():
                if signal != event_params.get("signal"):
                    continue

                # Find the row index corresponding to the signal
                signal_row = signals_sorted.index(signal)

                # Check if signal is in sensor_data or derived_data
                if signal in data_pkl["sensor_data"]:
                    signal_data = data_pkl["sensor_data"][signal]
                elif signal in data_pkl["derived_data"]:
                    signal_data = data_pkl["derived_data"][signal]
                else:
                    continue  # Skip if signal not found

                # Get state events for this type
                if "event_data" in data_pkl and data_pkl["event_data"] is not None:
                    import pandas as pd

                    state_events = data_pkl["event_data"][
                        (data_pkl["event_data"]["key"] == event_type)
                    ]

                    # Filter by time range if provided
                    if time_range:
                        state_events = state_events[
                            (state_events["datetime"] >= time_range[0])
                            & (state_events["datetime"] <= time_range[1])
                        ]

                    for _, event in state_events.iterrows():
                        start_time = event["datetime"]
                        end_time = start_time + pd.to_timedelta(
                            event["duration"], unit="s"
                        )

                        # Ensure the y-range is valid for the given signal
                        y_min = (
                            signal_data.iloc[:, 1:].min().min()
                        )  # Min value across all channels
                        y_max = (
                            signal_data.iloc[:, 1:].max().max()
                        )  # Max value across all channels

                        # Draw a shaded rectangle on the specified signal
                        fig.add_shape(
                            type="rect",
                            x0=start_time,
                            x1=end_time,
                            y0=y_min,
                            y1=y_max,
                            fillcolor=event_params.get(
                                "color", "rgba(150, 150, 150, 0.3)"
                            ),
                            line=dict(width=0),
                            row=signal_row + 2,  # +2 to account for blank plot
                            col=1,
                            layer="below",
                        )

        # Update y-axis label for each subplot
        if row_counter == 2:
            # Align the title of the blank plot (row 2) with the first plot (row 1)
            fig.update_yaxes(title_text=signal, row=1, col=1)
            # Invert depth axis if applicable
            if "depth" in signal.lower():
                fig.update_yaxes(autorange="reversed", row=1, col=1)
        else:
            # Keep the title where it is for the other rows
            fig.update_yaxes(title_text=signal, row=row_counter, col=1)
            # Invert depth axis if applicable
            if "depth" in signal.lower():
                fig.update_yaxes(autorange="reversed", row=row_counter, col=1)
        row_counter += 1

    # Add event values as separate subplots
    if plot_event_values:
        for event_type in plot_event_values:
            event_data = data_pkl.event_data[data_pkl.event_data["key"] == event_type]
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
        # title="Tag Data Visualization",
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
        uirevision="constant",  # Maintain UI state across updates
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.15,
            xanchor="right",
            x=1,
        ),
        font_family="Figtree",
        title_font_family="Figtree",
        font=dict(
            family="Figtree",
            size=14,
            weight="bold",
        ),
        paper_bgcolor="rgba(0,0,0,0)",  # Transparent background
        plot_bgcolor="rgba(245,245,245,1)",  # Light gray plot background
        margin=dict(l=0, r=0, t=0, b=0),
    )

    return fig
