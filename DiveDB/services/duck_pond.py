"""
Delta Lake Manager
"""

import logging
import os
import pandas as pd
from typing import List, Literal

import duckdb
import pyarrow as pa
from deltalake import DeltaTable, write_deltalake
from DiveDB.services.utils.sampling import resample

# flake8: noqa

LAKES = [
    "DATA",
    "POINT_EVENTS",
    "STATE_EVENTS",
]

LAKE_CONFIGS = {
    "DATA": {
        "name": "DataLake",
        "path": os.getenv("CONTAINER_DELTA_LAKE_PATH") + "/data",
        "schema": pa.schema(
            [
                pa.field("signal_name", pa.string()),
                pa.field("animal", pa.string()),
                pa.field("deployment", pa.string()),
                pa.field("recording", pa.string()),
                pa.field("data_labels", pa.list_(pa.string())),
                pa.field("datetime", pa.timestamp("us", tz="UTC")),
                pa.field("values", pa.list_(pa.float64())),
            ]
        ),
    },
    "POINT_EVENTS": {
        "name": "PointEventsLake",
        "path": os.getenv("CONTAINER_DELTA_LAKE_PATH") + "/point_events",
        "schema": pa.schema(
            [
                pa.field("animal", pa.string()),
                pa.field("deployment", pa.string()),
                pa.field("recording", pa.string()),
                pa.field("event_key", pa.string()),
                pa.field("datetime", pa.timestamp("us", tz="UTC")),
                pa.field("short_description", pa.string()),
                pa.field("long_description", pa.string()),
            ]
        ),
    },
    "STATE_EVENTS": {
        # TODO: Support these in DataUploader
        "name": "StateEventsLake",
        "path": os.getenv("CONTAINER_DELTA_LAKE_PATH") + "/state_events",
        "schema": pa.schema(
            [
                pa.field("animal", pa.string()),
                pa.field("deployment", pa.string()),
                pa.field("recording", pa.string()),
                pa.field("event_key", pa.string()),
                pa.field("datetime_start", pa.timestamp("us", tz="UTC")),
                pa.field("datetime_end", pa.timestamp("us", tz="UTC")),
                pa.field("short_description", pa.string()),
                pa.field("long_description", pa.string()),
            ]
        ),
    },
}


class DuckPond:
    """Delta Lake Manager"""

    delta_lakes: dict[str, DeltaTable] = {}

    def __init__(self, delta_path: str | None = None, connect_to_postgres: bool = True):
        if delta_path:
            self.delta_path = delta_path
        logging.info("Connecting to DuckDB")
        self.conn = duckdb.connect()
        self._create_lake_views()

        if connect_to_postgres:
            logging.info("Connecting to PostgreSQL")
            POSTGRES_CONNECTION_STRING = f"postgresql://{os.environ.get('POSTGRES_USER')}:{os.environ.get('POSTGRES_PASSWORD')}@{os.environ.get('POSTGRES_HOST')}:{os.environ.get('POSTGRES_PORT')}/{os.environ.get('POSTGRES_DB')}"
            pg_connection_string = POSTGRES_CONNECTION_STRING
            self.conn.execute(f"ATTACH 'postgres:{pg_connection_string}' AS metadata")

    def _create_lake_views(self, lake: str | None = None):
        """Create a view of the delta lake"""
        if lake:
            lake_config = LAKE_CONFIGS[lake]
            if os.path.exists(lake_config["path"]):
                self.conn.sql(
                    f"""
                DROP VIEW IF EXISTS {lake_config['name']};
                CREATE VIEW {lake_config['name']} AS SELECT * FROM delta_scan('{lake_config['path']}');
                """
                )
        else:
            for lake in LAKES:
                lake_config = LAKE_CONFIGS[lake]
                if os.path.exists(lake_config["path"]):
                    self.conn.sql(
                        f"""
                        DROP VIEW IF EXISTS {lake_config['name']};
                        CREATE VIEW {lake_config['name']} AS SELECT * FROM delta_scan('{lake_config['path']}');
                        """
                    )

    def read_from_delta(self, query: str):
        """Read data from our delta lake"""
        return self.conn.execute(query).fetchall()

    def write_to_delta(
        self,
        data: pa.table,
        lake: Literal["DATA", "POINT_EVENTS", "STATE_EVENTS"],
        mode: str,
        partition_by: list[str],
        name: str,
        description: str,
        schema_mode: str | None = None,
    ):
        """Write data to our delta lake"""
        write_deltalake(
            table_or_uri=LAKE_CONFIGS[lake]["path"],
            data=data,
            schema=LAKE_CONFIGS[lake]["schema"],
            partition_by=partition_by,
            mode=mode,
            name=name,
            description=description,
            schema_mode=schema_mode,
        )
        self._create_lake_views(lake)

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
        frequency: int | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame | duckdb.DuckDBPyConnection:
        """
        Get data from the Delta Lake based on various filters.

        Parameters:
        - signal_names (str | List[str] | None): Filter by signal names.
        - logger_ids (str | List[str] | None): Filter by logger IDs.
        - animal_ids (str | List[str] | None): Filter by animal IDs.
        - deployment_ids (str | List[str] | None): Filter by deployment IDs.
        - recording_ids (str | List[str] | None): Filter by recording IDs.
        - date_range (tuple[str, str] | None): Filter by date range (start_date, end_date).
        - frequency (int | None): Filter by frequency (Hz)
        - limit (int | None): Limit the number of rows returned.

        Returns:
        - If frequency is not None, returns a pd.DataFrame.
        - If frequency is None, returns a DuckDBPyConnection object.
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
            return " OR ".join([f"{predicate} = '{value}'" for value in values])

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
        query_string += "signal_name, "
        query_string += "datetime, UNNEST(data_labels) AS label, UNNEST(values) AS value FROM DataLake"

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

        # First query to unnest and get distinct labels
        results = self.conn.sql(query_string)

        labels_query = "SELECT DISTINCT label FROM results"
        labels = [row[0] for row in self.conn.sql(labels_query).fetchall()]

        pivot_query = f"""
            SELECT
                signal_name,
                datetime,
                {', '.join([f"MAX(CASE WHEN label = '{label}' THEN value END) AS {label}" for label in labels])}
            FROM results
            GROUP BY signal_name, datetime
        """
        results = self.conn.sql(pivot_query)

        if frequency:
            # Get dfs for each signal name
            df = results.df()
            signal_dfs = {
                signal_name: df[df["signal_name"] == signal_name]
                for signal_name in signal_names
            }
            # Resample each df to the desired frequency
            # TODO: Figure out why the new index is so wonky
            for signal_name, df in signal_dfs.items():
                df["datetime"] = pd.to_datetime(df["datetime"])
                signal_dfs[signal_name] = resample(df, frequency)
            # Concatenate the dfs
            results = pd.concat(signal_dfs)
            results = results.reset_index()
            results = results.pivot_table(
                index="datetime",
                columns="signal_name",
                values=labels,
            )
            results = results.dropna().reset_index()

        return results
