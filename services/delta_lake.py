"""
Delta Lake Manager
"""
import os
import duckdb
import pyarrow as pa
from deltalake import DeltaTable, write_deltalake
from typing import List
import logging


class Duck_Lake:
    """Delta Lake Manager"""
    delta_path: str = os.getenv("CONTAINER_DELTA_LAKE_PATH")
    delta_lake: DeltaTable | None = None
    
    conn = duckdb.connect()

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

        
    def write_parquet_to_delta(
        self,
        parquet_files: List[str],
        **kwargs
    ):
        """Write data to our delta lake"""
        for parquet_path in parquet_files:
            parquet_file = pa.parquet.ParquetFile(parquet_path)
            logging.info(parquet_file.num_row_groups)
            for i in range(parquet_file.num_row_groups):
                row_group = parquet_file.read_row_group(i)
                self.write_to_delta(
                    data=row_group,
                    **kwargs
                )
                logging.info(f"Streamed row group {i} from {parquet_file} to Delta Lake")

    @staticmethod
    def get_schema():
        """Get the schema of our delta lake"""
        return Duck_Lake.delta_table.schema()

    def close_connection(self):
        """Close the connection to our delta lake"""
        self.conn.close()
