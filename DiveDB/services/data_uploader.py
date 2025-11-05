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
import time

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

    def _create_data_table(
        self,
        dataset: str,
        metadata: Dict[str, Any],
        times: pa.Array,
        group: str,
        class_name: str,
        label: str,
        values: Union[np.ndarray, List[Any]],
    ) -> pa.Table:
        """Helper function to create a PyArrow table for signal data without writing."""
        # Convert numpy array to list if needed
        if isinstance(values, np.ndarray):
            values = values.tolist()

        # Transform values using wide format
        (
            val_dbl,
            val_int,
            val_bool,
            val_str,
            data_type,
        ) = self.duck_pond._create_wide_values(values)

        # Create schema
        wide_schema = pa.schema(
            [
                pa.field("dataset", pa.string(), nullable=False),
                pa.field("animal", pa.string(), nullable=False),
                pa.field("deployment", pa.string(), nullable=False),
                pa.field("recording", pa.string(), nullable=True),
                pa.field("group", pa.string(), nullable=False),
                pa.field("class", pa.string(), nullable=False),
                pa.field("label", pa.string(), nullable=False),
                pa.field("datetime", pa.timestamp("us"), nullable=False),
                pa.field("val_dbl", pa.float64(), nullable=True),
                pa.field("val_int", pa.int64(), nullable=True),
                pa.field("val_bool", pa.bool_(), nullable=True),
                pa.field("val_str", pa.string(), nullable=True),
                pa.field("data_type", pa.string(), nullable=False),
            ]
        )

        # Create table with dictionary encoding for repeated metadata
        table = pa.table(
            [
                pa.array([dataset] * len(values)).dictionary_encode(),
                pa.array([metadata["animal"]] * len(values)).dictionary_encode(),
                pa.array(
                    [str(metadata["deployment"])] * len(values)
                ).dictionary_encode(),
                pa.array([metadata.get("recording")] * len(values)).dictionary_encode(),
                pa.array([group] * len(values)).dictionary_encode(),
                pa.array([class_name] * len(values)).dictionary_encode(),
                pa.array([label] * len(values)).dictionary_encode(),
                times,
                val_dbl,
                val_int,
                val_bool,
                val_str,
                data_type,
            ],
            schema=wide_schema,
        )

        return table

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

            self.duck_pond.write_to_iceberg(
                batch_table, "events", dataset=dataset, skip_view_refresh=True
            )

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
        # Initialize timing dictionary
        timing = {}
        upload_start = time.time()

        # Extract dataset from metadata
        if "dataset" not in metadata:
            raise ValueError("metadata must contain 'dataset' key (string)")
        dataset = metadata["dataset"]
        if not isinstance(dataset, str):
            raise TypeError("The 'dataset' value must be set (string)")

        # Set default rename_map if None
        if rename_map is None:
            rename_map = {}

        # Load dataset
        t0 = time.time()
        ds = xr.open_dataset(netcdf_file_path)
        timing["file_loading"] = time.time() - t0

        # validate netcdf file
        t0 = time.time()
        if not skip_validation:
            self.validate_netcdf(ds)
        timing["validation"] = time.time() - t0

        # Apply renaming if rename_map is provided
        t0 = time.time()
        if rename_map:
            # Convert all data variable names to lowercase
            lower_case_rename_map = {k.lower(): v for k, v in rename_map.items()}
            ds = ds.rename(
                {
                    var: lower_case_rename_map.get(var.lower(), var)
                    for var in ds.data_vars
                }
            )
        timing["renaming"] = time.time() - t0

        # Calculate total work units for progress bar
        sample_coords = [
            coord
            for coord in ds.coords
            if "_sample" in coord.lower() and "event_data" not in coord.lower()
        ]

        # Count total variables to process
        total_vars = 0
        for coord in sample_coords:
            variables_with_coord = [
                var for var in ds.data_vars if coord in ds[var].dims
            ]
            for var_name in variables_with_coord:
                var_data = ds[var_name]
                if isinstance(var_data.values, np.ndarray) and var_data.values.ndim > 1:
                    # Multi-variable data arrays
                    total_vars += len(var_data.attrs.get("variables", []))
                else:
                    # Single-variable data arrays
                    total_vars += 1

        # Add 1 for event processing if events exist
        event_data_vars = [var for var in ds.data_vars if var.startswith("event_data")]
        has_events = bool(event_data_vars)
        if has_events:
            total_vars += 1

        print(
            f"Processing {len(sample_coords)} coordinate(s) with {total_vars} total variable(s) in the netCDF file."
        )

        # Process event data variables
        t0 = time.time()
        if event_data_vars:
            duration_var = next(
                (var for var in event_data_vars if "duration" in var.lower()), None
            )
            if duration_var:
                # Get event type information from the netCDF coordinate
                event_types = ds["event_data_type"].values
                duration_data = ds[duration_var].values
                duration_array = np.array(duration_data, dtype="timedelta64[s]")

                # Get start times as numpy array (timezone-naive, represents UTC)
                start_times_np = ds.coords["event_data_samples"].values
                end_times_np = start_times_np.copy()

                # Differentiate between point and state events using explicit event_data_type
                # Point events: end_times = start_times
                # State events: end_times = start_times + duration
                is_state_event = event_types == "state"
                end_times_np[is_state_event] = (
                    start_times_np[is_state_event] + duration_array[is_state_event]
                )

                # Convert to PyArrow arrays with explicit UTC timezone
                start_times = pa.array(
                    start_times_np,
                    type=self._get_datetime_type(ds.coords["event_data_samples"]),
                )
                end_times = pa.array(
                    end_times_np,
                    type=self._get_datetime_type(ds.coords["event_data_samples"]),
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
        timing["event_processing"] = time.time() - t0

        # Pre-compute time coordinates (optimization)
        t0 = time.time()
        time_coord_arrays = {}
        for coord in sample_coords:
            time_coord_arrays[coord] = pa.array(
                ds.coords[coord].values,
                type=self._get_datetime_type(ds.coords[coord]),
            )
        timing["time_coord_precompute"] = time.time() - t0

        # Process other data variables with enhanced progress tracking
        t0 = time.time()

        with tqdm(total=total_vars, desc="Processing variables") as pbar:
            # Update progress for events if they were processed
            if has_events:
                pbar.update(1)

            for coord in sample_coords:
                variables_with_coord = set(
                    var for var in ds.data_vars if coord in ds[var].dims
                )

                # Upload data with batched writes per variable
                for var_name, var_data in ds[variables_with_coord].items():
                    if (
                        isinstance(var_data.values, np.ndarray)
                        and var_data.values.ndim > 1
                    ):
                        # Handle multi-variable data arrays
                        for var_index, sub_var_name in enumerate(
                            var_data.attrs.get("variables", [])
                        ):
                            # Collect all batches for this variable
                            tables_to_write = []

                            for start in range(0, var_data.shape[0], batch_size):
                                end = min(start + batch_size, var_data.shape[0])

                                time_coord = list(var_data.coords.keys())[0]
                                # Slice from pre-computed time array
                                times = time_coord_arrays[time_coord][start:end]

                                group = var_data.attrs.get("group", None)
                                class_name = var_name
                                label = rename_map.get(
                                    sub_var_name.lower(), sub_var_name
                                )

                                values = var_data.values[start:end, var_index]

                                # Create table but don't write yet
                                table = self._create_data_table(
                                    dataset=dataset,
                                    metadata=metadata,
                                    times=times,
                                    group=group,
                                    class_name=class_name,
                                    label=label.lower(),
                                    values=values,
                                )
                                tables_to_write.append(table)

                            # Write all batches for this variable at once
                            if tables_to_write:
                                combined_table = pa.concat_tables(tables_to_write)
                                self.duck_pond.write_to_iceberg(
                                    combined_table,
                                    "data",
                                    dataset=dataset,
                                    skip_view_refresh=True,
                                )
                                gc.collect()

                            pbar.update(1)
                    else:
                        # Handle single-variable data arrays
                        tables_to_write = []

                        for start in range(0, var_data.shape[0], batch_size):
                            end = min(start + batch_size, var_data.shape[0])

                            time_coord = list(var_data.coords.keys())[0]
                            # Slice from pre-computed time array
                            times = time_coord_arrays[time_coord][start:end]

                            group = var_data.attrs.get("group", None)
                            class_name = (
                                var_name
                                if "variables" in var_data.attrs
                                else "classless"
                            )
                            label = (
                                var_data.attrs["variable"]
                                if "variable" in var_data.attrs
                                else (
                                    var_data.attrs["variables"]
                                    if "variables" in var_data.attrs
                                    else var_name
                                )
                            )
                            label = rename_map.get(label.lower(), label)

                            values = var_data.values[start:end]

                            # Create table but don't write yet
                            table = self._create_data_table(
                                dataset=dataset,
                                metadata=metadata,
                                times=times,
                                group=group,
                                class_name=class_name,
                                label=label.lower(),
                                values=values,
                            )
                            tables_to_write.append(table)

                        # Write all batches for this variable at once
                        if tables_to_write:
                            combined_table = pa.concat_tables(tables_to_write)
                            self.duck_pond.write_to_iceberg(
                                combined_table,
                                "data",
                                dataset=dataset,
                                skip_view_refresh=True,
                            )
                            gc.collect()

                        pbar.update(1)

        timing["variable_processing"] = time.time() - t0

        # Refresh views once at the end
        t0 = time.time()
        self.duck_pond.dataset_manager._create_dataset_views(dataset)
        timing["view_refresh"] = time.time() - t0

        # Calculate total time
        timing["total"] = time.time() - upload_start

        # Print timing summary
        print("\n" + "=" * 60)
        print("Upload Performance Summary")
        print("=" * 60)
        print(f"{'Step':<30} {'Time (s)':<15} {'% of Total':<15}")
        print("-" * 60)
        for step, duration in timing.items():
            if step != "total":
                percentage = (duration / timing["total"]) * 100
                print(f"{step:<30} {duration:>10.2f}     {percentage:>10.1f}%")
        print("-" * 60)
        print(f"{'TOTAL':<30} {timing['total']:>10.2f}     {100.0:>10.1f}%")
        print("=" * 60)
        print("\nUpload complete.")
