import json
import os

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
