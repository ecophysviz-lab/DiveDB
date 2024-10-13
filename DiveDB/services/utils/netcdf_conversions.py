import netCDF4 as nc
import xarray as xr
import pandas as pd
import numpy as np


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
                # Check if DATE array is empty or contains only empty strings
                if ds["DATE"].size == 0 or np.all(ds["DATE"].values == ""):
                    print(f"No valid dates in group {group}. SKIPPING GROUP.")
                    continue

                # Check if datetime is in MATLAB datenum format by checking if dtype is float
                if ds["DATE"].dtype == np.float64 and np.all(
                    ds["DATE"].values < 800000
                ):
                    datetime_coord = matlab_datenum_to_datetime_vectorized(
                        ds["DATE"].values
                    )
                else:
                    try:
                        # Check the format of the first date string to determine the correct format
                        first_date_str = ds["DATE"].values[0]
                        if ":" in first_date_str.split()[0]:  # Check if time is first
                            datetime_coord = np.array(
                                pd.to_datetime(ds["DATE"].values)
                            ).astype("datetime64[ns]")
                        else:  # Assume date is first
                            datetime_coord = np.array(
                                pd.to_datetime(ds["DATE"].values)
                            ).astype("datetime64[ns]")
                    except Exception as e:
                        print(f"Error converting dates in group {group}: {e}")
                        print(ds["DATE"].values)
                        continue

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
