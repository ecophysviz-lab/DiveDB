import os
import uuid
import xarray as xr
from google.cloud import storage
import pandas as pd
from DiveDB.services.data_uploader import DataUploader
from DiveDB.services.utils.netcdf_conversions import convert_to_formatted_dataset
import datetime

# Initialize the Google Cloud Storage client
client = storage.Client()

# Define the bucket and prefix
bucket_name = "female_elephant_seal_netcdfs"
# prefix = "female_elephant_seal_raw/"

# Get the bucket
bucket = client.get_bucket(bucket_name)

# List all blobs in the specified bucket with the given prefix
blobs = bucket.list_blobs()
blobs_list = list(blobs)

# Load the CSV file
metadata_df = pd.read_csv("scripts/metadata/11_Restimates_ALL_SealsUsed.csv")

data_uploader = DataUploader()

os.environ["SKIP_OPENSTACK_UPLOAD"] = "true"


def convert_file(file_path, idx):
    # Convert the file if it doesn't already exist
    converted_file_path = f"./data/processed_{idx}.nc"
    if not os.path.exists(converted_file_path):
        convert_to_formatted_dataset(file_path, output_file_path=converted_file_path)
    return converted_file_path


def upload_file(converted_file_path, idx):
    with xr.open_dataset(converted_file_path) as ds:
        # Extract necessary data from the dataset
        deployment_id = int(ds.attrs["Deployment_ID"])
        logger_id = ds.attrs["Tags_TDR1_Model"] + "_" + ds.attrs["Tags_TDR1_ID"]
        filtered_df = metadata_df[metadata_df["TOPPID"] == deployment_id]
        seal_id = (
            filtered_df.iloc[0]["SEALID"]
            if not filtered_df.empty
            else str(uuid.uuid4())
        )

        # Convert date strings to the correct format
        arrival_datetime_str = ds.attrs.get("Deployment_Arrival_Datetime")
        departure_datetime_str = ds.attrs.get("Deployment_Departure_Datetime")

        # Assuming the original format is "MM/DD/YYYY HH:MM"
        arrival_datetime = datetime.datetime.strptime(
            arrival_datetime_str, "%m/%d/%Y %H:%M"
        )
        departure_datetime = datetime.datetime.strptime(
            departure_datetime_str, "%m/%d/%Y %H:%M"
        )

        # Format to "YYYY-MM-DD HH:MM"
        formatted_arrival_datetime = arrival_datetime.strftime("%Y-%m-%d %H:%M")
        formatted_departure_datetime = departure_datetime.strftime("%Y-%m-%d %H:%M")

        # Prepare data for each model
        animal_data = {
            "animal_id": seal_id,
            "project_id": ds.attrs.get("Animal_ID"),
            "scientific_name": ds.attrs.get("Animal_Species"),
            "common_name": ds.attrs.get("Animal_Species_CommonName"),
            "lab_id": ds.attrs.get("Animal_ID"),
            "birth_year": (
                ds.attrs.get("Animal_BirthYear")
                if not pd.isna(ds.attrs.get("Animal_BirthYear"))
                else 0
            ),
            "sex": ds.attrs.get("Animal_Sex"),
            "domain_ids": str(ds.attrs.get("Animal_OtherDeployments")),
        }

        deployment_data = {
            "deployment_id": ds.attrs.get("Deployment_ID"),
            "domain_deployment_id": ds.attrs.get("Deployment_ID"),
            "animal_age_class": ds.attrs.get("Animal_AgeClass"),
            "animal_age": (
                ds.attrs.get("Deployment_Year") - ds.attrs.get("Animal_BirthYear")
                if not pd.isna(ds.attrs.get("Animal_BirthYear"))
                else 0
            ),
            "deployment_type": ds.attrs.get("Deployment_Trip"),
            "deployment_name": ds.attrs.get("Deployment_ID"),
            "rec_date": departure_datetime.strftime("%Y-%m-%d"),
            "deployment_latitude": ds.attrs.get("Deployment_Departure_Lat"),
            "deployment_longitude": ds.attrs.get("Deployment_Departure_Lon"),
            "deployment_location": ds.attrs.get("Deployment_Departure_Location"),
            "departure_datetime": formatted_departure_datetime,
            "recovery_latitude": ds.attrs.get("Deployment_Arrival_Lat"),
            "recovery_longitude": ds.attrs.get("Deployment_Arrival_Lon"),
            "recovery_location": ds.attrs.get("Deployment_Arrival_Location"),
            "arrival_datetime": formatted_arrival_datetime,
            "notes": ds.attrs.get("Notes"),
        }

        logger_data = {
            "logger_id": logger_id,
            "manufacturer": ds.attrs.get("Tags_TDR1_Manufacturer"),
            "manufacturer_name": ds.attrs.get("Tags_TDR1_Model"),
            "serial_no": ds.attrs.get("Tags_TDR1_ID"),
            "ptt": ds.attrs.get("Tags_PTT"),
            "type": ds.attrs.get("TDR"),
            "notes": ds.attrs.get("Tags_TDR1_Comments"),
        }

        # Create or get records
        animal, _ = data_uploader.get_or_create_animal(animal_data)
        logger, _ = data_uploader.get_or_create_logger(logger_data)
        deployment, _ = data_uploader.get_or_create_deployment(deployment_data)

        recording_data = {
            "recording_id": f"{deployment_id}_{seal_id}_{logger_id}",
            "name": f"Recording {idx}",
            "animal": animal,
            "deployment": deployment,
            "logger": logger,
            "start_time": formatted_arrival_datetime,
            "end_time": formatted_departure_datetime,
            "timezone": ds.attrs.get("Time_Zone"),
            "quality": ds.attrs.get("Quality"),
            "attachment_location": ds.attrs.get("Attachment_Location"),
            "attachment_type": ds.attrs.get("Attachment_Type"),
        }

        recording, _ = data_uploader.get_or_create_recording(recording_data)

        metadata = {
            "animal": animal.id,
            "deployment": deployment.id,
            "recording": recording.id,
        }

        data_uploader.upload_netcdf(
            converted_file_path,
            metadata,
            rename_map={
                "depth": "sensor_data_pressure",
                "corr_depth": "derived_data_depth",
                "lat": "derived_data_latitude",
                "lon": "derived_data_longitude",
                "loc_class": "derived_data_location_class",
                "light": "sensor_data_light",
                "exernal_temp": "sensor_data_exernal_temp",
            },
        )

    os.remove(converted_file_path)

    print(f"Uploaded {converted_file_path}")


