import os
import streamlit as st
import pickle
from pyologger.plot_data.plotter import plot_tag_data_interactive, save_color_mapping, load_color_mapping

# Define paths
root_dir = "/Users/jessiekb/Documents/GitHub/pyologger"
data_dir = os.path.join(root_dir, "data")
deployment_folder = os.path.join(data_dir, "2024-01-16_oror-002a_Shuka-HR")
pkl_path = os.path.join(deployment_folder, 'outputs', 'data.pkl')

# Load the data_reader object from the pickle file
with open(pkl_path, 'rb') as file:
    data_pkl = pickle.load(file)

# Load color mappings
color_mapping_path = os.path.join(root_dir, 'color_mappings.json')

# Load the existing color mappings or initialize with default if not present
color_mapping = load_color_mapping(color_mapping_path)

# Sidebar for time range selection
imu_logger_to_use = 'CC-96'
ephys_logger_to_use = 'UF-01'

imu_df = data_pkl.data[imu_logger_to_use]
ephys_df = data_pkl.data[ephys_logger_to_use]
overlap_start_time = max(imu_df['datetime'].min(), ephys_df['datetime'].min()).to_pydatetime()
overlap_end_time = min(imu_df['datetime'].max(), ephys_df['datetime'].max()).to_pydatetime()

st.sidebar.title("Select Time Range")
start_time = st.sidebar.slider("Start Time", value=overlap_start_time, min_value=overlap_start_time, max_value=overlap_end_time, format="YYYY-MM-DD HH:mm:ss")
end_time = st.sidebar.slider("End Time", value=overlap_end_time, min_value=overlap_start_time, max_value=overlap_end_time, format="YYYY-MM-DD HH:mm:ss")

# Interactive color pickers
st.sidebar.header("Customize Colors")
for key in color_mapping.keys():
    new_color = st.sidebar.color_picker(f"Select color for {key}", value=color_mapping[key])
    if new_color != color_mapping[key]:
        color_mapping[key] = new_color  # Update color in memory

# Define notes to plot
notes_to_plot = {
    'heartbeat_manual_ok': 'ecg',
    'exhalation_breath': 'depth'
}

# Display title
st.title('Interactive Plot Customization')

# Plotting
fig = plot_tag_data_interactive(data_pkl, 
                                imu_channels=['depth', 'corrdepth', 'accX', 'accY', 'accZ', 'gyrX', 'gyrY', 'gyrZ', 'magX', 'magY', 'magZ'], 
                                ephys_channels=['ecg'], 
                                imu_logger=imu_logger_to_use, 
                                ephys_logger=ephys_logger_to_use, 
                                time_range=(start_time, end_time), 
                                note_annotations=notes_to_plot, 
                                color_mapping=color_mapping)

# Display the plot
st.plotly_chart(fig)

# Save color mapping changes if needed
if st.sidebar.button('Save Color Mappings'):
    save_color_mapping(color_mapping, color_mapping_path)
    st.success("Color mappings saved.")
