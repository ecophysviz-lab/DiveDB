"""
Test Delta Lake Class
"""

# import pytest
import pyarrow as pa
from unittest.mock import patch

# from services.duck_pond import DuckPond
# from services.data_uploader import DataUploader


metadata = {
    "animal": "animal1",
    "deployment": "deployment1",
    "logger": "logger1",
    "recording": "recording1",
}


# @pytest.fixture
# def duck_pond():
#     edf_file_paths = [
#         "../data/files/test12_Wednesday_05_DAY1_PROCESSED.edf",
#         "../data/files/test12_Wednesday_05_DAY2_PROCESSED.edf",
#     ]
#     metadata_file_path = "../data/files/Sleep Study Metadata.csv"
#     metadata_map = {
#         "animal": "Nickname",
#         "deployment": "Deployment",
#         "logger": "Logger Used",
#         "recording": "Recording ID",
#     }

#     duck_pond = DuckPond("data/test-delta-lake", connect_to_postgres=False)
#     data_uploader = DataUploader()


def test_init_connection(duck_pond):
    assert duck_pond.conn is not None
    assert duck_pond.conn.execute("SELECT 1").fetchone()[0] == 1


def test_write_to_delta(duck_pond):
    data = pa.table({"column1": [1, 2, 3], "column2": ["a", "b", "c"]})
    schema = pa.schema([("column1", pa.int32()), ("column2", pa.string())])
    mode = "overwrite"
    partition_by = ["column1"]
    name = "test_table"
    description = "Test table description"

    with patch("services.duck_pond.write_deltalake") as mock_write_deltalake:
        duck_pond.write_to_delta(data, schema, mode, partition_by, name, description)
        mock_write_deltalake.assert_called_once_with(
            table_or_uri=duck_pond.delta_path,
            data=data,
            schema=schema,
            partition_by=partition_by,
            mode=mode,
            name=name,
            description=description,
        )


def test_get_delta_data(duck_pond):
    logger_ids = ["logger1", "logger2"]
    animal_ids = ["animal1"]
    deployment_ids = None
    recording_ids = None
    date_range = ("2023-01-01", "2023-12-31")

    # query_string = (
    #     "SELECT datetime, data FROM DeltaLake WHERE "
    #     "logger IN ('logger1', 'logger2') AND "
    #     "animal IN ('animal1') AND "
    #     "datetime BETWEEN '2023-01-01' AND '2023-12-31'"
    # )

    result = duck_pond.get_delta_data(
        logger_ids, animal_ids, deployment_ids, recording_ids, date_range
    )
    assert result
