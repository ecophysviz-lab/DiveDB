import pytest
from unittest.mock import patch, MagicMock
from services.metadata_manager import MetadataManager, ModelNames


@pytest.fixture
def metadata_manager():
    return MetadataManager()


@patch("services.metadata_manager.Client")
def test_delete_all_records(mock_client, metadata_manager):
    mock_model = MagicMock()
    metadata_manager.models[ModelNames.LOGGER] = mock_model
    metadata_manager.delete_all_records(ModelNames.LOGGER)
    mock_model.objects.all().delete.assert_called_once()


@patch("services.metadata_manager.Client")
def test_convert_notion_to_model_logger(mock_client, metadata_manager):
    notion_data = [
        {
            "properties": {
                "LoggerID": {"title": [{"plain_text": "logger1"}]},
                "SerialNo": {"rich_text": [{"plain_text": "12345"}]},
                "Manufacturer": {"select": {"name": "ABC Corp"}},
                "Type": {"select": {"name": "Type1"}},
                "TypeName": {"select": {"name": "TypeName1"}},
                "Notes": {"rich_text": [{"plain_text": "Some notes"}]},
                "Owner": {"rich_text": [{"plain_text": "Owner1"}]},
                "Icon": {"files": [{"file": {"url": "http://example.com/icon.png"}}]},
            }
        }
    ]
    result = metadata_manager.convert_notion_to_model(notion_data, ModelNames.LOGGER)
    expected = [
        {
            "id": "logger1",
            "serial_no": "12345",
            "manufacturer": "ABC Corp",
            "type": "Type1",
            "type_name": "TypeName1",
            "notes": "Some notes",
            "owner": "Owner1",
            "icon_url": "http://example.com/icon.png",
        }
    ]
    assert result == expected


@patch("services.metadata_manager.Client")
def test_create_logger_records(mock_client, metadata_manager):
    logger_data = [
        {
            "id": "logger1",
            "serial_no": "12345",
            "manufacturer": "ABC Corp",
            "type": "Type1",
            "type_name": "TypeName1",
            "notes": "Some notes",
            "owner": "Owner1",
            "icon_url": "http://example.com/icon.png",
        }
    ]
    with patch("services.metadata_manager.Loggers.objects.create") as mock_create:
        metadata_manager.create_logger_records(logger_data)
        mock_create.assert_called_once_with(**logger_data[0])


@patch("services.metadata_manager.Client")
def test_compare_to_notion(mock_client, metadata_manager):
    mock_client_instance = mock_client.return_value
    mock_client_instance.databases.query.return_value = {
        "results": [{"properties": {"ID": {"unique_id": {"number": 1}}}}]
    }
    with patch("services.metadata_manager.Deployments.objects.all") as mock_all:
        mock_all.return_value.values.return_value = [{"id": 2}]
        metadata_manager.compare_to_notion(ModelNames.DEPLOYMENT)
        # Check the print statements or logs for the expected output


@patch("services.metadata_manager.Client")
def test_seed_from_notion(mock_client, metadata_manager):
    mock_client_instance = mock_client.return_value
    mock_client_instance.pages.retrieve.side_effect = [
        {"properties": {"ID": {"unique_id": {"number": 1}}}},
        {"properties": {"ID": {"unique_id": {"number": 2}}}},
    ]
    with patch("services.metadata_manager.Deployments.objects.create") as mock_create:
        metadata_manager.seed_from_notion(ModelNames.DEPLOYMENT, [1, 2])
        assert mock_create.call_count == 2


@patch("services.metadata_manager.Client")
def test_reset_from_notion(mock_client, metadata_manager):
    mock_client_instance = mock_client.return_value
    mock_client_instance.databases.query.return_value = {
        "results": [{"properties": {"ID": {"unique_id": {"number": 1}}}}]
    }
    with patch(
        "services.metadata_manager.Deployments.objects.create"
    ) as mock_create, patch(
        "services.metadata_manager.MetadataManager.delete_all_records"
    ) as mock_delete:
        metadata_manager.reset_from_notion(ModelNames.DEPLOYMENT)
        mock_delete.assert_called_once_with(ModelNames.DEPLOYMENT)
        mock_create.assert_called_once()
