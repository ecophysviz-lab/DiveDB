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
            SELECT "class", class, label
            FROM {view_name}
            WHERE label IS NOT NULL
            GROUP BY 1,2,3
            ORDER BY 1,2,3
        """
        query_groups = f"""
            SELECT "class"
            FROM {view_name}
            WHERE "class" IS NOT NULL
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
        load_metadata: bool = True,
    ) -> List[Dict]:
        """
        Discover available channels for a dataset and optionally hydrate metadata from Signal DB.

        Args:
            dataset: Dataset identifier
            include_metadata: If True, join metadata from Signal DB via Standardized Channel DB lookup
            pack_groups: If True, groups are returned as one collection with all standardized children
            load_metadata: If False, skip loading metadata from Notion (faster for initial discovery)

        Returns:
            List[Dict] of channels/groups as specified
        """

        triples, present_groups = self._discover_dataset_channels(dataset)
        # print(triples)
        # print(present_groups)
        # Prepare lookup mappings
        channel_id_to_signal_id: Dict[str, str] = {}
        original_alias_to_channel_id: Dict[str, str] = {}
        signal_metadata_map: Dict[str, Dict] = {}

        if include_metadata and load_metadata and self.notion_manager:
            (
                channel_id_to_signal_id,
                original_alias_to_channel_id,
                signal_metadata_map,
            ) = self.notion_integration.get_metadata_mappings()
        # import pprint
        # pprint.pprint({"signal_metadata_map": signal_metadata_map})
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
            # print(signal_meta)
            # import pprint
            # pprint.pprint(signal_metadata_map)
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
                print("metadata", metadata, group_name)
                name = metadata.get("name") if metadata.get("name") else "None"
                if name.lower() == group_name.lower():
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

    def get_channels_metadata(
        self, dataset: str, channel_ids: List[str]
    ) -> Dict[str, Dict]:
        """
        Get metadata for specific channels only (lazy loading).

        Args:
            dataset: Dataset identifier
            channel_ids: List of channel IDs to load metadata for

        Returns:
            Dict mapping channel_id -> metadata dict
        """
        if not self.notion_manager or not channel_ids:
            return {}

        # Get metadata mappings for specific channels only
        (
            channel_id_to_signal_id,
            original_alias_to_channel_id,
            signal_metadata_map,
        ) = self.notion_integration.get_metadata_mappings(channel_ids=channel_ids)

        # Build result dict keyed by channel_id
        result = {}
        for channel_id in channel_ids:
            chan_key = channel_id.lower()

            # Try direct channel_id lookup first
            signal_id = None
            if chan_key in channel_id_to_signal_id:
                signal_id = channel_id_to_signal_id[chan_key]
            # Try alias lookup
            elif chan_key in original_alias_to_channel_id:
                mapped_channel_id = original_alias_to_channel_id[chan_key]
                signal_id = channel_id_to_signal_id.get(mapped_channel_id.lower())

            # Get metadata from Signal DB if signal ID found
            if signal_id and signal_id in signal_metadata_map:
                result[channel_id] = signal_metadata_map[signal_id]

        return result

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
        skip_view_refresh: bool = False,
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
            if not skip_view_refresh:
                self.dataset_manager._create_dataset_views(dataset)

        except Exception as e:
            logging.error(f"Failed to write to {table_name}: {e}")
            raise

    def read_from_delta(self, query: str):
        """Read data using SQL query (backward compatibility)"""
        return self.conn.execute(query).fetchall()

    def _apply_date_handling(
        self,
        df: pd.DataFrame,
        datetime_col: str,
        apply_timezone_offset: Optional[int] = None,
        add_timestamp_column: bool = False,
        timestamp_col_name: str = "timestamp",
    ) -> pd.DataFrame:
        """
        Apply date handling transformations to a DataFrame.

        Args:
            df: Input DataFrame
            datetime_col: Name of the datetime column to process
            apply_timezone_offset: Optional timezone offset in hours to add to datetime column
            add_timestamp_column: If True, adds a timestamp column (seconds since epoch)
            timestamp_col_name: Name for the timestamp column (default: "timestamp")

        Returns: Transformed DataFrame
        """
        if datetime_col not in df.columns:
            return df

        # Ensure datetime column is in datetime format
        if apply_timezone_offset is not None:
            df[datetime_col] = pd.to_datetime(
                df[datetime_col], errors="coerce"
            ) + pd.Timedelta(hours=apply_timezone_offset)

        # Add timestamp column if requested
        if add_timestamp_column:
            df[timestamp_col_name] = df[datetime_col].apply(lambda x: x.timestamp())

        return df

    def _normalize_to_list(self, value: str | List[str] | None) -> List[str] | None:
        """
        Convert a single string to a list, or return as-is if already a list or None.
        Args: value: String, list of strings, or None
        Returns: List of strings, or None
        """
        if isinstance(value, str):
            return [value]
        return value

    def _normalize_list_to_list(self, *params):
        """
        Normalize each parameter to a list using _normalize_to_list, and return the tuple of normalized values.
        Args: *params: Any number of parameters (str, list, or None)
        Returns: Tuple of lists or None, in the same order as params.
        """
        return tuple(self._normalize_to_list(param) for param in params)

    def _build_base_query(
        self,
        view_name: str,
        labels: List[str] | None,
        animal_ids: List[str] | None,
        deployment_ids: List[str] | None,
        recording_ids: List[str] | None,
        groups: List[str] | None,
        classes: List[str] | None,
        date_range: tuple[str, str] | None,
        limit: int | None,
    ) -> str:
        """
        Build the base SQL query with all filters.
        Extracted for clarity and reusability.
        """

        def get_predicate_string(predicate: str, values: List[str]):
            if not values:
                return ""
            if len(values) == 1:
                return f"{predicate} = '{values[0]}'"
            quoted_values = ", ".join(f"'{value}'" for value in values)
            return f"{predicate} IN ({quoted_values})"

        query = f"""
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
            query += " WHERE " + " AND ".join(predicates)

        if limit:
            query += f" LIMIT {limit}"

        return query

    def _get_distinct_labels(self, base_query: str) -> List[str]:
        """Get distinct labels from a query."""
        query = f"SELECT DISTINCT label FROM ({base_query}) ORDER BY label"
        return [row[0] for row in self.conn.sql(query).fetchall()]

    def _estimate_label_frequency(self, base_query: str, label: str) -> float | None:
        """
        Estimate the native sampling frequency of a label using SQL.
        Fast and memory-efficient - only samples the data.
        """
        query = f"""
        WITH time_intervals AS (
            SELECT
                EXTRACT(EPOCH FROM (datetime - LAG(datetime) OVER (ORDER BY datetime))) AS interval_sec
            FROM ({base_query})
            WHERE label = '{label}'
            LIMIT 1000
        )
        SELECT 1.0 / MEDIAN(interval_sec) as freq_hz
        FROM time_intervals
        WHERE interval_sec > 0
        """

        try:
            result = self.conn.sql(query).fetchone()
            return result[0] if result and result[0] else None
        except Exception as e:
            logging.warning(f"Could not estimate frequency for label '{label}': {e}")
            return None

    def _build_downsample_query(
        self, base_query: str, label: str, native_fs: float, target_fs: float
    ) -> str:
        """
        Build SQL query that downsamples a single label.
        Only selects every Nth row - never loads unnecessary data!
        """
        downsample_factor = int(native_fs / target_fs)

        return f"""
        WITH labeled_data AS (
            SELECT
                datetime,
                '{label}' as label,
                CASE data_type
                    WHEN 'double' THEN float_value
                    WHEN 'int' THEN CAST(int_value AS DOUBLE)
                    WHEN 'bool' THEN CAST(boolean_value AS DOUBLE)
                    ELSE TRY_CAST(string_value AS DOUBLE)
                END AS numeric_value,
                ROW_NUMBER() OVER (ORDER BY datetime) as rn
            FROM ({base_query})
            WHERE label = '{label}'
        )
        SELECT datetime, label, numeric_value
        FROM labeled_data
        WHERE (rn - 1) % {downsample_factor} = 0
        """

    def _build_upsample_query(
        self, base_query: str, label: str, target_fs: float
    ) -> str:
        """
        Build SQL query that upsamples a single label using time grid.
        Uses ASOF join for forward-fill interpolation.
        """
        # Get time range for this label
        range_query = f"""
        SELECT MIN(datetime) as start_time, MAX(datetime) as end_time
        FROM ({base_query})
        WHERE label = '{label}'
        """
        result = self.conn.sql(range_query).fetchone()
        if not result or not result[0]:
            return self._build_passthrough_label_query(base_query, label)

        start_time, end_time = result
        interval_ms = int(1000 / target_fs)

        return f"""
        WITH time_grid AS (
            SELECT datetime AS grid_time
            FROM generate_series(
                TIMESTAMP '{start_time}',
                TIMESTAMP '{end_time}',
                INTERVAL '{interval_ms} milliseconds'
            ) AS t(datetime)
        ),
        label_data AS (
            SELECT
                datetime,
                CASE data_type
                    WHEN 'double' THEN float_value
                    WHEN 'int' THEN CAST(int_value AS DOUBLE)
                    WHEN 'bool' THEN CAST(boolean_value AS DOUBLE)
                    ELSE TRY_CAST(string_value AS DOUBLE)
                END AS numeric_value
            FROM ({base_query})
            WHERE label = '{label}'
        )
        SELECT
            time_grid.grid_time AS datetime,
            '{label}' as label,
            LAST_VALUE(label_data.numeric_value IGNORE NULLS) OVER (
                ORDER BY time_grid.grid_time
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) as numeric_value
        FROM time_grid
        ASOF LEFT JOIN label_data
        ON time_grid.grid_time >= label_data.datetime
        """

    def _build_passthrough_label_query(self, base_query: str, label: str) -> str:
        """Build query that passes through label data without resampling."""
        return f"""
        SELECT
            datetime,
            '{label}' as label,
            CASE data_type
                WHEN 'double' THEN float_value
                WHEN 'int' THEN CAST(int_value AS DOUBLE)
                WHEN 'bool' THEN CAST(boolean_value AS DOUBLE)
                ELSE TRY_CAST(string_value AS DOUBLE)
            END AS numeric_value
        FROM ({base_query})
        WHERE label = '{label}'
        """

    def _wrap_query_with_resampling(
        self,
        base_query: str,
        target_fs: float,
        labels: List[str] | None,
    ) -> str:
        """
        Transform a base query to include resampling logic.

        This method:
        1. Creates a common time grid for ALL labels
        2. Estimates native frequency for each label
        3. Downsamples high-frequency data and joins to common grid
        4. Upsamples low-frequency data and joins to common grid

        All done at the SQL level for maximum performance.
        """
        # Discover labels if not provided
        if not labels:
            labels = self._get_distinct_labels(base_query)

        # Get global time range across all labels
        time_range_query = f"""
        SELECT MIN(datetime) as start_time, MAX(datetime) as end_time
        FROM ({base_query})
        """
        result = self.conn.sql(time_range_query).fetchone()
        if not result or not result[0]:
            # No data, return empty query
            return """
            SELECT
                CAST(NULL AS TIMESTAMP) as datetime,
                CAST(NULL AS VARCHAR) as label,
                CAST(NULL AS DOUBLE) as numeric_value
            WHERE 1=0
            """

        start_time, end_time = result
        interval_ms = int(1000 / target_fs)

        # Create common time grid CTE
        common_time_grid = f"""
        common_time_grid AS (
            SELECT datetime AS grid_time
            FROM generate_series(
                TIMESTAMP '{start_time}',
                TIMESTAMP '{end_time}',
                INTERVAL '{interval_ms} milliseconds'
            ) AS t(datetime)
        )
        """

        # Estimate frequency for each label
        label_frequencies = {
            label: self._estimate_label_frequency(base_query, label) for label in labels
        }

        # Build resampling query for each label, joining to common grid
        label_queries = []
        for label in labels:
            native_fs = label_frequencies.get(label)

            if native_fs is None or abs(native_fs - target_fs) <= target_fs * 0.01:
                # Pass through or already at target frequency
                label_data_query = f"""
                SELECT
                    datetime,
                    CASE data_type
                        WHEN 'double' THEN float_value
                        WHEN 'int' THEN CAST(int_value AS DOUBLE)
                        WHEN 'bool' THEN CAST(boolean_value AS DOUBLE)
                        ELSE TRY_CAST(string_value AS DOUBLE)
                    END AS numeric_value
                FROM ({base_query})
                WHERE label = '{label}'
                """
            elif native_fs > target_fs * 1.01:
                # Downsample: select every Nth row
                downsample_factor = int(native_fs / target_fs)
                label_data_query = f"""
                SELECT
                    datetime,
                    numeric_value
                FROM (
                    SELECT
                        datetime,
                        CASE data_type
                            WHEN 'double' THEN float_value
                            WHEN 'int' THEN CAST(int_value AS DOUBLE)
                            WHEN 'bool' THEN CAST(boolean_value AS DOUBLE)
                            ELSE TRY_CAST(string_value AS DOUBLE)
                        END AS numeric_value,
                        ROW_NUMBER() OVER (ORDER BY datetime) as rn
                    FROM ({base_query})
                    WHERE label = '{label}'
                ) sub
                WHERE (rn - 1) % {downsample_factor} = 0
                """
            else:
                # Upsample: use original data, will forward-fill when joined to grid
                label_data_query = f"""
                SELECT
                    datetime,
                    CASE data_type
                        WHEN 'double' THEN float_value
                        WHEN 'int' THEN CAST(int_value AS DOUBLE)
                        WHEN 'bool' THEN CAST(boolean_value AS DOUBLE)
                        ELSE TRY_CAST(string_value AS DOUBLE)
                    END AS numeric_value
                FROM ({base_query})
                WHERE label = '{label}'
                """

            # Join label data to common time grid with forward fill
            label_query = f"""
            label_{label.replace('-', '_').replace(' ', '_')} AS (
                SELECT
                    grid_time AS datetime,
                    '{label}' as label,
                    LAST_VALUE(ld.numeric_value IGNORE NULLS) OVER (
                        ORDER BY grid_time
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ) as numeric_value
                FROM common_time_grid
                ASOF LEFT JOIN ({label_data_query}) AS ld
                ON grid_time >= ld.datetime
            )
            """
            label_queries.append(label_query)

        # Build final query with common time grid and all label CTEs
        all_ctes = [common_time_grid] + label_queries
        select_unions = [
            f"SELECT datetime, label, numeric_value FROM label_{label.replace('-', '_').replace(' ', '_')}"
            for label in labels
        ]

        final_query = f"""
        WITH {', '.join(all_ctes)}
        {' UNION ALL '.join(select_unions)}
        ORDER BY label, datetime
        """

        return final_query

    def _execute_pivoted_query(
        self, query: str, labels: List[str] | None, is_resampled: bool = False
    ) -> pd.DataFrame:
        """
        Execute a query and pivot the results.
        Works with both resampled and non-resampled data.
        """
        # Get labels if not provided
        if not labels:
            labels = self._get_distinct_labels(query)

        # Execute query
        df = self.conn.sql(query).df()

        if is_resampled or "numeric_value" in df.columns:
            # Data from resampling (already has numeric_value)
            pivoted_df = df.pivot_table(
                index="datetime",
                columns="label",
                values="numeric_value",
                aggfunc="first",
            ).reset_index()
        else:
            # Original data format - need to build pivot expressions in SQL
            # Build pivot query with SQL
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

            pivot_query = f"""
            SELECT
                datetime,
                {', '.join(pivot_expressions)}
            FROM ({query}) AS sub
            GROUP BY datetime
            ORDER BY datetime
            """
            pivoted_df = self.conn.sql(pivot_query).df()

        pivoted_df.columns.name = None
        return pivoted_df

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
        apply_timezone_offset: Optional[int] = None,
        add_timestamp_column: bool = False,
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
            frequency: Resample frequency in Hz (if provided, applies SQL-based resampling)
            limit: Row limit
            pivoted: If True, returns data with labels as columns grouped by datetime
            apply_timezone_offset: Optional timezone offset in hours to add to datetime column
            add_timestamp_column: If True, adds a 'timestamp' column (seconds since epoch)

        Returns:
        - If frequency is not None, returns a pd.DataFrame (resampled to target frequency).
        - If pivoted is True, returns DataFrame with labels as columns.
        - Otherwise, returns a DiveData object with long-format data.
        """

        # Ensure dataset is initialized
        self.dataset_manager.ensure_dataset_initialized(dataset)

        # Convert single strings to lists
        (
            labels,
            animal_ids,
            deployment_ids,
            recording_ids,
            groups,
            classes,
        ) = self._normalize_list_to_list(
            labels, animal_ids, deployment_ids, recording_ids, groups, classes
        )

        # Build base query using the dataset-specific Data view
        view_name = f'"{dataset}_Data"'
        base_query = self._build_base_query(
            view_name=view_name,
            labels=labels,
            animal_ids=animal_ids,
            deployment_ids=deployment_ids,
            recording_ids=recording_ids,
            groups=groups,
            classes=classes,
            date_range=date_range,
            limit=limit if not frequency else None,  # Don't limit before resampling
        )

        # Apply resampling transformation if frequency is provided
        if frequency:
            query = self._wrap_query_with_resampling(
                base_query=base_query,
                target_fs=frequency,
                labels=labels,
            )
            is_resampled = True
        else:
            query = base_query
            is_resampled = False

        # Apply limit after resampling
        if frequency and limit:
            query = f"SELECT * FROM ({query}) LIMIT {limit}"

        # Handle pivoting (works on resampled or non-resampled data)
        if pivoted:
            df = self._execute_pivoted_query(query, labels, is_resampled=is_resampled)
            df = self._apply_date_handling(
                df, "datetime", apply_timezone_offset, add_timestamp_column
            )
            return df
        elif frequency:
            # For resampled data, return DataFrame directly
            df = self.conn.sql(query).df()
            df = self._apply_date_handling(
                df, "datetime", apply_timezone_offset, add_timestamp_column
            )
            return df
        else:
            # For non-resampled data without pivoting, return DiveData object
            results = self.conn.sql(query)
            return DiveData(results, self.conn, notion_manager=self.notion_manager)

    def estimate_data_size(
        self,
        dataset: str,
        labels: str | List[str] | None = None,
        animal_ids: str | List[str] | None = None,
        deployment_ids: str | List[str] | None = None,
        recording_ids: str | List[str] | None = None,
        groups: str | List[str] | None = None,
        classes: str | List[str] | None = None,
        date_range: tuple[str, str] | None = None,
    ) -> int:
        """
        Quickly estimate the number of rows that would be returned by get_data.
        Uses COUNT(*) which is much faster than loading actual data.

        Args:
            Same as get_data() (excluding frequency, limit, pivoted, etc.)

        Returns:
            Estimated row count
        """
        # Ensure dataset is initialized
        self.dataset_manager.ensure_dataset_initialized(dataset)

        # Convert single strings to lists
        (
            labels,
            animal_ids,
            deployment_ids,
            recording_ids,
            groups,
            classes,
        ) = self._normalize_list_to_list(
            labels, animal_ids, deployment_ids, recording_ids, groups, classes
        )

        # Build base query using existing method
        view_name = f'"{dataset}_Data"'
        base_query = self._build_base_query(
            view_name=view_name,
            labels=labels,
            animal_ids=animal_ids,
            deployment_ids=deployment_ids,
            recording_ids=recording_ids,
            groups=groups,
            classes=classes,
            date_range=date_range,
            limit=None,
        )

        # Wrap in COUNT query
        count_query = f"SELECT COUNT(*) as row_count FROM ({base_query})"
        result = self.conn.sql(count_query).fetchone()
        return result[0] if result else 0

    def get_events(
        self,
        dataset: str,
        animal_ids: str | List[str] | None = None,
        deployment_ids: str | List[str] | None = None,
        recording_ids: str | List[str] | None = None,
        event_keys: str | List[str] | None = None,
        date_range: tuple[str, str] | None = None,
        limit: int | None = None,
        apply_timezone_offset: Optional[int] = None,
        add_timestamp_columns: bool = False,
    ):
        """
        Get events from a specific dataset.

        Args:
            dataset: Dataset identifier (required)
            animal_ids: Animal ID filter
            deployment_ids: Deployment ID filter
            recording_ids: Recording ID filter
            event_keys: Event key filter
            date_range: Date range tuple (start, end)
            limit: Row limit
            apply_timezone_offset: Optional timezone offset in hours to add to datetime columns
            add_timestamp_columns: If True, adds 'timestamp_start' and 'timestamp_end' columns (seconds since epoch)

        Returns:
            pd.DataFrame with columns: dataset, animal, deployment, recording,
            group, event_key, datetime_start, datetime_end, short_description,
            long_description, event_data
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
        (
            animal_ids,
            deployment_ids,
            recording_ids,
            event_keys,
        ) = self._normalize_list_to_list(
            animal_ids, deployment_ids, recording_ids, event_keys
        )

        # Build query using the dataset-specific Events view
        view_name = self.get_view_name(dataset, "events")

        base_query = f"""
            SELECT
                dataset,
                animal,
                deployment,
                recording,
                "group",
                event_key,
                datetime_start,
                datetime_end,
                short_description,
                long_description,
                event_data
            FROM {view_name}
        """

        # Build WHERE clause
        predicates = []
        if animal_ids:
            predicates.append(get_predicate_string("animal", animal_ids))
        if deployment_ids:
            predicates.append(get_predicate_string("deployment", deployment_ids))
        if recording_ids:
            predicates.append(get_predicate_string("recording", recording_ids))
        if event_keys:
            predicates.append(get_predicate_string("event_key", event_keys))
        if date_range:
            # Events that overlap with the date range
            predicates.append(
                f"datetime_start <= '{date_range[1]}' AND datetime_end >= '{date_range[0]}'"
            )

        if predicates:
            base_query += " WHERE " + " AND ".join(predicates)

        base_query += " ORDER BY datetime_start"

        if limit:
            base_query += f" LIMIT {limit}"

        # Execute query and return DataFrame
        results = self.conn.sql(base_query)
        df = results.df()

        # Apply date handling transformations to both datetime columns
        if apply_timezone_offset is not None or add_timestamp_columns:
            df = self._apply_date_handling(
                df,
                "datetime_start",
                apply_timezone_offset,
                add_timestamp_columns,
                timestamp_col_name="timestamp_start",
            )
            df = self._apply_date_handling(
                df,
                "datetime_end",
                apply_timezone_offset,
                add_timestamp_columns,
                timestamp_col_name="timestamp_end",
            )

        return df

    def ensure_dataset_initialized(self, dataset: str):
        """Ensure a dataset's tables and views are initialized"""
        return self.dataset_manager.ensure_dataset_initialized(dataset)

    def get_all_datasets(self) -> List[str]:
        """Get list of all initialized datasets"""
        return self.dataset_manager.get_all_datasets()

    def get_all_datasets_and_deployments(self) -> Dict[str, List[Dict]]:
        """
        Get all datasets and their deployments in a single call using one optimized query.

        Returns:
            Dict mapping dataset names to lists of deployment records.
            Each deployment record contains: deployment, animal, min_date, max_date, sample_count
            Format: {"dataset1": [{"deployment": "...", "animal": "...", ...}, ...], ...}
        """
        datasets = self.get_all_datasets()
        result = {}

        if not datasets:
            return result

        # Ensure all datasets are initialized first
        for dataset in datasets:
            self.ensure_dataset_initialized(dataset)

        # Build a single UNION ALL query for all valid datasets
        union_queries = []
        for dataset in datasets:
            view_name = self.get_view_name(dataset, "data")
            # Escape single quotes in dataset name for SQL literal
            dataset_escaped = dataset.replace("'", "''")
            # Use dataset field from the view, or hardcode it as a literal string
            union_queries.append(
                f"""
                SELECT
                    '{dataset_escaped}' as dataset,
                    deployment,
                    animal,
                    MIN(datetime) as min_date,
                    MAX(datetime) as max_date,
                    COUNT(*) as sample_count
                FROM {view_name}
                WHERE deployment IS NOT NULL AND animal IS NOT NULL
                GROUP BY deployment, animal
            """
            )

        # Combine all queries with UNION ALL
        combined_query = " UNION ALL ".join(union_queries)

        # Execute single query for all datasets
        all_deployments_df = self.conn.sql(combined_query).df()
        all_deployments_df["deployment_date"] = all_deployments_df["deployment"].apply(
            lambda x: x.split("_")[0]
        )

        # Group results by dataset
        if len(all_deployments_df) > 0:
            # Sort by dataset and min_date descending
            all_deployments_df = all_deployments_df.sort_values(
                by=["dataset", "min_date"], ascending=[True, False]
            )

            # Group by dataset and convert to list of dicts
            for dataset in datasets:
                dataset_df = all_deployments_df[
                    all_deployments_df["dataset"] == dataset
                ]
                # Remove dataset column from records (it's redundant in the dict key)
                dataset_df_clean = dataset_df.drop(columns=["dataset"])
                result[dataset] = dataset_df_clean.to_dict("records")
        else:
            # No deployments found for any dataset
            for dataset in datasets:
                result[dataset] = []

        return result

    def list_dataset_tables(self, dataset: str) -> List[str]:
        """List tables for a specific dataset"""
        return self.dataset_manager.list_dataset_tables(dataset)

    def dataset_exists(self, dataset: str) -> bool:
        """Check if a dataset has been initialized"""
        return self.dataset_manager.dataset_exists(dataset)

    def remove_dataset(self, dataset: str):
        """Remove a dataset and all its tables (use with caution!)"""
        return self.dataset_manager.remove_dataset(dataset)

    def get_deployment_timezone_offset(self, deployment_id: str) -> float:
        """
        Get timezone offset for a deployment from Notion Deployments table.
        Args: deployment_id: Deployment identifier (e.g., "2019-11-08_apfo-001")
        Returns: Timezone offset in hours (e.g., 13.0 for Antarctica/McMurdo)
        """
        from zoneinfo import ZoneInfo
        from datetime import datetime, timezone

        try:
            # Query the Deployments table (loaded from Notion into DuckDB)
            result = self.conn.sql(
                f"""
                SELECT time_zone
                FROM Deployments
                WHERE deployment_id = '{deployment_id}'
            """
            ).fetchone()

            if result and result[0]:
                tz_name = result[0]
                # Convert timezone name to UTC offset in hours
                tz = ZoneInfo(tz_name)
                offset_seconds = (
                    datetime.now(timezone.utc)
                    .astimezone(tz)
                    .utcoffset()
                    .total_seconds()
                )
                return offset_seconds / 3600
            else:
                logging.warning(
                    f"No timezone found for deployment {deployment_id}, using UTC"
                )

        except Exception as e:
            logging.warning(
                f"Could not get timezone for deployment {deployment_id}: {e}"
            )

        return 0.0  # Default to UTC if not found

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
        Uses vectorized operations for performance.

        Args:
            values: list with mixed types (bool, int, float, str)

        Returns:
            tuple: (val_dbl_array, val_int_array, val_bool_array, val_str_array, data_type_array)
        """
        # Convert to numpy array for vectorized operations
        values_array = np.asarray(values, dtype=object)
        n = len(values_array)

        # Initialize output arrays
        val_dbl = np.full(n, None, dtype=object)
        val_int = np.full(n, None, dtype=object)
        val_bool = np.full(n, None, dtype=object)
        val_str = np.full(n, None, dtype=object)
        data_type = np.full(n, None, dtype=object)

        # Vectorized type checking using numpy
        # Check for None values
        is_none = np.array([v is None for v in values_array])

        # Check for NaN values (only for float types)
        is_nan = np.array(
            [isinstance(v, (float, np.floating)) and np.isnan(v) for v in values_array]
        )
        is_null = is_none | is_nan

        # Check for boolean (must come before numeric checks)
        is_bool = np.array([isinstance(v, (bool, np.bool_)) for v in values_array])

        # Check for integer (excluding booleans)
        is_int = np.array(
            [
                isinstance(v, (int, np.integer)) and not isinstance(v, (bool, np.bool_))
                for v in values_array
            ]
        )

        # Check for float (excluding NaN)
        is_float = np.array(
            [
                isinstance(v, (float, np.floating)) and np.isfinite(v)
                for v in values_array
            ]
        )

        # Everything else is string
        is_str = ~(is_null | is_bool | is_int | is_float)

        # Populate arrays using boolean indexing
        if np.any(is_null):
            data_type[is_null] = "null"

        if np.any(is_bool):
            val_bool[is_bool] = [bool(v) for v in values_array[is_bool]]
            data_type[is_bool] = "bool"

        if np.any(is_int):
            val_int[is_int] = [int(v) for v in values_array[is_int]]
            data_type[is_int] = "int"

        if np.any(is_float):
            val_dbl[is_float] = [float(v) for v in values_array[is_float]]
            data_type[is_float] = "double"

        if np.any(is_str):
            val_str[is_str] = [str(v) for v in values_array[is_str]]
            data_type[is_str] = "str"

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
        # Use dictionary encoding for repeated metadata to reduce memory overhead
        wide_table = pa.table(
            [
                pa.array([dataset] * len(values)).dictionary_encode(),  # dataset
                pa.array(
                    [metadata["animal"]] * len(values)
                ).dictionary_encode(),  # animal
                pa.array(
                    [str(metadata["deployment"])] * len(values)
                ).dictionary_encode(),  # deployment
                pa.array(
                    [metadata.get("recording")] * len(values)
                ).dictionary_encode(),  # recording (can be None)
                pa.array([group] * len(values)).dictionary_encode(),  # group
                pa.array([class_name] * len(values)).dictionary_encode(),  # class
                pa.array([label] * len(values)).dictionary_encode(),  # label
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
