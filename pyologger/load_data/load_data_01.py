# Import libraries and set working directory (adjust to fit your preferences)
import os
from pyologger.load_data.datareader import DataReader
from pyologger.load_data.metadata import Metadata

# Change the current working directory to the root directory
# os.chdir("/Users/fbar/Documents/GitHub/pyologger")
os.chdir("/Users/jessiekb/Documents/GitHub/pyologger")

root_dir = os.getcwd()
data_dir = os.path.join(root_dir, "data")

# Verify the current working directory
print(f"Current working directory: {root_dir}")

# Initialize the info class
metadata = Metadata()
metadata.fetch_databases(verbose=False)

# Save databases
dep_db = metadata.get_metadata("dep_DB")
logger_db = metadata.get_metadata("logger_DB")
rec_db = metadata.get_metadata("rec_DB")
animal_db = metadata.get_metadata("animal_DB")

# Assuming you have the metadata and dep_db loaded:
datareader = DataReader()
deployment_folder = datareader.check_deployment_folder(dep_db, data_dir)

if deployment_folder:
    datareader.read_files(metadata, save_csv=True, save_parq=True)