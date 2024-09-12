import plotly.graph_objs as go
from plotly.subplots import make_subplots
from itertools import groupby
import json
import os
import numpy as np
import random


def load_color_mapping(path):
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    else:
        return {
            'ECG': '#FFCCCC',
            'Depth': '#00008B',
            'Corrected Depth': '#6CA1C3',
            'Accelerometer X [m/s²]': '#6CA1C3',
            'Accelerometer Y [m/s²]': '#98FB98',
            'Accelerometer Z [m/s²]': '#FF6347',
            'Gyroscope X [mrad/s]': '#9370DB',
            'Gyroscope Y [mrad/s]': '#BA55D3',
            'Gyroscope Z [mrad/s]': '#8A2BE2',
            'Magnetometer X [µT]': '#FFD700',
            'Magnetometer Y [µT]': '#FFA500',
            'Magnetometer Z [µT]': '#FF8C00',
            'Filtered Heartbeats': '#808080',
            'Exhalation Breath': '#0000FF',
        }

def save_color_mapping(mapping, path):
    with open(path, 'w') as f:
        json.dump(mapping, f, indent=4)

def generate_random_color():
    """Generate a random pastel color in HEX format."""
    r = lambda: random.randint(100, 255)
    return f'#{r():02x}{r():02x}{r():02x}'

