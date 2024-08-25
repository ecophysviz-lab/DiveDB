import os
from notion_client import Client
from datetime import datetime
import logging
import django
from enum import Enum
from typing import List

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.django_app.settings")
django.setup()

from server.metadata.models import (  # noqa: E402
    Deployments,
    Loggers,
    Animals,
    Recordings,
    AnimalDeployments,
)

if os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE", "false") != "true":
    logging.warning(
        "DJANGO_ALLOW_ASYNC_UNSAFE is not set to true. This is required for MetadataManager to work outside of a Django server."
    )


class ModelNames(Enum):
    LOGGER = "logger"
    ANIMAL = "animal"
    DEPLOYMENT = "deployment"
    RECORDING = "recording"


class MetadataManager:
    notion = Client(auth=os.getenv("NOTION_API_KEY"), log_level="ERROR")
    model_names = ModelNames
    databases = {
        model_names.DEPLOYMENT: os.getenv("DEPLOYMENTS_DB_ID"),
        model_names.RECORDING: os.getenv("RECORDINGS_DB_ID"),
        model_names.LOGGER: os.getenv("LOGGERS_DB_ID"),
        model_names.ANIMAL: os.getenv("ANIMALS_DB_ID"),
    }
    models = {
        model_names.DEPLOYMENT: Deployments,
        model_names.RECORDING: Recordings,
        model_names.LOGGER: Loggers,
        model_names.ANIMAL: Animals,
    }

    def delete_all_records(self, model_name):
        all_records = self.models[model_name].objects.all()
        all_records.delete()

    def convert_notion_to_model(self, notion_data: list, model_name: ModelNames):
        converted_data = []
        for item in notion_data:
            properties = item["properties"]
            if model_name == self.model_names.LOGGER:
                converted_data.append(
                    {
                        "id": properties["LoggerID"]["title"][0]["plain_text"],
                        "serial_no": properties["SerialNo"]["rich_text"][0][
                            "plain_text"
                        ]
                        if properties["SerialNo"]["rich_text"]
                        else None,
                        "manufacturer": properties["Manufacturer"]["select"]["name"]
                        if properties["Manufacturer"]["select"]
                        else None,
                        "type": properties["Type"]["select"]["name"]
                        if properties["Type"]["select"]
                        else None,
                        "type_name": properties["TypeName"]["select"]["name"]
                        if properties["TypeName"]["select"]
                        else None,
                        "notes": properties["Notes"]["rich_text"][0]["plain_text"]
                        if properties["Notes"]["rich_text"]
                        else None,
                        "owner": properties["Owner"]["rich_text"][0]["plain_text"]
                        if properties["Owner"]["rich_text"]
                        else None,
                        "icon_url": properties["Icon"]["files"][0]["file"]["url"]
                        if properties["Icon"]["files"]
                        else None,
                    }
                )
            elif model_name == self.model_names.ANIMAL:
                converted_data.append(
                    {
                        "id": properties["AnimalID"]["title"][0]["plain_text"],
                        "project_id": properties["ProjectID"]["rich_text"][0][
                            "plain_text"
                        ]
                        if properties["ProjectID"]["rich_text"]
                        else None,
                        "common_name": properties["CommonName"]["select"]["name"],
                        "scientific_name": properties["ScientificName"]["select"][
                            "name"
                        ],
                    }
                )
            elif model_name == self.model_names.DEPLOYMENT:
                start_time = (
                    properties["Start time"]["rich_text"][0]["plain_text"]
                    if properties["Start time"]["rich_text"]
                    else None
                )
                if start_time:
                    start_time = datetime.fromisoformat(
                        properties["Rec Date"]["date"]["start"] + "T" + start_time
                    )
                converted_data.append(
                    {
                        "id": properties["ID"]["unique_id"]["number"],
                        "rec_date": properties["Rec Date"]["date"]["start"],
                        "animal": properties["Animal"]["select"]["name"],
                        "start_time": start_time,
                        "start_time_precision": properties["Start Time Precision"][
                            "select"
                        ]["name"]
                        if properties["Start Time Precision"]["select"]
                        else None,
                        "timezone": properties["Time Zone"]["select"]["name"],
                        "notes": properties["Notes"]["rich_text"][0]["plain_text"]
                        if properties["Notes"]["rich_text"]
                        else None,
                    }
                )
            elif model_name == self.model_names.RECORDING:
                start_time = (
                    properties["Start time"]["rich_text"][0]["plain_text"]
                    if properties["Start time"]["rich_text"]
                    else None
                )
                if start_time:
                    start_time = datetime.fromisoformat(
                        properties["Created time"]["created_time"][:10]
                        + "T"
                        + start_time
                    )
                actual_start_time = (
                    properties["Actual Start Time"]["rich_text"][0]["plain_text"]
                    if properties["Actual Start Time"]["rich_text"]
                    else None
                )
                if actual_start_time:
                    actual_start_time = datetime.fromisoformat(
                        properties["Created time"]["created_time"][:10]
                        + "T"
                        + actual_start_time
                    )
                end_time = (
                    properties["End Time"]["rich_text"][0]["plain_text"]
                    if properties["End Time"]["rich_text"]
                    else None
                )
                if end_time:
                    end_time = datetime.fromisoformat(
                        properties["Created time"]["created_time"][:10] + "T" + end_time
                    )
                converted_data.append(
                    {
                        "id": properties["ID"]["unique_id"]["number"],
                        "start_time": start_time,
                        "actual_start_time": actual_start_time,
                        "end_time": end_time,
                        "start_time_precision": properties["Start Time Precision"][
                            "select"
                        ]["name"]
                        if properties["Start Time Precision"]["select"]
                        else None,
                        "deployment_id": properties["Deployment"]["relation"][0]["id"]
                        if properties["Deployment"]["relation"]
                        else None,
                        "logger_id": properties["LL-Loggers"]["relation"][0]["id"]
                        if properties["LL-Loggers"]["relation"]
                        else None,
                    }
                )
        return converted_data

    def create_logger_records(self, logger_data):
        for logger in logger_data:
            Loggers.objects.create(**logger)

    def create_animal_records(self, animal_data):
        for animal in animal_data:
            Animals.objects.create(**animal)

    def create_deployment_records(self, deployment_data):
        for deployment in deployment_data:
            Deployments.objects.create(**deployment)

    def create_recording_records(self, recording_data):
        for recording in recording_data:
            deployment_id = recording.pop("deployment_id")
            logger_id = recording.pop("logger_id")
            if not deployment_id or not logger_id:
                print(
                    f"Skipping recording {recording['id']} due to missing required variables: deployment_id={deployment_id}, logger_id={logger_id}"
                )
                continue
            try:
                logger_page = self.notion.pages.retrieve(logger_id)
                recording["logger_id"] = logger_page["properties"]["LoggerID"]["title"][
                    0
                ]["plain_text"]
                deployment_page = self.notion.pages.retrieve(deployment_id)
                deployment_id = deployment_page["properties"]["ID"]["unique_id"][
                    "number"
                ]
                notion_animal_ids = [
                    relation["id"]
                    for relation in deployment_page["properties"]["AnimalIDs"][
                        "relation"
                    ]
                ]
                animal_ids = [
                    self.notion.pages.retrieve(notion_animal_id)["properties"][
                        "AnimalID"
                    ]["title"][0]["plain_text"]
                    for notion_animal_id in notion_animal_ids
                ]
                animals = list(Animals.objects.filter(id__in=animal_ids))
                deployment = Deployments.objects.get(id=deployment_id)
                if not deployment or not recording["logger_id"]:
                    print(
                        f"Skipping recording {recording['id']} due to missing required variables: deployment_id={deployment_id}, logger_id={logger_id}"
                    )
                    continue
                for animal in animals:
                    animal_deployment, _ = AnimalDeployments.objects.get_or_create(
                        animal=animal, deployment=deployment
                    )
                print(f"Created animal deployment {animal_deployment}")
                Recordings.objects.create(
                    animal_deployment=animal_deployment, **recording
                )
            except Exception as e:
                print(f"Error creating recording {recording['id']}")
                print(e)

    def compare_to_notion(self, model_name: ModelNames):
        # Fetch records from Notion
        notion_data = self.notion.databases.query(self.databases[model_name]).get(
            "results"
        )
        notion_records = self.convert_notion_to_model(notion_data, model_name)
        notion_ids = {record["id"] for record in notion_records}

        # Fetch records from PostgreSQL
        postgres_records = self.models[model_name].objects.all().values("id")
        postgres_ids = {record["id"] for record in postgres_records}

        # Compare records
        notion_not_in_postgres = notion_ids - postgres_ids
        postgres_not_in_notion = postgres_ids - notion_ids

        # Print discrepancies
        if notion_not_in_postgres:
            print(
                f"Records in Notion but not in PostgreSQL for {model_name.name}: {notion_not_in_postgres}"
            )
        else:
            print(
                f"No records found in Notion but not in PostgreSQL for {model_name.name}"
            )

        if postgres_not_in_notion:
            print(
                f"Records in PostgreSQL but not in Notion for {model_name.name}: {postgres_not_in_notion}"
            )
        else:
            print(
                f"No records found in PostgreSQL but not in Notion for {model_name.name}"
            )

    def seed_from_notion(self, model_name: ModelNames, record_ids: List[int]):
        # Fetch records from Notion
        notion_data = []
        for record_id in record_ids:
            notion_record = self.notion.pages.retrieve(record_id)
            notion_data.append(notion_record)

        # Convert Notion data to model format
        converted_data = self.convert_notion_to_model(notion_data, model_name)

        # Create records in PostgreSQL
        if model_name == ModelNames.LOGGER:
            self.create_logger_records(converted_data)
        elif model_name == ModelNames.ANIMAL:
            self.create_animal_records(converted_data)
        elif model_name == ModelNames.DEPLOYMENT:
            self.create_deployment_records(converted_data)
        elif model_name == ModelNames.RECORDING:
            self.create_recording_records(converted_data)

    def reset_from_notion(self, model_name: ModelNames):
        logging.info("Deleting all %s records", model_name)
        self.delete_all_records(model_name)
        logging.info("Creating %s records", model_name)
        notion_data = self.notion.databases.query(self.databases[model_name]).get(
            "results"
        )
        converted_data = self.convert_notion_to_model(notion_data, model_name)
        if model_name == ModelNames.LOGGER:
            self.create_logger_records(converted_data)
        elif model_name == ModelNames.ANIMAL:
            self.create_animal_records(converted_data)
        elif model_name == ModelNames.DEPLOYMENT:
            self.create_deployment_records(converted_data)
        elif model_name == ModelNames.RECORDING:
            self.create_recording_records(converted_data)
