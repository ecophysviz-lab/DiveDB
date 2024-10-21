import netCDF4 as nc
import xarray as xr
import pandas as pd
import numpy as np
from datetime import datetime


def matlab_datenum_to_datetime_vectorized(
    matlab_serial_dates: np.ndarray,
) -> np.ndarray:
    """
    Converts a vector of MATLAB datenum values to pandas datetime in a vectorized manner.

    MATLAB datenum starts from year 0000-01-00, while Python's datetime starts from 1970-01-01.
    We need to adjust by subtracting the number of days between these dates.
    """
    # MATLAB serialized dates start from 0000-01-01
    matlab_start_date = np.datetime64("0000-01-01")

    # Split into days and fractional days
    days = np.floor(matlab_serial_dates).astype(int)
    fraction = matlab_serial_dates - days

    # Convert MATLAB serial date to Python datetime
    converted_dates = (
        matlab_start_date
        + days.astype("timedelta64[D]")
        + (fraction * 24 * 3600).astype("timedelta64[s]")
    ).astype("datetime64[ns]")
    return converted_dates


possible_formats = [
    "%H:%M:%S %d-%b-%Y",  # e.g., "00:11:12 21-Feb-2017"
    "%Y-%m-%d %H:%M:%S",  # e.g., "2017-02-21 00:11:12"
    "%d/%m/%Y %H:%M",  # e.g., "21/02/2017 00:11"
    "%m/%d/%Y %I:%M:%S %p",  # e.g., "02/21/2017 12:11:12 AM"
]


def infer_date_format(date_str, possible_formats=possible_formats):
    """
    Infers the date format of a date string from a list of possible formats.

    Parameters:
    - date_str (str): The date string to parse.
    - possible_formats (list): A list of date format strings.

    Returns:
    - str: The matching date format string.

    Raises:
    - ValueError: If no matching format is found.
    """
    if date_str is None:
        return None

    for fmt in possible_formats:
        try:
            datetime.strptime(date_str, fmt)
            return fmt
        except ValueError:
            continue


def convert_to_formatted_dataset(
    input_file_path: str,
    output_file_path: str = None,
):
    """
    Convert an initial dataset to a formatted dataset.
    """
    date_data_vars = ["DATE", "YEAR", "MONTH", "DAY", "HOUR", "MIN", "SEC"]

    with nc.Dataset(input_file_path, "r") as rootgrp:
        root_ds = xr.Dataset()

        # Copy global attributes
        for attr_name in rootgrp.ncattrs():
            root_ds.attrs[attr_name] = rootgrp.getncattr(attr_name)

        for group in rootgrp.groups:
            with xr.open_dataset(input_file_path, group=group) as ds:
                # Check if datetime is in MATLAB datenum format by checking if dtype is float
                if ds["DATE"].dtype == np.float64 and np.all(
                    ds["DATE"].values < 800000
                ):
                    datetime_coord = matlab_datenum_to_datetime_vectorized(
                        ds["DATE"].values
                    )
                else:
                    first_date_str = (
                        ds["DATE"].values[0] if len(ds["DATE"].values) > 0 else None
                    )
                    date_format = infer_date_format(first_date_str, possible_formats)
                    datetime_coord = np.array(
                        pd.to_datetime(
                            ds["DATE"].values,
                            format=date_format if date_format else "mixed",
                        )
                    ).astype("datetime64[ns]")

                datetime_coord = datetime_coord[
                    ~np.isnat(datetime_coord) & (datetime_coord != np.datetime64(""))
                ]

                vars_to_convert = [
                    var
                    for var in ds.data_vars
                    if var not in date_data_vars and len(ds[var]) == len(datetime_coord)
                ]

                if len(vars_to_convert) == 0 or len(datetime_coord) == 0:
                    print(f"No valid variables to convert for group {group}")
                    continue

                for var in vars_to_convert:
                    array_name = f"{var}"
                    sample_dim_name = f"{group}_samples"

                    if np.all(pd.isna(ds[var].values)) or np.all(ds[var].values == ""):
                        print(
                            f"All values are NaN or empty string for variable {var} in group {group}"
                        )
                        continue

                    dive_data_array = xr.DataArray(
                        ds[var].values,
                        dims=[sample_dim_name],
                        coords=[datetime_coord],
                        attrs={
                            "group": group,
                            "variable": var,
                        },
                    )

                    if array_name in root_ds:
                        root_ds[f"{array_name}__{group}"] = dive_data_array
                    else:
                        root_ds[array_name] = dive_data_array

    if output_file_path is not None:
        root_ds.to_netcdf(output_file_path)

    return root_ds
