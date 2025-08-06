"""
DuckPond - Apache Iceberg data lake interface (formerly Delta Lake)
"""

import logging
import os
from typing import List, Literal, Dict, Optional

import duckdb
import pyarrow as pa
import pandas as pd
from pyiceberg.catalog.sql import SqlCatalog
from pyiceberg.schema import Schema
from pyiceberg.types import (
    NestedField,
    StringType,
    TimestampType,
    DoubleType,
    BooleanType,
    LongType,
)
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import IdentityTransform

from DiveDB.services.notion_orm import NotionORMManager
from DiveDB.services.dive_data import DiveData
from DiveDB.services.utils.sampling import resample


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
    ):
        # Validate configuration
        self.use_s3 = bool(
            s3_endpoint and s3_access_key and s3_secret_key and s3_bucket
        )

        if self.use_s3:
            # S3 configuration
            self.s3_endpoint = s3_endpoint
            self.s3_access_key = s3_access_key
            self.s3_secret_key = s3_secret_key
            self.s3_bucket = s3_bucket
            self.s3_region = s3_region
            self.warehouse_path = f"s3://{s3_bucket}/iceberg-warehouse"
            logging.info(f"Using S3 backend: {self.s3_endpoint}")
        else:
            # Local filesystem configuration
            if not warehouse_path:
                warehouse_path = "./local_iceberg_warehouse"
                logging.info(
                    "No warehouse_path provided, using default: ./local_iceberg_warehouse"
                )
            self.warehouse_path = warehouse_path
            logging.info(f"Using local filesystem backend: {self.warehouse_path}")

        self.conn = duckdb.connect()

        # Install and load extensions
        try:
            self.conn.execute("INSTALL iceberg;")
            self.conn.execute("LOAD iceberg;")

            if self.use_s3:
                # Install and load S3 extension for DuckDB
                self.conn.execute("INSTALL httpfs;")  # Required for S3
                self.conn.execute("LOAD httpfs;")
                logging.info("Loaded DuckDB S3 extensions")
        except Exception as e:
            logging.warning(f"Could not load extensions: {e}")

        # Create catalog (local filesystem or S3-based)
        if self.use_s3:
            # S3-based catalog configuration for PyIceberg
            # Use local persistent SQLite for catalog metadata, S3 for data storage
            catalog_db_path = os.path.join(
                os.path.expanduser("~"), ".iceberg", "s3_catalog.db"
            )
            os.makedirs(os.path.dirname(catalog_db_path), exist_ok=True)

            self.catalog = SqlCatalog(
                "s3_catalog",
                **{
                    "uri": f"sqlite:///{catalog_db_path}",
                    "warehouse": self.warehouse_path,  # s3://bucket/iceberg-warehouse
                    "s3.endpoint": self.s3_endpoint,
                    "s3.access-key-id": self.s3_access_key,
                    "s3.secret-access-key": self.s3_secret_key,
                    "s3.region": self.s3_region,
                },
            )

            # Configure DuckDB S3 settings for Ceph compatibility
            self.conn.execute(
                f"SET s3_endpoint='{self.s3_endpoint.replace('https://', '')}';"
            )
            self.conn.execute(f"SET s3_access_key_id='{self.s3_access_key}';")
            self.conn.execute(f"SET s3_secret_access_key='{self.s3_secret_key}';")
            self.conn.execute(f"SET s3_region='{self.s3_region}';")
            # Additional settings for Ceph/MinIO compatibility
            self.conn.execute("SET s3_use_ssl=true;")  # Enable SSL for security
            self.conn.execute("SET s3_url_style='path';")  # Path-style URLs for Ceph

            logging.info(
                f"Configured DuckDB S3 settings for Ceph compatibility: {self.s3_endpoint}"
            )

        else:
            catalog_db_path = os.path.join(self.warehouse_path, "catalog.db")
            os.makedirs(self.warehouse_path, exist_ok=True)

            self.catalog = SqlCatalog(
                "local",
                **{
                    "uri": f"sqlite:///{catalog_db_path}",  # Persistent SQLite file
                    "warehouse": f"file://{os.path.abspath(self.warehouse_path)}",
                },
            )

        # Initialize Notion ORM manager
        if notion_manager:
            self.notion_manager = notion_manager
        elif notion_db_map and notion_token:
            self.notion_manager = NotionORMManager(notion_db_map, notion_token)
        else:
            self.notion_manager = None

        # Track Notion table names
        self._notion_table_names = []

        # Track initialized datasets
        self.initialized_datasets = set()

        self.lakes = [
            "data",
            "point_events",
            "state_events",
        ]

        # Lake schemas
        self.LAKE_SCHEMAS = {
            "data": Schema(
                NestedField(1, "dataset", StringType(), required=True),
                NestedField(2, "animal", StringType(), required=True),
                NestedField(3, "deployment", StringType(), required=True),
                NestedField(4, "recording", StringType(), required=False),
                NestedField(5, "group", StringType(), required=True),
                NestedField(6, "class", StringType(), required=True),
                NestedField(7, "label", StringType(), required=True),
                NestedField(8, "datetime", TimestampType(), required=True),
                NestedField(9, "val_dbl", DoubleType(), required=False),
                NestedField(10, "val_int", LongType(), required=False),
                NestedField(11, "val_bool", BooleanType(), required=False),
                NestedField(12, "val_str", StringType(), required=False),
                NestedField(
                    13, "data_type", StringType(), required=True
                ),  # 'double', 'int', 'bool', 'str'
            ),
            "point_events": Schema(
                NestedField(1, "dataset", StringType(), required=True),
                NestedField(2, "animal", StringType(), required=True),
                NestedField(3, "deployment", StringType(), required=True),
                NestedField(4, "recording", StringType(), required=False),
                NestedField(5, "group", StringType(), required=True),
                NestedField(6, "event_key", StringType(), required=True),
                NestedField(7, "datetime", TimestampType(), required=True),
                NestedField(8, "short_description", StringType(), required=False),
                NestedField(9, "long_description", StringType(), required=False),
                NestedField(10, "event_data", StringType(), required=True),
            ),
            "state_events": Schema(
                NestedField(1, "dataset", StringType(), required=True),
                NestedField(2, "animal", StringType(), required=True),
                NestedField(3, "deployment", StringType(), required=True),
                NestedField(4, "recording", StringType(), required=False),
                NestedField(5, "group", StringType(), required=True),
                NestedField(6, "event_key", StringType(), required=True),
                NestedField(7, "datetime_start", TimestampType(), required=True),
                NestedField(8, "datetime_end", TimestampType(), required=True),
                NestedField(9, "short_description", StringType(), required=True),
                NestedField(10, "long_description", StringType(), required=True),
                NestedField(11, "event_data", StringType(), required=True),
            ),
        }

        # Initialize datasets if provided, otherwise discover existing ones
        if datasets:
            for dataset in datasets:
                self._setup_dataset_tables(dataset)
        else:
            # Auto-discover existing datasets in the warehouse
            self._discover_and_load_existing_datasets()

        # Load Notion databases if available
        if self.notion_manager:
            self._load_notion_databases()

    def _setup_dataset_tables(self, dataset: str):
        """Create Iceberg tables for a specific dataset"""
        # Create namespace for dataset
        try:
            self.catalog.create_namespace_if_not_exists(dataset)
            logging.info(f"Created/verified namespace: {dataset}")
        except Exception as e:
            logging.debug(f"Namespace {dataset} may already exist: {e}")

        # Create tables with updated partitioning (no dataset field needed since it's the namespace)
        for lake_name in self.lakes:
            table_name = f"{dataset}.{lake_name}"
            try:
                # Updated partition spec - remove dataset since it's now the namespace
                partition_spec = PartitionSpec(
                    PartitionField(
                        source_id=2,  # animal field (now becomes first partition field)
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
                )

                self.catalog.create_table_if_not_exists(
                    identifier=table_name,
                    schema=self.LAKE_SCHEMAS[lake_name],
                    partition_spec=partition_spec,
                )
                logging.info(f"Created/loaded Iceberg table: {table_name}")

            except Exception as e:
                logging.error(f"Failed to create table {table_name}: {e}")

        # Create views for this dataset
        self._create_dataset_views(dataset)

        # Track this dataset as initialized
        self.initialized_datasets.add(dataset)

    def _discover_and_load_existing_datasets(self):
        """
        Discover existing datasets in the Iceberg warehouse and load views for them.
        A dataset is considered valid if it has at least the 'data' table.
        """
        try:
            discovered_datasets = []

            if self.use_s3:
                discovered_datasets = self._discover_s3_datasets()
            else:
                discovered_datasets = self._discover_local_datasets()

            logging.info(
                f"Loading views for {len(discovered_datasets)} discovered datasets"
            )
            for dataset in discovered_datasets:
                try:
                    # Set up tables and views for discovered dataset
                    self._setup_dataset_tables(dataset)
                    logging.info(f"Loaded views for dataset: {dataset}")
                except Exception as e:
                    logging.warning(
                        f"Failed to load views for dataset '{dataset}': {e}"
                    )

        except Exception as e:
            logging.warning(f"Failed to discover existing datasets: {e}")
            logging.info("Starting with empty warehouse - no existing datasets found")

    def _discover_local_datasets(self):
        """Discover datasets by scanning the local filesystem warehouse directory"""

        discovered_datasets = []

        if not os.path.exists(self.warehouse_path):
            logging.debug(f"Warehouse path does not exist: {self.warehouse_path}")
            return discovered_datasets

        try:
            # List directories in warehouse - each directory is potentially a dataset namespace
            for item in os.listdir(self.warehouse_path):
                item_path = os.path.join(self.warehouse_path, item)

                # Skip files, hidden or system directories
                if (
                    not os.path.isdir(item_path)
                    or item.startswith(".")
                    or item.startswith("_")
                ):
                    continue

                # Check if this directory contains a 'data' subdirectory (indicating a dataset)
                data_path = os.path.join(item_path, "data")
                if os.path.exists(data_path) and os.path.isdir(data_path):
                    # Remove .db extension if present to get the actual dataset name
                    dataset_name = item[:-3] if item.endswith(".db") else item
                    discovered_datasets.append(dataset_name)
                    logging.info(f"Discovered dataset: {dataset_name}")

        except Exception as e:
            logging.debug(f"Error scanning local warehouse: {e}")

        return discovered_datasets

    def _discover_s3_datasets(self):
        """Discover datasets in S3 warehouse (limited by catalog capabilities)"""
        discovered_datasets = []

        try:
            # Try to list namespaces through catalog
            namespaces = self.catalog.list_namespaces()
            logging.info(f"Found {len(namespaces)} namespaces in S3 warehouse")

            for namespace_tuple in namespaces:
                # Namespace comes as a tuple, convert to string
                namespace = (
                    namespace_tuple[0]
                    if isinstance(namespace_tuple, tuple)
                    else str(namespace_tuple)
                )

                # Skip empty or system namespaces
                if not namespace or namespace.startswith("_"):
                    continue

                # Check if this namespace has our expected tables
                tables = self.catalog.list_tables(namespace)
                table_names = [
                    table[1] if isinstance(table, tuple) else str(table)
                    for table in tables
                ]

                # A dataset must have at least the 'data' table
                if "data" in table_names:
                    discovered_datasets.append(namespace)
                    logging.info(f"Discovered S3 dataset: {namespace}")

        except Exception as e:
            logging.debug(f"Error discovering S3 datasets through catalog: {e}")

        return discovered_datasets

    def _create_dataset_views(self, dataset: str):
        """Create DuckDB views for a specific dataset using direct Parquet access"""
        for lake_name in self.lakes:
            table_name = f"{dataset}.{lake_name}"
            # Create dataset-first view names with proper quoting
            if lake_name == "data":
                view_name = f'"{dataset}_Data"'
            elif lake_name == "point_events":
                view_name = f'"{dataset}_PointEvents"'
            elif lake_name == "state_events":
                view_name = f'"{dataset}_StateEvents"'

            try:
                # Load table and get metadata location
                table = self.catalog.load_table(table_name)

                # Build direct Parquet path instead of using iceberg_scan
                if self.use_s3:
                    # For S3, construct the data path
                    dataset_db = f"{dataset}.db"
                    # Structure: warehouse/dataset.db/table_type/data/**/*.parquet
                    parquet_path = f"{self.warehouse_path}/{dataset_db}/{lake_name}/data/**/*.parquet"
                else:
                    # For local filesystem, construct the file path
                    data_dir = os.path.join(
                        self.warehouse_path, f"{dataset}.db", lake_name, "data"
                    )
                    parquet_path = f"file://{os.path.abspath(data_dir)}/**/*.parquet"

                logging.debug(f"Hive-partitioned Parquet path: {parquet_path}")

                # Check if table has any snapshots (data)
                snapshots = table.snapshots()
                if not snapshots:
                    # Create empty placeholder view with correct schema
                    if lake_name == "data":
                        self.conn.execute(
                            f"""
                            DROP VIEW IF EXISTS {view_name};
                            CREATE VIEW {view_name} AS
                            SELECT
                                CAST(NULL AS VARCHAR) as dataset,
                                CAST(NULL AS VARCHAR) as animal,
                                CAST(NULL AS VARCHAR) as deployment,
                                CAST(NULL AS VARCHAR) as recording,
                                CAST(NULL AS VARCHAR) as "group",
                                CAST(NULL AS VARCHAR) as class,
                                CAST(NULL AS VARCHAR) as label,
                                CAST(NULL AS TIMESTAMP) as datetime,
                                CAST(NULL AS DOUBLE) as value,
                                CAST(NULL AS DOUBLE) as float_value,
                                CAST(NULL AS BIGINT) as int_value,
                                CAST(NULL AS BOOLEAN) as boolean_value,
                                CAST(NULL AS VARCHAR) as string_value
                            WHERE FALSE;
                        """
                        )
                    else:
                        # Create empty placeholder for events tables
                        schema_fields = self.LAKE_SCHEMAS[lake_name].fields
                        select_fields = []
                        for field in schema_fields:
                            if field.field_type == StringType():
                                select_fields.append(
                                    f"CAST(NULL AS VARCHAR) as {field.name}"
                                )
                            elif field.field_type == TimestampType():
                                select_fields.append(
                                    f"CAST(NULL AS TIMESTAMP) as {field.name}"
                                )
                            else:
                                select_fields.append(
                                    f"CAST(NULL AS VARCHAR) as {field.name}"
                                )

                        self.conn.execute(
                            f"""
                            DROP VIEW IF EXISTS {view_name};
                            CREATE VIEW {view_name} AS
                            SELECT {', '.join(select_fields)}
                            WHERE FALSE;
                        """
                        )
                    logging.info(f"Created empty placeholder view: {view_name}")
                else:
                    # Table has data, use read_parquet with hive_partitioning
                    if lake_name == "data":
                        # Create view that converts wide format back to single value column
                        self.conn.execute(
                            f"""
                            DROP VIEW IF EXISTS {view_name};
                            CREATE VIEW {view_name} AS
                            SELECT
                                dataset,
                                animal,
                                deployment,
                                recording,
                                "group",
                                class,
                                label,
                                datetime,
                                CASE data_type
                                    WHEN 'double' THEN val_dbl
                                    WHEN 'int' THEN CAST(val_int AS DOUBLE)
                                    WHEN 'bool' THEN CAST(val_bool AS DOUBLE)
                                    WHEN 'str' THEN TRY_CAST(val_str AS DOUBLE)
                                    ELSE NULL
                                END as value,
                                -- Also expose individual typed columns for new queries
                                val_dbl as float_value,
                                val_int as int_value,
                                val_bool as boolean_value,
                                val_str as string_value,
                                data_type
                            FROM read_parquet('{parquet_path}', hive_partitioning = true);
                        """
                        )
                    else:
                        # For events tables, create simple pass-through view
                        self.conn.execute(
                            f"""
                            DROP VIEW IF EXISTS {view_name};
                            CREATE VIEW {view_name} AS
                            SELECT * FROM read_parquet('{parquet_path}', hive_partitioning = true);
                        """
                        )
                    logging.info(f"Created DuckDB view: {view_name}")

            except Exception as e:
                logging.warning(f"Could not create view for {dataset}.{lake_name}: {e}")

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
        import os

        # Check for S3 configuration first
        s3_endpoint = os.getenv("S3_ENDPOINT")
        s3_access_key = os.getenv("S3_ACCESS_KEY")
        s3_secret_key = os.getenv("S3_SECRET_KEY")
        s3_bucket = os.getenv("S3_BUCKET")
        s3_region = os.getenv("S3_REGION", "us-east-1")

        # Check for local warehouse path (support both env var names for compatibility)
        warehouse_path = os.getenv("LOCAL_ICEBERG_PATH") or os.getenv(
            "CONTAINER_ICEBERG_PATH"
        )

        return cls(
            warehouse_path=warehouse_path if not s3_endpoint else None,
            s3_endpoint=s3_endpoint,
            s3_access_key=s3_access_key,
            s3_secret_key=s3_secret_key,
            s3_bucket=s3_bucket,
            s3_region=s3_region,
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
                        source_id=1,  # dataset field
                        field_id=1000,
                        transform=IdentityTransform(),
                        name="dataset",
                    ),
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
        lake: Literal["data", "point_events", "state_events"],
        dataset: str,
        mode: str = "append",
    ):
        """Write data to dataset-specific Iceberg table"""
        # Ensure dataset is initialized
        self.ensure_dataset_initialized(dataset)

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
            self._create_dataset_views(dataset)

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
    ):
        """
        Get data from a specific dataset using direct Parquet access (bypassing Iceberg layer).

        Args:
            dataset: Dataset identifier (required)
            ... (other parameters unchanged)

        Returns:
        - If frequency is not None, returns a pd.DataFrame.
        - If frequency is None, returns a DiveData object with pivoted data.
        """

        # Ensure dataset is initialized
        self.ensure_dataset_initialized(dataset)

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

        # Execute query and get results as DuckDB relation
        results = self.conn.sql(base_query)

        if frequency:
            # Pull data into memory for resampling
            df = results.df()
            df = df.drop(["recording", "class"], axis=1)

            df_resampled = resample(df, frequency)

            return df_resampled
        else:
            # Return the DuckDB relation without pulling data into memory
            return DiveData(results, self.conn, notion_manager=self.notion_manager)

    def ensure_dataset_initialized(self, dataset: str):
        """Ensure a dataset's tables and views are initialized"""
        if dataset not in self.initialized_datasets:
            self._setup_dataset_tables(dataset)

    def get_all_datasets(self) -> List[str]:
        """Get list of all initialized datasets"""
        return list(self.initialized_datasets)

    def list_dataset_tables(self, dataset: str) -> List[str]:
        """List tables for a specific dataset"""
        if dataset not in self.initialized_datasets:
            return []
        return [f"{dataset}.{lake}" for lake in self.lakes]

    def dataset_exists(self, dataset: str) -> bool:
        """Check if a dataset has been initialized"""
        return dataset in self.initialized_datasets

    def remove_dataset(self, dataset: str):
        """Remove a dataset and all its tables (use with caution!)"""
        if dataset not in self.initialized_datasets:
            logging.warning(f"Dataset '{dataset}' not found in initialized datasets")
            return

        # Drop tables
        for lake_name in self.lakes:
            table_name = f"{dataset}.{lake_name}"
            try:
                self.catalog.drop_table(table_name)
                logging.info(f"Dropped table: {table_name}")
            except Exception as e:
                logging.warning(f"Could not drop table {table_name}: {e}")

        # Drop views
        for lake_name in self.lakes:
            if lake_name == "data":
                view_name = f'"{dataset}_Data"'
            elif lake_name == "point_events":
                view_name = f'"{dataset}_PointEvents"'
            elif lake_name == "state_events":
                view_name = f'"{dataset}_StateEvents"'

            try:
                self.conn.execute(f"DROP VIEW IF EXISTS {view_name}")
                logging.info(f"Dropped view: {view_name}")
            except Exception as e:
                logging.warning(f"Could not drop view {view_name}: {e}")

        # Remove from tracking
        self.initialized_datasets.discard(dataset)
        logging.info(f"Removed dataset '{dataset}' from tracking")

    def get_view_name(self, dataset: str, table_type: str) -> str:
        """
        Get the properly quoted view name for a dataset and table type.

        Args:
            dataset: Dataset identifier (e.g., "EP Physiology")
            table_type: Type of table - "data", "point_events", or "state_events"

        Returns:
            Quoted view name ready for SQL queries

        Examples:
            >>> duck_pond.get_view_name("EP Physiology", "data")
            '"EP Physiology_Data"'
            >>> duck_pond.get_view_name("EP Physiology", "point_events")
            '"EP Physiology_PointEvents"'
        """
        if table_type == "data":
            return f'"{dataset}_Data"'
        elif table_type == "point_events":
            return f'"{dataset}_PointEvents"'
        elif table_type == "state_events":
            return f'"{dataset}_StateEvents"'
        else:
            raise ValueError(
                f"Invalid table_type: {table_type}. Must be 'data', 'point_events', or 'state_events'"
            )

    def get_db_schema(self):
        """View all tables in the database"""
        return self.conn.sql("SHOW ALL TABLES")

    def list_all_views(self) -> List[str]:
        """
        List all dataset views in the warehouse.

        Returns:
            List of view names for all initialized datasets

        Examples:
            >>> duck_pond.list_all_views()
            ['"EP Physiology_Data"', '"EP Physiology_PointEvents"', '"EP Physiology_StateEvents"',
             '"Pilot Study_Data"', '"Pilot Study_PointEvents"', '"Pilot Study_StateEvents"']
        """
        all_views = []
        for dataset in self.initialized_datasets:
            for table_type in ["data", "point_events", "state_events"]:
                all_views.append(self.get_view_name(dataset, table_type))
        return sorted(all_views)

    def list_dataset_views(self, dataset: str) -> List[str]:
        """
        List all views for a specific dataset.

        Args:
            dataset: Dataset identifier

        Returns:
            List of view names for the specified dataset

        Examples:
            >>> duck_pond.list_dataset_views("EP Physiology")
            ['"EP Physiology_Data"', '"EP Physiology_PointEvents"', '"EP Physiology_StateEvents"']
        """
        if dataset not in self.initialized_datasets:
            return []

        return [
            self.get_view_name(dataset, table_type)
            for table_type in ["data", "point_events", "state_events"]
        ]

    def test_s3_connectivity(self):
        """Test S3 connectivity and direct Parquet access"""
        if not self.use_s3:
            return {"status": "skipped", "reason": "Not using S3 backend"}

        try:
            # Test basic S3 connectivity
            test_query = "SELECT 1 as test_value"
            result = self.conn.sql(test_query).df()

            # Test S3 configuration
            settings = {}
            for setting in ["s3_endpoint", "s3_region", "s3_access_key_id"]:
                try:
                    setting_result = self.conn.sql(
                        f"SELECT current_setting('{setting}') as value"
                    ).df()
                    settings[setting] = setting_result.iloc[0]["value"]
                except Exception:
                    settings[setting] = "not_set"

            return {
                "status": "success",
                "basic_query": len(result) > 0,
                "s3_settings": settings,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def close_connection(self):
        """Close the connection"""
        self.conn.close()

    def _load_notion_databases(self):
        """Load all available Notion databases into DuckDB tables"""
        if not self.notion_manager:
            return

        try:
            # Get all available database names from the notion manager
            for db_map_key, db_id in self.notion_manager.db_map.items():
                try:
                    model_name = None

                    # Try different model names to see which one results in our db_map_key
                    possible_model_names = [
                        db_map_key.replace(" DB", ""),  # Remove " DB" suffix
                        db_map_key.replace(" DB", "") + "s",  # Remove " DB" and add "s"
                        db_map_key,  # Try the key directly
                    ]

                    for candidate in possible_model_names:
                        # Simulate the get_model transformation
                        test_db_name = (
                            f"{candidate} DB"
                            if not candidate.endswith(" DB")
                            else candidate
                        )
                        test_db_name = test_db_name.replace("s DB", " DB")

                        if test_db_name == db_map_key:
                            model_name = candidate
                            break

                    if not model_name:
                        logging.warning(
                            f"Could not determine model name for database '{db_map_key}'"
                        )
                        continue

                    # Now use the existing get_model logic
                    model = self.notion_manager.get_model(model_name)

                    # Query all data from the model
                    records = model.objects.all()

                    if records:
                        data_rows = []
                        for record in records:
                            row_data = {"id": record.id}

                            # Get all properties that were parsed by NotionModel._from_notion_page
                            for prop_name in record._meta.schema.keys():
                                if hasattr(record, prop_name):
                                    value = getattr(record, prop_name)
                                    # Handle different value types
                                    if value is not None:
                                        attr_name = prop_name.replace(" ", "_").lower()
                                        if isinstance(value, (list, dict)):
                                            row_data[attr_name] = str(
                                                value
                                            )  # Use transformed name for column
                                        else:
                                            row_data[attr_name] = (
                                                value  # Use transformed name for column
                                            )
                                    else:
                                        row_data[attr_name] = None

                            data_rows.append(row_data)

                        # Create DuckDB table - use db_map key directly as table name
                        table_name = model_name + "s"
                        self.conn.execute(f"DROP TABLE IF EXISTS {table_name}")
                        df = pd.DataFrame(data_rows)
                        self.conn.register(table_name, df)

                        # Track this table name
                        self._notion_table_names.append(table_name)

                        logging.info(
                            f"Loaded Notion database '{db_map_key}' into DuckDB table '{table_name}' with {len(df)} records"
                        )

                except Exception as e:
                    logging.warning(
                        f"Failed to load Notion database '{db_map_key}': {e}"
                    )
                    continue

        except Exception as e:
            logging.error(f"Error loading Notion databases: {e}")

    def list_notion_tables(self) -> List[str]:
        """List all available Notion tables in DuckDB"""
        if not self.notion_manager:
            return []

        return self._notion_table_names.copy()

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

    def write_sensor_data(
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
        Write sensor data using the new wide format.
        High-level method for writing sensor data to the Iceberg data lake.

        Args:
            dataset: Dataset identifier (new field!)
            metadata: Dict with 'animal', 'deployment', 'recording' keys
            times: PyArrow timestamp array
            group: Data group (e.g., 'sensor_data')
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
