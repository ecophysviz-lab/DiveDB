import numpy as np
import pandas as pd
from scipy.signal import medfilt, decimate
from sklearn.linear_model import LinearRegression
from itertools import groupby

def smooth_downsample_derivative(depth, original_sampling_rate, downsampled_sampling_rate=1):
    """
    Downsamples, smooths, and calculates the first derivative of the depth signal.

    Parameters
    ----------
    depth : numpy.ndarray
        Array of depth measurements (in meters).
    original_sampling_rate : float
        Original sampling rate of the depth data (in Hz).
    downsampled_sampling_rate : float, optional
        Desired downsampled sampling rate of the depth data (in Hz, default is 1 Hz).

    Returns
    -------
    tuple
        A tuple containing:
        - first_derivative (numpy.ndarray): First derivative of the smoothed and downsampled depth signal.
        - downsampled_depth (numpy.ndarray): Smoothed and downsampled depth signal.
    """
    # Calculate the downsample factor based on the original and target sampling rates
    downsample_factor = int(original_sampling_rate / downsampled_sampling_rate)
    
    # Downsample the depth data
    downsampled_depth = decimate(depth, downsample_factor, zero_phase=True)
    
    # Apply median filtering for smoothing
    smoothed_depth = medfilt(downsampled_depth, kernel_size=5)
    
    # Calculate the first derivative of the smoothed depth signal
    first_derivative = np.gradient(smoothed_depth)
    
    return first_derivative, downsampled_depth

def run_length_encoding(binary_array):
    """
    Perform run-length encoding on a binary array.

    Parameters
    ----------
    binary_array : numpy.ndarray
        Binary array to encode (e.g., an array of boolean values).

    Returns
    -------
    list of tuple
        A list of tuples, where each tuple contains:
        - key (bool): The value of the segment (True/False).
        - length (int): The length of the segment.
    """
    return [(key, len(list(group))) for key, group in groupby(binary_array)]

def detect_flat_chunks(depth, datetime_data, first_derivative, threshold=0.1, 
                       min_duration=5, depth_threshold=25, original_sampling_rate=400, downsampled_sampling_rate=1):
    """
    Detect flat chunks in the depth signal likely representing surface intervals.

    Parameters
    ----------
    depth : numpy.ndarray
        Array of depth measurements (in meters).
    datetime_data : pandas.Series
        Series of datetime objects corresponding to the original (high-frequency) depth measurements.
    first_derivative : numpy.ndarray
        First derivative of the downsampled depth signal.
    threshold : float, optional
        Threshold for detecting flat chunks based on the first derivative (default is 0.1).
    min_duration : int, optional
        Minimum duration for a flat chunk to be considered (in seconds, default is 5).
    depth_threshold : float, optional
        Maximum depth (in meters) for a chunk to be considered a surface interval (default is 25).
    original_sampling_rate : float, optional
        Sampling rate of the original depth data (in Hz, default is 400).
    downsampled_sampling_rate : float, optional
        Sampling rate of the downsampled depth data (in Hz, default is 1).

    Returns
    -------
    pandas.DataFrame
        DataFrame containing the detected flat chunks with columns:
        - 'start' (int): Start index of the flat chunk in the downsampled data.
        - 'end' (int): End index of the flat chunk in the downsampled data.
        - 'median_depth' (float): Median depth of the flat chunk.
        - 'start_time' (datetime): Datetime of the start of the flat chunk in the original data.
        - 'end_time' (datetime): Datetime of the end of the flat chunk in the original data.
    """
    is_flat_chunk = np.abs(first_derivative) < threshold
    rle_encoded = run_length_encoding(is_flat_chunk)
    
    flat_chunks = []
    current_index = 0
    min_duration_samples = min_duration * downsampled_sampling_rate
    
    # Calculate the factor by which the data was downsampled
    downsample_factor = int(original_sampling_rate / downsampled_sampling_rate)
    
    for value, length in rle_encoded:
        if value and length >= min_duration_samples:
            start_ix = current_index
            end_ix = current_index + length
            median_depth = np.median(depth[start_ix:end_ix])
            if np.abs(median_depth) < depth_threshold:
                # Map the downsampled indices back to the original datetime indices
                start_time_index = start_ix * downsample_factor
                end_time_index = end_ix * downsample_factor - 1

                # Ensure that the indices do not go out of bounds
                start_time_index = min(start_time_index, len(datetime_data) - 1)
                end_time_index = min(end_time_index, len(datetime_data) - 1)

                flat_chunks.append({
                    'start': start_ix,
                    'end': end_ix,
                    'median_depth': median_depth,
                    'start_time': datetime_data.iloc[start_time_index],
                    'end_time': datetime_data.iloc[end_time_index]
                })
        current_index += length
    
    return pd.DataFrame(flat_chunks)

