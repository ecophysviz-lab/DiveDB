from unittest.mock import MagicMock, patch

import pytest

from DiveDB.services.metadata_manager import MetadataManager, ModelNames


@pytest.fixture
def metadata_manager():
    return MetadataManager()


def test_delete_all_records(metadata_manager):
    mock_model = MagicMock()
    metadata_manager.models[ModelNames.LOGGER] = mock_model
    metadata_manager.delete_all_records(ModelNames.LOGGER)
    mock_model.objects.all().delete.assert_called_once()


def test_convert_notion_to_model_logger(metadata_manager):
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


def test_create_logger_records(metadata_manager):
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
