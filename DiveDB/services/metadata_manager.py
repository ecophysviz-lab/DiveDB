import logging
import os
from time import sleep
from datetime import datetime
from enum import Enum
from typing import List
import pandas as pd
import sys

import django
from notion_client import Client

django_prefix = os.environ.get("DJANGO_PREFIX", "DiveDB")
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", f"{django_prefix}.server.django_app.settings"
)
django.setup()

from DiveDB.server.metadata.models import (  # noqa: E402
    AnimalDeployments,
    Animals,
    Deployments,
    Loggers,
    Recordings,
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


ModelLookupKeys = {
    ModelNames.ANIMAL: "project_id",
    ModelNames.DEPLOYMENT: "deployment_name",
    ModelNames.LOGGER: "id",
    ModelNames.RECORDING: "name",
}

NotionLookupKeys = {
    ModelNames.ANIMAL: "Project ID",
    ModelNames.DEPLOYMENT: "Deployment Name",
    ModelNames.LOGGER: "Logger ID",
    ModelNames.RECORDING: "Recording Name",
}


class MetadataManager:
    def __init__(self):
        self.models = {
            ModelNames.ANIMAL: Animals,
            ModelNames.DEPLOYMENT: Deployments,
            ModelNames.LOGGER: Loggers,
            ModelNames.RECORDING: Recordings,
        }
        self.databases = {
            ModelNames.DEPLOYMENT: os.getenv("DEPLOYMENTS_DB_ID"),
            ModelNames.RECORDING: os.getenv("RECORDINGS_DB_ID"),
            ModelNames.LOGGER: os.getenv("LOGGERS_DB_ID"),
            ModelNames.ANIMAL: os.getenv("ANIMALS_DB_ID"),
        }
        self.notion = Client(auth=os.getenv("NOTION_API_KEY"), log_level="ERROR")
        self.csv_data = None
        self.csv_metadata_map = None
        self.model_names = ModelNames

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
                        "id": properties["Logger ID"]["title"][0]["plain_text"],
                        "serial_no": (
                            properties["Serial Number"]["rich_text"][0]["plain_text"]
                            if properties["Serial Number"]["rich_text"]
                            else None
                        ),
                        "manufacturer": (
                            properties["Manufacturer"]["select"]["name"]
                            if properties["Manufacturer"]["select"]
                            else None
                        ),
                        "type": (
                            properties["Type"]["select"]["name"]
                            if properties["Type"]["select"]
                            else None
                        ),
                        "type_name": (
                            properties["Manufacturer Name"]["select"]["name"]
                            if properties["Manufacturer Name"]["select"]
                            else None
                        ),
                        "notes": (
                            properties["Notes"]["rich_text"][0]["plain_text"]
                            if properties["Notes"]["rich_text"]
                            else None
                        ),
                        "owner": (
                            properties["Owner"]["rich_text"][0]["plain_text"]
                            if properties["Owner"]["rich_text"]
                            else None
                        ),
                        "icon_url": (
                            properties["Icon"]["files"][0]["file"]["url"]
                            if properties["Icon"]["files"]
                            else None
                        ),
                    }
                )
            elif model_name == self.model_names.ANIMAL:
                converted_data.append(
                    {
                        "id": properties["Animal ID"]["title"][0]["plain_text"],
                        "project_id": (
                            properties["Project ID"]["rich_text"][0]["plain_text"]
                            if properties["Project ID"]["rich_text"]
                            else None
                        ),
                        "common_name": properties["Common Name"]["select"]["name"],
                        "scientific_name": properties["Scientific Name"]["select"][
                            "name"
                        ],
                    }
                )
            elif model_name == self.model_names.DEPLOYMENT:
                start_time = (
                    properties["Start Time"]["rollup"]["array"][0]["rich_text"][0][
                        "plain_text"
                    ]
                    if properties["Start Time"]["rollup"]["array"]
                    else None
                )
                if start_time:
                    start_time = datetime.fromisoformat(
                        properties["Recording Date"]["date"]["start"] + "T" + start_time
                    )
                converted_data.append(
                    {
                        "id": properties["ID"]["unique_id"]["number"],
                        "deployment_name": properties["Deployment ID"]["title"][0][
                            "plain_text"
                        ],
                        "rec_date": properties["Recording Date"]["date"]["start"],
                        "animal": properties["Animal"]["select"]["name"],
                        "start_time": start_time,
                        "start_time_precision": None,
                        "timezone": properties["Time Zone"]["select"]["name"],
                        "notes": (
                            properties["Notes"]["rich_text"][0]["plain_text"]
                            if properties["Notes"]["rich_text"]
                            else None
                        ),
                    }
                )
            elif model_name == self.model_names.RECORDING:
                start_time = (
                    properties["Start Time"]["rich_text"][0]["plain_text"]
                    if properties["Start Time"]["rich_text"]
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
                        "name": properties["Recording ID"]["title"][0]["plain_text"],
                        "start_time": start_time,
                        "actual_start_time": actual_start_time,
                        "end_time": end_time,
                        "start_time_precision": (
                            properties["Start Time Precision"]["select"]["name"]
                            if properties["Start Time Precision"]["select"]
                            else None
                        ),
                        "deployment_id": (
                            properties["Deployment"]["relation"][0]["id"]
                            if properties["Deployment"]["relation"]
                            else None
                        ),
                        "logger_id": (
                            properties["Logger ID"]["relation"][0]["id"]
                            if properties["Logger ID"]["relation"]
                            else None
                        ),
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
                recording["logger_id"] = logger_page["properties"]["Logger ID"][
                    "title"
                ][0]["plain_text"]
                deployment_page = self.notion.pages.retrieve(deployment_id)
                deployment_id = deployment_page["properties"]["ID"]["unique_id"][
                    "number"
                ]
                notion_animal_ids = [
                    relation["id"]
                    for relation in deployment_page["properties"]["Animal ID"][
                        "relation"
                    ]
                ]
                animal_ids = [
                    self.notion.pages.retrieve(notion_animal_id)["properties"][
                        "Animal ID"
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

    def get_metadata_for_model(self, model_name: ModelNames):
        """
        Facilitates the retrieval of metadata for a specified model from CSV, PostgreSQL, and Notion.

        Parameters:
            model_name (ModelNames): The name of the model for which metadata is being retrieved.

        Workflow:
            1. Fetches Notion data and converts it to the model format.
            2. Checks if the metadata lookup key exists in the CSV file.
            3. User Interaction:
                - Prompts the user to select a name from the CSV metadata.
                - If no selection, prompts the user to select a name from the PostgreSQL database.
                - If no selection, prompts the user to select a name from the Notion data.
            4. Returns the selected, newly created record, or closes the program if no selection is made.
        """
        from IPython.display import clear_output

        notion_data = self.notion.databases.query(self.databases[model_name]).get(
            "results"
        )
        notion_records = self.convert_notion_to_model(notion_data, model_name)
        metadata_lookup = (
            self.csv_metadata_map.get(model_name.value, "name")
            if self.csv_metadata_map
            else "name"
        )
        first_column_header = self.csv_data.columns[0]
        if metadata_lookup not in self.csv_data[first_column_header].values:
            print(f"The {metadata_lookup} header does not exist in the first column.")
        else:
            name_index = self.csv_data[
                self.csv_data[first_column_header] == metadata_lookup
            ].index[0]
            names = self.csv_data.iloc[
                name_index, 1:
            ]  # Assuming names are in the same row
        clear_output(wait=True)
        print(
            f"Pick from the following {model_name.value}s in the Metadata CSV or enter nothing to look up a new {model_name.value} in DiveDB: "
        )
        for name in names:
            print(name)
        sleep(1)
        metadata_name = input(f"Metadata CSV {model_name.value.capitalize()} Name: ")
        if metadata_name == "":
            items = self.models[model_name].objects.all()
            clear_output(wait=True)
            print(
                f"Pick from the following {model_name.value}s in DiveDB or enter nothing to look a new {model_name.value} in Notion: "
            )
            for item in items:
                print(getattr(item, ModelLookupKeys[model_name]))
            sleep(1)
            dive_db_name = input(f"DiveDB {model_name.value.capitalize()} Name: ")
            if dive_db_name == "":
                clear_output(wait=True)
                print(
                    f"Pick from the following {model_name.value}s in Notion or enter nothing to cancel: "
                )
                for notion_record in notion_records:
                    print(notion_record[ModelLookupKeys[model_name]])
                sleep(1)
                notion_name = input(f"Notion {model_name.value.capitalize()} Name: ")
                if notion_name == "":
                    logging.info("No Notion record selected.")
                    sleep(1)
                    sys.exit()
                else:
                    for notion_record in notion_records:
                        if notion_record["id"] == notion_name:
                            new_item = self.models[model_name].objects.create(
                                **notion_record
                            )
                            clear_output(wait=True)
                            return new_item
                    logging.info("No valid Notion record selected (%s)", metadata_name)
                    sleep(1)
                    sys.exit()
            else:
                clear_output(wait=True)
                return self.models[model_name].objects.get(
                    **{ModelLookupKeys[model_name]: dive_db_name}
                )
        else:
            for notion_record in notion_records:
                if notion_record[ModelLookupKeys[model_name]] == metadata_name:
                    if (
                        self.models[model_name]
                        .objects.filter(**{ModelLookupKeys[model_name]: metadata_name})
                        .exists()
                    ):
                        clear_output(wait=True)
                        return self.models[model_name].objects.get(
                            **{ModelLookupKeys[model_name]: metadata_name}
                        )
                    else:
                        clear_output(wait=True)
                        return self.models[model_name].objects.create(**notion_record)
            logging.info("No valid Notion record selected (%s)", metadata_name)
            sleep(1)
            sys.exit()

    def get_animal_from_csv(self):
        return self.get_metadata_for_model(ModelNames.ANIMAL)

    def get_deployment_from_csv(self):
        return self.get_metadata_for_model(ModelNames.DEPLOYMENT)

    def get_logger_from_csv(self):
        return self.get_metadata_for_model(ModelNames.LOGGER)

    def get_recording_from_csv(self):
        return self.get_metadata_for_model(ModelNames.RECORDING)

    def get_metadata_models(
        self, csv_metadata_path: str, csv_metadata_map: dict = None
    ):
        self.csv_data = pd.read_csv(csv_metadata_path, header=None)
        self.csv_metadata_map = csv_metadata_map
        animal = self.get_animal_from_csv()
        deployment = self.get_deployment_from_csv()
        logger = self.get_logger_from_csv()
        recording = self.get_recording_from_csv()

        # For dev mode: Find a random animal and deployment and logger
        # animal = Animals.objects.order_by("?").first()
        # deployment = Deployments.objects.order_by("?").first()
        # logger = Loggers.objects.order_by("?").first()
        # recording = Recordings.objects.order_by("?").first()

        # Create a new animal deployment (if one doesn't exist)
        AnimalDeployments.objects.get_or_create(animal=animal, deployment=deployment)

        return {
            "animal": animal,
            "deployment": deployment,
            "logger": logger,
            "recording": recording,
        }
