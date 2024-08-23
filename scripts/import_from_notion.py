import asyncio

import django
import sys
import os

from notion_client import Client
from asgiref.sync import sync_to_async
from datetime import datetime

import logging
from server.metadata.models import (
    Deployments,
    Loggers,
    Animals,
    Recordings,
    AnimalDeployments,
)

# Add the parent directory to the system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.django_app.settings")
django.setup()


async def main():
    """
    Imports data from Notion into the Metadta database.
    """
    notion_token = os.getenv("NOTION_API_KEY")
    notion = Client(auth=notion_token, log_level="ERROR")

    databases = {
        "deployments": os.getenv("DEPLOYMENTS_DB_ID"),
        "recordings": os.getenv("RECORDINGS_DB_ID"),
        "loggers": os.getenv("LOGGERS_DB_ID"),
        "animals": os.getenv("ANIMALS_DB_ID"),
    }

    async def delete_all_records(model):
        all_records = await sync_to_async(model.objects.all)()
        await sync_to_async(all_records.delete)()

    async def create_logger_records(logger_data):
        for logger in logger_data:
            properties = logger["properties"]
            logger_id = properties["LoggerID"]["title"][0]["plain_text"]
            serial_no = (
                properties["SerialNo"]["rich_text"][0]["plain_text"]
                if properties["SerialNo"]["rich_text"]
                else None
            )
            manufacturer = (
                properties["Manufacturer"]["select"]["name"]
                if properties["Manufacturer"]["select"]
                else None
            )
            logger_type = (
                properties["Type"]["select"]["name"]
                if properties["Type"]["select"]
                else None
            )
            type_name = (
                properties["TypeName"]["select"]["name"]
                if properties["TypeName"]["select"]
                else None
            )
            notes = (
                properties["Notes"]["rich_text"][0]["plain_text"]
                if properties["Notes"]["rich_text"]
                else None
            )
            owner = (
                properties["Owner"]["rich_text"][0]["plain_text"]
                if properties["Owner"]["rich_text"]
                else None
            )
            icon_url = (
                properties["Icon"]["files"][0]["file"]["url"]
                if properties["Icon"]["files"]
                else None
            )

            await sync_to_async(Loggers.objects.create)(
                id=logger_id,
                serial_no=serial_no,
                manufacturer=manufacturer,
                type=logger_type,
                type_name=type_name,
                notes=notes,
                owner=owner,
                icon_url=icon_url,
            )

    async def create_animal_records(animal_data):
        for animal in animal_data:
            properties = animal["properties"]
            animal_id = properties["AnimalID"]["title"][0]["plain_text"]
            common_name = properties["CommonName"]["select"]["name"]
            scientific_name = properties["ScientificName"]["select"]["name"]
            project_id = (
                properties["ProjectID"]["rich_text"][0]["plain_text"]
                if properties["ProjectID"]["rich_text"]
                else None
            )

            await sync_to_async(Animals.objects.create)(
                id=animal_id,
                project_id=project_id,
                common_name=common_name,
                scientific_name=scientific_name,
            )

    async def create_deployment_records(deployment_data):
        for deployment in deployment_data:
            properties = deployment["properties"]
            deployment_id = properties["ID"]["unique_id"]["number"]
            rec_date = properties["Rec Date"]["date"]["start"]
            animal = properties["Animal"]["select"]["name"]
            start_time = (
                properties["Start time"]["rich_text"][0]["plain_text"]
                if properties["Start time"]["rich_text"]
                else None
            )
            if start_time:
                start_time = datetime.fromisoformat(rec_date + "T" + start_time)

            start_time_precision = (
                properties["Start Time Precision"]["select"]["name"]
                if properties["Start Time Precision"]["select"]
                else None
            )
            timezone = properties["Time Zone"]["select"]["name"]
            notes = (
                properties["Notes"]["rich_text"][0]["plain_text"]
                if properties["Notes"]["rich_text"]
                else None
            )

            await sync_to_async(Deployments.objects.create)(
                id=deployment_id,
                rec_date=rec_date,
                animal=animal,
                start_time=start_time,
                start_time_precision=start_time_precision,
                timezone=timezone,
                notes=notes,
            )

    async def create_recording_records(recording_data):
        for recording in recording_data:
            properties = recording["properties"]
            recording_id = properties["ID"]["unique_id"]["number"]
            start_time = (
                properties["Start time"]["rich_text"][0]["plain_text"]
                if properties["Start time"]["rich_text"]
                else None
            )
            if start_time:
                start_time = datetime.fromisoformat(
                    properties["Created time"]["created_time"][:10] + "T" + start_time
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

            start_time_precision = (
                properties["Start Time Precision"]["select"]["name"]
                if properties["Start Time Precision"]["select"]
                else None
            )

            deployment_id = (
                properties["Deployment"]["relation"][0]["id"]
                if properties["Deployment"]["relation"]
                else None
            )
            logger_id = (
                properties["LL-Loggers"]["relation"][0]["id"]
                if properties["LL-Loggers"]["relation"]
                else None
            )

            if not deployment_id or not logger_id:
                print(
                    f"Skipping recording {recording_id} due to missing required variables: deployment_id={deployment_id}, logger_id={logger_id}"
                )
                continue

            try:
                logger_page = notion.pages.retrieve(logger_id)
                logger_id = logger_page["properties"]["LoggerID"]["title"][0][
                    "plain_text"
                ]
                deployment_page = notion.pages.retrieve(deployment_id)
                deployment_id = deployment_page["properties"]["ID"]["unique_id"][
                    "number"
                ]
                notion_animal_ids = [
                    relation["id"]
                    for relation in deployment_page["properties"]["AnimalIDs"][
                        "relation"
                    ]
                ]
                animal_ids = []
                for notion_animal_id in notion_animal_ids:
                    animal_page = notion.pages.retrieve(notion_animal_id)
                    animal_ids.append(
                        animal_page["properties"]["AnimalID"]["title"][0]["plain_text"]
                    )
                animals = await sync_to_async(list)(
                    Animals.objects.filter(id__in=animal_ids)
                )
                deployment = await sync_to_async(Deployments.objects.get)(
                    id=deployment_id
                )
                if deployment_id is None or logger_id is None:
                    print(
                        f"Skipping recording {recording_id} due to missing required variables: deployment_id={deployment_id}, logger_id={logger_id}"
                    )
                    continue

                for animal in animals:
                    animal_deployment, _ = await sync_to_async(
                        AnimalDeployments.objects.get_or_create
                    )(animal=animal, deployment=deployment)
                print(f"Created animal deployment {animal_deployment}")

                await sync_to_async(Recordings.objects.create)(
                    id=recording_id,
                    animal_deployment=animal_deployment,
                    logger_id=logger_id,
                    start_time=start_time,
                    actual_start_time=actual_start_time,
                    end_time=end_time,
                    start_time_precision=start_time_precision,
                )
            except Exception as e:
                print(f"Error creating recording {recording_id}")
                print(e)

    loggers = notion.databases.query(databases["loggers"]).get("results")
    deployments = notion.databases.query(databases["deployments"]).get("results")
    recordings = notion.databases.query(databases["recordings"]).get("results")
    animals = notion.databases.query(databases["animals"]).get("results")

    async def delete_and_create_records(model, create_func, data, record_type):
        logging.info("Deleting all %s records", record_type)
        await delete_all_records(model)
        logging.info("Creating %s records", record_type)
        await create_func(data)

    await delete_and_create_records(Loggers, create_logger_records, loggers, "logger")
    await delete_and_create_records(Animals, create_animal_records, animals, "animal")
    await delete_and_create_records(
        Deployments, create_deployment_records, deployments, "deployment"
    )
    await delete_and_create_records(
        Recordings, create_recording_records, recordings, "recording"
    )


if __name__ == "__main__":
    asyncio.run(main())
