"""
Delta Lake Manager
"""

import logging
import os
from typing import List

import duckdb
import pyarrow as pa
from deltalake import DeltaTable, write_deltalake


class DuckPond:
    """Delta Lake Manager"""

    delta_path: str = os.getenv("CONTAINER_DELTA_LAKE_PATH")
    delta_lake: DeltaTable | None = None

    def __init__(self):
        print("Connecting to DuckDB")
        self.conn = duckdb.connect()

        # print("Installing PostgreSQL extension")
        # self.conn.install_extension("postgres_scanner")

        # print("Loading PostgreSQL extension")
        # self.conn.load_extension("postgres_scanner")

        # print("Connecting to PostgreSQL")
        # POSTGRES_CONNECTION_STRING = f"postgresql://{os.environ.get('POSTGRES_USER')}:{os.environ.get('POSTGRES_PASSWORD')}@{os.environ.get('POSTGRES_HOST')}:{os.environ.get('POSTGRES_PORT')}/{os.environ.get('POSTGRES_DB')}"
        # print(POSTGRES_CONNECTION_STRING)
        # pg_connection_string = POSTGRES_CONNECTION_STRING
        # self.conn.execute(f"ATTACH 'postgres:{pg_connection_string}' AS postgres")

        # logging.info("Registering Delta Lake")
        # self.conn.execute(f"CALL delta_register_table('{self.delta_path}', 'delta_table')")

    def read_from_delta(self, query: str):
        """Read data from our delta lake"""
        return self.conn.execute(query).fetchall()

    def write_to_delta(
        self,
        data: pa.table,
        schema: pa.schema,
        mode: str,
        partition_by: list[str],
        name: str,
        description: str,
    ):
        """Write data to our delta lake"""
        self.delta_lake = write_deltalake(
            table_or_uri=self.delta_path,
            data=data,
            schema=schema,
            partition_by=partition_by,
            mode=mode,
            name=name,
            description=description,
        )

    def write_parquet(self, parquet_files: List[str], **kwargs):
        """Write data to our delta lake"""
        for parquet_path in parquet_files:
            parquet_file = pa.parquet.ParquetFile(parquet_path)
            logging.info(parquet_file.num_row_groups)
            for i in range(parquet_file.num_row_groups):
                row_group = parquet_file.read_row_group(i)
                self.write_to_delta(data=row_group, **kwargs)
                logging.info(
                    f"Streamed row group {i} from {parquet_file} to Delta Lake"
                )

    def query_combined_data(self, query: str):
        """Query data from both Delta Lake and PostgreSQL"""
        return self.conn.execute(query).fetchdf()

    def close_connection(self):
        """Close the connection to our delta lake"""
        self.conn.close()
