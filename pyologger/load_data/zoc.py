import os
import streamlit as st
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import pickle
import numpy as np
import pandas as pd
from scipy.signal import medfilt, decimate
from sklearn.linear_model import LinearRegression
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
st.set_page_config(page_title="Interactive Plot", layout="wide", initial_sidebar_state="auto")

# Helper functions
def calculate_derivative(depth, sampling_rate):
    """Calculate first derivative of the depth after downsampling and smoothing."""
    # Downsample to 1Hz
    downsampled_depth = decimate(depth, int(sampling_rate / 1), zero_phase=True)
    
    # Apply smoothing
    smoothed_depth = medfilt(downsampled_depth, kernel_size=5)
    
    # Calculate first derivative
    first_derivative = np.gradient(smoothed_depth)
    
    return first_derivative, downsampled_depth

def run_length_encoding(binary_array):
    """Run-length encode a binary array."""
    return [(key, len(list(group))) for key, group in groupby(binary_array)]

def detect_flat_chunks(depth, first_derivative, threshold=0.1, min_duration=5, depth_threshold=25, sampling_rate=1):
    """Detect flat chunks likely representing surface intervals using run-length encoding."""
    is_flat_chunk = np.abs(first_derivative) < threshold
    
    # Run-length encoding to find flat segments
    rle_encoded = run_length_encoding(is_flat_chunk)
    
    # Convert RLE to flat chunk indices
    flat_chunks = []
    current_index = 0
    
    # Convert min_duration from seconds to samples
    min_duration_samples = min_duration * sampling_rate
    
    for value, length in rle_encoded:
        if value:  # True indicates a flat chunk
            if length >= min_duration_samples:
                start_ix = current_index
                end_ix = current_index + length
                median_depth = np.median(depth[start_ix:end_ix])
                flat_chunks.append((start_ix, end_ix, median_depth))
        current_index += length
    
    # Filter out chunks with median depths greater than depth_threshold meters (likely not surface intervals)
    flat_chunks = [chunk for chunk in flat_chunks if np.abs(chunk[2]) < depth_threshold]
    
    return flat_chunks

def apply_zero_offset_correction(depth, temp, flat_chunks):
    """Apply zero offset correction by adjusting surface intervals to zero and correcting based on temperature."""
    corrected_depth = depth.copy()
    temp_correction = np.zeros_like(depth)
    
    # Create depth correction based on flat chunks
    depth_correction = np.full_like(depth, np.nan)
    
    # Iterate over flat chunks to calculate temperature correction
    for start, end, median_depth in flat_chunks:
        depth_correction[start:end] = median_depth
        
        if temp is not None:
            # Linear regression to fit temperature correction
            temp_chunk = temp[start:end] - 20  # Adjust for reference temperature (TREF)
            depth_chunk = depth[start:end]
            
            if len(temp_chunk) > 1:
                reg = LinearRegression()
                reg.fit(temp_chunk.reshape(-1, 1), depth_chunk)
                temp_correction[start:end] = reg.coef_[0] * temp_chunk + reg.intercept_
    
    # Interpolate gaps in depth correction
    depth_correction = pd.Series(depth_correction).interpolate().fillna(0).to_numpy()
    
    # Apply the temperature correction and depth correction
    corrected_depth_temp = corrected_depth - depth_correction - temp_correction
    corrected_depth_no_temp = corrected_depth - depth_correction
    
    return corrected_depth_temp, corrected_depth_no_temp, depth_correction

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


# Load the depth and temperature data
depth_data = data_pkl.data['CC-96']['depth'].values
temp_data = data_pkl.data['CC-96'].get('tempIMU')  # Replace with the actual temperature column name if it exists
sampling_rate = int(data_pkl.info['CC-96']['datetime_metadata']['fs'])  # Replace with actual sampling rate
datetime_data = pd.to_datetime(data_pkl.data['CC-96']['datetime'])

