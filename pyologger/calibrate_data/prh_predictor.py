import numpy as np
from scipy.signal import decimate, savgol_filter
import matplotlib.pyplot as plt
from pyologger.calibrate_data.zoc import *

import numpy as np
import matplotlib.pyplot as plt

# PRH predictor not yet working



def prh_predictor2(acc_data, depth_data, datetime_data, sampling_rate, max_depth=1):
    """
    Predict tag position on a diving animal parameterized by p0, r0, and h0 angles. Re-uses functionality from `zoc.py`

    Parameters
    ----------
    acc_data : numpy.ndarray
        An nx3 matrix containing accelerometer data. Each row corresponds to [accX, accY, accZ].
    depth_data : numpy.ndarray
        A vector containing depth data corresponding to the accelerometer data.
    datetime_data : pandas.Series
        Series of datetime objects corresponding to the depth measurements.
    sampling_rate : float
        Sampling rate of the data in Hz.
    max_depth : float, optional
        The maximum depth of near-surface dives to consider. Default is 1 m.

    Returns
    -------
    prh : numpy.ndarray
        A matrix with rows [cue, p0, r0, h0, q, length] for each dive edge analyzed.
    """

    # Step 1: Downsample, smooth, and calculate the derivative of the depth data
    first_derivative, downsampled_depth = smooth_downsample_derivative(
        depth_data, original_sampling_rate=sampling_rate, downsampled_sampling_rate=1
    )

    # # Step 2: Detect flat chunks (surface intervals)
    # flat_chunks = detect_flat_chunks(
    #     depth=downsampled_depth, 
    #     datetime_data=datetime_data, 
    #     first_derivative=first_derivative, 
    #     threshold=0.1, 
    #     min_duration=5, 
    #     depth_threshold=max_depth, 
    #     original_sampling_rate=sampling_rate, 
    #     downsampled_sampling_rate=1
    # )

    # Step 4: Normalize the accelerometer data to 1 g
    acc_data = normalize_acceleration(acc_data)

    # Step 5: Detect dives based on the corrected depth data
    dives = find_dives(
        depth_series=depth_data,
        datetime_data=datetime_data,
        min_depth_threshold=max_depth,
        sampling_rate=1,  # after downsampling, the sampling rate is now 1 Hz
        duration_threshold=10,
        smoothing_window=5
    )

    if dives.empty:
        print(f"No dives deeper than {max_depth} meters found in dive profile.")
        return np.array([])

    # Step 6: Segment dives and estimate PRH angles
    prh = estimate_prh(acc_data, depth_data, 1, dives)
    
    # Step 7: Plot the PRH results
    plot_prh(depth_data, 1, prh)

    return prh

def normalize_acceleration(A):
    """ Normalize acceleration data to 1 g. """
    norm = np.linalg.norm(A, axis=1)
    return A / norm[:, np.newaxis]

def estimate_prh(A, P, fs, dives):
    """
    Estimate PRH angles for given dive segments.

    Parameters
    ----------
    A : numpy.ndarray
        Normalized acceleration data.
    P : numpy.ndarray
        Corrected depth data.
    fs : float
        Sampling rate of the data in Hz.
    dives : pandas.DataFrame
        DataFrame containing detected dives.

    Returns
    -------
    prh : numpy.ndarray
        A matrix with rows [cue, p0, r0, h0, q, length] for each dive edge analyzed.
    """
    prh = np.full((len(dives), 6), np.nan)
    
    for i, dive in dives.iterrows():
        segment = (dive['start'], dive['end'])
        prh_est = apply_method2(A, P, fs, segment)
        if prh_est is not None:
            prh[i] = [segment[0], *prh_est, segment[1] - segment[0]]

    return prh


