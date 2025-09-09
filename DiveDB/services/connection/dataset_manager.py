"""
Dataset management for DiveDB - handles dataset lifecycle, discovery, and initialization.
"""

import logging
import os
from typing import List, Set, Optional

from pyiceberg.schema import Schema
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import IdentityTransform
from pyiceberg.types import (
    NestedField,
    StringType,
    TimestampType,
    DoubleType,
    BooleanType,
    LongType,
)

from .warehouse_config import WarehouseConfig
from .catalog_manager import CatalogManager
from .duckdb_connection import DuckDBConnection


class DatasetManager:
    """Manages dataset lifecycle: creation, discovery, initialization, and removal"""

    def __init__(
        self,
        config: WarehouseConfig,
        catalog_manager: CatalogManager,
        duckdb_connection: DuckDBConnection,
    ):
        self.config = config
        self.catalog_manager = catalog_manager
        self.catalog = catalog_manager.catalog
        self.duckdb_connection = duckdb_connection

        # Track initialized datasets
        self.initialized_datasets: Set[str] = set()

        # Define lake types and their schemas
        self.lakes = ["data", "events"]

        # Lake schemas
        self.LAKE_SCHEMAS = {
            "data": Schema(
                NestedField(1, "dataset", StringType(), required=True),
                NestedField(2, "animal", StringType(), required=True),
                NestedField(3, "deployment", StringType(), required=True),
                NestedField(4, "recording", StringType(), required=False),
                NestedField(5, "group", StringType(), required=False),
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
            "events": Schema(
                NestedField(1, "dataset", StringType(), required=True),
                NestedField(2, "animal", StringType(), required=True),
                NestedField(3, "deployment", StringType(), required=True),
                NestedField(4, "recording", StringType(), required=False),
                NestedField(5, "group", StringType(), required=False),
                NestedField(6, "event_key", StringType(), required=True),
                NestedField(7, "datetime_start", TimestampType(), required=True),
                NestedField(8, "datetime_end", TimestampType(), required=True),
                NestedField(9, "short_description", StringType(), required=False),
                NestedField(10, "long_description", StringType(), required=False),
                NestedField(11, "event_data", StringType(), required=True),
            ),
        }

    def setup_dataset_tables(self, dataset: str):
        """Create Iceberg tables for a specific dataset"""
        try:
            self.catalog.create_namespace_if_not_exists(dataset)
            logging.info(f"Created/verified namespace: {dataset}")
        except Exception as e:
            logging.debug(f"Namespace {dataset} may already exist: {e}")

        for lake_name in self.lakes:
            table_name = f"{dataset}.{lake_name}"
            try:
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

        self._create_dataset_views(dataset)
        self.initialized_datasets.add(dataset)

    def _create_dataset_views(self, dataset: str):
        """Create DuckDB views for a specific dataset using direct Parquet access"""
        for lake_name in self.lakes:
            table_name = f"{dataset}.{lake_name}"
            # Create dataset-first view names with proper quoting
            if lake_name == "data":
                view_name = f'"{dataset}_Data"'
            elif lake_name == "events":
                view_name = f'"{dataset}_Events"'

            try:
                # Load table and get metadata location
                table = self.catalog.load_table(table_name)

                # Build direct Parquet path instead of using iceberg_scan
                if self.config.use_s3:
                    dataset_db = f"{dataset}.db"
                    # Structure: warehouse/dataset.db/table_type/data/**/*.parquet
                    parquet_path = f"{self.config.warehouse_path}/{dataset_db}/{lake_name}/data/**/*.parquet"
                else:
                    # For local filesystem, construct the file path
                    data_dir = os.path.join(
                        self.config.warehouse_path, f"{dataset}.db", lake_name, "data"
                    )
                    parquet_path = f"file://{os.path.abspath(data_dir)}/**/*.parquet"

                logging.debug(f"Hive-partitioned Parquet path: {parquet_path}")

                # Check if table has any snapshots (data)
                snapshots = table.snapshots()
                if not snapshots:
                    # Create empty placeholder view with correct schema
                    if lake_name == "data":
                        self.duckdb_connection.execute(
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

                        self.duckdb_connection.execute(
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
                        self.duckdb_connection.execute(
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
                        self.duckdb_connection.execute(
                            f"""
                            DROP VIEW IF EXISTS {view_name};
                            CREATE VIEW {view_name} AS
                            SELECT * FROM read_parquet('{parquet_path}', hive_partitioning = true);
                        """
                        )
                    logging.info(f"Created DuckDB view: {view_name}")

            except Exception as e:
                logging.warning(f"Could not create view for {dataset}.{lake_name}: {e}")

    def discover_and_load_existing_datasets(self):
        """
        Discover existing datasets in the Iceberg warehouse and load views for them.
        A dataset is considered valid if it has at least the 'data' table.
        """
        try:
            discovered_datasets = []

            if self.config.use_s3:
                discovered_datasets = self._discover_s3_datasets()
            else:
                discovered_datasets = self._discover_local_datasets()

            logging.info(
                f"Loading views for {len(discovered_datasets)} discovered datasets"
            )
            for dataset in discovered_datasets:
                try:
                    # Set up tables and views for discovered dataset
                    self.setup_dataset_tables(dataset)
                    logging.info(f"Loaded views for dataset: {dataset}")
                except Exception as e:
                    logging.warning(
                        f"Failed to load views for dataset '{dataset}': {e}"
                    )

        except Exception as e:
            logging.warning(f"Failed to discover existing datasets: {e}")
            logging.info("Starting with empty warehouse - no existing datasets found")

    def _discover_local_datasets(self) -> List[str]:
        """Discover datasets by scanning the local filesystem warehouse directory"""
        discovered_datasets = []

        if not os.path.exists(self.config.warehouse_path):
            logging.debug(
                f"Warehouse path does not exist: {self.config.warehouse_path}"
            )
            return discovered_datasets

        try:
            # List directories in warehouse - each directory is potentially a dataset namespace
            for item in os.listdir(self.config.warehouse_path):
                item_path = os.path.join(self.config.warehouse_path, item)

                # Skip files, hidden or system directories
                if (
                    not os.path.isdir(item_path)
                    or item.startswith(".")
                    or item.startswith("_")
                ):
                    continue

                # If directory contains a 'data' subdirectory, it's a dataset
                data_path = os.path.join(item_path, "data")
                if os.path.exists(data_path) and os.path.isdir(data_path):
                    # Remove .db extension if present to get the actual dataset name
                    dataset_name = item[:-3] if item.endswith(".db") else item
                    discovered_datasets.append(dataset_name)
                    logging.info(f"Discovered dataset: {dataset_name}")

        except Exception as e:
            logging.debug(f"Error scanning local warehouse: {e}")

        return discovered_datasets

    def _discover_s3_datasets(self) -> List[str]:
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

    def ensure_dataset_initialized(self, dataset: str):
        """Ensure a dataset's tables and views are initialized"""
        if dataset not in self.initialized_datasets:
            self.setup_dataset_tables(dataset)

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
            elif lake_name == "events":
                view_name = f'"{dataset}_Events"'

            try:
                self.duckdb_connection.execute(f"DROP VIEW IF EXISTS {view_name}")
                logging.info(f"Dropped view: {view_name}")
            except Exception as e:
                logging.warning(f"Could not drop view {view_name}: {e}")

        # Remove from tracking
        self.initialized_datasets.discard(dataset)
        logging.info(f"Removed dataset '{dataset}' from tracking")

    def initialize_datasets(self, datasets: Optional[List[str]] = None):
        """Initialize specific datasets or discover existing ones"""
        if datasets:
            for dataset in datasets:
                self.setup_dataset_tables(dataset)
        else:
            # Auto-discover existing datasets in the warehouse
            self.discover_and_load_existing_datasets()