# Interactive widgets for parameters
st.sidebar.title("Zero Offset Correction Parameters")
threshold = st.sidebar.slider("Flat Chunk Threshold", min_value=0.01, max_value=1.0, value=0.1, step=0.01)
min_duration = st.sidebar.slider("Minimum Duration (seconds)", min_value=1, max_value=100, value=30, step=1)
depth_threshold = st.sidebar.slider("Maximum Depth for Surface Interval (meters)", min_value=-10, max_value=25, value=5, step=1)

# Checkbox to apply temperature correction
apply_temp_correction = st.sidebar.checkbox("Apply Temperature Correction", value=False)

# Dive detection parameters
st.sidebar.title("Dive Detection Parameters")
min_depth_threshold = st.sidebar.slider("Minimum Depth Threshold for Dive (meters)", min_value=0.1, max_value=10.0, value=1.0, step=0.1)
dive_duration_threshold = st.sidebar.slider("Dive Duration Threshold (seconds)", min_value=1, max_value=100, value=10, step=1)
smoothing_window = st.sidebar.slider("Smoothing Window for Dives", min_value=1, max_value=20, value=5, step=1)

# Step 1: Calculate the first derivative after downsampling and smoothing
first_derivative, downsampled_depth = calculate_derivative(depth_data, sampling_rate)

# Step 2: Detect flat chunks likely representing surface intervals
flat_chunks = detect_flat_chunks(downsampled_depth, first_derivative, threshold=threshold, min_duration=min_duration, depth_threshold=depth_threshold, sampling_rate=1)

# Step 3: Apply zero offset correction with and without temperature adjustment
corrected_depth_temp, corrected_depth_no_temp, depth_correction = apply_zero_offset_correction(downsampled_depth, temp_data.values if temp_data is not None else None, flat_chunks)

# Step 4: Upsample the corrected depth back to the original sampling rate
upsampling_factor = int(sampling_rate / 1)  # Adjust this if needed
repeated_corrected_depth_temp = np.repeat(corrected_depth_temp, upsampling_factor)
repeated_corrected_depth_no_temp = np.repeat(corrected_depth_no_temp, upsampling_factor)

# Ensure the upsampled arrays match the original length
def adjust_length(repeated_depth, original_length):
    if len(repeated_depth) > original_length:
        return repeated_depth[:original_length]
    elif len(repeated_depth) < original_length:
        return np.pad(repeated_depth, (0, original_length - len(repeated_depth)), 'edge')
    return repeated_depth

repeated_corrected_depth_temp = adjust_length(repeated_corrected_depth_temp, len(depth_data))
repeated_corrected_depth_no_temp = adjust_length(repeated_corrected_depth_no_temp, len(depth_data))

# Number of flat chunks detected
num_flat_chunks = len(flat_chunks)
st.sidebar.write(f"Number of flat chunks detected: {num_flat_chunks}")

# Step 4: Detect dives in the corrected depth data
dives = find_dives(repeated_corrected_depth_no_temp, min_depth_threshold=min_depth_threshold, 
                   sampling_rate=sampling_rate, duration_threshold=dive_duration_threshold, 
                   smoothing_window=smoothing_window)
# Number of dives detected
num_dives = len(dives)
st.sidebar.write(f"Number of dives detected: {num_dives}")

data_pkl.info['CC-96']['dives'] = {}
data_pkl.info['CC-96']['dives'] = dives

# Adjust the length of datetime data to match the downsampled data
downsampled_datetime = datetime_data[::upsampling_factor]

# Create subplots with only 4 rows (removing the second plot)
fig = make_subplots(rows=4, cols=1, shared_xaxes=True,
                    subplot_titles=("Original vs. Corrected Depth",
                                    "First Derivative of Depth",
                                    "Depth Correction Over Time",
                                    "Temperature Correction" if temp_data is not None else None))

# Plot 1: Original Depth (reversed y-axis)
fig.add_trace(go.Scatter(x=downsampled_datetime, y=depth_data[::upsampling_factor], 
                         mode='lines', name='Original Depth', 
                         line=dict(color='LightBlue')), row=1, col=1)