def plot_tag_data_interactive(data_pkl, imu_channels, ephys_channels=None, imu_logger=None, 
                              ephys_logger=None, imu_sampling_rate=10, ephys_sampling_rate=50, 
                              time_range=None, note_annotations=None, color_mapping_path=None):
    """
    Function to plot tag data interactively using Plotly.

    Parameters
    ----------
    data_pkl : object
        The pickle object containing the data.
    imu_channels : list
        List of IMU channels to plot.
    ephys_channels : list, optional
        List of electrophysiology channels to plot.
    imu_logger : str, optional
        IMU logger identifier.
    ephys_logger : str, optional
        Electrophysiology logger identifier.
    imu_sampling_rate : int, optional
        Sampling rate for IMU data.
    ephys_sampling_rate : int, optional
        Sampling rate for electrophysiology data.
    time_range : tuple, optional
        Tuple specifying the start and end time for plotting.
    note_annotations : dict, optional
        Dictionary of annotations to plot.
    color_mapping_path : str, optional
        Path to the JSON file containing the color mappings.
    """
    
    # Load the color mapping
    color_mapping = load_color_mapping(color_mapping_path) if color_mapping_path else {}

    # Ensure the order of channels: ECG, Depth, Accel, Gyro, Mag
    ordered_channels = []
    if ephys_channels and 'ecg' in [ch.lower() for ch in ephys_channels]:
        ordered_channels.append(('ECG', 'ecg'))
    if 'depth' in [ch.lower() for ch in imu_channels]:
        ordered_channels.append(('Depth', 'depth'))
    if 'corrdepth' in imu_channels:
        ordered_channels.append(('Corrected Depth', 'corrdepth'))
    if any(ch.lower() in ['accx', 'accy', 'accz'] for ch in imu_channels):
        ordered_channels.append(('Accel', ['accX', 'accY', 'accZ']))
    if any(ch.lower() in ['gyrx', 'gyry', 'gyrz'] for ch in imu_channels):
        ordered_channels.append(('Gyro', ['gyrX', 'gyrY', 'gyrZ']))
    if any(ch.lower() in ['magx', 'magy', 'magz'] for ch in imu_channels):
        ordered_channels.append(('Mag', ['magX', 'magY', 'magZ']))

    # Add any undefined channels to the bottom of the list
    defined_channels = {ch.lower() for channel_type, channels in ordered_channels for ch in (channels if isinstance(channels, list) else [channels])}
    undefined_channels = [ch for ch in imu_channels if ch.lower() not in defined_channels]

    for ch in undefined_channels:
        ordered_channels.append(('Undefined', ch))

    # Get the datetime overlap between IMU and ePhys data
    imu_df = data_pkl.data[imu_logger] if imu_logger else None
    ephys_df = data_pkl.data[ephys_logger] if ephys_logger else None

    imu_start_time = imu_df['datetime'].min().to_pydatetime() if imu_df is not None else None
    imu_end_time = imu_df['datetime'].max().to_pydatetime() if imu_df is not None else None
    ephys_start_time = ephys_df['datetime'].min().to_pydatetime() if ephys_df is not None else None
    ephys_end_time = ephys_df['datetime'].max().to_pydatetime() if ephys_df is not None else None

    # Determine overlapping time range
    start_time = max(imu_start_time, ephys_start_time) if imu_start_time and ephys_start_time else imu_start_time or ephys_start_time
    end_time = min(imu_end_time, ephys_end_time) if imu_end_time and ephys_end_time else imu_end_time or ephys_end_time

    # Use the user-defined time range if provided
    if time_range:
        start_time = max(start_time, time_range[0])
        end_time = min(end_time, time_range[1])

    # Filter data to the overlapping time range
    def get_time_filtered_df(df, start_time, end_time):
        return df[(df['datetime'] >= start_time) & (df['datetime'] <= end_time)]
    
    def downsample(df, original_fs, target_fs):
        if target_fs >= original_fs:
            return df
        conversion_factor = int(original_fs / target_fs)
        return df.iloc[::conversion_factor, :]

    if imu_logger:
        imu_fs = 1 / imu_df['datetime'].diff().dt.total_seconds().mean()
        imu_df_downsampled = downsample(imu_df, imu_fs, imu_sampling_rate)
        imu_df_filtered = get_time_filtered_df(imu_df_downsampled, start_time, end_time)
        imu_info = data_pkl.info[imu_logger]['channelinfo']

    if ephys_logger:
        ephys_fs = 1 / ephys_df['datetime'].diff().dt.total_seconds().mean()
        ephys_df_downsampled = downsample(ephys_df, ephys_fs, ephys_sampling_rate)
        ephys_df_filtered = get_time_filtered_df(ephys_df_downsampled, start_time, end_time)
        ephys_info = data_pkl.info[ephys_logger]['channelinfo']

    # Set up plotting
    num_rows = len(ordered_channels)
    fig = make_subplots(rows=num_rows, cols=1, shared_xaxes=True, vertical_spacing=0.03)

    row_counter = 1

    for channel_type, channels in ordered_channels:
        if channel_type == 'ECG' and ephys_channels and 'ecg' in [ch.lower() for ch in ephys_channels]:
            channel = 'ecg'
            df = ephys_df_filtered
            info = ephys_info
            original_name = info[channel]['original_name']
            unit = info[channel]['unit']

            y_data = df[channel]
            x_data = df['datetime']

            y_label = f"{original_name} [{unit}]"
            color = color_mapping.get('ECG', '#FFCCCC')

            # Add vertical lines for annotations
            if note_annotations and 'heartbeat_manual_ok' in note_annotations:
                filtered_notes = data_pkl.notes_df[data_pkl.notes_df['key'] == 'heartbeat_manual_ok']
                if not filtered_notes.empty:
                    for dt in filtered_notes['datetime']:
                        fig.add_trace(go.Scatter(
                            x=[dt, dt],
                            y=[y_data.min(), y_data.max()],
                            mode='lines',
                            line=dict(color=color_mapping.get('Filtered Heartbeats', '#808080'), width=1, dash='dot'),
                            showlegend=False
                        ), row=row_counter, col=1)

            fig.add_trace(go.Scatter(
                x=x_data,
                y=y_data,
                mode='lines',
                name=y_label,
                line=dict(color=color)
            ), row=row_counter, col=1)

            fig.update_yaxes(title_text=y_label, row=row_counter, col=1)
            row_counter += 1

        elif channel_type == 'Depth' and 'depth' in [ch.lower() for ch in imu_channels]:
            channel = 'depth'
            df = imu_df_filtered
            info = imu_info
            original_name = info[channel]['original_name']
            unit = info[channel]['unit']

            y_data = df[channel]
            x_data = df['datetime']

            y_label = f"{original_name} [{unit}]"
            color = color_mapping.get('Depth', '#00008B')

            fig.add_trace(go.Scatter(
                x=x_data,
                y=y_data,
                mode='lines',
                name=y_label,
                line=dict(color=color)
            ), row=row_counter, col=1)

            # Add vertical lines for annotations
            if note_annotations and 'exhalation_breath' in note_annotations:
                filtered_notes = data_pkl.notes_df[data_pkl.notes_df['key'] == 'exhalation_breath']
                if not filtered_notes.empty:
                    for dt in filtered_notes['datetime']:
                        fig.add_trace(go.Scatter(
                            x=[dt, dt],
                            y=[y_data.min(), y_data.max()],
                            mode='lines',
                            line=dict(color=color_mapping.get('Exhalation Breath', '#0000FF'), width=1, dash='dot'),
                            showlegend=False
                        ), row=row_counter, col=1)

            fig.update_yaxes(title_text=y_label, autorange="reversed", row=row_counter, col=1)
            row_counter += 1

        elif channel_type == 'Corrected Depth' and 'corrdepth' in imu_df_filtered.columns:
            channel = 'corrdepth'
            df = imu_df_filtered
            original_name = "Corrected Depth"
            unit = 'm'

            y_data = df[channel]
            x_data = df['datetime']

            y_label = f"{original_name} [{unit}]"
            color = color_mapping.get('Corrected Depth', '#6CA1C3')

            fig.add_trace(go.Scatter(
                x=x_data,
                y=y_data,
                mode='lines',
                name=y_label,
                line=dict(color=color)
            ), row=row_counter-1, col=1)  # Plot on the same row as original depth

        elif channel_type in ['Accel', 'Gyro', 'Mag']:
            for sub_channel in channels:
                if sub_channel in imu_df_filtered.columns:
                    df = imu_df_filtered
                    info = imu_info
                    original_name = info[sub_channel]['original_name']
                    unit = info[sub_channel]['unit']

                    y_data = df[sub_channel]
                    x_data = df['datetime']

                    y_label = f"{original_name} [{unit}]"
                    color = color_mapping.get(original_name, '#000000')

                    fig.add_trace(go.Scatter(
                        x=x_data,
                        y=y_data,
                        mode='lines',
                        name=y_label,
                        line=dict(color=color)
                    ), row=row_counter, col=1)

            fig.update_yaxes(title_text=f"{channel_type} [{unit}]", row=row_counter, col=1)
            row_counter += 1

        elif channel_type == 'Undefined':
            channel = channels  # Single channel
            df = imu_df_filtered

            if channel in df.columns:
                y_data = df[channel]
                x_data = df['datetime']

                y_label = channel  # Use the channel name directly
                color = color_mapping.get(y_label)

                # If no color mapping exists, create one
                if color is None:
                    color = generate_random_color()
                    color_mapping[y_label] = color
                    if color_mapping_path:
                        save_color_mapping(color_mapping, color_mapping_path)

                fig.add_trace(go.Scatter(
                    x=x_data,
                    y=y_data,
                    mode='lines',
                    name=y_label,
                    line=dict(color=color)
                ), row=row_counter, col=1)

                fig.update_yaxes(title_text=y_label, row=row_counter, col=1)
                row_counter += 1

    fig.update_layout(
        height=200 * num_rows,
        width=1200,
        title_text=f"{data_pkl.selected_deployment['Deployment Name']}",
        showlegend=True,
        legend=dict(
            orientation="h",  # Horizontal legend
            x=0.5,  # Center the legend horizontally
            y=-0.3,  # Place the legend above the plot
            xanchor='center',  # Anchor the legend horizontally at the center
            yanchor='bottom'   # Anchor the legend vertically at the bottom of the legend box
        )
    )

    fig.update_xaxes(title_text="Datetime", row=row_counter-1, col=1)

    return fig