def apply_method2(A, P, fs, segment):
    """ 
    Apply PRH estimation method on segments. 
    """
    ks = slice(int(segment[0] * fs), int(segment[1] * fs))
    As = A[ks]
    vs = np.gradient(P[ks]) * fs  # Calculate vertical speed

    # Calculate energy ratio between plane-of-motion and axis of rotation
    QQ = np.dot(As.T, As)
    _, D, V = np.linalg.svd(QQ)
    pow_ratio = D[-1] / D[-2]

    if pow_ratio > 0.05:  # If motion is more three-dimensional
        return None

    # Estimate r0 and h0
    aa = np.arccos([0, 1, 0] @ V[:, -1])
    phi = np.cross([0, 1, 0], V[:, -1]) / np.sin(aa)
    S = skew_matrix(phi)
    Q = np.eye(3) + (1 - np.cos(aa)) * S @ S - np.sin(aa) * S

    am = As.mean(axis=0) @ Q.T
    p0 = np.arctan2(am[0], am[2])
    Q = euler2rotmat([p0, 0, 0]) @ Q

    prh = [np.arcsin(Q[2, 0]), np.arctan2(Q[2, 1], Q[2, 2]), np.arctan2(Q[1, 0], Q[0, 0])]
    aa_transformed = As @ Q[1, :]

    prh.append(min([pow_ratio, np.std(aa_transformed)]))

    if np.polyfit(As[:, 0] @ Q[0, :], vs, 1)[0] > 0:
        prh[2] = (prh[2] - np.pi) % (2 * np.pi)

    prh[1:] = [(angle + np.pi) % (2 * np.pi) - np.pi for angle in prh[1:]]
    return prh

def euler2rotmat(p, r=None, h=None):
    """
    Calculate rotation matrix from Euler angles (pitch, roll, and heading/yaw).

    Parameters
    ----------
    p : float or numpy.ndarray
        Pitch angle in radians. Can be a scalar or an array.
    r : float or numpy.ndarray, optional
        Roll angle in radians. Can be a scalar or an array. Required if `p`, `r`, and `h` are not provided as a matrix.
    h : float or numpy.ndarray, optional
        Heading (yaw) angle in radians. Can be a scalar or an array. Required if `p`, `r`, and `h` are not provided as a matrix.

    Returns
    -------
    numpy.ndarray
        Rotation matrix or stack of rotation matrices. If input angles are scalars, the output is a 3x3 matrix.
        If input angles are arrays, the output is a 3x3xn array, where n is the number of sets of angles.
    """

    if r is None and h is None:
        # Assume p is a matrix with columns [pitch, roll, heading]
        h = p[:, 2]
        r = p[:, 1]
        p = p[:, 0]

    p, r, h = np.broadcast_arrays(p, r, h)

    cp = np.cos(p)
    sp = np.sin(p)
    cr = np.cos(r)
    sr = np.sin(r)
    ch = np.cos(h)
    sh = np.sin(h)

    n = len(p)
    Q = np.zeros((3, 3, n))

    for k in range(n):
        P = np.array([[cp[k], 0, -sp[k]],
                      [0, 1, 0],
                      [sp[k], 0, cp[k]]])

        R = np.array([[1, 0, 0],
                      [0, cr[k], -sr[k]],
                      [0, sr[k], cr[k]]])

        H = np.array([[ch[k], -sh[k], 0],
                      [sh[k], ch[k], 0],
                      [0, 0, 1]])

        Q[:, :, k] = H @ P @ R

    if n == 1:
        return Q[:, :, 0]
    else:
        return Q.squeeze()

def skew_matrix(vector):
    """ Create a skew-symmetric matrix for a given vector. """
    return np.array([[0, -vector[2], vector[1]],
                     [vector[2], 0, -vector[0]],
                     [-vector[1], vector[0], 0]])

def plot_prh(P, fs, prh):
    """ Plot the PRH results and allow user adjustments. """
    plt.figure(figsize=(10, 8))

    plt.subplot(3, 1, 1)
    plt.plot(np.arange(len(P)) / fs, P)
    plt.gca().invert_yaxis()
    plt.title("Depth Profile")
    plt.ylabel("Depth (m)")

    plt.subplot(3, 1, 2)
    plt.plot(prh[:, 0], prh[:, 1:4] * 180 / np.pi, marker='*')
    plt.ylabel("PRH Angles (degrees)")

    plt.subplot(3, 1, 3)
    plt.plot(prh[:, 0], np.minimum(prh[:, 4], 0.15), marker='*')
    plt.xlabel("Time (s)")
    plt.ylabel("Quality")

    plt.show()

