import os
import streamlit as st
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import numpy as np
import pandas as pd
import pickle
from scipy.signal import decimate, medfilt
from scipy.linalg import norm
from scipy.stats import iqr
from datareader import DataReader
from itertools import groupby

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
st.set_page_config(page_title="PRH Predictor", layout="wide", initial_sidebar_state="auto")

# Helper function to calculate orientation quality
def calculate_orientation_quality(orientation_variation):
    thr = np.median(orientation_variation) + 1.5 * iqr(orientation_variation) * np.array([-1, 1])
    return thr

# Helper function for PRH inference
def prh_predictor2_gui(depth_data, accel_data, sampling_rate, max_depth_threshold=10):
    """
    Predict the tag position on a diving animal from depth and acceleration data.
    Returns: DataFrame with p0, r0, h0, and quality estimates.
    """
    min_segment_length = 30  # minimum surface segment length in seconds
    max_segment_length = 300  # maximum surface segment length in seconds
    gap_time = 5  # gap time in seconds to avoid dive edges

    # Decimate data to 5Hz if needed
    if sampling_rate >= 7.5:
        decimation_factor = round(sampling_rate / 5)
        depth_data = decimate(depth_data, decimation_factor, zero_phase=True)
        accel_data = decimate(accel_data, decimation_factor, axis=0, zero_phase=True)
        sampling_rate /= decimation_factor

    # Normalize acceleration to 1 g
    accel_data = accel_data / np.linalg.norm(accel_data, axis=1)[:, np.newaxis]

    # Detect dive start/ends using the find_dives function
    dive_times = find_dives(depth_data, min_depth_threshold=max_depth_threshold, 
                            sampling_rate=sampling_rate, duration_threshold=10)

    if dive_times.shape[0] == 0:
        raise ValueError(f"No dives deeper than {max_depth_threshold:.0f} found - change max_depth_threshold.")

    # Augment all dive-start and dive-end times by gap_time seconds
    dive_times['start'] -= gap_time
    dive_times['end'] += gap_time

    # Initialize the PRH and quality estimates DataFrame
    prh_data = []

    for i, row in dive_times.iterrows():
        start_time = int(row['start'] * sampling_rate)
        end_time = int(row['end'] * sampling_rate)

        # Analyze orientation segments
        accel_segment = accel_data[start_time:end_time, :]
        orientation_variation = norm(np.std(accel_segment, axis=0))
        quality = np.abs(orientation_variation) / np.mean(orientation_variation)

        # Estimate p0, r0, h0 (random example for simplicity)
        p0 = np.mean(accel_segment[:, 0])
        r0 = np.mean(accel_segment[:, 1])
        h0 = np.mean(accel_segment[:, 2])

        # Append the estimates to the list
        prh_data.append({
            'cue': row['tmax'],
            'p0': p0,
            'r0': r0,
            'h0': h0,
            'quality': quality
        })

    # Convert the list of dictionaries into a DataFrame
    prh_data = pd.DataFrame(prh_data)

    return prh_data

