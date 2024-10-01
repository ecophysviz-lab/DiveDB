import os
import requests
from bs4 import BeautifulSoup
import csv

from DiveDB.services.data_uploader import DataUploader
from DiveDB.services.utils.netcdf_conversions import convert_to_formatted_dataset

# flake8: noqa

base_url = "https://datadryad.org"
hash_value = os.getenv("DRYAD_HASH", "default_hash_value")
page_url = f"https://datadryad.org/stash/share/{hash_value}"

response = requests.get(page_url)
soup = BeautifulSoup(response.text, "html.parser")

ul = soup.find("ul", class_="c-file-group__list")
li_elements = ul.find_all("li")

# Total number of files
total_files = len(li_elements)

# Index of the second-to-last file (CSV file)
csv_idx = total_files - 2

# Extract the CSV file first
csv_li = li_elements[csv_idx]
a_tag = csv_li.find("a")
csv_file_name = a_tag.get("title")
csv_download_href = a_tag.get("href")
csv_download_url = base_url + csv_download_href

print(f"Downloading CSV file: {csv_file_name} from {csv_download_url}")

# Download and parse the Metdata CSV file
csv_response = requests.get(csv_download_url)
with open(csv_file_name, "wb") as f:
    f.write(csv_response.content)
with open(csv_file_name, "r", newline="", encoding="utf-8") as csvfile:
    csvreader = csv.reader(csvfile)
    for row in csvreader:
        print(row)

data_uploader = DataUploader()

# Loop through each file, excluding the last one and the CSV file
for idx, li in enumerate(li_elements):
    if idx == total_files - 1 or idx == csv_idx:
        continue

    a_tag = li.find("a")
    file_name = a_tag.get("title")
    download_href = a_tag.get("href")
    download_url = base_url + download_href

    print(f"Downloading {file_name} from {download_url}")

    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    temp_file_path = os.path.join(temp_dir, file_name)
    file_response = requests.get(download_url)
    with open(temp_file_path, "wb") as f:
        f.write(file_response.content)

    converted_file_path = f"./data/processed_{idx}.nc"
    converts_ds = convert_to_formatted_dataset(
        temp_file_path, output_file_path=converted_file_path
    )

    # TODO: Get metadata from csvreader
    metadata = {
        "animal": "oror-002",
        "deployment": "2024-01-16_oror-002a",
        "recording": "2024-01-16_oror-002a_UF-01_001",
    }

    data_uploader.upload_netcdf(converted_file_path, metadata)
