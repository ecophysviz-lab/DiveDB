"""
Test Delta Lake Class
"""
import os
from unittest.mock import patch, MagicMock
import pytest
from services.delta_lake import Duck_Lake


@pytest.fixture(name="delta_lake")
def delta_lake_instance():
    """Create a delta lake instance"""
    with patch.dict(os.environ, {"HOST_DELTA_LAKE_PATH": "/mock/path"}):
        with patch("services.delta_lake.DeltaTable") as mock_delta_table:
            with patch("services.delta_lake.duckdb.connect") as mock_duckdb_connect:
                mock_conn = MagicMock()
                mock_duckdb_connect.return_value = mock_conn
                mock_delta_table.return_value = MagicMock()
                yield Duck_Lake()


def test_read_from_delta(delta_lake):
    """Test reading from delta lake"""
    # Write data to the delta table
    data = [("row1",), ("row2",)]
    schema_name = "schema1"
    table_name = "test_table"

    with patch("services.delta_lake.write_deltalake"):
        delta_lake.write_to_delta(
            data, schema_name, "overwrite", [], table_name, "Test table"
        )

    # Mock the DuckDB connection to return the written data
    delta_lake.conn.execute.return_value.fetchall.return_value = data

    # Read from the delta table
    query = f"SELECT * FROM {table_name}"
    result = delta_lake.read_from_delta(query)

    # Assert that the correct query was executed
    delta_lake.conn.execute.assert_called_once_with(query)

    # Assert that the result matches the written data
    assert result == data


def test_write_to_delta(delta_lake):
    """Test writing to delta lake"""
    data = [("row1",), ("row2",)]
    schema_name = "schema1"
    mode = "append"
    partition_by = ["id"]
    name = "test_table"
    description = "test description"

    with patch("services.delta_lake.write_deltalake") as mock_write_deltalake:
        delta_lake.write_to_delta(
            data, schema_name, mode, partition_by, name, description
        )
        mock_write_deltalake.assert_called_once_with(
            table_or_uri="/mock/path",
            data=data,
            schema=delta_lake.predefined_schemas[schema_name],
            partition_by=partition_by,
            mode=mode,
            name=name,
            description=description,
        )


def test_write_to_delta_invalid_schema(delta_lake):
    """Test writing to delta lake with invalid schema"""
    data = [("row1",), ("row2",)]
    schema_name = "invalid_schema"
    mode = "append"
    partition_by = ["id"]
    name = "test_table"
    description = "test description"

    with pytest.raises(ValueError, match="Schema invalid_schema is not predefined."):
        delta_lake.write_to_delta(
            data, schema_name, mode, partition_by, name, description
        )


def test_get_schema(delta_lake):
    """Test getting schema"""
    mock_schema = MagicMock()
    delta_lake.delta_table.schema.return_value = mock_schema
    result = delta_lake.get_schema()
    delta_lake.delta_table.schema.assert_called_once()
    assert result == mock_schema


def test_close_connection(delta_lake):
    """Test closing connection"""
    delta_lake.close_connection()
    delta_lake.conn.close.assert_called_once()
