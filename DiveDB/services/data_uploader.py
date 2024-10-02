"""
Data Uploader
"""

import os
import edfio
import django
from django.core.files import File
from DiveDB.services.duck_pond import DuckPond, LAKE_CONFIGS
import numpy as np
import gc
import pyarrow as pa
from tqdm import tqdm
import xarray as xr
import json
import math

from dataclasses import dataclass
from datetime import datetime, timezone
from DiveDB.services.utils.openstack import SwiftClient

duckpond = DuckPond()
swift_client = SwiftClient()

django_prefix = os.environ.get("DJANGO_PREFIX", "DiveDB")
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", f"{django_prefix}.server.django_app.settings"
)
django.setup()

from DiveDB.server.metadata.models import Files, Recordings  # noqa: E402


@dataclass
class SignalMetadata:
    label: str
    frequency: float
    start_time: str
    end_time: str


@dataclass
class SignalData:
    label: str
    time: pa.Array
    data: np.ndarray
    signal_length: int


class DataUploader:
    """Data Uploader"""

    def _read_edf_signal(self, edf: edfio.Edf, label: str):
        """Function to read a single signal from an EDF file."""
        signal = edf.get_signal(label)
        data = signal.data
        start_datetime_str = f"{edf.startdate}T{edf.starttime}"
        start_time = np.datetime64(start_datetime_str).astype("datetime64[us]")
        freq = signal.sampling_frequency
        data_indices = np.arange(len(data)) / float(freq)
        timedelta_array = (data_indices * 1000000).astype("timedelta64[us]")
        times = pa.array(
            start_time + timedelta_array, type=pa.timestamp("us", tz="UTC")
        )
        end_time = times[-1].as_py().replace(tzinfo=timezone.utc)

        return (
            SignalData(label=label, time=times, data=data, signal_length=len(data)),
            SignalMetadata(
                label=label,
                frequency=freq,
                start_time=start_time.astype(datetime)
                .replace(tzinfo=timezone.utc)
                .isoformat(),
                end_time=end_time.isoformat(),
            ),
        )

    def _get_datetime_type(self, time_data_array: xr.DataArray):
        """Function to get the datetime type from a PyArrow array."""
        time_dtype = time_data_array.dtype
        if time_dtype == "datetime64[ns]":
            return pa.timestamp("ns", tz="UTC")
        elif time_dtype == "datetime64[us]":
            return pa.timestamp("us", tz="UTC")
        else:
            raise ValueError(f"Unsupported time dtype: {time_dtype}")

    # Convert ds.attrs to a JSON-serializable dictionary
    def _make_json_serializable(self, attrs):
        serializable_attrs = {}
        for key, value in attrs.items():
            if isinstance(value, (np.integer, np.floating)):
                if math.isnan(value):
                    serializable_attrs[key] = None
                else:
                    serializable_attrs[key] = value.item()
            elif isinstance(value, np.ndarray):
                serializable_attrs[key] = [
                    None if math.isnan(v) else v for v in value.tolist()
                ]
            else:
                serializable_attrs[key] = value
        return serializable_attrs

    def _create_value_structs(self, values):
        """Helper function to create value structs for PyArrow table."""
        boolean_values = np.where(
            np.isin(values, [True, False]) & ~np.isin(values, [1.0, 0.0]),
            values,
            None,
        )
        numeric_values = np.vectorize(
            lambda x: (float(x) if isinstance(x, (int, float)) else np.nan)
        )(values)

        # Determine if any value has a decimal place
        if np.any(numeric_values % 1 != 0):
            float_values = np.where(np.isfinite(numeric_values), numeric_values, None)
            int_values = None
        else:
            float_values = None
            int_values = np.where(
                np.isfinite(numeric_values), numeric_values.astype(int), None
            )

        string_values = np.where(
            ~np.isin(values, [True, False])
            & np.vectorize(
                lambda x: (
                    not np.isfinite(float(x)) if isinstance(x, (int, float)) else True
                )
            )(values),
            values,
            None,
        )
        # Ensure string_values are actually strings
        string_values = np.where(
            np.vectorize(lambda x: isinstance(x, str))(string_values),
            string_values,
            None,
        )
        return pa.StructArray.from_arrays(
            [
                (
                    pa.array(float_values, type=pa.float64())
                    if float_values is not None
                    else pa.nulls(len(values), type=pa.float64())
                ),
                pa.array(string_values, type=pa.string()),
                pa.array(boolean_values, type=pa.bool_()),
                (
                    pa.array(int_values, type=pa.int64())
                    if int_values is not None
                    else pa.nulls(len(values), type=pa.int64())
                ),
            ],
            fields=[
                pa.field("float", pa.float64(), nullable=True),
                pa.field("string", pa.string(), nullable=True),
                pa.field("boolean", pa.bool_(), nullable=True),
                pa.field("int", pa.int64(), nullable=True),
            ],
        )

    def _write_data_to_duckpond(
        self,
        metadata: dict,
        times: pa.Array,
        group: str,
        class_name: str,
        label: str,
        values: np.ndarray,
        file_name: str,
    ):
        """Helper function to write data to DuckPond."""
        value_structs = self._create_value_structs(values)
        batch_table = pa.table(
            {
                "animal": pa.array(
                    [metadata["animal"]] * len(values), type=pa.string()
                ),
                "deployment": pa.array(
                    [metadata["deployment"]] * len(values), type=pa.string()
                ),
                "recording": pa.array(
                    [metadata["recording"]] * len(values), type=pa.string()
                ),
                "group": pa.array([group] * len(values), type=pa.string()),
                "class": pa.array([class_name] * len(values), type=pa.string()),
                "label": pa.array([label] * len(values), type=pa.string()),
                "datetime": times,
                "value": value_structs,
            },
            schema=LAKE_CONFIGS["DATA"]["schema"],
        )
        duckpond.write_to_delta(
            data=batch_table,
            lake="DATA",
            mode="append",
            partition_by=[
                "animal",
                "deployment",
                "recording",
                "group",
                "class",
                "label",
            ],
            name=file_name,
            description="test",
        )
        del batch_table
        gc.collect()

    def _write_event_to_duckpond(
        self,
        metadata: dict,
        start_times: pa.Array,
        end_times: pa.Array,
        group: str = None,
        event_keys: list = None,
        event_data: list = None,
        short_descriptions: list[str] | None = None,
        long_descriptions: list[str] | None = None,
        file_name: str = None,
    ):
        """Helper function to write data to DuckPond."""
        if short_descriptions is None:
            short_descriptions = [None] * len(event_keys)
        if long_descriptions is None:
            long_descriptions = [None] * len(event_keys)

        batch_table = pa.table(
            {
                "animal": pa.array(
                    [metadata["animal"]] * len(event_keys), type=pa.string()
                ),
                "deployment": pa.array(
                    [metadata["deployment"]] * len(event_keys), type=pa.string()
                ),
                "recording": pa.array(
                    [metadata["recording"]] * len(event_keys), type=pa.string()
                ),
                "group": pa.array([group] * len(event_keys), type=pa.string()),
                "event_key": event_keys,
                "datetime_start": start_times,
                "datetime_end": end_times,
                "event_data": [json.dumps(data) for data in event_data],
                "short_description": short_descriptions,
                "long_description": long_descriptions,
            },
            schema=LAKE_CONFIGS["STATE_EVENTS"]["schema"],
        )
        duckpond.write_to_delta(
            data=batch_table,
            lake="STATE_EVENTS",
            mode="append",
            partition_by=["animal", "deployment", "recording", "group", "event_key"],
            name=file_name,
            description="test",
        )
        del batch_table
        gc.collect()

    def upload_netcdf(
        self, netcdf_file_path: str, metadata: dict, batch_size: int = 1000000
    ):
        """
        Uploads a netCDF file to the database and DuckPond.

        Parameters:
        netcdf_file_path (str): Path to the netCDF file.
        metadata (dict): Metadata dictionary.
            Required keys:
                - animal: Animal ID (int)
                - deployment: Deployment Name (str)
                - recording: Recording Name (str)
        batch_size (int, optional): Size of data batches for processing. Defaults to 1 million
        """
        ds = xr.open_dataset(netcdf_file_path)

        print(
            f"Creating file record for {os.path.basename(netcdf_file_path)} and uploading to OpenStack..."
        )
        if os.environ.get("SKIP_OPENSTACK_UPLOAD", "false").lower() == "true":
            print("Skipping OpenStack upload...")

            class FileWrapper:
                def __init__(self, name):
                    self.file = {"name": name}

            file = FileWrapper("mock file name")
        else:
            with open(netcdf_file_path, "rb") as f:
                file_object = File(f, name=os.path.basename(netcdf_file_path))
                file = Files.objects.create(
                    recording=Recordings.objects.get(name=metadata["recording"]),
                    file=file_object,
                    extension="nc",
                    type="data",
                    metadata=self._make_json_serializable(ds.attrs),
                )

        sample_coords = [coord for coord in ds.coords if "_sample" in coord.lower()]
        print(f"Processing {sample_coords} datasets in the netCDF file.")

        with tqdm(total=len(sample_coords), desc="Processing variables") as pbar:
            for coord in sample_coords:
                variables_with_coord = set(
                    var for var in ds.data_vars if coord in ds[var].dims
                )
                if any("duration" in var.lower() for var in variables_with_coord):
                    duration_var = [
                        var for var in variables_with_coord if "duration" in var.lower()
                    ][0]
                    duration_data = ds[duration_var].values
                    start_times = ds[coord].values
                    end_times = start_times + np.array(
                        duration_data, dtype="timedelta64[s]"
                    )

                    event_data = [
                        {
                            var: ds[var].values[i]
                            for var in variables_with_coord
                            if var != duration_var
                        }
                        for i in range(len(start_times))
                    ]

                    event_keys = ["dive"] * len(start_times)

                    self._write_event_to_duckpond(
                        metadata=metadata,
                        start_times=start_times,
                        end_times=end_times,
                        group=coord.replace("_samples", ""),
                        event_keys=event_keys,
                        event_data=event_data,
                        file_name=file.file["name"],
                    )
                for var_name, var_data in ds[variables_with_coord].items():
                    if (
                        isinstance(var_data.values, np.ndarray)
                        and var_data.values.ndim > 1
                    ):
                        # Handle multi-variable data arrays
                        for var_index, sub_var_name in enumerate(
                            var_data.attrs.get("variables", [])
                        ):
                            print(f"Starting {sub_var_name}")
                            for start in range(0, var_data.shape[0], batch_size):
                                end = min(start + batch_size, var_data.shape[0])

                                time_coord = list(var_data.coords.keys())[0]
                                times = pa.array(
                                    ds.coords[time_coord].values[start:end],
                                    type=self._get_datetime_type(ds.coords[time_coord]),
                                )

                                group = var_data.attrs.get("group", "ungrouped")
                                class_name = var_name
                                label = sub_var_name

                                values = var_data.values[start:end, var_index]
                                self._write_data_to_duckpond(
                                    metadata=metadata,
                                    times=times,
                                    group=group,
                                    class_name=class_name,
                                    label=label.lower(),
                                    values=values,
                                    file_name=file.file.name,
                                )
                    else:
                        # Handle single-variable data arrays
                        for start in range(0, var_data.shape[0], batch_size):
                            end = min(start + batch_size, var_data.shape[0])

                            time_coord = list(var_data.coords.keys())[0]
                            times = pa.array(
                                ds.coords[time_coord].values[start:end],
                                type=self._get_datetime_type(ds.coords[time_coord]),
                            )

                            group = var_data.attrs.get("group", "ungrouped")
                            class_name = (
                                var_name
                                if "variables" in var_data.attrs
                                else "classless"
                            )
                            label = (
                                var_data.attrs["variable"]
                                if "variable" in var_data.attrs
                                else var_name
                            )

                            values = var_data.values[start:end]
                            self._write_data_to_duckpond(
                                metadata=metadata,
                                times=times,
                                group=group,
                                class_name=class_name,
                                label=label.lower(),
                                values=values,
                                file_name=file.file.name,
                            )

                pbar.update(1)

        print("Upload complete.")
