import os
import sys
import xarray as xr
from google.cloud import storage
from DiveDB.services.data_uploader import DataUploader
import importlib
import pandas as pd

# Add the directory containing your local module to the Python path
local_module_path = os.path.abspath("DiveDB/services/utils/netcdf_conversions.py")
if local_module_path not in sys.path:
    sys.path.insert(0, local_module_path)

import DiveDB.services.utils.netcdf_conversions

importlib.reload(DiveDB.services.utils.netcdf_conversions)
from DiveDB.services.utils.netcdf_conversions import convert_to_formatted_dataset

# Initialize the Google Cloud Storage client
client = storage.Client()

# Define the bucket and prefix
bucket_name = "dive_db"
prefix = "female_elephant_seal_raw/"

# Get the bucket
bucket = client.get_bucket(bucket_name)

# List all blobs in the specified bucket with the given prefix
blobs = bucket.list_blobs(prefix=prefix)

# Load the CSV file
metadata_df = pd.read_csv("scripts/metadata/11_Restimates_ALL_DailyActivity.csv")

data_uploader = DataUploader()

os.environ["SKIP_OPENSTACK_UPLOAD"] = "true"

# Loop through each blob
for idx, blob in enumerate(blobs):
    # Skip directories
    if blob.name.endswith("/"):
        continue

    file_name = blob.name.split("/")[-1]
    print(f"Processing file: {file_name}")

    # Download the blob to a local file
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = os.path.join(temp_dir, file_name)
    blob.download_to_filename(temp_file_path)

    # Convert the file
    converted_file_path = f"./data/processed_{idx}.nc"
    converts_ds = convert_to_formatted_dataset(
        temp_file_path, output_file_path=converted_file_path
    )

    with xr.open_dataset(converted_file_path) as ds:
        # Find the row in the CSV where "TOPPID" matches "Deployment_ID"
        deployment_id = int(ds.attrs["Deployment_ID"])
        logger_id = ds.attrs["Tags_TDR1_Model"] + "_" + ds.attrs["Tags_TDR1_ID"]
        filtered_df = metadata_df[metadata_df["TOPPID"] == deployment_id]

        if filtered_df.empty:
            print(f"No matching row found for Deployment_ID: {deployment_id}")
            continue  # Skip to the next blob if no match is found

        matching_row = filtered_df.iloc[0]

        # Use "SEALID" from the matching row as the animal
        metadata = {
            "animal": matching_row["SEALID"],
            "deployment": deployment_id,
            "recording": f"{deployment_id}_{matching_row['SEALID']}_{logger_id}",
        }

    # Upload the converted file
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

    # Clean up temporary files
    os.remove(temp_file_path)
    os.remove(converted_file_path)

    print(f"Uploaded {file_name}")
    print(f"Processed {idx} files")

print("Processing complete.")