files_with_errors = []
converted_files = []

# First, convert all files
for idx, blob in enumerate(blobs_list):
    # Skip directories
    if blob.name.endswith("/"):
        continue

    file_name = blob.name.split("/")[-1]
    converted_file_path = f"./data/processed_{idx}.nc"

    # Check if the converted file already exists
    if os.path.exists(converted_file_path):
        print(f"Skipping conversion for {file_name}, already processed.")
        converted_files.append((converted_file_path, idx))
        continue

    print(f"Converting file: {file_name}")

    # Download the blob to a local file
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = os.path.join(temp_dir, file_name)
    blob.download_to_filename(temp_file_path)
    try:
        converted_file_path = convert_file(temp_file_path, idx)
        converted_files.append((converted_file_path, idx))
    except Exception as e:
        print(f"Error converting file: {e}")
        files_with_errors.append(file_name)
    os.remove(temp_file_path)

# Then, upload all converted files
for converted_file_path, idx in converted_files:
    try:
        upload_file(converted_file_path, idx)
    except Exception as e:
        print(f"Error uploading file: {e}")
        files_with_errors.append(converted_file_path)

print(files_with_errors)

# data_directory = "data/files"
# for idx, file_name in enumerate(os.listdir(data_directory)):
#     file_path = os.path.join(data_directory, file_name)

#     upload_file(file_path, idx)
