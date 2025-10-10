"""
Data Uploader
"""

from typing import Dict, List, Optional, Union, Any

import numpy as np
import gc
import pyarrow as pa
from tqdm import tqdm
import xarray as xr
import json
import math

from DiveDB.services.duck_pond import DuckPond


class NetCDFValidationError(Exception):
    """Custom exception for NetCDF validation errors."""

    pass


class DataUploader:
    """Data Uploader"""

    def __init__(
        self,
        duck_pond: Optional[DuckPond] = None,
    ) -> None:
        """
        Initialize DataUploader with optional DuckPond instance and Notion configuration.

        Args:
            duck_pond: DuckPond instance for Iceberg data storage
            notion_manager: NotionORMManager instance for database operations
            notion_config: Dictionary with 'db_map' and 'token' keys for Notion ORM (ignored if notion_manager is provided)
        """
        self.duck_pond = duck_pond or DuckPond.from_environment()

    def _get_datetime_type(self, time_data_array: xr.DataArray) -> pa.DataType:
        """Function to get the datetime type from a PyArrow array."""
        time_dtype = time_data_array.dtype
        if time_dtype == "datetime64[ns]":
            return pa.timestamp("ns", tz="UTC")
        elif time_dtype == "datetime64[us]":
            return pa.timestamp("us", tz="UTC")
        else:
            raise ValueError(f"Unsupported time dtype: {time_dtype}")

    # Convert ds.attrs to a JSON-serializable dictionary
    def _make_json_serializable(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
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

    def _write_data_to_duck_pond(
        self,
        dataset: str,
        metadata: Dict[str, Any],
        times: pa.Array,
        group: str,
        class_name: str,
        label: str,
        values: Union[np.ndarray, List[Any]],
    ) -> None:
        """Helper function to write signal data to DuckPond (Iceberg)."""
        # Convert numpy array to list if needed (DuckPond expects mixed-type lists)
        if isinstance(values, np.ndarray):
            values = values.tolist()

        self.duck_pond.write_signal_data(
            dataset=dataset,
            metadata=metadata,
            times=times,
            group=group,
            class_name=class_name,
            label=label,
            values=values,
        )

        # Clean up memory
        gc.collect()

    def _write_events_to_duck_pond(
        self,
        dataset: str,
        metadata: Dict[str, Any],
        start_times: pa.Array,
        end_times: pa.Array,
        group: Optional[str] = None,
        event_keys: Optional[List[str]] = None,
        event_data: Optional[List[Dict[str, Any]]] = None,
        short_descriptions: Optional[List[str]] = None,
        long_descriptions: Optional[List[str]] = None,
    ) -> None:
        """Helper function to write event data to DuckPond (Iceberg)."""
        if short_descriptions is None:
            short_descriptions = [None] * len(event_keys)
        if long_descriptions is None:
            long_descriptions = [None] * len(event_keys)

        # Collect all events in a single list
        events = []
        for i in range(len(event_keys)):
            # For point events, end_time equals start_time
            # For state events, end_time is different from start_time
            event = {
                "dataset": dataset,
                "animal": metadata["animal"],
                "deployment": str(metadata["deployment"]),
                "recording": metadata.get("recording"),  # Optional field
                "group": group,
                "event_key": event_keys[i],
                "datetime_start": start_times[i],
                "datetime_end": end_times[i],
                "short_description": short_descriptions[i],
                "long_description": long_descriptions[i],
                "event_data": json.dumps(event_data[i]),
            }
            events.append(event)

        # Write all events using single schema and table
        if events:
            # Create unified schema for all events (matching DuckPond events schema)
            events_schema = pa.schema(
                [
                    pa.field("dataset", pa.string(), nullable=False),
                    pa.field("animal", pa.string(), nullable=False),
                    pa.field("deployment", pa.string(), nullable=False),
                    pa.field("recording", pa.string(), nullable=True),
                    pa.field("group", pa.string(), nullable=False),
                    pa.field("event_key", pa.string(), nullable=False),
                    pa.field("datetime_start", pa.timestamp("us"), nullable=False),
                    pa.field("datetime_end", pa.timestamp("us"), nullable=False),
                    pa.field("short_description", pa.string(), nullable=True),
                    pa.field("long_description", pa.string(), nullable=True),
                    pa.field("event_data", pa.string(), nullable=False),
                ]
            )

            batch_table = pa.table(
                [
                    pa.array([e["dataset"] for e in events]),
                    pa.array([e["animal"] for e in events]),
                    pa.array([e["deployment"] for e in events]),
                    pa.array([e["recording"] for e in events]),
                    pa.array([e["group"] for e in events]),
                    pa.array([e["event_key"] for e in events]),
                    pa.array([e["datetime_start"] for e in events]),
                    pa.array([e["datetime_end"] for e in events]),
                    pa.array([e["short_description"] for e in events]),
                    pa.array([e["long_description"] for e in events]),
                    pa.array([e["event_data"] for e in events]),
                ],
                schema=events_schema,
            )

            self.duck_pond.write_to_iceberg(batch_table, "events", dataset=dataset)

        gc.collect()

    def validate_netcdf(self, ds: xr.Dataset) -> bool:
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
            if not np.issubdtype(ds[dim].dtype, np.datetime64):
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
                if "variable" not in var.attrs and "variables" not in var.attrs:
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

    def _get_model_by_id(
        self, model_name: str, model_id: str, id_field: str = "id"
    ) -> Any:
        """
        Generic method to get a model by ID from Notion database.

        Args:
            model_name: Name of the model to get
            model_id: ID value to search for
            id_field: Field name to search by (default: "id")

        Returns: Model instance

        Raises: ValueError: If notion_manager is not configured or model not found
        """
        if not self.duck_pond.notion_manager:
            raise ValueError("Notion configuration required for database operations")

        Model = self.duck_pond.notion_manager.get_model(model_name)
        filter_kwargs = {id_field: model_id}
        instance = Model.objects.filter(**filter_kwargs).first()

        if not instance:
            raise ValueError(f"{model_name} with {id_field}='{model_id}' not found")

        return instance

    def get_logger(self, logger_data: Dict[str, Any]) -> Any:
        """
        Get logger from Notion database.

        Args: logger_data: Dict with logger information including 'logger_id'
        Returns: Logger instance
        Raises: ValueError: If logger not found
        """
        return self._get_model_by_id("Logger", logger_data["logger_id"])

    def get_recording(self, recording_data: Dict[str, Any]) -> Any:
        """
        Get recording from Notion database.

        Args: recording_data: Dict with recording information including 'recording_id'
        Returns: Recording instance
        Raises: ValueError: If recording not found
        """
        return self._get_model_by_id("Recording", recording_data["recording_id"])

    def get_deployment(self, deployment_data: Dict[str, Any]) -> Any:
        """
        Get deployment from Notion database.

        Args: deployment_data: Dict with deployment information including 'deployment_id'
        Returns: Deployment instance
        Raises: ValueError: If deployment not found
        """
        return self._get_model_by_id("Deployment", deployment_data["deployment_id"])

    def get_animal(self, animal_data: Dict[str, Any]) -> Any:
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
        metadata: Dict[str, Any],
        batch_size: int = 5_000_000,
        rename_map: Optional[Dict[str, str]] = None,
        skip_validation: bool = False,
    ) -> None:
        """
        Uploads a netCDF file to the database and Ice Pond (Iceberg).

        Parameters:
        netcdf_file_path (str): Path to the netCDF file.
        metadata (Dict[str, Any]): Metadata dictionary.
            Required keys:
                - dataset: Dataset identifier (str)
                - animal: Animal ID (int)
                - deployment: Deployment Name (str)
            Optional key:
                - recording: Recording Name (str)
        batch_size (int, optional): Size of data batches for processing. Defaults to 5 million which is safe for an 8GB RAM machine.
        rename_map (Optional[Dict[str, str]], optional): A dictionary mapping original variable names to new names.
        skip_validation (bool, optional): Skip validation of the netCDF file. Defaults to False.
        """

        # Extract dataset from metadata
        if "dataset" not in metadata:
            raise ValueError("metadata must contain 'dataset' key (string)")
        dataset = metadata["dataset"]
        if not isinstance(dataset, str):
            raise TypeError("The 'dataset' value must be set (string)")

        # Set default rename_map if None
        if rename_map is None:
            rename_map = {}

        ds = xr.open_dataset(netcdf_file_path)

        # validate netcdf file
        if not skip_validation:
            self.validate_netcdf(ds)

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

                # TODO: Update to diffentiate between point and state events
                # If point events, end_times = start_times
                # If state events, end_times = start_times + duration
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

                self._write_events_to_duck_pond(
                    dataset=dataset,
                    metadata=metadata,
                    start_times=start_times,
                    end_times=end_times,
                    group="events",
                    event_keys=event_keys,
                    event_data=event_data,
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

                                group = var_data.attrs.get("group", None)
                                class_name = var_name
                                label = rename_map.get(
                                    sub_var_name.lower(), sub_var_name
                                )

                                values = var_data.values[start:end, var_index]
                                self._write_data_to_duck_pond(
                                    dataset=dataset,
                                    metadata=metadata,
                                    times=times,
                                    group=group,
                                    class_name=class_name,
                                    label=label.lower(),
                                    values=values,
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

                            group = var_data.attrs.get("group", None)
                            class_name = (
                                var_name
                                if "variables" in var_data.attrs
                                else "classless"
                            )
                            label = (
                                var_data.attrs["variable"]
                                if "variable" in var_data.attrs
                                else var_data.attrs["variables"]
                                if "variables" in var_data.attrs
                                else var_name
                            )
                            label = rename_map.get(label.lower(), label)

                            values = var_data.values[start:end]
                            self._write_data_to_duck_pond(
                                dataset=dataset,
                                metadata=metadata,
                                times=times,
                                group=group,
                                class_name=class_name,
                                label=label.lower(),
                                values=values,
                            )

                pbar.update(1)

        print("Upload complete.")