def apply_zero_offset_correction(depth, temp, flat_chunks):
    """
    Apply zero offset correction to the depth signal by adjusting surface intervals and correcting based on temperature.

    Parameters
    ----------
    depth : numpy.ndarray
        Array of depth measurements (in meters).
    temp : numpy.ndarray or None
        Array of temperature measurements (in degrees Celsius), or None if not available.
    flat_chunks : pandas.DataFrame
        DataFrame of detected flat chunks with columns 'start', 'end', 'median_depth', 'start_time', 'end_time'.

    Returns
    -------
    tuple
        A tuple containing:
        - corrected_depth_temp (numpy.ndarray): Depth signal corrected with temperature adjustment.
        - corrected_depth_no_temp (numpy.ndarray): Depth signal corrected without temperature adjustment.
        - depth_correction (numpy.ndarray): Array of depth correction values applied to the original depth signal.
    """
    corrected_depth = depth.copy()
    temp_correction = np.zeros_like(depth)
    depth_correction = np.full_like(depth, np.nan)
    
    for _, row in flat_chunks.iterrows():
        start, end = row['start'], row['end']
        depth_correction[start:end] = row['median_depth']
        if temp is not None:
            temp_chunk = temp[start:end] - 20  # Adjust for reference temperature (TREF)
            if len(temp_chunk) > 1:
                reg = LinearRegression()
                reg.fit(temp_chunk.reshape(-1, 1), depth[start:end])
                temp_correction[start:end] = reg.coef_[0] * temp_chunk + reg.intercept_
    
    depth_correction = pd.Series(depth_correction).interpolate().fillna(0).to_numpy()
    corrected_depth_temp = corrected_depth - depth_correction - temp_correction
    corrected_depth_no_temp = corrected_depth - depth_correction
    
    return corrected_depth_temp, corrected_depth_no_temp, depth_correction

def find_dives(depth_series, datetime_data, min_depth_threshold, sampling_rate, duration_threshold=10, smoothing_window=5, search_window=20):
    """
    Detect dives in the depth signal based on smoothing and run-length encoding.

    Parameters
    ----------
    depth_series : numpy.ndarray
        Array of depth measurements (in meters).
    datetime_data : pandas.Series
        Series of datetime objects corresponding to the depth measurements.
    min_depth_threshold : float
        Minimum depth (in meters) to recognize a dive.
    sampling_rate : float
        Sampling rate of the depth data (in Hz).
    duration_threshold : float, optional
        Minimum duration (in seconds) for a dive to be considered valid (default is 10).
    smoothing_window : int, optional
        Window size for median filtering to smooth the depth data (default is 5).
    search_window : int, optional
        Window size (in seconds) to search for the nearest surface point around dive edges (default is 20).

    Returns
    -------
    pandas.DataFrame
        DataFrame containing the detected dives with columns:
        - 'start' (int): Start index of the dive.
        - 'end' (int): End index of the dive.
        - 'max_depth' (float): Maximum depth reached during the dive.
        - 'tmax' (datetime): Datetime of the maximum depth during the dive.
        - 'start_time' (datetime): Datetime of the start of the dive.
        - 'end_time' (datetime): Datetime of the end of the dive.
    """
    smoothed_depth = medfilt(depth_series, kernel_size=smoothing_window)
    is_dive = smoothed_depth > min_depth_threshold
    rle = [(key, len(list(group))) for key, group in groupby(is_dive)]
    
    dive_chunks = []
    current_index = 0

    for is_diving, length in rle:
        if is_diving and (length / sampling_rate) >= duration_threshold:
            dive_chunks.append((current_index, current_index + length))
        current_index += length

    dives = []
    for start, end in dive_chunks:
        start_search_window = max(start - round(search_window * sampling_rate), 0)
        end_search_window = min(end + round(search_window * sampling_rate), len(smoothed_depth) - 1)
        dive_start_index = start_search_window + np.argmin(np.abs(smoothed_depth[start_search_window:start]))
        dive_end_index = end + np.argmin(np.abs(smoothed_depth[end:end_search_window]))
        max_depth = np.max(smoothed_depth[dive_start_index:dive_end_index])
        max_depth_index = np.argmax(smoothed_depth[dive_start_index:dive_end_index])
        dives.append({
            'start': dive_start_index,
            'end': dive_end_index,
            'max_depth': max_depth,
            'tmax': datetime_data.iloc[dive_start_index + max_depth_index],
            'start_time': datetime_data.iloc[dive_start_index],
            'end_time': datetime_data.iloc[dive_end_index - 1]
        })

    return pd.DataFrame(dives)
