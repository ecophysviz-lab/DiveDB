"""
Delta Lake Manager
"""
import os
import duckdb
import pyarrow
from deltalake import DeltaTable, write_deltalake


class Duck_Lake:
    """Delta Lake Manager"""

    predefined_schemas = {
        "schema1": pyarrow.schema(
            [("id", pyarrow.int32()), ("name", pyarrow.string())]
        ),
        "schema2": pyarrow.schema(
            [("timestamp", pyarrow.timestamp("s")), ("value", pyarrow.float64())]
        ),
    }

    def __init__(self):
        self.delta_path = os.getenv("HOST_DELTA_LAKE_PATH")
        self.delta_table = DeltaTable(self.delta_path)
        self.conn = duckdb.connect()

    def read_from_delta(self, query: str):
        """Read data from our delta lake"""
        return self.conn.execute(query).fetchall()

    def write_to_delta(
        self,
        data,
        schema_name: str,
        mode: str,
        partition_by: list[str],
        name: str,
        description: str,
    ):
        """Write data to our delta lake"""
        if schema_name not in self.predefined_schemas:
            raise ValueError(f"Schema {schema_name} is not predefined.")

        schema = self.predefined_schemas[schema_name]
        write_deltalake(
            table_or_uri=self.delta_path,
            data=data,
            schema=schema,
            partition_by=partition_by,
            mode=mode,
            name=name,
            description=description,
        )

    def get_schema(self):
        """Get the schema of our delta lake"""
        return self.delta_table.schema()

    def close_connection(self):
        """Close the connection to our delta lake"""
        self.conn.close()