# Add temperature-corrected depth with low opacity if the checkbox is selected
if apply_temp_correction:
    fig.add_trace(go.Scatter(x=downsampled_datetime, y=repeated_corrected_depth_temp[::upsampling_factor], mode='lines', name='Temp Corrected Depth', line=dict(color='red', dash='dot')), row=1, col=1)

# Add the no temperature-corrected depth as the main corrected depth
fig.add_trace(go.Scatter(x=downsampled_datetime, y=repeated_corrected_depth_no_temp[::upsampling_factor], 
                         mode='lines', name='Corrected Depth (no Temp Correction)', 
                         line=dict(color='DarkBlue')), row=1, col=1)
fig.update_yaxes(title_text="Depth (meters)", autorange="reversed", row=1, col=1)

# Highlight detected dives in blue
for _, row in dives.iterrows():
    start_time = datetime_data.iloc[int(row['start'] * sampling_rate)]
    end_time = datetime_data.iloc[int(row['end'] * sampling_rate)]

    fig.add_shape(
        type="rect",
        x0=start_time, x1=end_time,
        y0=0, y1=max(depth_data),
        fillcolor="DarkBlue", opacity=0.2,
        layer="below", line_width=0,
        row=1, col=1
    )

# Highlight flat chunks in green
for start_ix, end_ix, _ in flat_chunks:
    if start_ix < len(downsampled_datetime):
        start_time = downsampled_datetime.iloc[start_ix]
        end_time = downsampled_datetime.iloc[min(end_ix - 1, len(downsampled_datetime) - 1)]
    
        fig.add_shape(
            type="rect",
            x0=start_time, x1=end_time,
            y0=1, y1=1.5,
            fillcolor="LightBlue", opacity=0.5,
            layer="below", line_width=0,
            row=1, col=1
        )

# Plot 2: First Derivative of Depth with Flat Chunks
fig.add_trace(go.Scatter(x=downsampled_datetime, y=first_derivative, 
                         mode='lines', name='First Derivative of Depth', 
                         line=dict(color='green')), row=2, col=1)
fig.add_trace(go.Scatter(x=downsampled_datetime, y=[-threshold]*len(downsampled_datetime), 
                         mode='lines', name=f'Flat Chunk Threshold (-{threshold})', 
                         line=dict(color='LightGreen', dash='dot')), row=2, col=1)
fig.add_trace(go.Scatter(x=downsampled_datetime, y=[threshold]*len(downsampled_datetime), 
                         mode='lines', name=f'Flat Chunk Threshold ({threshold})', 
                         line=dict(color='LightGreen', dash='dot')), row=2, col=1)
fig.update_yaxes(title_text="Rate of Depth Change", row=2, col=1)

# Plot 3: Depth Correction Over Time
fig.add_trace(go.Scatter(x=downsampled_datetime, y=depth_correction, mode='lines', name='Depth Correction', 
                         line=dict(color='DarkBlue')), row=3, col=1)
fig.update_yaxes(title_text="Depth Correction (m)", row=3, col=1)

if temp_data is not None:
    # Plot 4: Temperature Correction Over Time
    fig.add_trace(go.Scatter(x=downsampled_datetime, y=repeated_corrected_depth_temp[::upsampling_factor], 
                             mode='lines', name='Temperature Correction (optional- check in checkbox if desired)', 
                             line=dict(color='orange')), row=4, col=1)
    fig.update_yaxes(title_text="Temperature Correction (m)", row=4, col=1)

# Update layout
fig.update_layout(title="Depth Data Analysis", height=800)

# Display the figure in Streamlit
st.plotly_chart(fig, use_container_width=True)

# Save the corrected depth back to the data structure
if apply_temp_correction:
    data_pkl.data['CC-96']['corrdepth'] = repeated_corrected_depth_temp
else:
    data_pkl.data['CC-96']['corrdepth'] = repeated_corrected_depth_no_temp

# Optionally save the updated data back to the pickle file
if st.button('Save Corrected Data & Dives'):
    with open(pkl_path, 'wb') as file:
        pickle.dump(data_pkl, file)
    st.success("Corrected depth data & pickle file saved.")
