"""
Data Uploader
"""

import os

import numpy as np
import gc
import pyarrow as pa
from tqdm import tqdm
import xarray as xr
import json
import math

from DiveDB.services.duck_pond import DuckPond
from DiveDB.services.notion_orm import NotionORMManager


class NetCDFValidationError(Exception):
    """Custom exception for NetCDF validation errors."""

    pass


class DataUploader:
    """Data Uploader"""

    def __init__(
        self,
        duckpond: DuckPond = None,
        notion_manager: NotionORMManager = None,
        notion_config: dict = None,
    ):
        """
        Initialize DataUploader with optional DuckPond instance and Notion configuration.

        Args:
            duckpond: DuckPond instance for data storage
            notion_manager: NotionORMManager instance for database operations
            notion_config: Dictionary with 'db_map' and 'token' keys for Notion ORM (ignored if notion_manager is provided)
        """
        self.duckpond = duckpond or DuckPond(os.environ["CONTAINER_DELTA_LAKE_PATH"])

        if notion_manager:
            self.notion_manager = notion_manager
        elif notion_config:
            self.notion_manager = NotionORMManager(
                db_map=notion_config["db_map"], token=notion_config["token"]
            )
        else:
            self.notion_manager = None

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

        # Check if the data type is integer
        if np.issubdtype(numeric_values.dtype, np.integer):
            float_values = None
            int_values = np.where(
                np.isfinite(numeric_values), numeric_values.astype(int), None
            )
        else:
            float_values = np.where(np.isfinite(numeric_values), numeric_values, None)
            int_values = None

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
                    [str(metadata["deployment"])] * len(values),
                    type=pa.string(),
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
            schema=self.duckpond.LAKE_CONFIGS["DATA"]["schema"],
        )
        self.duckpond.write_to_delta(
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

    def _write_events_to_duckpond(
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

        # Determine if events are point or state based on duration
        is_point_event = (end_times - start_times) == np.timedelta64(0, "s")

        # Collect point and state events separately
        point_events = []
        state_events = []

        for i, is_point in enumerate(is_point_event):
            event = {
                "animal": metadata["animal"],
                "deployment": str(metadata["deployment"]),
                "recording": metadata["recording"],
                "group": group,
                "event_key": event_keys[i],
                "event_data": json.dumps(event_data[i]),
                "short_description": short_descriptions[i],
                "long_description": long_descriptions[i],
            }
            if is_point:
                event["datetime"] = start_times[i]
                point_events.append(event)
            else:
                event["datetime_start"] = start_times[i]
                event["datetime_end"] = end_times[i]
                state_events.append(event)

        # Write point events
        if point_events:
            batch_table = pa.table(
                {
                    "animal": pa.array(
                        [e["animal"] for e in point_events], type=pa.string()
                    ),
                    "deployment": pa.array(
                        [e["deployment"] for e in point_events], type=pa.string()
                    ),
                    "recording": pa.array(
                        [e["recording"] for e in point_events], type=pa.string()
                    ),
                    "group": pa.array(
                        [e["group"] for e in point_events], type=pa.string()
                    ),
                    "event_key": pa.array(
                        [e["event_key"] for e in point_events], type=pa.string()
                    ),
                    "datetime": pa.array([e["datetime"] for e in point_events]),
                    "event_data": pa.array(
                        [e["event_data"] for e in point_events], type=pa.string()
                    ),
                    "short_description": pa.array(
                        [e["short_description"] for e in point_events], type=pa.string()
                    ),
                    "long_description": pa.array(
                        [e["long_description"] for e in point_events], type=pa.string()
                    ),
                },
                schema=self.duckpond.LAKE_CONFIGS["POINT_EVENTS"]["schema"],
            )
            self.duckpond.write_to_delta(
                data=batch_table,
                lake="POINT_EVENTS",
                mode="append",
                partition_by=[
                    "animal",
                    "deployment",
                    "recording",
                    "group",
                    "event_key",
                ],
                name=file_name,
                description="test",
            )

        # Write state events
        if state_events:
            batch_table = pa.table(
                {
                    "animal": pa.array(
                        [e["animal"] for e in state_events], type=pa.string()
                    ),
                    "deployment": pa.array(
                        [e["deployment"] for e in state_events], type=pa.string()
                    ),
                    "recording": pa.array(
                        [e["recording"] for e in state_events], type=pa.string()
                    ),
                    "group": pa.array(
                        [e["group"] for e in state_events], type=pa.string()
                    ),
                    "event_key": pa.array(
                        [e["event_key"] for e in state_events], type=pa.string()
                    ),
                    "datetime_start": pa.array(
                        [e["datetime_start"] for e in state_events]
                    ),
                    "datetime_end": pa.array([e["datetime_end"] for e in state_events]),
                    "event_data": pa.array(
                        [e["event_data"] for e in state_events], type=pa.string()
                    ),
                    "short_description": pa.array(
                        [e["short_description"] for e in state_events], type=pa.string()
                    ),
                    "long_description": pa.array(
                        [e["long_description"] for e in state_events], type=pa.string()
                    ),
                },
                schema=self.duckpond.LAKE_CONFIGS["STATE_EVENTS"]["schema"],
            )
            self.duckpond.write_to_delta(
                data=batch_table,
                lake="STATE_EVENTS",
                mode="append",
                partition_by=[
                    "animal",
                    "deployment",
                    "recording",
                    "group",
                    "event_key",
                ],
                name=file_name,
                description="test",
            )

        gc.collect()

    def validate_netcdf(self, ds: xr.Dataset):
        """
        Validates netCDF file before upload.

        Dimensions:
            - Sampling: Must have suffix "_samples". Array of datetime64.
            - Labeling: Must have suffix "_variables". Array of str.

        Data variables:
            - Must be associated with sampling dim, and maybe labeling dim.
            - If flat array (ndim=1), should have attribute "variable" with str.
            - If nested list (ndim=2), should have attribute "variables" with list of str.

        Args:
            ds (xr.Dataset): A formatted (no groups) netCDF dataset.

        Raises:
            NetCDFValidationError: Generic exception for validation errors. Provides details in msg.


        Returns:
            bool: True if dataset passes all checks.
        """
        required_dimensions_suffix = ["_samples", "_variables"]

        if not ds.dims:
            raise NetCDFValidationError(
                "Dataset does not have any dimensions. This may be due to formatting issues."
            )

        if not ds.data_vars:
            raise NetCDFValidationError(
                "Dataset does not have any data variables. This may be due to formatting issues."
            )

        for dim in ds.dims:
            if not any(dim.endswith(suffix) for suffix in required_dimensions_suffix):
                raise NetCDFValidationError(
                    f"Dimension '{dim}' does not match the required suffixes: {required_dimensions_suffix}."
                )

        sample_dimensions = [dim for dim in ds.dims if dim.endswith("_samples")]
        for dim in sample_dimensions:
            if not np.isdtype(ds[dim].dtype, np.datetime64):
                raise NetCDFValidationError(
                    f"Dimension '{dim}' must contain datetime64 values."
                )

        label_dimensions = [dim for dim in ds.dims if dim.endswith("_variables")]
        for dim in label_dimensions:
            if not np.issubdtype(ds[dim].dtype, np.str_):
                raise NetCDFValidationError(
                    f"Dimension '{dim}' must contain string values."
                )

        for var_name, var in ds.data_vars.items():
            if var.ndim == 1:
                if var.dims[0] not in sample_dimensions:
                    raise NetCDFValidationError(
                        f"1D Variable '{var_name}' must have a dimension in '{sample_dimensions}', found '{var.dims[0]}'."
                    )
                if "variable" not in var.attrs:
                    found = list(var.attrs.keys())
                    raise NetCDFValidationError(
                        f"Variable '{var_name}' must have a 'variable' attribute for flat arrays. Found '{found}'."
                    )

            elif var.ndim > 1:
                dim_set = set(var.dims)
                # not sure if order will always be sample, label in dims
                if not (
                    dim_set & set(sample_dimensions) and dim_set & set(label_dimensions)
                ):
                    raise NetCDFValidationError(
                        f"2D Variable '{var_name}' must have one dimension in '{sample_dimensions}' and the other in '{label_dimensions}'. "
                        f"Found dimensions: {var.dims}."
                    )
                if "variables" not in var.attrs:
                    found = list(var.attrs.keys())
                    raise NetCDFValidationError(
                        f"Variable '{var_name}' must have a 'variables' attribute for nested arrays. Found '{found}'"
                    )

            else:
                raise NetCDFValidationError(
                    f"Variable '{var_name}' has an unsupported number of dimensions: {var.ndim}"
                )
        return True

    def _get_model_by_id(self, model_name: str, model_id: str, id_field: str = "id"):
        """
        Generic method to get a model by ID from Notion database.

        Args:
            model_name: Name of the model to get
            model_id: ID value to search for
            id_field: Field name to search by (default: "id")

        Returns: Model instance

        Raises: ValueError: If notion_manager is not configured or model not found
        """
        if not self.notion_manager:
            raise ValueError("Notion configuration required for database operations")

        Model = self.notion_manager.get_model(model_name)
        filter_kwargs = {id_field: model_id}
        instance = Model.objects.filter(**filter_kwargs).first()

        if not instance:
            raise ValueError(f"{model_name} with {id_field}='{model_id}' not found")

        return instance

    def get_logger(self, logger_data):
        """
        Get logger from Notion database.

        Args: logger_data: Dict with logger information including 'logger_id'
        Returns: Logger instance
        Raises: ValueError: If logger not found
        """
        return self._get_model_by_id("Logger", logger_data["logger_id"])

    def get_recording(self, recording_data):
        """
        Get recording from Notion database.

        Args: recording_data: Dict with recording information including 'recording_id'
        Returns: Recording instance
        Raises: ValueError: If recording not found
        """
        return self._get_model_by_id("Recording", recording_data["recording_id"])

    def get_deployment(self, deployment_data):
        """
        Get deployment from Notion database.

        Args: deployment_data: Dict with deployment information including 'deployment_id'
        Returns: Deployment instance
        Raises: ValueError: If deployment not found
        """
        return self._get_model_by_id("Deployment", deployment_data["deployment_id"])

    def get_animal(self, animal_data):
        """
        Get animal from Notion database.

        Args: animal_data: Dict with animal information including 'animal_id'
        Returns: Animal instance
        Raises: ValueError: If animal not found
        """
        return self._get_model_by_id("Animal", animal_data["animal_id"])

    def upload_netcdf(
        self,
        netcdf_file_path: str,
        metadata: dict,
        batch_size: int = 1000000,
        rename_map: dict = {},
        skip_validation: bool = False,
    ):
        """
        Uploads a netCDF file to the database and DuckPond.

        Parameters:
        netcdf_file_path (str): Path to the netCDF file.
        metadata (dict): Metadata dictionary.
            Required keys:
                - animal: Animal ID (int)
                - deployment: Deployment Name (str)
            Optional key:
                - recording: Recording Name (str)
        batch_size (int, optional): Size of data batches for processing. Defaults to 1 million
        rename_map (dict, optional): A dictionary mapping original variable names to new names.
        skip_validation (bool, optional): Skip validation of the netCDF file. Defaults to False.
        """

        ds = xr.open_dataset(netcdf_file_path)

        # Apply renaming if rename_map is provided
        if rename_map:
            # Convert all data variable names to lowercase
            lower_case_rename_map = {k.lower(): v for k, v in rename_map.items()}
            ds = ds.rename(
                {
                    var: lower_case_rename_map.get(var.lower(), var)
                    for var in ds.data_vars
                }
            )

        # Process event data variables
        event_data_vars = [var for var in ds.data_vars if var.startswith("event_data")]
        if event_data_vars:
            duration_var = next(
                (var for var in event_data_vars if "duration" in var.lower()), None
            )
            if duration_var:
                duration_data = ds[duration_var].values
                start_times = ds["event_data_value"].values
                # Convert start_times to datetime64 if it's not already
                start_times = pa.array(
                    ds.coords["event_data_samples"].values,
                    type=self._get_datetime_type(ds.coords["event_data_samples"]),
                )

                end_times = start_times + np.array(
                    duration_data, dtype="timedelta64[s]"
                )

                event_keys = ds["event_data_key"].values

                event_data = [
                    {
                        var: ds[var].values[i]
                        for var in event_data_vars
                        if var != duration_var
                    }
                    for i in range(len(start_times))
                ]

                self._write_events_to_duckpond(
                    metadata=metadata,
                    start_times=start_times,
                    end_times=end_times,
                    group="events",
                    event_keys=event_keys,
                    event_data=event_data,
                    file_name=netcdf_file_path,
                )

        # Process other data variables
        sample_coords = [
            coord
            for coord in ds.coords
            if "_sample" in coord.lower() and "event_data" not in coord.lower()
        ]
        print(f"Processing {sample_coords} datasets in the netCDF file.")

        with tqdm(total=len(sample_coords), desc="Processing variables") as pbar:
            for coord in sample_coords:
                variables_with_coord = set(
                    var for var in ds.data_vars if coord in ds[var].dims
                )

                # Upload data
                for var_name, var_data in ds[variables_with_coord].items():
                    if (
                        isinstance(var_data.values, np.ndarray)
                        and var_data.values.ndim > 1
                    ):
                        # Handle multi-variable data arrays
                        for var_index, sub_var_name in enumerate(
                            var_data.attrs.get("variables", [])
                        ):
                            for start in range(0, var_data.shape[0], batch_size):
                                end = min(start + batch_size, var_data.shape[0])

                                time_coord = list(var_data.coords.keys())[0]
                                times = pa.array(
                                    ds.coords[time_coord].values[start:end],
                                    type=self._get_datetime_type(ds.coords[time_coord]),
                                )

                                group = var_data.attrs.get("group", "ungrouped")
                                class_name = var_name
                                label = rename_map.get(
                                    sub_var_name.lower(), sub_var_name
                                )

                                values = var_data.values[start:end, var_index]
                                self._write_data_to_duckpond(
                                    metadata=metadata,
                                    times=times,
                                    group=group,
                                    class_name=class_name,
                                    label=label.lower(),
                                    values=values,
                                    file_name=netcdf_file_path,
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
                            label = rename_map.get(label.lower(), label)

                            values = var_data.values[start:end]
                            self._write_data_to_duckpond(
                                metadata=metadata,
                                times=times,
                                group=group,
                                class_name=class_name,
                                label=label.lower(),
                                values=values,
                                file_name=netcdf_file_path,
                            )

                pbar.update(1)

        print("Upload complete.")
