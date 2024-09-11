import pytest
from unittest.mock import patch
from django.utils import timezone

from src.DiveDB.server.metadata.models import (
    AnimalDeployments,
    Animals,
    Deployments,
    Files,
    Loggers,
    LoggersWiki,
    MediaUpdates,
    Recordings,
)


@pytest.fixture
def setup_test_data():
    loggers_wiki = LoggersWiki.objects.create(
        description="Test Logger Wiki",
        tags=["tag1", "tag2"],
        projects=["project1", "project2"],
    )

    logger = Loggers.objects.create(
        wiki=loggers_wiki, serial_no="SN001", manufacturer="Test Manufacturer"
    )

    animal = Animals.objects.create(
        id="A001",
        project_id="P001",
        common_name="Test Animal",
        scientific_name="Testus animalus",
    )

    deployment = Deployments.objects.create(
        id="D001", rec_date=timezone.now().date(), animal="A001", timezone="UTC"
    )

    animal_deployment = AnimalDeployments.objects.create(
        deployment=deployment, animal=animal
    )

    recording = Recordings.objects.create(
        id="R001",
        animal_deployment=animal_deployment,
        logger=logger,
        start_time=timezone.now(),
    )

    file = Files.objects.create(extension=".wav", type="media", recording=recording)

    media_update = MediaUpdates.objects.create(
        file=file, update_type="type1", update_factor=1.5
    )

    return {
        "loggers_wiki": loggers_wiki,
        "logger": logger,
        "animal": animal,
        "deployment": deployment,
        "animal_deployment": animal_deployment,
        "recording": recording,
        "file": file,
        "media_update": media_update,
    }


@pytest.fixture
def mock_swiftclient():
    with patch("DiveDB.services.utils.storage.SwiftClient") as MockSwiftClient:
        instance = MockSwiftClient.return_value
        instance.get_containers.return_value = []
        instance.list_objects.return_value = []
        instance.get_object_binary.return_value = b""
        instance.write_object_to_local.return_value = None
        instance.create_container.return_value = None
        instance.put_object.return_value = "mocked_url"
        yield instance


@pytest.mark.django_db
def test_loggers_wiki_creation(setup_test_data, mock_swiftclient):
    loggers_wiki = setup_test_data["loggers_wiki"]
    assert loggers_wiki.description == "Test Logger Wiki"
    assert loggers_wiki.tags == ["tag1", "tag2"]
    assert loggers_wiki.projects == ["project1", "project2"]


@pytest.mark.django_db
def test_loggers_creation(setup_test_data, mock_swiftclient):
    logger = setup_test_data["logger"]
    loggers_wiki = setup_test_data["loggers_wiki"]
    assert logger.wiki == loggers_wiki
    assert logger.serial_no == "SN001"
    assert logger.manufacturer == "Test Manufacturer"


@pytest.mark.django_db
def test_animals_creation(setup_test_data, mock_swiftclient):
    animal = setup_test_data["animal"]
    assert animal.id == "A001"
    assert animal.project_id == "P001"
    assert animal.common_name == "Test Animal"
    assert animal.scientific_name == "Testus animalus"


@pytest.mark.django_db
def test_deployments_creation(setup_test_data, mock_swiftclient):
    deployment = setup_test_data["deployment"]
    assert deployment.id == "D001"
    assert deployment.animal == "A001"
    assert deployment.timezone == "UTC"


@pytest.mark.django_db
def test_animal_deployments_creation(setup_test_data, mock_swiftclient):
    animal_deployment = setup_test_data["animal_deployment"]
    deployment = setup_test_data["deployment"]
    animal = setup_test_data["animal"]
    assert animal_deployment.deployment == deployment
    assert animal_deployment.animal == animal


@pytest.mark.django_db
def test_recordings_creation(setup_test_data, mock_swiftclient):
    recording = setup_test_data["recording"]
    animal_deployment = setup_test_data["animal_deployment"]
    logger = setup_test_data["logger"]
    assert recording.id == "R001"
    assert recording.animal_deployment == animal_deployment
    assert recording.logger == logger


@pytest.mark.django_db
def test_files_creation(setup_test_data, mock_swiftclient):
    file = setup_test_data["file"]
    recording = setup_test_data["recording"]
    assert file.extension == ".wav"
    assert file.type == "media"
    assert file.recording == recording


@pytest.mark.django_db
def test_media_updates_creation(setup_test_data, mock_swiftclient):
    media_update = setup_test_data["media_update"]
    file = setup_test_data["file"]
    assert media_update.file == file
    assert media_update.update_type == "type1"
    assert media_update.update_factor == 1.5


@pytest.mark.django_db
def test_relationships(setup_test_data, mock_swiftclient):
    loggers_wiki = setup_test_data["loggers_wiki"]
    logger = setup_test_data["logger"]
    deployment = setup_test_data["deployment"]
    animal_deployment = setup_test_data["animal_deployment"]
    animal = setup_test_data["animal"]
    recording = setup_test_data["recording"]
    file = setup_test_data["file"]
    media_update = setup_test_data["media_update"]

    # Test LoggersWiki to Loggers relationship
    assert loggers_wiki.loggers == logger

    # Test Deployments to AnimalDeployments relationship
    assert deployment.animaldeployments_set.filter(id=animal_deployment.id).exists()

    # Test Animals to AnimalDeployments relationship
    assert animal.animaldeployments_set.filter(id=animal_deployment.id).exists()

    # Test AnimalDeployments to Recordings relationship
    assert animal_deployment.recordings_set.filter(id=recording.id).exists()

    # Test Loggers to Recordings relationship
    assert logger.recordings_set.filter(id=recording.id).exists()

    # Test Recordings to Files relationship
    assert recording.files_set.filter(id=file.id).exists()

    # Test Files to MediaUpdates relationship
    assert file.mediaupdates_set.filter(id=media_update.id).exists()
