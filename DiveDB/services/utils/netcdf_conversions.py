import netCDF4 as nc
import xarray as xr
import pandas as pd
import numpy as np


def convert_to_formatted_dataset(
    input_file_path: str, level: 1 | 2 | 3 = None, output_file_path: str = None
):
    """
    Convert an initial dataset to a formatted dataset.
    """
    if level not in [1, 2, 3]:
        raise ValueError("Level must be specified. Valid levels include 1, 2, and 3.")

    date_data_vars = ["DATE", "YEAR", "MONTH", "DAY", "HOUR", "MIN", "SEC"]

    with nc.Dataset(input_file_path, "r") as rootgrp:
        root_ds = xr.Dataset()

        # Copy global attributes
        for attr_name in rootgrp.ncattrs():
            root_ds.attrs[attr_name] = rootgrp.getncattr(attr_name)

        for group in rootgrp.groups:
            with xr.open_dataset(input_file_path, group=group) as ds:
                datetime_coord = pd.to_datetime(ds["DATE"].values)
                datetime_coord = datetime_coord[
                    datetime_coord.notnull() & (datetime_coord != "")
                ]
                vars_to_convert = [
                    var
                    for var in ds.data_vars
                    if var not in date_data_vars and len(ds[var]) == len(datetime_coord)
                ]

                if len(vars_to_convert) == 0 or len(datetime_coord) == 0:
                    continue

                # Separate variables containing strings from those containing numeric data
                string_vars = [
                    var
                    for var in vars_to_convert
                    if ds[var].dtype == "O" or np.issubdtype(ds[var].dtype, np.str_)
                ]
                numeric_vars = [
                    var for var in vars_to_convert if var not in string_vars
                ]

                if len(numeric_vars) > 0:
                    numeric_data_array = ds[numeric_vars].to_array().values
                    numeric_data_array = numeric_data_array[
                        ~pd.isna(numeric_data_array).all(axis=1)
                    ]

                    numeric_array_name = (
                        f"processed_{group}" if level == 3 else f"{group}"
                    )
                    numeric_var_dim_name = (
                        f"processed_{group}_variables"
                        if level == 3
                        else f"{group}_variables"
                    )
                    numeric_sample_dim_name = (
                        f"processed_{group}_samples"
                        if level == 3
                        else f"{group}_samples"
                    )

                    numeric_dive_data_array = xr.DataArray(
                        numeric_data_array,
                        dims=[numeric_var_dim_name, numeric_sample_dim_name],
                        coords={numeric_sample_dim_name: datetime_coord},
                    )

                    root_ds[numeric_array_name] = numeric_dive_data_array
                    root_ds[numeric_array_name].attrs["variables"] = numeric_vars

    if output_file_path is not None:
        root_ds.to_netcdf(output_file_path)

    return root_ds
