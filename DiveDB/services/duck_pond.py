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
from DiveDB.services.dive_data import DiveData

# flake8: noqa


class DuckPond:
    """Delta Lake Manager"""

    delta_lakes: dict[str, DeltaTable] = {}

    def __init__(self, delta_path: str, connect_to_postgres: bool = True):
        self.delta_path = delta_path
        self.conn = duckdb.connect()

        self.lakes = [
            "DATA",
            "POINT_EVENTS",
            "STATE_EVENTS",
        ]

        self.LAKE_CONFIGS = {
            "DATA": {
                "name": "DataLake",
                "path": os.path.join(self.delta_path, "data"),
                "schema": pa.schema(
                    [
                        pa.field("animal", pa.string()),
                        pa.field("deployment", pa.string()),
                        pa.field("recording", pa.string()),
                        pa.field("group", pa.string()),
                        pa.field("class", pa.string()),
                        pa.field("label", pa.string()),
                        pa.field("datetime", pa.timestamp("us", tz="UTC")),
                        pa.field(
                            "value",
                            pa.struct(
                                [
                                    pa.field("float", pa.float64(), nullable=True),
                                    pa.field("string", pa.string(), nullable=True),
                                    pa.field("boolean", pa.bool_(), nullable=True),
                                    pa.field("int", pa.int64(), nullable=True),
                                ]
                            ),
                        ),
                    ]
                ),
            },
            "POINT_EVENTS": {
                "name": "PointEventsLake",
                "path": os.path.join(self.delta_path, "point_events"),
                "schema": pa.schema(
                    [
                        pa.field("animal", pa.string()),
                        pa.field("deployment", pa.string()),
                        pa.field("recording", pa.string()),
                        pa.field("group", pa.string()),
                        pa.field("event_key", pa.string()),
                        pa.field("datetime", pa.timestamp("us", tz="UTC")),
                        pa.field("short_description", pa.string(), nullable=True),
                        pa.field("long_description", pa.string(), nullable=True),
                        pa.field("event_data", pa.string()),
                    ]
                ),
            },
            "STATE_EVENTS": {
                "name": "StateEventsLake",
                "path": os.path.join(self.delta_path, "state_events"),
                "schema": pa.schema(
                    [
                        pa.field("animal", pa.string()),
                        pa.field("deployment", pa.string()),
                        pa.field("recording", pa.string()),
                        pa.field("group", pa.string()),
                        pa.field("event_key", pa.string()),
                        pa.field("datetime_start", pa.timestamp("us", tz="UTC")),
                        pa.field("datetime_end", pa.timestamp("us", tz="UTC")),
                        pa.field("short_description", pa.string()),
                        pa.field("long_description", pa.string()),
                        pa.field("event_data", pa.string()),
                    ]
                ),
            },
        }

        if self.delta_path.startswith("s3://"):
            os.environ["AWS_S3_ALLOW_UNSAFE_RENAME"] = "true"

            # Load HTTPFS extension for S3 support
            self.conn.execute("INSTALL httpfs;")
            self.conn.execute("LOAD httpfs;")

            # Set S3 configurations
            self.conn.execute("SET s3_url_style='path';")
            self.conn.execute("SET s3_use_ssl=true;")
            self.conn.execute(
                """
                CREATE SECRET secret1 (
                    TYPE S3,
                    REGION '{}',
                    KEY_ID '{}',
                    SECRET '{}',
                    ENDPOINT '{}'
                );
            """.format(
                    os.getenv("AWS_REGION"),
                    os.getenv("AWS_ACCESS_KEY_ID"),
                    os.getenv("AWS_SECRET_ACCESS_KEY"),
                    os.getenv("AWS_ENDPOINT_URL").replace("https://", ""),
                )
            )

        self._create_lake_views()

        if connect_to_postgres:
            logging.info("Connecting to PostgreSQL")
            POSTGRES_CONNECTION_STRING = f"postgresql://{os.environ.get('POSTGRES_USER')}:{os.environ.get('POSTGRES_PASSWORD')}@{os.environ.get('POSTGRES_HOST')}:{os.environ.get('POSTGRES_PORT')}/{os.environ.get('POSTGRES_DB')}"
            pg_connection_string = POSTGRES_CONNECTION_STRING
            self.conn.execute(f"ATTACH 'postgres:{pg_connection_string}' AS metadata")

    def _create_lake_views(self, lake: str | None = None):
        """Create a view of the delta lake"""
        if lake:
            lake_config = self.LAKE_CONFIGS[lake]
            if lake_config["path"].startswith("s3://") or os.path.exists(
                lake_config["path"]
            ):
                try:
                    self.conn.sql(
                        f"""
                        DROP VIEW IF EXISTS {lake_config['name']};
                        CREATE VIEW {lake_config['name']} AS SELECT * FROM delta_scan('{lake_config['path']}');
                        """
                    )
                except Exception as e:
                    print(e)
        else:
            for lake in self.lakes:
                lake_config = self.LAKE_CONFIGS[lake]
                if lake_config["path"].startswith("s3://") or os.path.exists(
                    lake_config["path"]
                ):
                    try:
                        self.conn.sql(
                            f"""
                        DROP VIEW IF EXISTS {lake_config['name']};
                        CREATE VIEW {lake_config['name']} AS SELECT * FROM delta_scan('{lake_config['path']}');
                        """
                        )
                    except Exception as e:
                        print(e)

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
            table_or_uri=self.LAKE_CONFIGS[lake]["path"],
            data=data,
            schema=self.LAKE_CONFIGS[lake]["schema"],
            partition_by=partition_by,
            mode=mode,
            name=name,
            description=description,
            schema_mode=schema_mode,
        )

    def get_db_schema(self):
        """View all tables in the database"""
        return self.conn.sql("SHOW ALL TABLES")

    def close_connection(self):
        """Close the connection to our delta lake"""
        self.conn.close()

    def get_delta_data(
        self,
        labels: str | List[str] | None = None,
        class_names: str | List[str] | None = None,
        animal_ids: str | List[str] | None = None,
        deployment_ids: str | List[str] | None = None,
        recording_ids: str | List[str] | None = None,
        groups: str | List[str] | None = None,
        classes: str | List[str] | None = None,
        date_range: tuple[str, str] | None = None,
        frequency: int | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame | DiveData:
        """
        Get data from the Delta Lake based on various filters.

        Returns:
        - If frequency is not None, returns a pd.DataFrame.
        - If frequency is None, returns a DuckDBPyRelation object with pivoted data.
        """

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
        if isinstance(class_names, str):
            class_names = [class_names]
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

        # Build the initial SELECT query
        base_query = f"""
            SELECT
                animal,
                deployment,
                recording,
                "group",
                class,
                label,
                datetime,
                value.float AS float_value,
                value.int AS int_value,
                value.boolean AS boolean_value,
                value.string AS string_value
            FROM DataLake
        """

        # Build the WHERE clause
        predicates = []
        if labels:
            predicates.append(get_predicate_string("label", labels))
        if class_names:
            predicates.append(get_predicate_string("class", class_names))
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

        # If labels are not specified, retrieve all distinct labels
        if not labels:
            labels = [
                row[0]
                for row in self.conn.sql(
                    f"SELECT DISTINCT label FROM ({base_query}) AS sub_labels"
                ).fetchall()
            ]

        # Perform pivoting in DuckDB, handling different value types
        pivot_expressions = []
        for label in labels:
            pivot_expressions.append(
                f"""
                MAX(CASE WHEN label = '{label}' THEN float_value END) AS "{label}_float",
                MAX(CASE WHEN label = '{label}' THEN int_value END) AS "{label}_int",
                MAX(CASE WHEN label = '{label}' THEN boolean_value END) AS "{label}_bool",
                MAX(CASE WHEN label = '{label}' THEN string_value END) AS "{label}_str"
            """
            )

        pivot_query = f"""
            SELECT
                datetime, recording, class,
                {', '.join(pivot_expressions)}
            FROM ({base_query}) AS sub
            GROUP BY datetime, recording, class
            ORDER BY datetime
        """

        # Execute the pivot query and materialize the results
        self.conn.execute("DROP TABLE IF EXISTS pivot_results")
        self.conn.execute(f"CREATE TEMPORARY TABLE pivot_results AS {pivot_query}")

        # Determine the best column for each label based on the presence of NaNs
        best_columns = []
        for label in labels:
            nan_counts_query = f"""
                SELECT
                    SUM(CASE WHEN "{label}_float" IS NULL THEN 1 ELSE 0 END) AS nan_count_float,
                    SUM(CASE WHEN "{label}_int" IS NULL THEN 1 ELSE 0 END) AS nan_count_int,
                    SUM(CASE WHEN "{label}_bool" IS NULL THEN 1 ELSE 0 END) AS nan_count_bool,
                    SUM(CASE WHEN "{label}_str" IS NULL THEN 1 ELSE 0 END) AS nan_count_str
                FROM pivot_results
            """
            nan_counts = self.conn.execute(nan_counts_query).fetchone()
            nan_counts = [
                count if count is not None else float("inf") for count in nan_counts
            ]
            best_type = min(
                zip(["float", "int", "bool", "str"], nan_counts), key=lambda x: x[1]
            )[0]
            best_columns.append(f"{label}_{best_type} AS {label}")

        # Keep only the best columns, the required metadata columns, and the datetime column
        final_query = f"""
            SELECT datetime, class, recording, {', '.join(best_columns)}
            FROM pivot_results
        """
        results = self.conn.sql(final_query)

        if frequency:
            # Pull data into memory for resampling
            df = results.df()
            df = df.drop(['recording', 'class'], axis=1)

            # Ensure 'datetime' is in datetime format
            df["datetime"] = pd.to_datetime(df["datetime"])

            # Set 'datetime' as index for resampling
            df.set_index("datetime", inplace=True)

            # Resample the data
            resample_period = pd.to_timedelta(1 / frequency, unit="s")
            df_resampled = (
                df.resample(resample_period).mean().dropna(how="all").reset_index()
            )

            return df_resampled
        else:
            # Return the DuckDB relation without pulling data into memory
            return DiveData(results, self.conn)