def find_dives(depth_series, min_depth_threshold, sampling_rate, duration_threshold=10, smoothing_window=5, search_window=20):
    """
    Find time cues for dives in a depth record with smoothing and run-length encoding.
    
    Parameters:
    - depth_series (numpy.ndarray): Depth time series in meters.
    - min_depth_threshold (float): Minimum depth in meters to recognize a dive.
    - sampling_rate (float): Sampling rate of the depth data in Hz (samples per second).
    - duration_threshold (float): Minimum duration in seconds for a dive to be considered valid.
    - smoothing_window (int): Window size for median filtering to smooth depth data.
    - search_window (int): Window size in seconds to search for the nearest surface point around dive edges.
    
    Returns:
    - pandas.DataFrame: DataFrame with columns 'start', 'end', 'max', 'tmax' representing the dive times.
    """

    # Step 1: Apply smoothing to the depth series
    smoothed_depth = medfilt(depth_series, kernel_size=smoothing_window)

    # Step 2: Perform run-length encoding to detect chunks below the min depth threshold
    is_dive = smoothed_depth > min_depth_threshold
    rle = [(key, len(list(group))) for key, group in groupby(is_dive)]

    # Step 3: Filter out dives that are too short
    dive_chunks = []
    current_index = 0

    for is_diving, length in rle:
        if is_diving:
            duration = length / sampling_rate
            if duration >= duration_threshold:
                dive_start = current_index
                dive_end = current_index + length
                dive_chunks.append((dive_start, dive_end))
        current_index += length

    # Step 4: Refine dive start and end times by searching for nearest surface points
    dives = []
    for start, end in dive_chunks:
        # Define search window around start and end times
        start_search_window = max(start - round(search_window * sampling_rate), 0)
        end_search_window = min(end + round(search_window * sampling_rate), len(smoothed_depth) - 1)

        # Find nearest surface points around the dive start and end
        dive_start_index = start_search_window + np.argmin(np.abs(smoothed_depth[start_search_window:start]))
        dive_end_index = end + np.argmin(np.abs(smoothed_depth[end:end_search_window]))

        # Determine max depth and its timing within the dive
        max_depth = np.max(smoothed_depth[dive_start_index:dive_end_index])
        max_depth_index = np.argmax(smoothed_depth[dive_start_index:dive_end_index])
        max_depth_time = (dive_start_index + max_depth_index) / sampling_rate

        # Append dive information
        dives.append({
            'start': dive_start_index / sampling_rate,
            'end': dive_end_index / sampling_rate,
            'max': max_depth,
            'tmax': max_depth_time
        })

    return pd.DataFrame(dives)



# Example usage
depth_data = data_pkl.data['CC-96']['corrdepth'].values
accel_data = np.vstack((data_pkl.data['CC-96']['accX'].values, 
                        data_pkl.data['CC-96']['accY'].values, 
                        data_pkl.data['CC-96']['accZ'].values)).T
sampling_rate = int(data_pkl.info['CC-96']['datetime_metadata']['fs'])
dives = data_pkl.info['CC-96']['dives']

prh_data = prh_predictor2_gui(depth_data, accel_data, sampling_rate=sampling_rate, max_depth_threshold=1)

# Plotting Interface
st.title('PRH Predictor GUI')

# Top Panel: Dive Profile
fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                    subplot_titles=('Dive Profile', 'Tag-to-Animal Orientation Estimates', 'Quality of Estimates'))

# Dive Profile Plot
fig.add_trace(go.Scatter(x=dives['tmax'], y=-depth_data[dives['tmax'].astype(int) * sampling_rate],
                         mode='lines', name='Dive Profile'), row=1, col=1)

# Orientation Estimates Plot
fig.add_trace(go.Scatter(x=prh_data['cue'], y=prh_data['p0'], mode='markers', name='p0 Estimate', marker=dict(color='red')), row=2, col=1)
fig.add_trace(go.Scatter(x=prh_data['cue'], y=prh_data['r0'], mode='markers', name='r0 Estimate', marker=dict(color='green')), row=2, col=1)
fig.add_trace(go.Scatter(x=prh_data['cue'], y=prh_data['h0'], mode='markers', name='h0 Estimate', marker=dict(color='blue')), row=2, col=1)

# Quality of Estimates Plot
fig.add_trace(go.Scatter(x=prh_data['cue'], y=prh_data['quality'], mode='markers', name='Quality of Estimate', marker=dict(color='purple')), row=3, col=1)

# Update layout
fig.update_layout(height=800, showlegend=True)

# Display the figure in Streamlit
st.plotly_chart(fig, use_container_width=True)

# Instruction Text
st.text("Click on a point in the middle panel to edit orientation estimates.")
st.text("The bottom panel indicates the quality of the estimates. Values < 0.05 indicate good quality.")
