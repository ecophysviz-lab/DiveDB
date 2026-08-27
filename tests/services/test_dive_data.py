"""
Tests for the DiveData module.

Covers the organism/animal terminology fallbacks used when reading metadata from
Notion, so that workspaces which have not yet been renamed keep working.
"""

import pytest

from DiveDB.services.dive_data import (
    get_organism_model,
    get_recording_organism_id,
)


class FakeNotionManager:
    """Minimal stand-in for NotionORMManager.get_model."""

    def __init__(self, known_db_names):
        self.known_db_names = set(known_db_names)
        self.requested = []

    def get_model(self, model_name):
        self.requested.append(model_name)
        if model_name not in self.known_db_names:
            raise ValueError(f"Database '{model_name}' not found in database map")
        return f"model:{model_name}"


class FakeRecording:
    """Stand-in for a Notion Recording record with dynamic properties."""

    def __init__(self, id="rec-1", **properties):
        self.id = id
        for key, value in properties.items():
            setattr(self, key, value)


class TestGetOrganismModel:
    def test_prefers_organism_db(self):
        manager = FakeNotionManager(["Organism DB", "Animal DB"])
        assert get_organism_model(manager) == "model:Organism DB"
        assert manager.requested == ["Organism DB"]

    def test_falls_back_to_legacy_animal_db(self):
        manager = FakeNotionManager(["Animal DB"])
        assert get_organism_model(manager) == "model:Animal DB"
        assert manager.requested == ["Organism DB", "Animal DB"]

    def test_raises_when_neither_present(self):
        manager = FakeNotionManager(["Recording DB"])
        with pytest.raises(ValueError, match="Neither 'Organism DB' nor 'Animal DB'"):
            get_organism_model(manager)


class TestGetRecordingOrganismId:
    def test_prefers_organism_id(self):
        recording = FakeRecording(organism_id="mian-013", animal_id="legacy-999")
        assert get_recording_organism_id(recording) == "mian-013"

    def test_falls_back_to_legacy_animal_id(self):
        recording = FakeRecording(animal_id="mian-013")
        assert get_recording_organism_id(recording) == "mian-013"

    def test_skips_empty_organism_id(self):
        recording = FakeRecording(organism_id=None, animal_id="mian-013")
        assert get_recording_organism_id(recording) == "mian-013"

    def test_raises_when_neither_property_present(self):
        recording = FakeRecording()
        with pytest.raises(Exception, match="neither an 'Organism ID' nor an"):
            get_recording_organism_id(recording)
