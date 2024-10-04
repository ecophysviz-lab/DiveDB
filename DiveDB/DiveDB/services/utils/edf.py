import mne
import numpy as np
from duckdb import DuckDBPyConnection
import pyedflib


def create_mne_array(
    data: DuckDBPyConnection,
    info=None,
    resample: float = None,
    l_freq: float = None,
    h_freq: float = None,
):
    """
    Create a raw array from an EDF file

    Note: This assumes the data is continuous and from the same recording.
    """
    df = data.df()

    if "label" in df.columns and df["label"].nunique() > 1:
        raise ValueError("Multiple signal names found in the data.")

    df["time_diff"] = df["datetime"].diff().dt.total_seconds()

    # Calculate the frequency
    avg_time_diff = df["time_diff"].mean()
    sfreq = round(1 / avg_time_diff)

    data = df["data"].values[np.newaxis, :]

    # Create the MNE Info object
    info = mne.create_info(ch_names=["ECG_ICA2"], sfreq=sfreq, ch_types=["eeg"])

    # Create the RawArray
    raw = mne.io.RawArray(data, info)
    if resample:
        raw.resample(resample)
    if l_freq:
        raw.filter(l_freq, h_freq)
    return raw


def create_mne_edf(
    data: DuckDBPyConnection,
    file_path: str,
):
    """
    Create an EDF file from an MNE RawArray
    """
    df = data.df()
    unique_signals = df["label"].unique()
    # Initialize lists to hold data and channel names
    data_list = []
    ch_names = []
    sfreq_list = []
    # Loop through each unique signal and collect data
    for signal in unique_signals:
        # Filter data for the current signal
        channel_df = df[df["label"] == signal]
        channel_data = channel_df["data"].values
        data_list.append(channel_data)
        ch_names.append(signal)

        # Calculate the frequency
        channel_df["time_diff"] = channel_df["datetime"].diff().dt.total_seconds()
        avg_time_diff = channel_df["time_diff"].mean()
        sfreq_list.append(round(1 / avg_time_diff))

    data = np.array(data_list)
    signal_headers = pyedflib.highlevel.make_signal_headers(
        ch_names,
        sample_rate=max(sfreq_list),
        physical_min=data.min(),
        physical_max=data.max(),
    )
    # Create an empty file at file_path
    with open(file_path, "w") as f:
        f.write("")

    pyedflib.highlevel.write_edf(file_path, data, signal_headers)
    rawEdf = mne.io.read_raw_edf(file_path)

    print(f"EDF file created with {len(ch_names)} channels: {file_path}")

    return rawEdf
