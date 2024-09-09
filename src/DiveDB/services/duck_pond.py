"""
Delta Lake Manager
"""

import logging
import os
from typing import List

import duckdb
import pyarrow as pa
from deltalake import DeltaTable, write_deltalake

# flake8: noqa


class DuckPond:
    """Delta Lake Manager"""

    delta_path: str = os.getenv("CONTAINER_DELTA_LAKE_PATH")
    delta_lake: DeltaTable | None = None

    def __init__(self, delta_path: str | None = None, connect_to_postgres: bool = True):
        if delta_path:
            self.delta_path = delta_path
        logging.info("Connecting to DuckDB")
        self.conn = duckdb.connect()
        self._create_view()

        if connect_to_postgres:
            logging.info("Connecting to PostgreSQL")
            POSTGRES_CONNECTION_STRING = f"postgresql://{os.environ.get('POSTGRES_USER')}:{os.environ.get('POSTGRES_PASSWORD')}@{os.environ.get('POSTGRES_HOST')}:{os.environ.get('POSTGRES_PORT')}/{os.environ.get('POSTGRES_DB')}"
            pg_connection_string = POSTGRES_CONNECTION_STRING
            self.conn.execute(f"ATTACH 'postgres:{pg_connection_string}' AS Metadata")

    def _create_view(self):
        """Create a view of the delta lake"""
        if os.path.exists(self.delta_path):
            self.conn.sql(
                f"""
                DROP VIEW IF EXISTS DeltaLake;
                CREATE VIEW DeltaLake AS SELECT * FROM delta_scan('{self.delta_path}');
                """
            )

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
        schema_mode: str | None = None,
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
            schema_mode=schema_mode,
        )
        self._create_view()

    def get_db_schema(self):
        """View all tables in the database"""
        return self.conn.sql("SHOW ALL TABLES")

    def close_connection(self):
        """Close the connection to our delta lake"""
        self.conn.close()

    def get_delta_data(
        self,
        signal_names: str | List[str] | None = None,
        logger_ids: str | List[str] | None = None,
        animal_ids: str | List[str] | None = None,
        deployment_ids: str | List[str] | None = None,
        recording_ids: str | List[str] | None = None,
        date_range: tuple[str, str] | None = None,
        limit: int | None = None,
    ):
        """
        Get data from the Delta Lake based on various filters.

        Parameters:
        - signal_names (str | List[str] | None): Filter by signal names.
        - logger_ids (str | List[str] | None): Filter by logger IDs.
        - animal_ids (str | List[str] | None): Filter by animal IDs.
        - deployment_ids (str | List[str] | None): Filter by deployment IDs.
        - recording_ids (str | List[str] | None): Filter by recording IDs.
        - date_range (tuple[str, str] | None): Filter by date range (start_date, end_date).
        - limit (int | None): Limit the number of rows returned.

        Returns:
        - List[tuple]: Query results from the Delta Lake.
        """
        has_predicates = False

        def get_predicate_preface():
            nonlocal has_predicates
            if has_predicates:
                return " AND"
            else:
                has_predicates = True
                return " WHERE"

        def get_predicate_string(predicate: str, values: List[str]):
            if len(values) == 0:
                return ""
            if len(values) == 1:
                return f"{predicate} = '{values[0]}'"
            list_of_values = [f"'{value}'" for value in values]
            return f"{predicate} IN ({', '.join(list_of_values)})"

        if isinstance(signal_names, str):
            signal_names = [signal_names]
        if isinstance(animal_ids, str):
            animal_ids = [animal_ids]
        if isinstance(logger_ids, str):
            logger_ids = [logger_ids]
        if isinstance(animal_ids, str):
            animal_ids = [animal_ids]
        if isinstance(deployment_ids, str):
            deployment_ids = [deployment_ids]
        if isinstance(recording_ids, str):
            recording_ids = [recording_ids]

        query_string = "SELECT "
        if not signal_names or len(signal_names) != 1:
            query_string += "signal_name, "
        query_string += "datetime, data FROM DeltaLake"

        if signal_names:
            query_string += f"{get_predicate_preface()} {get_predicate_string('signal_name', signal_names)}"
        if logger_ids:
            query_string += f"{get_predicate_preface()} {get_predicate_string('logger', logger_ids)}"
        if animal_ids:
            query_string += f"{get_predicate_preface()} {get_predicate_string('animal', animal_ids)}"
        if deployment_ids:
            query_string += f"{get_predicate_preface()} {get_predicate_string('deployment', deployment_ids)}"
        if recording_ids:
            query_string += f"{get_predicate_preface()} {get_predicate_string('recording', recording_ids)}"
        if date_range:
            query_string += f"{get_predicate_preface()} datetime >= '{date_range[0]}' AND datetime <= '{date_range[1]}'"
        if limit:
            query_string += f" LIMIT {limit}"

        logging.info("Running the following query:")
        logging.info(query_string)

        return self.conn.sql(query_string)
