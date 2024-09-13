"""
Delta Lake Manager
"""

import logging
import os
from typing import List, Literal
import duckdb
import pyarrow as pa
from deltalake import DeltaTable, write_deltalake

# from swiftclient import client as swiftclient
from swiftclient.exceptions import ClientException
from DiveDB.services.utils.openstack import SwiftClient

# flake8: noqa

LAKES = [
    "DATA",
    "POINT_EVENTS",
    "STATE_EVENTS",
]

LAKE_CONFIGS = {
    "DATA": {
        "name": "DataLake",
        "path": "s3://divedb-delta-lakes" + "/data",
        "schema": pa.schema(
            [
                pa.field("signal_name", pa.string()),
                pa.field("animal", pa.string()),
                pa.field("deployment", pa.string()),
                pa.field("recording", pa.string()),
                pa.field("data_labels", pa.string()),
                pa.field("datetime", pa.timestamp("us", tz="UTC")),
                pa.field("values", pa.list_(pa.float64())),
            ]
        ),
    },
    "POINT_EVENTS": {
        "name": "PointEventsLake",
        "path": "s3://divedb-delta-lakes" + "/point_events",
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
        "path": "s3://divedb-delta-lakes" + "/state_events",
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

    def __init__(self, delta_path: str | None = None, connect_to_postgres: bool = True):
        self.swift_client = SwiftClient()
        self.delta_path = "s3://divedb-delta-lakes"
        logging.info("Connecting to DuckDB")
        self.conn = duckdb.connect()
        self._authenticate()
        # self._create_lake_views()

        if connect_to_postgres:
            logging.info("Connecting to PostgreSQL")
            POSTGRES_CONNECTION_STRING = f"postgresql://{os.environ.get('POSTGRES_USER')}:{os.environ.get('POSTGRES_PASSWORD')}@{os.environ.get('POSTGRES_HOST')}:{os.environ.get('POSTGRES_PORT')}/{os.environ.get('POSTGRES_DB')}"
            pg_connection_string = POSTGRES_CONNECTION_STRING
            self.conn.execute(f"ATTACH 'postgres:{pg_connection_string}' AS metadata")

    def _authenticate(self):
        """Authenticate with OpenStack Swift"""
        self.conn.execute(f"""
        CREATE SECRET my_secret (
            TYPE S3,
            ENDPOINT 'https://object.cloud.sdsc.edu:443/v1/AUTH_413c350724914abbbb2ece619b2b69d4/',
            KEY_ID '{os.getenv("OPENSTACK_APPLICATION_CREDENTIAL_ID")}',
            SECRET '{os.getenv("OPENSTACK_APPLICATION_CREDENTIAL_SECRET")}',
            REGION 'us-east-1'
        );
        """)

    def _create_lake_views(self, lake: str | None = None):
        """Create a view of the delta lake"""
        if lake:
            lake_config = LAKE_CONFIGS[lake]
            if self._check_path_exists(lake_config["path"]):
                self.conn.sql(
                    f"""
                    DROP VIEW IF EXISTS {lake_config['name']};
                    CREATE VIEW {lake_config['name']} AS SELECT * FROM delta_scan('{lake_config['path']}');
                    """
                )
        else:
            for lake in LAKES:
                lake_config = LAKE_CONFIGS[lake]
                if self._check_path_exists(lake_config["path"]):
                    self.conn.sql(
                        f"""
                        DROP VIEW IF EXISTS {lake_config['name']};
                        CREATE VIEW {lake_config['name']} AS SELECT * FROM delta_scan('{lake_config['path']}');
                        """
                    )

    def _check_path_exists(self, path: str) -> bool:
        """Check if a path exists in the Swift  container or local file system"""
        if path.startswith("s3://"):
            try:
                self.swift_client.client.get_container(path.split("/")[2])
                return True
            except ClientException as e:
                logging.error(f"Swift client error: {e}")
                return False
        else:
            return os.path.exists(path)

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
        import logging
        logging.basicConfig(level=logging.DEBUG)
        self.delta_lake = write_deltalake(
            table_or_uri=LAKE_CONFIGS[lake]["path"],
            data=data,
            schema=LAKE_CONFIGS[lake]["schema"],
            partition_by=partition_by,
            mode=mode,
            name=name,
            description=description,
            schema_mode=schema_mode,
            storage_options={
                "AWS_ENDPOINT_URL": "http://localhost:9000",
                "AWS_ACCESS_KEY_ID": os.getenv("OPENSTACK_APPLICATION_CREDENTIAL_ID"),
                "AWS_SECRET_ACCESS_KEY": os.getenv("OPENSTACK_APPLICATION_CREDENTIAL_SECRET"),
                "AWS_REGION": "us-east-1",
                "AWS_S3_URL_STYLE": "path",
            },
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
        query_string += "datetime, values FROM DataLake"

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

        print("Running the following query:")
        print(query_string)

        results = self.conn.sql(query_string)
        value_index = 2 if len(signal_names) != 1 else 1
        if len(results.fetchone()[value_index]) == 1:
            if len(signal_names) != 1:
                return self.conn.sql(
                    f"""
                    SELECT signal_name, datetime, unnest(values) as value
                    FROM results
                    """
                )
            else:
                return self.conn.sql(
                    f"""
                SELECT datetime, unnest(values) as value
                FROM results
                """
                )
        else:
            return results
