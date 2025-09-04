"""
DuckPond - Apache Iceberg data lake interface (formerly Delta Lake)
"""

import logging
from typing import List, Literal, Dict, Optional

import numpy as np
import pandas as pd
import pyarrow as pa
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import IdentityTransform

from DiveDB.services.notion_orm import NotionORMManager
from DiveDB.services.dive_data import DiveData
from DiveDB.services.utils.sampling import resample
from DiveDB.services.connection.warehouse_config import WarehouseConfig
from DiveDB.services.connection.catalog_manager import CatalogManager
from DiveDB.services.connection.duckdb_connection import DuckDBConnection
from DiveDB.services.connection.notion_integration import NotionIntegration
from DiveDB.services.connection.dataset_manager import DatasetManager


class DuckPond:
    """DuckPond - Iceberg-managed data lake with direct Parquet access for optimal query performance"""

    def __init__(
        self,
        warehouse_path: str = None,
        notion_manager: Optional[NotionORMManager] = None,
        notion_db_map: Optional[Dict[str, str]] = None,
        notion_token: Optional[str] = None,
        # S3 configuration for Ceph/S3 backend
        s3_endpoint: Optional[str] = None,
        s3_access_key: Optional[str] = None,
        s3_secret_key: Optional[str] = None,
        s3_bucket: Optional[str] = None,
        s3_region: Optional[str] = "us-east-1",  # Default region
        # Dataset-specific initialization
        datasets: Optional[List[str]] = None,  # List of dataset IDs to initialize
        # Notion load parallelism
        notion_parallelism: int = 8,
    ):
        # Create configuration
        self.config = WarehouseConfig.from_parameters(
            warehouse_path=warehouse_path,
            s3_endpoint=s3_endpoint,
            s3_access_key=s3_access_key,
            s3_secret_key=s3_secret_key,
            s3_bucket=s3_bucket,
            s3_region=s3_region,
        )

        # Create catalog manager
        self.catalog_manager = CatalogManager(self.config)
        self.catalog = self.catalog_manager.catalog

        # Create DuckDB connection manager
        self.connection = DuckDBConnection(self.config)
        self.conn = self.connection.conn

        # Legacy properties for backward compatibility
        self.use_s3 = self.config.use_s3
        self.warehouse_path = self.config.warehouse_path
        if self.config.use_s3:
            self.s3_endpoint = self.config.s3_endpoint
            self.s3_access_key = self.config.s3_access_key
            self.s3_secret_key = self.config.s3_secret_key
            self.s3_bucket = self.config.s3_bucket
            self.s3_region = self.config.s3_region

        # Initialize Notion ORM manager
        if notion_manager:
            self.notion_manager = notion_manager
        elif notion_db_map and notion_token:
            self.notion_manager = NotionORMManager(notion_db_map, notion_token)
        else:
            self.notion_manager = None

        # Initialize Notion integration
        self.notion_integration = NotionIntegration(
            notion_manager=self.notion_manager,
            duckdb_connection=self.connection,
            parallelism=notion_parallelism,
        )

        # Initialize dataset manager
        self.dataset_manager = DatasetManager(
            config=self.config,
            catalog_manager=self.catalog_manager,
            duckdb_connection=self.connection,
        )

        # Legacy properties for backward compatibility
        self.initialized_datasets = self.dataset_manager.initialized_datasets
        self.lakes = self.dataset_manager.lakes
        self.LAKE_SCHEMAS = self.dataset_manager.LAKE_SCHEMAS

        # In-memory discovery cache: { dataset: { 'triples': List[tuple(group,class,label)], 'groups': set[str] } }
        self._channel_discovery_cache = {}

        # Initialize datasets if provided, otherwise discover existing ones
        self.dataset_manager.initialize_datasets(datasets)

    # ------------------------------
    # Channel discovery and metadata
    # ------------------------------

    def _discover_dataset_channels(self, dataset: str):
        """
        Discover distinct (group, class, label) present in the dataset's Data view and cache in-memory.
        Returns a tuple of (triples, groups_set). triples is List[tuple(group, class, label)].
        """
        self.dataset_manager.ensure_dataset_initialized(dataset)

        cached = self._channel_discovery_cache.get(dataset)
        if cached:
            return cached["triples"], cached["groups"]

        view_name = self.get_view_name(dataset, "data")

        query_vars = f"""
            SELECT "group", class, label
            FROM {view_name}
            WHERE label IS NOT NULL
            GROUP BY 1,2,3
            ORDER BY 1,2,3
        """
        query_groups = f"""
            SELECT "group"
            FROM {view_name}
            WHERE "group" IS NOT NULL
            GROUP BY 1
            ORDER BY 1
        """

        triples = [(r[0], r[1], r[2]) for r in self.conn.sql(query_vars).fetchall()]
        groups = set(r[0] for r in self.conn.sql(query_groups).fetchall())

        self._channel_discovery_cache[dataset] = {"triples": triples, "groups": groups}
        return triples, groups

    def get_available_channels(
        self,
        dataset: str,
        include_metadata: bool = True,
        pack_groups: bool = True,
    ) -> List[Dict]:
        """
        Discover available channels for a dataset and optionally hydrate metadata from Signal DB.

        Args:
            dataset: Dataset identifier
            include_metadata: If True, join metadata from Signal DB via Standardized Channel DB lookup
            include: Which kinds to return: variables, groups, or both
            pack_groups: If True, groups are returned as one collection with all standardized children

        Returns:
            List[Dict] of channels/groups as specified
        """

        triples, present_groups = self._discover_dataset_channels(dataset)

        # Prepare lookup mappings
        channel_id_to_signal_id: Dict[str, str] = {}
        original_alias_to_channel_id: Dict[str, str] = {}
        signal_metadata_map: Dict[str, Dict] = {}

        if include_metadata and self.notion_manager:
            (
                channel_id_to_signal_id,
                original_alias_to_channel_id,
                signal_metadata_map,
            ) = self.notion_integration.get_metadata_mappings()

        # Build a presence map for labels per group for quick lookup
        group_to_labels_present: Dict[str, set] = {}
        for g, c, label in triples:
            if g is None:
                continue
            group_to_labels_present.setdefault(g, set()).add(str(label))

        results: List[Dict] = []

        # Variables view
        for g, c, label in triples:
            label_norm = (str(label) or "").strip()

            # Look up Signal DB ID for this channel
            signal_id = None
            chan_key = label_norm.lower()

            # Try direct channel_id lookup first
            if chan_key in channel_id_to_signal_id:
                signal_id = channel_id_to_signal_id[chan_key]
            # Try alias lookup
            elif chan_key in original_alias_to_channel_id:
                mapped_channel_id = original_alias_to_channel_id[chan_key]
                signal_id = channel_id_to_signal_id.get(mapped_channel_id.lower())

            # Get metadata from Signal DB if signal ID found
            signal_meta = None
            if signal_id:
                signal_meta = signal_metadata_map.get(signal_id)

            # Build item with metadata from Signal DB (no fallbacks)
            item = {
                "kind": "variable",
                "group": g,
                "class": c,
                "label": label_norm,
                "channel_id": label_norm,  # Use the label as channel_id
                "parent_signal": signal_meta.get("name") if signal_meta else None,
                "y_label": signal_meta.get("label") if signal_meta else None,
                "y_description": (
                    signal_meta.get("description") if signal_meta else None
                ),
                "y_units": (
                    signal_meta.get("standardized_unit") if signal_meta else None
                ),
                "line_label": signal_meta.get("label") if signal_meta else None,
                "color": signal_meta.get("color") if signal_meta else None,
                "icon": signal_meta.get("icon") if signal_meta else None,
            }
            results.append(item)

        # Group collections
        for group_name in sorted(present_groups):
            if not pack_groups:
                # Return a simple group stub without packing
                results.append(
                    {
                        "kind": "group",
                        "group": group_name,
                    }
                )
                continue

            # Try to get metadata for this group from Signal DB (by name lookup)
            group_meta = None
            # Find Signal DB record with matching name
            for signal_id, metadata in signal_metadata_map.items():
                if metadata.get("name", "").lower() == group_name.lower():
                    group_meta = metadata
                    break

            channels_payload: List[Dict] = []
            # Include labels present in dataset for this group
            for lbl in sorted(group_to_labels_present.get(group_name, set())):
                # Look up Signal DB ID for this specific channel
                lbl_key = lbl.lower()
                channel_signal_id = None
                if lbl_key in channel_id_to_signal_id:
                    channel_signal_id = channel_id_to_signal_id[lbl_key]
                elif lbl_key in original_alias_to_channel_id:
                    mapped_channel_id = original_alias_to_channel_id[lbl_key]
                    channel_signal_id = channel_id_to_signal_id.get(
                        mapped_channel_id.lower()
                    )

                # Get metadata from Signal DB for this channel's signal ID
                channel_signal_meta = None
                if channel_signal_id:
                    channel_signal_meta = signal_metadata_map.get(channel_signal_id)

                channels_payload.append(
                    {
                        "channel_id": lbl,
                        "parent_signal": (
                            channel_signal_meta.get("name")
                            if channel_signal_meta
                            else None
                        ),
                        "y_label": (
                            channel_signal_meta.get("label")
                            if channel_signal_meta
                            else None
                        ),
                        "y_description": (
                            channel_signal_meta.get("description")
                            if channel_signal_meta
                            else None
                        ),
                        "y_units": (
                            channel_signal_meta.get("standardized_unit")
                            if channel_signal_meta
                            else None
                        ),
                        "line_label": (
                            channel_signal_meta.get("label")
                            if channel_signal_meta
                            else None
                        ),
                        "color": (
                            channel_signal_meta.get("color")
                            if channel_signal_meta
                            else None
                        ),
                        "label": lbl,
                        "exists_in_dataset": True,
                        "icon": (
                            channel_signal_meta.get("icon")
                            if channel_signal_meta
                            else None
                        ),
                    }
                )

            group_item = {
                "kind": "group",
                "group": group_name,
                "present_in_dataset": len(
                    group_to_labels_present.get(group_name, set())
                )
                > 0,
                "channels": channels_payload,
                "coverage": {
                    "available": len(channels_payload),
                    "present": sum(
                        1 for ch in channels_payload if ch.get("exists_in_dataset")
                    ),
                },
                # Add group-level metadata from Signal DB
                "description": group_meta.get("description") if group_meta else None,
                "label": group_meta.get("label") if group_meta else None,
                "y_units": group_meta.get("standardized_unit") if group_meta else None,
                "color": group_meta.get("color") if group_meta else None,
                "icon": group_meta.get("icon") if group_meta else None,
            }
            results.append(group_item)

        return results

    @classmethod
    def from_environment(cls, **kwargs):
        """
        Create DuckPond instance from environment variables.

        Environment variables:
        - LOCAL_ICEBERG_PATH or CONTAINER_ICEBERG_PATH: Path for local filesystem warehouse
        - S3_ENDPOINT: S3/Ceph endpoint URL
        - S3_ACCESS_KEY: S3 access key
        - S3_SECRET_KEY: S3 secret key
        - S3_BUCKET: S3 bucket name
        - S3_REGION: S3 region (optional, defaults to us-east-1)
        """
        config = WarehouseConfig.from_environment()

        return cls(
            warehouse_path=config.warehouse_path if not config.use_s3 else None,
            s3_endpoint=config.s3_endpoint,
            s3_access_key=config.s3_access_key,
            s3_secret_key=config.s3_secret_key,
            s3_bucket=config.s3_bucket,
            s3_region=config.s3_region,
            **kwargs,
        )

    def _setup_iceberg_tables(self):
        """Create Iceberg tables with Hive partitioning"""
        # Create namespace
        try:
            self.catalog.create_namespace_if_not_exists("divedb")
            logging.info("Created/verified namespace: divedb")
        except Exception as e:
            logging.debug(f"Namespace may already exist: {e}")

        # Create tables with Hive partitioning
        for lake_name in self.lakes:
            table_name = f"divedb.{lake_name}"
            try:
                # Configure Hive partitioning
                partition_spec = PartitionSpec(
                    PartitionField(
                        source_id=2,  # animal field
                        field_id=1001,
                        transform=IdentityTransform(),
                        name="animal",
                    ),
                    PartitionField(
                        source_id=3,  # deployment field
                        field_id=1002,
                        transform=IdentityTransform(),
                        name="deployment",
                    ),
                    PartitionField(
                        source_id=6,  # class field
                        field_id=1003,
                        transform=IdentityTransform(),
                        name="class",
                    ),
                    PartitionField(
                        source_id=7,  # label field
                        field_id=1004,
                        transform=IdentityTransform(),
                        name="label",
                    ),
                )

                self.catalog.create_table_if_not_exists(
                    identifier=table_name,
                    schema=self.LAKE_SCHEMAS[lake_name],
                    partition_spec=partition_spec,
                )
                logging.info(f"Created/loaded Iceberg table: {table_name}")

            except Exception as e:
                logging.error(f"Failed to create table {table_name}: {e}")

    def write_to_iceberg(
        self,
        data: pa.Table,
        lake: Literal["data", "events"],
        dataset: str,
        mode: str = "append",
    ):
        """Write data to dataset-specific Iceberg table"""
        # Ensure dataset is initialized
        self.dataset_manager.ensure_dataset_initialized(dataset)

        table_name = f"{dataset}.{lake}"

        try:
            table = self.catalog.load_table(table_name)

            if mode == "append":
                table.append(data)
            elif mode == "overwrite":
                table.overwrite(data)
            else:
                raise ValueError(f"Unsupported mode: {mode}")

            logging.info(f"Successfully wrote {len(data)} rows to {table_name}")

            # Refresh views after writing to update metadata location
            self.dataset_manager._create_dataset_views(dataset)

        except Exception as e:
            logging.error(f"Failed to write to {table_name}: {e}")
            raise

    def read_from_delta(self, query: str):
        """Read data using SQL query (backward compatibility)"""
        return self.conn.execute(query).fetchall()

    def get_data(
        self,
        dataset: str,  # Dataset ID - required for new structure
        labels: str | List[str] | None = None,
        animal_ids: str | List[str] | None = None,
        deployment_ids: str | List[str] | None = None,
        recording_ids: str | List[str] | None = None,
        groups: str | List[str] | None = None,
        classes: str | List[str] | None = None,
        date_range: tuple[str, str] | None = None,
        frequency: int | None = None,
        limit: int | None = None,
        pivoted: bool = False,
    ):
        """
        Get data from a specific dataset using direct Parquet access (bypassing Iceberg layer).

        Args:
            dataset: Dataset identifier (required)
            labels: Specific labels to include (if None, gets all distinct labels)
            animal_ids: Animal ID filter
            deployment_ids: Deployment ID filter
            recording_ids: Recording ID filter
            groups: Group filter
            classes: Class filter
            date_range: Date range tuple (start, end)
            frequency: Resample frequency (if provided, returns DataFrame)
            limit: Row limit
            pivoted: If True, returns data with labels as columns grouped by datetime

        Returns:
        - If frequency is not None, returns a pd.DataFrame.
        - If pivoted is True, returns DuckDB relation with labels as columns.
        - Otherwise, returns a DiveData object with long-format data.
        """

        # Ensure dataset is initialized
        self.dataset_manager.ensure_dataset_initialized(dataset)

        def get_predicate_string(predicate: str, values: List[str]):
            if not values:
                return ""
            if len(values) == 1:
                return f"{predicate} = '{values[0]}'"
            quoted_values = ", ".join(f"'{value}'" for value in values)
            return f"{predicate} IN ({quoted_values})"

        # Convert single strings to lists
        if isinstance(labels, str):
            labels = [labels]
        if isinstance(animal_ids, str):
            animal_ids = [animal_ids]
        if isinstance(deployment_ids, str):
            deployment_ids = [deployment_ids]
        if isinstance(recording_ids, str):
            recording_ids = [recording_ids]
        if isinstance(groups, str):
            groups = [groups]
        if isinstance(classes, str):
            classes = [classes]

        # Build basic query using the dataset-specific Data view
        view_name = f'"{dataset}_Data"'

        base_query = f"""
            SELECT
                dataset,
                animal,
                deployment,
                recording,
                "group",
                class,
                label,
                datetime,
                value,
                float_value,
                int_value,
                boolean_value,
                string_value,
                data_type
            FROM {view_name}
        """

        # Build WHERE clause
        predicates = []
        if labels:
            predicates.append(get_predicate_string("label", labels))
        if animal_ids:
            predicates.append(get_predicate_string("animal", animal_ids))
        if deployment_ids:
            predicates.append(get_predicate_string("deployment", deployment_ids))
        if recording_ids:
            predicates.append(get_predicate_string("recording", recording_ids))
        if groups:
            predicates.append(get_predicate_string('"group"', groups))
        if classes:
            predicates.append(get_predicate_string("class", classes))
        if date_range:
            predicates.append(
                f"datetime >= '{date_range[0]}' AND datetime <= '{date_range[1]}'"
            )

        if predicates:
            base_query += " WHERE " + " AND ".join(predicates)

        if limit:
            base_query += f" LIMIT {limit}"

        # Handle frequency resampling FIRST (before pivoting)
        if frequency:
            # Get data in long format for resampling
            results = self.conn.sql(base_query)
            df = results.df()

            # Create numeric value column based on data_type
            df["numeric_value"] = df.apply(
                lambda row: (
                    row["float_value"]
                    if row["data_type"] == "double" and pd.notna(row["float_value"])
                    else row["int_value"]
                    if row["data_type"] == "int" and pd.notna(row["int_value"])
                    else row["boolean_value"]
                    if row["data_type"] == "bool" and pd.notna(row["boolean_value"])
                    else pd.to_numeric(row["string_value"], errors="coerce")
                    if pd.notna(row["string_value"])
                    else np.nan
                ),
                axis=1,
            )

            # Resample each label separately
            resampled_dfs = []
            for label_name in df["label"].unique():
                label_df = df[df["label"] == label_name][
                    ["datetime", "label", "numeric_value"]
                ].copy()
                label_df = label_df.dropna(subset=["numeric_value"])
                if len(label_df) > 0:
                    label_resampled = resample(label_df, frequency)
                    resampled_dfs.append(label_resampled)

            # Combine resampled data
            combined_df = pd.concat(resampled_dfs, ignore_index=True)

            # Pivot if requested
            if pivoted:
                pivoted_df = combined_df.pivot_table(
                    index="datetime",
                    columns="label",
                    values="numeric_value",
                    aggfunc="first",
                ).reset_index()
                pivoted_df.columns.name = None
                return pivoted_df
            else:
                return combined_df

        # Handle pivoted data request without frequency resampling
        elif pivoted:
            # Get distinct labels if not provided
            if not labels:
                labels_query = (
                    f"SELECT DISTINCT label FROM ({base_query}) AS sub_labels"
                )
                labels = [row[0] for row in self.conn.sql(labels_query).fetchall()]

            # Add labels filter to base query
            if labels:
                label_filter = get_predicate_string("label", labels)
                if predicates:
                    base_query += f" AND {label_filter}"
                else:
                    base_query += f" WHERE {label_filter}"

            # Create pivot expressions
            pivot_expressions = []
            for label in labels:
                pivot_expressions.append(
                    f"""
                    FIRST(CASE WHEN label = '{label}' THEN
                        CASE data_type
                            WHEN 'double' THEN float_value
                            WHEN 'int' THEN CAST(int_value AS DOUBLE)
                            WHEN 'bool' THEN CAST(boolean_value AS DOUBLE)
                            ELSE TRY_CAST(string_value AS DOUBLE)
                        END
                    END ORDER BY datetime) AS "{label}"
                """
                )

            # Pivot query
            pivot_query = f"""
            SELECT
                datetime,
                {', '.join(pivot_expressions)}
            FROM ({base_query}) AS sub
            GROUP BY datetime
            ORDER BY datetime
            """

            results = self.conn.sql(pivot_query)
            return results.df()
        else:
            # Return long-format data
            results = self.conn.sql(base_query)
            return DiveData(results, self.conn, notion_manager=self.notion_manager)

    def ensure_dataset_initialized(self, dataset: str):
        """Ensure a dataset's tables and views are initialized"""
        return self.dataset_manager.ensure_dataset_initialized(dataset)

    def get_all_datasets(self) -> List[str]:
        """Get list of all initialized datasets"""
        return self.dataset_manager.get_all_datasets()

    def list_dataset_tables(self, dataset: str) -> List[str]:
        """List tables for a specific dataset"""
        return self.dataset_manager.list_dataset_tables(dataset)

    def dataset_exists(self, dataset: str) -> bool:
        """Check if a dataset has been initialized"""
        return self.dataset_manager.dataset_exists(dataset)

    def remove_dataset(self, dataset: str):
        """Remove a dataset and all its tables (use with caution!)"""
        return self.dataset_manager.remove_dataset(dataset)

    def get_view_name(self, dataset: str, table_type: str) -> str:
        """
        Get the properly quoted view name for a dataset and table type.

        Args:
            dataset: Dataset identifier (e.g., "EP Physiology")
            table_type: Type of table - "data" or "events"

        Returns:
            Quoted view name ready for SQL queries

        Examples:
            >>> duck_pond.get_view_name("EP Physiology", "data")
            '"EP Physiology_Data"'
            >>> duck_pond.get_view_name("EP Physiology", "events")
            '"EP Physiology_Events"'
        """
        if table_type == "data":
            return f'"{dataset}_Data"'
        elif table_type == "events":
            return f'"{dataset}_Events"'
        else:
            raise ValueError(
                f"Invalid table_type: {table_type}. Must be 'data' or 'events'"
            )

    def get_db_schema(self):
        """View all tables in the database"""
        return self.conn.sql("SHOW ALL TABLES")

    def list_all_views(self) -> List[str]:
        """
        List all dataset views in the warehouse.

        Returns:
            List of view names for all initialized datasets
        """
        all_views = []
        for dataset in self.initialized_datasets:
            for table_type in ["data", "events"]:
                all_views.append(self.get_view_name(dataset, table_type))
        return sorted(all_views)

    def list_dataset_views(self, dataset: str) -> List[str]:
        """
        List all views for a specific dataset.

        Args:
            dataset: Dataset identifier

        Returns:
            List of view names for the specified dataset
        """
        if dataset not in self.initialized_datasets:
            return []

        return [
            self.get_view_name(dataset, table_type) for table_type in ["data", "events"]
        ]

    def close_connection(self):
        """Close the connection"""
        self.connection.close()

    def list_notion_tables(self) -> List[str]:
        """List all available Notion tables in DuckDB"""
        return self.notion_integration.list_notion_tables()

    def _create_wide_values(self, values):
        """
        Transform mixed-type values into wide format arrays.
        Transforms mixed-type values into separate typed columns for Iceberg storage.

        Args:
            values: list with mixed types (bool, int, float, str)

        Returns:
            tuple: (val_dbl_array, val_int_array, val_bool_array, val_str_array, data_type_array)
        """
        import numpy as np

        # Initialize arrays for each type
        val_dbl = np.full(len(values), None, dtype=object)
        val_int = np.full(len(values), None, dtype=object)
        val_bool = np.full(len(values), None, dtype=object)
        val_str = np.full(len(values), None, dtype=object)
        data_type = np.full(len(values), None, dtype=object)

        for i, value in enumerate(values):
            if value is None or (isinstance(value, float) and np.isnan(value)):
                # Handle null values
                data_type[i] = "null"
                continue

            # Check for boolean (must come before numeric checks)
            if isinstance(value, (bool, np.bool_)):
                val_bool[i] = bool(value)
                data_type[i] = "bool"
            # Check for integer
            elif isinstance(value, (int, np.integer)) and not isinstance(
                value, (bool, np.bool_)
            ):
                val_int[i] = int(value)
                data_type[i] = "int"
            # Check for float
            elif isinstance(value, (float, np.floating)) and np.isfinite(value):
                val_dbl[i] = float(value)
                data_type[i] = "double"
            # Check for string or anything else
            else:
                val_str[i] = str(value)
                data_type[i] = "str"

        # Convert to PyArrow arrays with proper nullable types
        return (
            pa.array(val_dbl, type=pa.float64()),  # val_dbl
            pa.array(val_int, type=pa.int64()),  # val_int
            pa.array(val_bool, type=pa.bool_()),  # val_bool
            pa.array(val_str, type=pa.string()),  # val_str
            pa.array(data_type, type=pa.string()),  # data_type (required field)
        )

    def write_signal_data(
        self,
        dataset: str,
        metadata: dict,
        times: pa.Array,
        group: str,
        class_name: str,
        label: str,
        values,  # list with mixed types
    ):
        """
        Write signal data using the new wide format.
        High-level method for writing signal data to the Iceberg data lake.

        Args:
            dataset: Dataset identifier
            metadata: Dict with 'animal', 'deployment', 'recording' keys
            times: PyArrow timestamp array
            group: Data group (e.g., 'signal_data')
            class_name: Data class (e.g., 'accelerometer')
            label: Data label (e.g., 'acc_x')
            values: Mixed-type list to be transformed
        """

        # Clean the label to prevent whitespace issues in queries
        label = label.strip() if label else label

        # Transform values using new wide format
        val_dbl, val_int, val_bool, val_str, data_type = self._create_wide_values(
            values
        )

        # Create the schema that matches Iceberg's requirements exactly
        wide_schema = pa.schema(
            [
                pa.field("dataset", pa.string(), nullable=False),  # Required
                pa.field("animal", pa.string(), nullable=False),  # Required
                pa.field("deployment", pa.string(), nullable=False),  # Required
                pa.field("recording", pa.string(), nullable=True),  # Optional
                pa.field("group", pa.string(), nullable=False),  # Required
                pa.field("class", pa.string(), nullable=False),  # Required
                pa.field("label", pa.string(), nullable=False),  # Required
                pa.field("datetime", pa.timestamp("us"), nullable=False),  # Required
                pa.field("val_dbl", pa.float64(), nullable=True),  # Optional
                pa.field("val_int", pa.int64(), nullable=True),  # Optional
                pa.field("val_bool", pa.bool_(), nullable=True),  # Optional
                pa.field("val_str", pa.string(), nullable=True),  # Optional
                pa.field("data_type", pa.string(), nullable=False),  # Required
            ]
        )

        # Create the wide format table using the explicit schema
        wide_table = pa.table(
            [
                pa.array([dataset] * len(values)),  # dataset
                pa.array([metadata["animal"]] * len(values)),  # animal
                pa.array([str(metadata["deployment"])] * len(values)),  # deployment
                pa.array(
                    [metadata.get("recording")] * len(values)
                ),  # recording (can be None)
                pa.array([group] * len(values)),  # group
                pa.array([class_name] * len(values)),  # class
                pa.array([label] * len(values)),  # label
                times,  # datetime
                val_dbl,  # val_dbl (from transformation)
                val_int,  # val_int (from transformation)
                val_bool,  # val_bool (from transformation)
                val_str,  # val_str (from transformation)
                data_type,  # data_type (from transformation)
            ],
            schema=wide_schema,
        )

        self.write_to_iceberg(wide_table, "data", dataset=dataset)

        return len(values)  # Return number of rows written