def plot_tag_data(data_pkl, imu_channels, ephys_channels=None, imu_logger=None, ephys_logger=None, imu_sampling_rate=10, ephys_sampling_rate=50, draw=True):
    if not imu_logger and not ephys_logger:
        raise ValueError("At least one logger (imu_logger or ephys_logger) must be specified.")

    fig = make_subplots(rows=len(imu_channels) + (len(ephys_channels) if ephys_channels else 0), cols=1, shared_xaxes=True, vertical_spacing=0.03)
    
    def downsample(df, original_fs, target_fs):
        if target_fs >= original_fs:
            return df
        conversion_factor = int(original_fs / target_fs)
        return df.iloc[::conversion_factor, :]

    if imu_logger:
        imu_df = data_pkl.data[imu_logger]
        imu_fs = 1 / imu_df['datetime'].diff().dt.total_seconds().mean()
        imu_df_downsampled = downsample(imu_df, imu_fs, imu_sampling_rate)
        imu_info = data_pkl.info[imu_logger]['channelinfo']
    
    if ephys_logger:
        ephys_df = data_pkl.data[ephys_logger]
        ephys_fs = 1 / ephys_df['datetime'].diff().dt.total_seconds().mean()
        ephys_df_downsampled = downsample(ephys_df, ephys_fs, ephys_sampling_rate)
        ephys_info = data_pkl.info[ephys_logger]['channelinfo']

    row_counter = 1
    
    # Plot IMU channels
    for channel in imu_channels:
        if channel in imu_df_downsampled.columns:
            df = imu_df_downsampled
            info = imu_info
        else:
            raise ValueError(f"IMU Channel {channel} not found in the specified loggers' DataFrames.")
        
        original_name = info[channel]['original_name']
        unit = info[channel]['unit']
        is_depth = 'depth' in channel.lower() or channel.lower() == 'p'

        y_data = df[channel]
        x_data = df['datetime']

        y_label = f"{original_name} [{unit}]"
        color = color_mapping.get(original_name, '#000000')  # Default to black if not found

        fig.add_trace(go.Scatter(
            x=x_data,
            y=y_data,
            mode='lines',
            name=y_label,
            line=dict(color=color)
        ), row=row_counter, col=1)

        if is_depth:
            fig.update_yaxes(autorange="reversed", row=row_counter, col=1)

        fig.update_yaxes(title_text=y_label, row=row_counter, col=1)
        row_counter += 1

    # Plot ePhys channels
    if ephys_channels and ephys_logger:
        for channel in ephys_channels:
            if channel in ephys_df_downsampled.columns:
                df = ephys_df_downsampled
                info = ephys_info
            else:
                raise ValueError(f"ePhys Channel {channel} not found in the specified loggers' DataFrames.")
            
            original_name = info[channel]['original_name']
            unit = info[channel]['unit']

            y_data = df[channel]
            x_data = df['datetime']

            y_label = f"{original_name} [{unit}]"
            color = color_mapping.get(original_name, '#00FF00')  # Default to green if not found

            fig.add_trace(go.Scatter(
                x=x_data,
                y=y_data,
                mode='lines',
                name=y_label,
                line=dict(color=color)
            ), row=row_counter, col=1)

            fig.update_yaxes(title_text=y_label, row=row_counter, col=1)

            # Add vertical lines for heartbeats if ECG is plotted
            if 'ecg' in channel.lower():
                filtered_notes = data_pkl.notes_df[data_pkl.notes_df['key'] == 'heartbeat_manual_ok']
                if not filtered_notes.empty:
                    for dt in filtered_notes['datetime']:
                        fig.add_trace(go.Scatter(
                            x=[dt, dt],
                            y=[y_data.min(), y_data.max()],
                            mode='lines',
                            line=dict(color=color_mapping['Filtered Heartbeats'], width=1, dash='dot'),
                            showlegend=False
                        ), row=row_counter, col=1)

            row_counter += 1

    fig.update_layout(
        height=200 * (len(imu_channels) + (len(ephys_channels) if ephys_channels else 0)),
        width=1200,
        title_text=f"{data_pkl.selected_deployment['Deployment Name']}",
        showlegend=True
    )
    
    fig.update_xaxes(title_text="Datetime", row=row_counter-1, col=1)

    if draw:
        fig.show()
    else:
        return fig
    
