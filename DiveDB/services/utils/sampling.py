import numpy as np
import pandas as pd


def upsample(df, target_fs):
    """
    Upsamples the DataFrame to the target frequency by forward-filling data
    and adjusting the datetime index accordingly.

    Parameters:
    - df: pandas DataFrame with a DatetimeIndex.
    - target_fs: float, the target frequency in Hz.

    Returns:
    - pandas DataFrame upsampled to the target frequency.
    """
    # Calculate the target sampling interval
    freq = pd.Timedelta(seconds=1 / target_fs)

    # Separate numeric and non-numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    non_numeric_cols = df.columns.difference(numeric_cols)

    # Resample numeric columns using interpolation
    df_numeric = df[numeric_cols].resample(freq).interpolate(method="linear")

    # Resample non-numeric columns using forward-fill
    df_non_numeric = df[non_numeric_cols].resample(freq).ffill()

    # Combine the numeric and non-numeric resampled data
    df_upsampled = pd.concat([df_numeric, df_non_numeric], axis=1)

    # Reorder columns to match the original DataFrame
    df_upsampled = df_upsampled[df.columns]

    return df_upsampled


def downsample(df, original_fs, target_fs):
    """
    Downsamples the DataFrame to the target frequency by taking the mean
    over intervals and adjusting the datetime index accordingly.

    Parameters:
    - df: pandas DataFrame with a DatetimeIndex.
    - original_fs: float, the original frequency in Hz.
    - target_fs: float, the target frequency in Hz.

    Returns:
    - pandas DataFrame downsampled to the target frequency.
    """
    if target_fs >= original_fs:
        return df

    # Calculate the target sampling interval
    freq = pd.Timedelta(seconds=1 / target_fs)

    # Separate numeric and non-numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    non_numeric_cols = df.columns.difference(numeric_cols)

    # Resample numeric columns using mean
    df_numeric = df[numeric_cols].resample(freq).mean()

    # Resample non-numeric columns using forward-fill
    df_non_numeric = df[non_numeric_cols].resample(freq).ffill()

    # Combine the numeric and non-numeric resampled data
    df_downsampled = pd.concat([df_numeric, df_non_numeric], axis=1)

    # Reorder columns to match the original DataFrame
    df_downsampled = df_downsampled[df.columns]

    return df_downsampled


def resample(df, target_fs, original_fs=None):
    """
    Resamples the DataFrame to the target frequency, adjusting the datetime
    index accordingly.

    Parameters:
    - df: pandas DataFrame with a DatetimeIndex.
    - target_fs: float, the target frequency in Hz.
    - original_fs: float, optional, the original frequency in Hz.

    Returns:
    - pandas DataFrame resampled to the target frequency.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        df = df.copy()
        df.index = pd.to_datetime(df.index)

    # Ensure the index is sorted
    df = df.sort_index()

    if original_fs is None:
        # Estimate the original frequency from the datetime index
        original_intervals = df.index.to_series().diff().dropna()

        # Filter out zero and negative intervals
        original_intervals = original_intervals[original_intervals > pd.Timedelta(0)]

        if len(original_intervals) == 0:
            raise ValueError(
                "Cannot estimate original frequency: all time intervals are zero or negative."
            )

        # Use median to estimate the interval
        original_interval = original_intervals.median()

        if original_interval.total_seconds() == 0:
            raise ValueError(
                "Original interval is zero after filtering; cannot estimate original frequency."
            )

        original_fs = 1 / original_interval.total_seconds()

    if original_fs == 0:
        raise ValueError("Original frequency is zero, cannot resample.")

    if target_fs < original_fs:
        return downsample(df, original_fs, target_fs)
    else:
        return upsample(df, target_fs)
