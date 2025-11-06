"""
Tests for the NotionORM module.

This module tests the functionality of the NotionORM, including:
- Model creation and schema introspection
- Query building and filtering
- Property parsing
- Relationship traversal
"""

import datetime
import pytest

from DiveDB.services.notion_orm import NotionORMManager


@pytest.fixture
def mock_notion_client(mocker):
    """Fixture that provides a mocked Notion client."""
    mock_client = mocker.patch("DiveDB.services.notion_orm.Client")

    # Mock the database schema response
    mock_db_response = {
        "properties": {
            "Animal ID": {"id": "animalid", "type": "title", "title": {}},
            "Common Name": {"id": "commonname", "type": "rich_text", "rich_text": {}},
            "Species": {
                "id": "species",
                "type": "select",
                "select": {"options": [{"name": "Seal"}, {"name": "Dolphin"}]},
            },
            "Birth Date": {"id": "birthdate", "type": "date", "date": {}},
            "Weight": {
                "id": "weight",
                "type": "number",
                "number": {"format": "number"},
            },
            "Tags": {
                "id": "tags",
                "type": "multi_select",
                "multi_select": {"options": [{"name": "Wild"}, {"name": "Captive"}]},
            },
            "Recordings": {
                "id": "recordings",
                "type": "relation",
                "relation": {"database_id": "recording_db_id"},
            },
            "Project ID": {
                "id": "projectid",
                "type": "select",
                "select": {"options": [{"name": "PL"}, {"name": "SN"}]},
            },
            "Active": {"id": "active", "type": "checkbox", "checkbox": {}},
        }
    }

    # Mock database query response
    mock_query_response = {
        "results": [
            {
                "id": "page1",
                "url": "https://notion.so/page1",
                "created_time": "2023-01-01T00:00:00.000Z",
                "last_edited_time": "2023-01-02T00:00:00.000Z",
                "properties": {
                    "Animal ID": {
                        "type": "title",
                        "title": [{"plain_text": "mian-013"}],
                    },
                    "Common Name": {
                        "type": "rich_text",
                        "rich_text": [{"plain_text": "Lazy Larry"}],
                    },
                    "Species": {"type": "select", "select": {"name": "Seal"}},
                    "Birth Date": {"type": "date", "date": {"start": "2020-05-15"}},
                    "Weight": {"type": "number", "number": 120.5},
                    "Tags": {
                        "type": "multi_select",
                        "multi_select": [{"name": "Wild"}, {"name": "Tagged"}],
                    },
                    "Recordings": {
                        "type": "relation",
                        "relation": [{"id": "rec1"}, {"id": "rec2"}],
                    },
                    "Project ID": {"type": "select", "select": {"name": "PL"}},
                    "Active": {"type": "checkbox", "checkbox": True},
                },
            }
        ],
        "has_more": False,
        "next_cursor": None,
    }

    # Mock page retrieval response
    mock_page_response = {
        "id": "rec1",
        "url": "https://notion.so/rec1",
        "created_time": "2023-01-05T00:00:00.000Z",
        "last_edited_time": "2023-01-06T00:00:00.000Z",
        "properties": {
            "Recording ID": {"type": "title", "title": [{"plain_text": "rec-001"}]},
            "Start Time": {
                "type": "date",
                "date": {"start": "2023-01-05T10:00:00.000Z"},
            },
            "End Time": {"type": "date", "date": {"start": "2023-01-05T11:00:00.000Z"}},
            "Animal": {"type": "relation", "relation": [{"id": "page1"}]},
            "Duration": {
                "type": "formula",
                "formula": {"type": "number", "number": 3600},
            },
        },
    }

    # Configure the mock client responses
    mock_instance = mock_client.return_value
    mock_instance.databases.retrieve.return_value = mock_db_response
    mock_instance.databases.query.return_value = mock_query_response
    mock_instance.pages.retrieve.return_value = mock_page_response

    return mock_instance


@pytest.fixture
def notion_orm(mock_notion_client):
    """Fixture that provides a NotionORMManager with mocked client."""
    db_map = {"Animal DB": "animal_db_id", "Recording DB": "recording_db_id"}
    return NotionORMManager(db_map=db_map, token="mock_token")


