import os
import streamlit as st
import pickle
import pandas as pd
from pyologger.calibrate_data.zoc import smooth_downsample_derivative, detect_flat_chunks, apply_zero_offset_correction, find_dives
from pyologger.plot_data.plotter import plot_depth_correction
from pyologger.process_data.sampling import upsample

# Define paths
root_dir = "/Users/jessiekb/Documents/GitHub/pyologger"
data_dir = os.path.join(root_dir, "data")
deployment_folder = os.path.join(data_dir, "2024-01-16_oror-002a_Shuka-HR")
pkl_path = os.path.join(deployment_folder, 'outputs', 'data.pkl')

# Load the data_reader object from the pickle file
with open(pkl_path, 'rb') as file:
    data_pkl = pickle.load(file)

# Load the depth and temperature data
depth_data = data_pkl.data['CC-96']['depth'].values
temp_data = data_pkl.data['CC-96'].get('tempIMU')
sampling_rate = int(data_pkl.info['CC-96']['datetime_metadata']['fs'])
datetime_data = pd.to_datetime(data_pkl.data['CC-96']['datetime'])

# Sidebar for parameters
st.sidebar.title("Zero Offset Correction Parameters")
threshold = st.sidebar.slider("Flat Chunk Threshold", min_value=0.01, max_value=1.0, value=0.1, step=0.01)
min_duration = st.sidebar.slider("Minimum Duration (seconds)", min_value=1, max_value=100, value=30, step=1)
depth_threshold = st.sidebar.slider("Maximum Depth for Surface Interval (meters)", min_value=-10, max_value=25, value=5, step=1)
apply_temp_correction = st.sidebar.checkbox("Apply Temperature Correction", value=False)

# Process depth data
first_derivative, downsampled_depth = smooth_downsample_derivative(depth_data, original_sampling_rate=sampling_rate, downsampled_sampling_rate=1)

# Detect flat chunks (potential surface intervals)
flat_chunks = detect_flat_chunks(
    depth=downsampled_depth, 
    datetime_data=datetime_data[::int(sampling_rate)],  # Adjust datetime data to match downsampled depth
    first_derivative=first_derivative, 
    threshold=threshold, 
    min_duration=min_duration, 
    depth_threshold=depth_threshold, 
    original_sampling_rate=400, 
    downsampled_sampling_rate=1
)
num_flat_chunks = len(flat_chunks)
st.sidebar.write(f"Number of potential surface intervals detected: {num_flat_chunks}")

# Dive detection parameters
st.sidebar.title("Dive Detection Parameters")
min_depth_threshold = st.sidebar.slider("Minimum Depth Threshold for Dive (meters)", min_value=0.1, max_value=10.0, value=1.0, step=0.1)
dive_duration_threshold = st.sidebar.slider("Dive Duration Threshold (seconds)", min_value=1, max_value=100, value=10, step=1)
smoothing_window = st.sidebar.slider("Smoothing Window for Dives", min_value=1, max_value=20, value=5, step=1)

# Apply zero offset correction
corrected_depth_temp, corrected_depth_no_temp, depth_correction = apply_zero_offset_correction(
    depth=downsampled_depth, 
    temp=temp_data.values if temp_data is not None else None, 
    flat_chunks=flat_chunks
)

# Upsample and adjust the corrected depths to match original sampling rate
upsampling_factor = int(sampling_rate / 1)
repeated_corrected_depth_temp = upsample(corrected_depth_temp, upsampling_factor, len(depth_data))
repeated_corrected_depth_no_temp = upsample(corrected_depth_no_temp, upsampling_factor, len(depth_data))

# Detect dives in the corrected depth data
dives = find_dives(
    depth_series=repeated_corrected_depth_no_temp,
    datetime_data=datetime_data,
    min_depth_threshold=min_depth_threshold,
    sampling_rate=sampling_rate,
    duration_threshold=dive_duration_threshold,
    smoothing_window=smoothing_window
)
num_dives = len(dives)
st.sidebar.write(f"Number of dives detected: {num_dives}")

# Plotting
fig = plot_depth_correction(datetime_data, upsampling_factor, depth_data, first_derivative, 
                            repeated_corrected_depth_temp, repeated_corrected_depth_no_temp, 
                            depth_correction, dives, flat_chunks, temp_data, apply_temp_correction)
st.plotly_chart(fig)

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
