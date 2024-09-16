import numpy as np
from scipy.signal import butter, filtfilt
from numpy.linalg import solve, inv
from scipy.linalg import lstsq

def compute_field_intensity_and_inclination(acceleration_data, magnetometer_data=None, sampling_rate=None, compute_inclination=True):
    """
    Compute the field intensity of acceleration and magnetometer data, 
    and the inclination angle of the magnetic field (in degrees). Based off of check_AM function from `tagtools`.
    
    Parameters
    ----------
    acceleration_data : numpy.ndarray or dict
        An accelerometer sensor matrix with columns [ax, ay, az].
        Can also be a sensor data dictionary containing 'data' and 'sampling_rate'.
    magnetometer_data : numpy.ndarray or None, optional
        A magnetometer sensor matrix with columns [mx, my, mz]. Optional.
    sampling_rate : float or None, optional
        The sampling rate of the sensor data in Hz. Required if `acceleration_data` is not a sensor dictionary.
    compute_inclination : bool, optional
        Whether to compute and return the inclination angle. Defaults to True.
    
    Returns
    -------
    dict or numpy.ndarray
        - If `compute_inclination` is False: returns the field intensity as a numpy array.
        - If `compute_inclination` is True: returns a dictionary with field intensity and inclination angle (in degrees).
    
    Raises
    ------
    ValueError
        If `sampling_rate` is not provided when `acceleration_data` is not a sensor dictionary, or if the data is invalid.
    """
    
    low_pass_filter_freq = 5  # Low-pass filter frequency in Hz

    if isinstance(acceleration_data, dict):
        if magnetometer_data is not None:
            if acceleration_data['sampling_rate'] == magnetometer_data['sampling_rate'] and len(acceleration_data['data']) == len(magnetometer_data['data']):
                sampling_rate = acceleration_data['sampling_rate']
                acceleration_data = acceleration_data['data']
                magnetometer_data = magnetometer_data['data']
        else:
            sampling_rate = acceleration_data['sampling_rate']
            acceleration_data = acceleration_data['data']
        if len(acceleration_data) == 0:
            raise ValueError("No data found in input argument 'acceleration_data'")
    else:
        if magnetometer_data is None and sampling_rate is None:
            raise ValueError("Sampling rate is required if 'acceleration_data' is not a sensor dictionary")
        if sampling_rate is None:
            raise ValueError("Need to specify sampling frequency for matrix arguments")

    # Handle single vector inputs
    if magnetometer_data is not None and magnetometer_data.ndim == 1:
        magnetometer_data = magnetometer_data.reshape(1, -1)
    if acceleration_data.ndim == 1:
        acceleration_data = acceleration_data.reshape(1, -1)

    # Check that sizes of acceleration_data and magnetometer_data are compatible
    if magnetometer_data is not None and acceleration_data.shape[0] != magnetometer_data.shape[0]:
        min_samples = min(acceleration_data.shape[0], magnetometer_data.shape[0])
        acceleration_data = acceleration_data[:min_samples, :]
        magnetometer_data = magnetometer_data[:min_samples, :]

    # Low-pass filter the data if sampling rate is greater than 10 Hz
    if sampling_rate > 10:
        filter_order = int(round(4 * sampling_rate / low_pass_filter_freq))
        if acceleration_data.shape[0] > filter_order:
            b, a = butter(4, low_pass_filter_freq / (sampling_rate / 2), btype='low')
            acceleration_data = filtfilt(b, a, acceleration_data, axis=0)
            if magnetometer_data is not None:
                magnetometer_data = filtfilt(b, a, magnetometer_data, axis=0)

    # Compute field intensity of the first input argument (acceleration_data)
    acceleration_field_intensity = np.sqrt(np.sum(acceleration_data**2, axis=1)).reshape(-1, 1)

    if magnetometer_data is not None:
        # Compute field intensity of the second input argument (magnetometer_data)
        magnetometer_field_intensity = np.sqrt(np.sum(magnetometer_data**2, axis=1)).reshape(-1, 1)
        field_intensity = np.hstack((acceleration_field_intensity, magnetometer_field_intensity))
    else:
        field_intensity = acceleration_field_intensity

    if compute_inclination and magnetometer_data is not None:
        dot_product = np.sum(acceleration_data * magnetometer_data, axis=1)
        inclination_angle = -np.degrees(np.arcsin(dot_product / (field_intensity[:, 0] * field_intensity[:, 1])))
        return {'field_intensity': field_intensity, 'inclination_angle': inclination_angle}
    else:
        return field_intensity