def test_get_model(notion_orm, mock_notion_client):
    """Test model class creation and schema loading."""
    Animal = notion_orm.get_model("Animal")

    # Verify the model was created with the right metadata
    assert Animal._meta.database_id == "animal_db_id"
    assert Animal._meta.database_name == "Animal DB"
    assert Animal._meta.notion_client == mock_notion_client

    # Verify schema was properly loaded
    assert "Animal ID" in Animal._meta.schema
    assert Animal._meta.schema["Animal ID"]["type"] == "title"

    # Verify that we only make the API call once
    mock_notion_client.databases.retrieve.assert_called_once_with(
        database_id="animal_db_id"
    )


def test_query_filter(notion_orm, mock_notion_client):
    """Test filtering records with the query builder."""
    Animal = notion_orm.get_model("Animal")
    animals = Animal.objects.filter(Species="Seal").all()

    # Verify the correct query was sent to Notion API
    mock_notion_client.databases.query.assert_called_once()
    call_args = mock_notion_client.databases.query.call_args[1]
    assert call_args["database_id"] == "animal_db_id"
    assert call_args["filter"]["and"][0]["property"] == "Species"
    assert call_args["filter"]["and"][0]["select"]["equals"] == "Seal"

    # Verify we got results back
    assert len(animals) == 1
    assert animals[0].id == "page1"
    assert getattr(animals[0], "Common Name") == "Lazy Larry"


def test_query_filter_with_spaces(notion_orm, mock_notion_client):
    """Test filtering with property names that contain spaces."""
    Animal = notion_orm.get_model("Animal")
    result = Animal.objects.filter(Project_ID="PL").all()

    # Verify we got results
    assert len(result) == 1

    # Verify the correct query was sent to Notion API
    call_args = mock_notion_client.databases.query.call_args[1]
    assert call_args["filter"]["and"][0]["property"] == "Project ID"
    assert call_args["filter"]["and"][0]["select"]["equals"] == "PL"


def test_get_by_id(notion_orm, mock_notion_client):
    """Test retrieving a specific record by ID."""
    Animal = notion_orm.get_model("Animal")
    animal = Animal.get_animal({"Animal ID": "mian-013"})

    # Verify the model was populated correctly
    assert animal.id == "page1"
    assert getattr(animal, "Animal ID") == "mian-013"
    assert getattr(animal, "Common Name") == "Lazy Larry"
    assert getattr(animal, "Species") == "Seal"
    assert getattr(animal, "Weight") == 120.5
    assert getattr(animal, "Birth Date") == datetime.date(2020, 5, 15)
    assert getattr(animal, "Tags") == ["Wild", "Tagged"]
    assert getattr(animal, "Active") is True

    # Verify original data is stored
    assert animal._raw_data["id"] == "page1"


def test_property_type_parsing(notion_orm):
    """Test proper parsing of different Notion property types."""
    Animal = notion_orm.get_model("Animal")
    animal = Animal.objects.filter(Species="Seal").first()

    # Verify property types are correctly parsed
    assert isinstance(getattr(animal, "Animal ID"), str)
    assert isinstance(getattr(animal, "Common Name"), str)
    assert isinstance(getattr(animal, "Species"), str)
    assert isinstance(getattr(animal, "Birth Date"), datetime.date)
    assert isinstance(getattr(animal, "Weight"), float)
    assert isinstance(getattr(animal, "Tags"), list)
    assert isinstance(getattr(animal, "Active"), bool)


def test_relationships(notion_orm, mock_notion_client):
    """Test traversing relationships between models."""
    Animal = notion_orm.get_model("Animal")
    # We need to create the Recording model to ensure relationship resolution works
    notion_orm.get_model("Recording")

    # Get an animal and its recordings
    animal = Animal.get_animal({"Animal ID": "mian-013"})
    recordings = animal.get_recording()

    # Verify relationship traversal
    assert len(recordings) == 2
    assert recordings[0].id == "rec1"
    assert getattr(recordings[0], "Recording ID") == "rec-001"

    # Verify Notion API was called correctly
    mock_notion_client.pages.retrieve.assert_called_with(page_id="rec2")


def test_first_result(notion_orm):
    """Test getting just the first result from a query."""
    Animal = notion_orm.get_model("Animal")
    animal = Animal.objects.filter(Species="Seal").first()

    assert animal is not None
    assert animal.id == "page1"