def plot_depth_correction(datetime_data, dec_factor, depth_data, first_derivative, repeated_corrected_depth_temp, 
                          repeated_corrected_depth_no_temp, depth_correction, dives, flat_chunks, 
                          temp_data=None, apply_temp_correction=False):
    """
    Plot the depth correction process including original, corrected depths, and temperature effects.
    
    Parameters:
    - datetime_data: Series of datetime objects corresponding to depth measurements- will use to calculate sampling rate and align indices of dives and SIs.
    - dec_factor: Decimation factor for plotting (try at least 400 for depth data at 400 Hz)
    - depth_data: Array of original depth measurements.
    - first_derivative: Array of first derivative of depth.
    - repeated_corrected_depth_temp: Array of temperature-corrected depth measurements, upsampled to match original sampling frequency of depth_data.
    - repeated_corrected_depth_no_temp: Array of depth measurements corrected without temperature adjustments, upsampled to match original sampling frequency of depth_data.
    - depth_correction: Array of depth correction values.
    - dives: DataFrame of detected dives with columns 'start', 'end', 'max', 'tmax'.
    - flat_chunks: List of tuples representing flat chunks detected as (start_index, end_index, median_depth).
    - temp_data: Array of temperature data (optional).
    - apply_temp_correction: Boolean flag to indicate if temperature correction was applied.
    
    Returns:
    - fig: Plotly figure object.
    """

    # Check the size of each array
    arrays = {
        "depth_data": depth_data[::dec_factor],
        "first_derivative": first_derivative[::dec_factor],
        "repeated_corrected_depth_temp": repeated_corrected_depth_temp[::dec_factor],
        "repeated_corrected_depth_no_temp": repeated_corrected_depth_no_temp[::dec_factor],
        "depth_correction": depth_correction[::dec_factor]
    }

    for name, array in arrays.items():
        if len(array) > 10000:
            raise ValueError(f"The downsampled array '{name}' has more than 10,000 values ({len(array)} values). Please downsample the data further or increase the dec_factor.")

    sampling_rate = 1 / datetime_data.diff().dt.total_seconds().mean()
    downsampled_datetime = datetime_data[::dec_factor]

    # Create subplots with four rows
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True,
                        subplot_titles=("Original vs. Corrected Depth",
                                        "First Derivative of Depth",
                                        "Depth Correction Over Time",
                                        "Temperature Correction" if temp_data is not None else None))

    # Downsample arrays for plotting
    depth_data_downsampled = depth_data[::dec_factor]
    first_derivative_downsampled = first_derivative #downsample not needed
    depth_correction_downsampled = depth_correction #downsample not needed
    repeated_corrected_depth_temp_downsampled = repeated_corrected_depth_temp[::dec_factor]
    repeated_corrected_depth_no_temp_downsampled = repeated_corrected_depth_no_temp[::dec_factor]
   

    # Plot 1: Original Depth (reversed y-axis)
    fig.add_trace(go.Scatter(x=downsampled_datetime, y=depth_data_downsampled, 
                             mode='lines', name='Original Depth', 
                             line=dict(color='LightBlue')), row=1, col=1)

    # Add temperature-corrected depth with low opacity if the checkbox is selected
    if apply_temp_correction:
        fig.add_trace(go.Scatter(x=downsampled_datetime, y=repeated_corrected_depth_temp_downsampled, 
                                 mode='lines', name='Temp Corrected Depth', 
                                 line=dict(color='red', dash='dot')), row=1, col=1)

    # Add the no temperature-corrected depth as the main corrected depth
    fig.add_trace(go.Scatter(x=downsampled_datetime, y=repeated_corrected_depth_no_temp_downsampled, 
                             mode='lines', name='Corrected Depth (no Temp Correction)', 
                             line=dict(color='DarkBlue')), row=1, col=1)
    fig.update_yaxes(title_text="Depth (meters)", autorange="reversed", row=1, col=1)

    # Highlight detected dives in blue
    for _, row in dives.iterrows():
        start_time = row['start_time']
        end_time = row['end_time']

        fig.add_shape(
            type="rect",
            x0=start_time, x1=end_time,
            y0=0, y1=max(depth_data),
            fillcolor="DarkBlue", opacity=0.2,
            layer="below", line_width=0,
            row=1, col=1
        )

    # Highlight flat chunks in green
    for _, row in flat_chunks.iterrows():
        start_time = row['start_time']
        end_time = row['end_time']
        
        fig.add_shape(
            type="rect",
            x0=start_time, x1=end_time,
            y0=1, y1=1.5,
            fillcolor="LightBlue", opacity=0.5,
            layer="below", line_width=0,
            row=1, col=1
        )

    # Plot 2: First Derivative of Depth with Flat Chunks
    fig.add_trace(go.Scatter(x=downsampled_datetime, y=first_derivative_downsampled, 
                             mode='lines', name='First Derivative of Depth', 
                             line=dict(color='green')), row=2, col=1)
    fig.add_trace(go.Scatter(x=downsampled_datetime, y=[-0.1]*len(downsampled_datetime), 
                             mode='lines', name='Flat Chunk Threshold (-0.1)', 
                             line=dict(color='LightGreen', dash='dot')), row=2, col=1)
    fig.add_trace(go.Scatter(x=downsampled_datetime, y=[0.1]*len(downsampled_datetime), 
                             mode='lines', name='Flat Chunk Threshold (0.1)', 
                             line=dict(color='LightGreen', dash='dot')), row=2, col=1)
    fig.update_yaxes(title_text="Rate of Depth Change", row=2, col=1)

    # Plot 3: Depth Correction Over Time
    fig.add_trace(go.Scatter(x=downsampled_datetime, y=depth_correction_downsampled, 
                             mode='lines', name='Depth Correction', 
                             line=dict(color='DarkBlue')), row=3, col=1)
    fig.update_yaxes(title_text="Depth Correction (m)", row=3, col=1)

    if temp_data is not None:
        # Plot 4: Temperature Correction Over Time
        fig.add_trace(go.Scatter(x=downsampled_datetime, y=repeated_corrected_depth_temp_downsampled, 
                                 mode='lines', name='Temperature Correction', 
                                 line=dict(color='orange')), row=4, col=1)
        fig.update_yaxes(title_text="Temperature Correction (m)", row=4, col=1)

    # Update layout
    fig.update_layout(title="Depth Data Analysis", height=800)

    return fig