def estimate_offset_triaxial(data):
    """
    Estimate and correct the offset in each axis of a triaxial field measurement. Based off of fix_offset_3d function from `tagtools`.

    Parameters
    ----------
    data : numpy.ndarray or dict
        A sensor matrix (numpy.ndarray) or dictionary containing measurements from a triaxial field sensor.
        The array should have a shape of (n_samples, 3) for triaxial data, and the dictionary should have a 'data' key 
        containing such an array. Optional keys in the dictionary include 'cal_map' and 'cal_cross' for calibration.

    Returns
    -------
    dict
        A dictionary containing:
        - 'X': numpy.ndarray or dict
            The adjusted triaxial sensor measurements. If the input was a dictionary, the output will be a dictionary 
            with the 'data' field containing the adjusted measurements.
        - 'G': dict
            A calibration dictionary containing the offset added to each axis. The key 'poly' maps to a 3x2 array, 
            where the first column is all ones, and the second column contains the estimated offsets for each axis.

    Raises
    ------
    ValueError
        If the input data is not a 3-axis sensor matrix, if the input is None, or if the condition number of the matrix 
        used for solving the offset is too poor to provide a reliable solution.
    """
    
    # Initialize the calibration polynomial
    poly1 = np.ones((3, 1))
    poly2 = np.zeros((3, 1))
    G = {'poly': np.hstack((poly1, poly2))}

    if data is None:
        raise ValueError("Input data is required")

    if isinstance(data, dict):
        x = data['data']
    else:
        x = data

    if x.shape[1] != 3:
        raise ValueError("Input data must be from a 3-axis sensor")

    # Filter out invalid rows
    valid_rows = np.all(np.isfinite(x), axis=1)
    x_valid = x[valid_rows, :]

    # Compute the squared magnitude of each vector and the mean magnitude
    bsq = np.sum(x_valid**2, axis=1)
    mb = np.sqrt(np.mean(bsq))

    # Prepare matrix for least-squares solution
    XX = np.hstack((2 * x_valid, np.full((len(x_valid), 1), mb)))
    R = np.dot(XX.T, XX)

    if np.linalg.cond(R) > 1e3:
        raise ValueError("Condition too poor to get reliable solution")

    # Solve for the offsets
    P = np.dot(bsq, XX)
    H = -solve(R, P)

    # Update the calibration polynomial with the offsets
    G['poly'] = np.hstack((poly1, H[:3].reshape(3, 1)))

    # Adjust the sensor data by adding the offset
    x_adjusted = x + H[:3]

    if not isinstance(data, dict):
        return {'X': x_adjusted, 'G': G}

    data['data'] = x_adjusted

    # Adjust the calibration polynomial if cal_map or cal_cross is present
    if 'cal_map' in data:
        G['poly'][:, 1] = np.dot(inv(data['cal_map']), G['poly'][:, 1])

    if 'cal_cross' in data:
        G['poly'][:, 1] = np.dot(inv(data['cal_cross']), G['poly'][:, 1])

    data['cal_poly'] = G['poly']

    # Update the history of the calibration
    if 'history' in data and data['history']:
        data['history'].append('estimate_offset_triaxial')
    else:
        data['history'] = ['estimate_offset_triaxial']

    return {'X': data, 'G': G}

