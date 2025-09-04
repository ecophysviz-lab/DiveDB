import numpy as np
import pandas as pd
import logging


logger = logging.getLogger(__name__)


def upsample(df, original_fs, target_fs):
    """
    Upsamples the DataFrame to the target frequency by forward-filling data
    and adjusting the datetime index accordingly.

    Parameters:
    - df: pandas DataFrame with a DatetimeIndex.
    - target_fs: float, the target frequency in Hz.

    Returns:
    - pandas DataFrame upsampled to the target frequency.
    """
    original_length = len(df)
    upsampling_factor = int(target_fs / original_fs)
    logger.info(
        f"Original FS: {original_fs}, Target FS: {target_fs}, Upsampling Factor: {upsampling_factor}"
    )

    # Step 1: Repeat the data to upsample
    new_df = pd.DataFrame()

    # For all columns that aren't datetime, repeat the data
    for col in df.columns:
        if col != "datetime":
            new_df[col] = pd.Series(np.repeat(df[col].values, upsampling_factor))
        else:
            number_of_seconds = (df[col].iloc[-1] - df[col].iloc[0]).total_seconds() + 1
            seconds_elapsed = np.arange(0, number_of_seconds, 1 / target_fs)

            new_df[col] = df[col].iloc[0] + pd.to_timedelta(seconds_elapsed, unit="ms")

    # Step 2: Adjust the length to match the original length
    if len(new_df) > original_length:
        new_df = new_df[:original_length]
    elif len(new_df) < original_length:
        new_df = np.pad(new_df, (0, original_length - len(new_df)), "edge")

    return new_df.reset_index(drop=True)


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
    conversion_factor = int(original_fs / target_fs)
    logger.info(
        f"Original FS: {original_fs}, Target FS: {target_fs}, Conversion Factor: {conversion_factor}"
    )
    return df.iloc[::conversion_factor, :].reset_index(drop=True)


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
    # Ensure the index is sorted
    df = df.sort_values(by="datetime")

    if original_fs is None:
        # Estimate the original frequency from the datetime index
        original_intervals = df["datetime"].diff().dropna()

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

    if target_fs == original_fs:
        return df
    elif target_fs < original_fs:
        return downsample(df, original_fs, target_fs)
    else:
        return upsample(df, original_fs, target_fs)
