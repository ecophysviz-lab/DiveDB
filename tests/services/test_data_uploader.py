import pytest
import xarray as xr
import numpy as np
import pandas as pd
from DiveDB.services.data_uploader import DataUploader
from DiveDB.services.data_uploader import NetCDFValidationError


@pytest.fixture
def valid_netcdf_dataset():
    time_samples = pd.date_range("2023-01-01", periods=5, freq="D")
    variable_labels = ["label1", "label2"]

    ds = xr.Dataset(
        {
            "data_var1": (("sensor_samples",), np.random.rand(5)),
            "data_var2": (
                ("sensor_samples", "sensor_variables"),
                np.random.rand(5, 2),
            ),
        },
        coords={
            "sensor_samples": ("sensor_samples", time_samples),
            "sensor_variables": ("sensor_variables", variable_labels),
        },
    )

    # Set the necessary attributes
    ds["data_var1"].attrs["variable"] = "example_variable"
    ds["data_var2"].attrs["variables"] = ["label1", "label2"]

    return ds


def test_validate_data_valid(valid_netcdf_dataset):
    uploader = DataUploader()
    ds = valid_netcdf_dataset
    assert uploader.validate_netcdf(ds)


def test_validate_data_invalid(valid_netcdf_dataset):
    uploader = DataUploader()
    ds = valid_netcdf_dataset
    ds = ds.rename({"sensor_samples": "sensor"})

    with pytest.raises(NetCDFValidationError):
        uploader.validate_netcdf(ds)
