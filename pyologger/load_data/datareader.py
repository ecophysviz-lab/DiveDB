import os
import struct
import pickle
import pytz
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class DataReader:
    """A class for handling the reading and processing of deployment data files.

    This class is responsible for managing and processing data from different logger devices
    within a deployment. It provides methods to read, organize, process, and save data from
    various file formats including UBE and CSV.

    :param deployment_folder_path: The path to the folder containing the deployment data, defaults to None
    :type deployment_folder_path: str, optional
    """
    def __init__(self, deployment_folder_path=None):
        """Constructor method for initializing the DataReader.

        :param deployment_folder_path: The path to the folder containing the deployment data, defaults to None
        :type deployment_folder_path: str, optional
        """
        self.deployment_data_folder = deployment_folder_path
        self.selected_deployment = None  # Store selected deployment metadata here
        self.data = {}  # Store data by logger ID
        self.info = {}  # Store info (metadata) by logger ID

    def read_files(self, metadata, save_csv=True, save_parq=True):
        """Reads and processes the deployment data files.

        This method reads the data files for each logger in the deployment, processes them,
        and optionally saves the results as CSV and/or Parquet files.

        :param metadata: The metadata object containing logger information.
        :type metadata: Metadata object
        :param save_csv: Flag indicating whether to save the processed data as CSV files, defaults to True
        :type save_csv: bool, optional
        :param save_parq: Flag indicating whether to save the processed data as Parquet files, defaults to True
        :type save_parq: bool, optional
        """
        if not self.deployment_data_folder:
            print("No deployment folder set. Please use check_deployment_folder first.")
            return

        print(f"Step 2: Deployment folder initialized at: {self.deployment_data_folder}")
        
        # Step 3: Fetch metadata
        print("Step 3: Fetching metadata...")
        metadata.fetch_databases(verbose=False)
        logger_db = metadata.get_metadata("logger_DB")
        print("Metadata fetched successfully.")

        # New Step: Import notes
        print("Step 3.5: Importing notes...")
        notes_df = self.import_notes()
        if notes_df is not None:
            print("Notes imported successfully.")
            self.notes_df = notes_df
        else:
            print("No valid notes were imported.")

        # Step 4: Organize files by logger ID
        print("Step 4: Organizing files by logger ID...")
        logger_ids = set(logger_db['LoggerID'])
        logger_files = {logger_id: [] for logger_id in logger_ids}

        for file in os.listdir(self.deployment_data_folder):
            for logger_id in logger_ids:
                if logger_id in file:
                    logger_files[logger_id].append(file)
                    break

        # Sort the files for each logger ID to ensure they are in the correct order
        for logger_id in logger_files:
            logger_files[logger_id].sort()

        # Filter down to loggers that actually have files
        loggers_with_files = {logger_id: files for logger_id, files in logger_files.items() if files}
        loggers_without_files = [logger_id for logger_id in logger_ids if logger_id not in loggers_with_files]

        # Print the summary of loggers with and without files
        print("Loggers with files:", ", ".join(loggers_with_files.keys()))
        print("Loggers without files:", ", ".join(loggers_without_files))

        # Initialize logger-specific dictionaries
        for logger_id in loggers_with_files:
            self.data[logger_id] = None
            self.info[logger_id] = {"channelinfo": {}}


        # Step 5: Check outputs folder to see if processing is needed
        if self.check_outputs_folder(loggers_with_files.keys()):
            print("All necessary files are already processed. Skipping further processing.")
            return

        # Step 5: Process each logger's files
        for logger_id, files in loggers_with_files.items():
            manufacturer = logger_db.loc[logger_db['LoggerID'] == logger_id, 'Manufacturer'].values[0]

            print(f"Step 6: Processing UBE files for logger: {logger_id} (Manufacturer: {manufacturer})")
            ube_files = [f for f in files if f.endswith('.ube')]
            csv_files = [f for f in files if f.endswith('.csv')]

            if ube_files:
                for ube_file in ube_files:
                    ube_df, self.info[logger_id]['channelinfo'] = self.process_ube_file(ube_file)
                    ube_df, datetime_metadata = self.process_datetime(ube_df, time_zone=self.selected_deployment['Time Zone'])
                    self.info[logger_id]['datetime_metadata'] = datetime_metadata
                    if ube_df is not None and 'datetime' in ube_df.columns:
                        self.save_data(ube_df, logger_id, f"{logger_id}.csv", save_csv, save_parq)
                        print(f"Files saved for logger {logger_id}.")
                    else:
                        print("Issue with UBE file saving.")

            if csv_files:
                print(f"Step 7: Processing CSV files for logger: {logger_id}")
                final_df, self.info[logger_id]['channelinfo'] = self.concatenate_and_save_csvs(csv_files)
                final_df, datetime_metadata = self.process_datetime(final_df, time_zone=self.selected_deployment['Time Zone'])
                self.info[logger_id]['datetime_metadata'] = datetime_metadata
                if final_df is not None and 'datetime' in final_df.columns:
                    self.save_data(final_df, logger_id, f"{logger_id}.csv", save_csv, save_parq)
                    print(f"Files saved for logger {logger_id}.")
                else:
                    print("Issue with CSV file saving.")

        print("Step 8: All processing complete.")
        
        # Step 9: Save the DataReader object as a pickle file
        pickle_filename = os.path.join(self.deployment_data_folder, 'outputs', 'data.pkl')
        with open(pickle_filename, 'wb') as f:
            pickle.dump(self, f)
        print(f"Step 9: DataReader object successfully saved to {pickle_filename}.")
    
    def check_deployment_folder(self, dep_db, data_dir):
        """Checks the deployment folder and allows the user to select a deployment.

        This method assists the user in selecting a deployment folder from a database and ensures that the
        folder exists. If the folder is not found, it attempts to find a similar folder in the directory.

        :param dep_db: The deployment database containing metadata about available deployments.
        :type dep_db: pandas.DataFrame
        :param data_dir: The directory containing deployment folders.
        :type data_dir: str
        :return: The path to the selected deployment folder, or None if not found
        :rtype: str or None
        """
        # Step 1: Display relevant information to help the user decide
        print("Step 1: Displaying deployments to help you select one.")
        print(dep_db[['Deployment Name', 'Notes']])

        # Step 1: Prompt the user for input
        selected_index = int(input("Enter the index of the deployment you want to work with: "))

        # Step 2: Process the user's selection
        if 0 <= selected_index < len(dep_db):
            selected_deployment = dep_db.iloc[selected_index]
            self.selected_deployment = selected_deployment  # Save selected deployment to self
            print(f"Step 1: You selected the deployment: {selected_deployment['Deployment Name']}")
            print(f"Description: {selected_deployment['Notes']}")
        else:
            print("Invalid index selected.")
            return None

        # Get to deployment folder
        deployment_folder = os.path.join(data_dir, selected_deployment['Deployment Name'])
        # Verify the current working directory
        print(f"Step 2: Deployment folder path: {deployment_folder}")

        # Step 3: Check if the folder exists
        if os.path.exists(deployment_folder):
            print(f"Deployment folder found: {deployment_folder}")
        else:
            # If not found, search for a folder that starts with the deployment name
            print(f"Folder {deployment_folder} not found. Searching for folders with a similar name...")
            
            # Get a list of all folders in the data directory
            possible_folders = [folder for folder in os.listdir(data_dir) 
                                if folder.startswith(selected_deployment['Deployment Name'])]
            
            if len(possible_folders) == 1:
                # If exactly one match is found, use that folder
                deployment_folder = os.path.join(data_dir, possible_folders[0])
                print(f"Using the found folder: {deployment_folder}")
            elif len(possible_folders) > 1:
                # If multiple matches are found, ask the user to select one
                print("Multiple matching folders found. Please select one:")
                for i, folder in enumerate(possible_folders):
                    print(f"{i}: {folder}")
                selected_index = int(input("Enter the index of the folder you want to use: "))
                if 0 <= selected_index < len(possible_folders):
                    deployment_folder = os.path.join(data_dir, possible_folders[selected_index])
                    print(f"Using the selected folder: {deployment_folder}")
                else:
                    print("Invalid selection. Aborting.")
                    return None
            else:
                # If no matches are found, return an error
                print("Error: Folder not found.")
                return None

        # Continue processing if a valid folder was found
        self.deployment_data_folder = deployment_folder
        print(f"Ready to process deployment folder: {self.deployment_data_folder}")
        return self.deployment_data_folder

    def import_notes(self):
        """Imports and processes notes associated with the selected deployment.

        This method reads a notes file in Excel format, processes the timestamps, and sorts
        the notes chronologically.

        :return: A DataFrame containing the processed notes, or None if notes could not be imported
        :rtype: pandas.DataFrame or None
        """
        if self.selected_deployment is None or self.selected_deployment.empty:
            print("Selected deployment metadata not found. Please ensure you have selected a deployment.")
            return None

        # Construct the filename based on the format: "{Deployment Name}_00_Notes.xlsx"
        notes_filename = f"{self.selected_deployment['Deployment Name']}_00_Notes.xlsx"
        
        rec_date = self.selected_deployment['Rec Date']
        start_time = self.selected_deployment.get('Start Time', "00:00:00")
        time_zone = self.selected_deployment.get('Time Zone')

        if not time_zone:
            print(f"No time zone information found for the selected deployment.")
            return None

        notes_filepath = os.path.join(self.deployment_data_folder, notes_filename)

        if not os.path.exists(notes_filepath):
            print(f"Notes file {notes_filename} not found in {self.deployment_data_folder}.")
            return None

        # Read the .xlsx file
        try:
            notes_df = pd.read_excel(notes_filepath)
        except Exception as e:
            print(f"Error reading {notes_filename}: {e}")
            return None

        # Use process_datetime to handle datetime creation and time zone localization
        notes_df, datetime_metadata = self.process_datetime(notes_df, time_zone=time_zone)
        
        if notes_df['datetime'].isna().any():
            print(f"WARNING: Some timestamps could not be parsed.")
            return notes_df

        # Sort the DataFrame by the 'datetime' column
        notes_df = notes_df.sort_values(by='datetime').reset_index(drop=True)

        print(f"Notes imported, processed, and sorted chronologically from {notes_filename}.")
        return notes_df


    def check_outputs_folder(self, logger_ids):
        """Checks if the processed data files for the given loggers already exist in the outputs folder.

        This method checks if all necessary files are present in the outputs folder and determines
        if further processing is needed.

        :param logger_ids: A list of logger IDs for which the outputs should be checked.
        :type logger_ids: list
        :return: True if all necessary files are found, False otherwise
        :rtype: bool
        """
        output_folder = os.path.join(self.deployment_data_folder, 'outputs')
        if not os.path.exists(output_folder):
            print("Outputs folder does not exist. Processing required.")
            return False  # Outputs folder doesn't exist, so we need to process files

        existing_files = os.listdir(output_folder)
        print(f"Existing files in output folder: {existing_files}")

        for logger_id in logger_ids:
            # Check if any file in the outputs folder contains the logger ID
            matching_files = [filename for filename in existing_files if logger_id in filename]
            if not matching_files:
                print(f"No files found for logger ID {logger_id} in the output folder. Processing required.")
                return False  # If any logger ID doesn't have a file containing its ID, we need to process files
            else:
                print(f"Files found for logger ID {logger_id}: {matching_files}")

        print("All necessary files are already processed and available in the outputs folder.")
        return True  # All logger IDs have corresponding files in the outputs folder

    def concatenate_and_save_csvs(self, csv_files):
        """Concatenates multiple CSV files and saves the result.

        This method reads multiple CSV files, concatenates them into a single DataFrame,
        and saves the result to disk with appropriate column mappings and units.

        :param csv_files: A list of CSV file names to be concatenated.
        :type csv_files: list
        :return: The concatenated DataFrame and column metadata
        :rtype: tuple (pandas.DataFrame, dict)
        """
        dfs = []
        for file in csv_files:
            file_path = os.path.join(self.deployment_data_folder, file)
            try:
                data = self.read_csv(file_path)
                dfs.append(data)
                print(f"File: {file} - Successfully processed.")
            except Exception as e:
                print(f"Error processing file {file}: {e}")

        # Concatenate DataFrames
        if len(dfs) > 1:
            concatenated_df = pd.concat(dfs, ignore_index=True)
        else:
            concatenated_df = dfs[0]

        # Define a mapping of original column names to computer-friendly names
        column_mapping = {
            "Date (UTC)": "date-utc",
            "Time (UTC)": "time-utc",
            " Date (local)": "date",
            " Time (local)": "time",
            "Accelerometer X [m/s²]": "accX",
            "Accelerometer Y [m/s²]": "accY",
            "Accelerometer Z [m/s²]": "accZ",
            "Gyroscope X [mrad/s]": "gyrX",
            "Gyroscope Y [mrad/s]": "gyrY",
            "Gyroscope Z [mrad/s]": "gyrZ",
            "Magnetometer X [µT]": "magX",
            "Magnetometer Y [µT]": "magY",
            "Magnetometer Z [µT]": "magZ",
            "Temperature (imu) [°C]": "tempIMU",
            "Depth (100bar) 1 [m]": "depth",
            "Depth (100bar) 2 [°C]": "depth2",
            "Light intensity 1 [raw]": "light",
            "Light intensity 2 [raw]": "light2",
            "System error": "sysError",
            "BATT [V]": "battV",
            "BATT [mA]": "battA",
            "BATT [mAh]": "battAh",
            "Camera": "camera",
            "Flags": "flags",
            "LED": "led",
            "Camera time": "cameraTime",
            "GPS": "gps",
            "CC status": "ccStatus",
            " CC vid. size [kBytes]": "ccVidSize",
            # Add more mappings as needed
        }

        # Define units for the computer-friendly names
        units_mapping = {
            "date-utc": "datetime",
            "time-utc": "time",
            "date": "date",
            "time": "time",
            "accX": "m/s²",
            "accY": "m/s²",
            "accZ": "m/s²",
            "gyrX": "mrad/s",
            "gyrY": "mrad/s",
            "gyrZ": "mrad/s",
            "magX": "µT",
            "magY": "µT",
            "magZ": "µT",
            "tempIMU": "°C",
            "depth": "m",
            "depth2": "°C",
            "light": "raw",
            "light2": "raw",
            "sysError": "unknown",
            "battV": "V",
            "battA": "mA",
            "battAh": "mAh",
            "camera": "unknown",
            "flags": "unknown",
            "led": "unknown",
            "cameraTime": "unknown",
            "gps": "unknown",
            "ccStatus": "unknown",
            "ccVidSize": "kBytes",
            # Add more units as needed
        }

        # Create a dictionary to store original names, friendly names, and units
        column_metadata = {}

        for original_name in concatenated_df.columns:
            friendly_name = column_mapping.get(original_name, original_name)  # Use original name if not mapped
            column_metadata[friendly_name] = {
                "original_name": original_name,
                "unit": units_mapping.get(friendly_name, "unknown")  # Default to "unknown" if not mapped
            }

        # Apply the renaming to the DataFrame
        concatenated_df.rename(columns={v["original_name"]: k for k, v in column_metadata.items()}, inplace=True)

        return concatenated_df, column_metadata

    def process_datetime(self, df, time_zone=None):
        """Processes datetime columns in the DataFrame and calculates sampling frequency.

        This method creates a 'datetime' column from existing date and time columns, localizes
        the timestamps, converts them to UTC, and calculates the sampling frequency.

        :param df: The DataFrame containing the data to be processed.
        :type df: pandas.DataFrame
        :param time_zone: The time zone to localize the datetime column, defaults to None
        :type time_zone: str, optional
        :return: The processed DataFrame and metadata about the datetime processing
        :rtype: tuple (pandas.DataFrame, dict)
        """
        metadata = {
            'datetime_created_from': None,
            'fs': None
        }

        # If 'datetime' column exists, calculate sampling frequency and return
        if 'datetime' in df.columns:
            print("'datetime' column found.")
            metadata['datetime_created_from'] = 'datetime'
            
            # If time_zone is provided and datetime is naive, localize it
            if time_zone and df['datetime'].dt.tz is None:
                print(f"Localizing datetime using timezone {time_zone}.")
                tz = pytz.timezone(time_zone)
                df['datetime'] = df['datetime'].dt.tz_localize(tz)

            # Convert to UTC and Unix timestamp in milliseconds
            df['datetime_utc'] = df['datetime'].dt.tz_convert('UTC')
            df['time_unix_ms'] = df['datetime_utc'].astype(np.int64) // 10**6

            # Calculate time differences and sampling frequency
            df['sec_diff'] = df['datetime_utc'].diff().dt.total_seconds()
            if len(df) > 1:
                mean_diff = df['sec_diff'].mean()
                sampling_frequency = 1 / mean_diff if mean_diff else None
                max_timediff = np.max(df['sec_diff'])
                formatted_fs = f"{sampling_frequency:.5g}" # Using 5 significant figures to save fs
                print(f"Sampling frequency: {formatted_fs} Hz with a maximum time difference of {max_timediff} seconds")
                metadata['fs'] = formatted_fs
            else:
                print("Insufficient data points to calculate sampling frequency.")
                metadata['fs'] = None

            return df, metadata
            
        # If 'date' and 'time' columns exist, combine them to create 'datetime'
        elif 'time' in df.columns and 'date' in df.columns:
            print("'datetime' column not found. Combining 'date' and 'time' columns.")
            dates = pd.to_datetime(df['date'], format='%d.%m.%Y', errors='coerce')
            times = pd.to_timedelta(df['time'].astype(str))
            df['datetime'] = dates + times
            metadata['datetime_created_from'] = 'date and time'

        # If only 'time' column exists, use it to create 'datetime'
        elif 'time' in df.columns:
            print("'datetime' and 'date' columns not found. Trying to parse 'time' as datetime.")
            df['datetime'] = pd.to_datetime(df['time'], errors='coerce')
            metadata['datetime_created_from'] = 'time'

        # If no suitable columns are found, return the DataFrame as is
        else:
            print("No suitable columns found to create a 'datetime' column.")
            return df, metadata

        # Convert the newly created datetime to the specified timezone if not already timezone-aware
        if time_zone and df['datetime'].dt.tz is None:
            print(f"Localizing datetime using timezone {time_zone}.")
            tz = pytz.timezone(time_zone)
            df['datetime'] = df['datetime'].dt.tz_localize(tz)

        print("Converting to UTC and Unix.")
        df['datetime_utc'] = df['datetime'].dt.tz_convert('UTC')
        df['time_unix_ms'] = df['datetime_utc'].astype(np.int64) // 10**6

        # Calculate time differences and sampling frequency
        df['sec_diff'] = df['datetime_utc'].diff().dt.total_seconds()
        if len(df) > 1:
            mean_diff = df['sec_diff'].mean()
            sampling_frequency = 1 / mean_diff if mean_diff else None
            max_timediff = np.max(df['sec_diff'])
            formatted_fs = f"{sampling_frequency:.5g}" # Using 5 significant digits to save frequency
            print(f"Sampling frequency: {formatted_fs} Hz with a maximum time difference of {max_timediff} seconds")
            metadata['fs'] = formatted_fs
        else:
            print("Insufficient data points to calculate sampling frequency.")
            metadata['fs'] = None

        # Return the updated DataFrame and metadata
        return df, metadata



    def process_ube_file(self, ube_file):
        """Processes a UBE file and extracts data.

        This method reads a UBE file, extracts the relevant data, and returns it in a DataFrame.

        :param ube_file: The name of the UBE file to be processed.
        :type ube_file: str
        :return: The DataFrame containing the processed data and column metadata
        :rtype: tuple (pandas.DataFrame, dict)
        """
        file_path = os.path.join(self.deployment_data_folder, ube_file)
        try:
            data = self.read_ube(file_path)
            return data
        except Exception as e:
            print(f"Error processing UBE file {ube_file}: {e}")
            return None

    def read_ube(self, ube_path):
        """Reads and processes the raw data from a UBE file.

        This method reads the raw binary data from a UBE file, processes it, and returns
        a DataFrame with the extracted data.

        :param ube_path: The path to the UBE file.
        :type ube_path: str
        :return: The DataFrame containing the processed data and column metadata
        :rtype: tuple (pandas.DataFrame, dict)
        """
        if self.selected_deployment is None or self.selected_deployment.empty:
            print("Selected deployment metadata not found. Please ensure you have selected a deployment.")
            return None

        with open(ube_path, 'rb') as file:
            ube_raw = file.read()

        dl_time_str = ube_raw[0:32].decode('utf-8').strip()
        print(f"Parsed download timestamp string: '{dl_time_str}'")
        try:
            dl_time = datetime.strptime(dl_time_str, "%m-%d-%Y, %H:%M:%S")
        except ValueError as e:
            print(f"Error parsing timestamp: {dl_time_str} - {e}")
            raise

        # Extracting the record start time components
        mdhms = struct.unpack('BBBBB', ube_raw[32:37])
        now = datetime.now()
        record_start = datetime(now.year, mdhms[0], mdhms[1], mdhms[2], mdhms[3], mdhms[4])

        # Convert record_start to the correct timezone
        timezone = self.selected_deployment.get('Time Zone')
        if timezone:
            tz = pytz.timezone(timezone)
            record_start = tz.localize(record_start)
            print(f"Recording start time (localized): {record_start}")

        # Ensure the record_start date matches the Rec Date
        rec_date = pd.to_datetime(self.selected_deployment['Rec Date']).date()
        if record_start.date() != rec_date:
            print(f"Error: Recording start date {record_start.date()} does not match Rec Date {rec_date}.")
            raise ValueError(f"Recording start date {record_start.date()} does not match Rec Date {rec_date}.")

        data_raw = ube_raw[40:]

        ecg_channel = 0x20
        ecg_data = []

        for i in range(0, len(data_raw), 2):
            channel = data_raw[i]
            value = data_raw[i + 1]
            if (channel & 0xF0) == ecg_channel:
                ecg_value = (channel & 0x0F) << 8 | value
                ecg_data.append(ecg_value)

        print(f"Total ECG data points: {len(ecg_data)}")

        # Generate the datetime column for the ECG data
        ecg_time = [record_start + timedelta(seconds=i/100) for i in range(len(ecg_data))]

        result = pd.DataFrame({
            'datetime': ecg_time,
            'ecg': ecg_data
        })
        result.attrs['created'] = dl_time

        # Define a mapping of original column names to computer-friendly names
        column_mapping = {
            "datetime": "datetime",
            "ecg": "ecg",
        }

        # Define units for the computer-friendly names
        units_mapping = {
            "datetime": "datetime",
            "ecg": "microVolts",
            # Add more units as needed
        }

        # Create a dictionary to store original names, friendly names, and units
        column_metadata = {}

        for original_name in result.columns:
            friendly_name = column_mapping.get(original_name, original_name)  # Use original name if not mapped
            column_metadata[friendly_name] = {
                "original_name": original_name,
                "unit": units_mapping.get(friendly_name, "unknown")  # Default to "unknown" if not mapped
            }

        # Apply the renaming to the DataFrame
        result.rename(columns={v["original_name"]: k for k, v in column_metadata.items()}, inplace=True)

        return result, column_metadata

    def read_csv(self, csv_path):
        """Reads a CSV file with multiple encoding attempts.

        This method attempts to read a CSV file using different encodings and returns the
        data as a DataFrame.

        :param csv_path: The path to the CSV file.
        :type csv_path: str
        :return: The DataFrame containing the CSV data
        :rtype: pandas.DataFrame
        """
        encodings = ['utf-8', 'ISO-8859-1', 'windows-1252']
        for encoding in encodings:
            try:
                print(f"Attempting to read {csv_path} with encoding {encoding}")
                return pd.read_csv(csv_path, encoding=encoding)
            except UnicodeDecodeError as e:
                print(f"Error reading {csv_path} with encoding {encoding}: {e}")
        raise UnicodeDecodeError(f"Failed to read {csv_path} with available encodings.")

    def save_data(self, data, logger_id, filename, save_csv=True, save_parq=False):
        """Saves the processed data to disk in CSV and/or Parquet format.

        This method saves the processed data for a specific logger to disk, either as a
        CSV file, a Parquet file, or both.

        :param data: The DataFrame containing the data to be saved.
        :type data: pandas.DataFrame
        :param logger_id: The ID of the logger whose data is being saved.
        :type logger_id: str
        :param filename: The filename to save the data under.
        :type filename: str
        :param save_csv: Flag indicating whether to save the data as a CSV file, defaults to True
        :type save_csv: bool, optional
        :param save_parq: Flag indicating whether to save the data as a Parquet file, defaults to False
        :type save_parq: bool, optional
        """
        self.data[logger_id] = {}
        output_folder = os.path.join(self.deployment_data_folder, 'outputs')
        os.makedirs(output_folder, exist_ok=True)
        self.data[logger_id] = data

        if save_csv:
            csv_path = os.path.join(output_folder, f"{filename}")
            data.to_csv(csv_path, index=False)
            print(f"Data for {logger_id} successfully saved as CSV to: {csv_path}")

        if save_parq:
            # Ensure no non-serializable attributes exist for Parquet
            if hasattr(data, 'attrs'):
                data.attrs = {key: str(value) for key, value in data.attrs.items()}
            
            parq_path = os.path.join(output_folder, f"{os.path.splitext(filename)[0]}.parquet")
            data.to_parquet(parq_path, index=False)
            print(f"Data for {logger_id} successfully saved as Parquet to: {parq_path}")

        if not save_csv and not save_parq:
            print(f"Data for {logger_id} saved to attribute {filename} but not to CSV or Parquet.")
