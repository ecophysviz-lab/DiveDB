import os
import streamlit as st
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import pickle
from datareader import DataReader
import pandas as pd
import json

# Change the current working directory to the root directory
os.chdir("/Users/jessiekb/Documents/GitHub/pyologger")
root_dir = os.getcwd()
data_dir = os.path.join(root_dir, "data")
deployment_folder = os.path.join(data_dir, "2024-01-16_oror-002a_Shuka-HR")

# Load the data_reader object from the pickle file
pkl_path = os.path.join(deployment_folder, 'outputs', 'data.pkl')

with open(pkl_path, 'rb') as file:
    data_pkl = pickle.load(file)

# Set Streamlit page config for light mode and wide layout
st.set_page_config(page_title="Interactive Plot", layout="wide", initial_sidebar_state="auto")

# Load color mappings from JSON file
color_mapping_path = os.path.join(root_dir, 'color_mappings.json')

# Load the existing color mappings or initialize with default if not present
if os.path.exists(color_mapping_path):
    with open(color_mapping_path, 'r') as f:
        color_mapping = json.load(f)
else:
    color_mapping = {
        'ECG': '#FFCCCC',
        'Depth': '#00008B',
        'Corrected Depth': '#6CA1C3',  # Added color for corrected depth
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
        'Exhalation Breath': '#0000FF',  # Added color for exhalation breath
    }

# Function to save updated color mappings to JSON
def save_color_mapping(mapping, path):
    with open(path, 'w') as f:
        json.dump(mapping, f, indent=4)

def plot_tag_data_interactive(data_pkl, imu_channels, ephys_channels=None, imu_logger=None, ephys_logger=None, imu_sampling_rate=10, ephys_sampling_rate=50, time_range=None, note_annotations=None):
    # Streamlit color pickers for each channel type
    st.sidebar.header("Customize Colors")
    for key in color_mapping.keys():
        new_color = st.sidebar.color_picker(f"Select color for {key}", value=color_mapping[key])
        if new_color != color_mapping[key]:
            color_mapping[key] = new_color  # Update color in memory
            save_color_mapping(color_mapping, color_mapping_path)  # Save the updated color mapping

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

    # Get the datetime overlap between IMU and ePhys data
    if imu_logger:
        imu_df = data_pkl.data[imu_logger]
        imu_start_time = imu_df['datetime'].min().to_pydatetime()
        imu_end_time = imu_df['datetime'].max().to_pydatetime()
    else:
        imu_start_time, imu_end_time = None, None

    if ephys_logger:
        ephys_df = data_pkl.data[ephys_logger]
        ephys_start_time = ephys_df['datetime'].min().to_pydatetime()
        ephys_end_time = ephys_df['datetime'].max().to_pydatetime()
    else:
        ephys_start_time, ephys_end_time = None, None

    # Determine overlapping time range
    start_time = max(imu_start_time, ephys_start_time)
    end_time = min(imu_end_time, ephys_end_time)

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
            color = color_mapping['ECG']

            # Add vertical lines for annotations
            if note_annotations and 'heartbeat_manual_ok' in note_annotations:
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
            color = color_mapping['Depth']

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
                            line=dict(color=color_mapping['Exhalation Breath'], width=1, dash='dot'),
                            showlegend=False
                        ), row=row_counter, col=1)

            fig.update_yaxes(title_text=y_label, autorange="reversed", row=row_counter, col=1)
            row_counter += 1

        elif channel_type == 'Corrected Depth' and 'corrdepth' in imu_df_filtered.columns:
            channel = 'corrdepth'
            df = imu_df_filtered
            info = imu_info
            original_name = "Corrected Depth"
            unit = info.get(channel, {}).get('unit', 'm')

            y_data = df[channel]
            x_data = df['datetime']

            y_label = f"{original_name} [{unit}]"
            color = color_mapping['Corrected Depth']

            fig.add_trace(go.Scatter(
                x=x_data,
                y=y_data,
                mode='lines',
                name=y_label,
                line=dict(color=color)
            ), row=row_counter-1, col=1)  # Plot on the same row as original depth

            # No need to update row_counter here since we plot on the same axis as Depth

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

    st.plotly_chart(fig)

# Example usage in Streamlit
imu_channels_to_plot = ['depth', 'corrdepth', 'accX', 'accY', 'accZ', 'gyrX', 'gyrY', 'gyrZ', 'magX', 'magY', 'magZ']
ephys_channels_to_plot = ['ecg']
imu_logger_to_use = 'CC-96'
ephys_logger_to_use = 'UF-01'

# Get the overlapping time range
imu_df = data_pkl.data[imu_logger_to_use]
ephys_df = data_pkl.data[ephys_logger_to_use]
overlap_start_time = max(imu_df['datetime'].min(), ephys_df['datetime'].min()).to_pydatetime()
overlap_end_time = min(imu_df['datetime'].max(), ephys_df['datetime'].max()).to_pydatetime()

# Add Streamlit slider for absolute time range selection
st.sidebar.title("Select Time Range")
start_time = st.sidebar.slider("Start Time", value=overlap_start_time, min_value=overlap_start_time, max_value=overlap_end_time, format="YYYY-MM-DD HH:mm:ss")
end_time = st.sidebar.slider("End Time", value=overlap_end_time, min_value=overlap_start_time, max_value=overlap_end_time, format="YYYY-MM-DD HH:mm:ss")

# Define notes to plot
notes_to_plot = {
    'heartbeat_manual_ok': 'ecg',
    'exhalation_breath': 'depth'
}

st.title('Interactive Plot Customization')
plot_tag_data_interactive(data_pkl, imu_channels_to_plot, ephys_channels=ephys_channels_to_plot, imu_logger=imu_logger_to_use, ephys_logger=ephys_logger_to_use, time_range=(start_time, end_time), note_annotations=notes_to_plot)
