"""
Data Uploader
"""

import os
import edfio
import django
from services.metadata_manager import MetadataManager
from services.duck_pond import DuckPond
import numpy as np
import gc
import pyarrow as pa
from tqdm import tqdm

# import pyarrow.compute as pc
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from services.utils.openstack import SwiftClient

duckpond = DuckPond()
swift_client = SwiftClient()

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.django_app.settings")
django.setup()

from server.metadata.models import Files  # noqa: E402


@dataclass
class SignalMetadata:
    signal_name: str
    frequency: float
    start_time: str
    end_time: str


@dataclass
class SignalData:
    signal_name: str
    time: pa.Array
    data: np.ndarray
    signal_length: int


DataSchema = pa.schema(
    [
        pa.field("signal_name", pa.string()),
        pa.field("datetime", pa.timestamp("us", tz="UTC")),
        pa.field("data", pa.float64()),
        pa.field("animal", pa.string()),
        pa.field("deployment", pa.string()),
        pa.field("logger", pa.string()),
        pa.field("recording", pa.string()),
    ]
)

MetadataSchema = pa.schema(
    [
        pa.field("signal_name", pa.string()),
        pa.field("freq", pa.int16()),
        pa.field("start_time", pa.timestamp("us", tz="UTC")),
        pa.field("end_time", pa.timestamp("us", tz="UTC")),
    ]
)


class DataUploader:
    """Data Uploader"""

    def read_signal(self, edf: edfio.Edf, signal_name: str):
        """Function to read a single signal from an EDF file."""
        signal = edf.get_signal(signal_name)
        data = signal.data
        start_datetime_str = f"{edf.startdate}T{edf.starttime}"
        start_time = np.datetime64(start_datetime_str).astype("datetime64[us]")
        freq = signal.sampling_frequency
        data_indices = np.arange(len(data)) / float(freq)
        timedelta_array = (data_indices * 1000000).astype("timedelta64[us]")
        times = pa.array(
            start_time + timedelta_array, type=pa.timestamp("us", tz="UTC")
        )
        end_time = times[-1].as_py().replace(tzinfo=timezone.utc)

        return (
            SignalData(
                signal_name=signal_name, time=times, data=data, signal_length=len(data)
            ),
            SignalMetadata(
                signal_name=signal_name,
                frequency=freq,
                start_time=start_time.astype(datetime)
                .replace(tzinfo=timezone.utc)
                .isoformat(),
                end_time=end_time.isoformat(),
            ),
        )

    def upload_edf(
        self,
        edf_file_paths: list[str],
        csv_metadata_path: str,
        csv_metadata_map: dict = None,
        signals: list[str] = "all",
        batch_size: int = 20000000,  # The slower the batch size, the slower and the more memory efficient. 20M stays comfortably under 8GB of RAM.
    ):
        """
        Uploads EDF data to the database and DuckPond.

        Parameters:
        edf_file_paths (list[str]): List of paths to EDF files.
        csv_metadata_path (str): Path to the CSV file containing metadata.
        csv_metadata_map (dict, optional): Mapping for CSV metadata. Defaults to None.
        signals (list[str], optional): List of signals to process. Defaults to "all".
        batch_size (int, optional): Size of data batches for processing. Defaults to 20,000,000.

        Workflow:
        1. Retrieves metadata models from the CSV file.
        2. Calculates the total number of signals to process.
        3. Initializes a progress bar for signal processing.
        4. For each EDF file:
        - Reads the EDF file and its signals.
        - Processes each signal in batches.
        - Creates and uploads data batches to DuckPond.
        - Updates the progress bar.
        5. Prints a completion message.
        """

        metadata_manager = MetadataManager()
        metadata_models = metadata_manager.get_metadata_models(
            csv_metadata_path, csv_metadata_map
        )

        # Calculate total number of signals to process
        total_signals = 0
        for edf_file_path in edf_file_paths:
            edf = edfio.read_edf(edf_file_path, lazy_load_data=True)
            total_signals += len(signals if signals != "all" else edf.signals)
            # Add this once we have a dev bucket
            # swift_client.put_object_to_swift(
            #     container_name="EDF_DATA",
            #     object_name=file.file_path,
            #     contents=edf,
            # )

        # Initialize progress bar
        print(f"Processing {total_signals} signals in {len(edf_file_paths)} files.")
        with tqdm(total=total_signals, desc="Processing signals") as pbar:
            for edf_file_path in edf_file_paths:
                edf = edfio.read_edf(edf_file_path, lazy_load_data=True)

                for signal in signals if signals != "all" else edf.signals:
                    signalData, signalMetadata = self.read_signal(edf, signal.label)

                    # Process data in batches
                    for start in range(0, signalData.signal_length, batch_size):
                        end = min(start + batch_size, signalData.signal_length)
                        length = end - start

                        # Create repeated arrays using list multiplication
                        signal_name_array = pa.array(
                            [signalData.signal_name] * length, type=pa.string()
                        )
                        animal_array = pa.array(
                            [metadata_models["animal"].id] * length, type=pa.string()
                        )
                        deployment_array = pa.array(
                            [metadata_models["deployment"].id] * length,
                            type=pa.string(),
                        )
                        logger_array = pa.array(
                            [metadata_models["logger"].id] * length, type=pa.string()
                        )
                        recording_array = pa.array(
                            [metadata_models["recording"].id] * length, type=pa.string()
                        )

                        # Create PyArrow table with repeated and direct data columns
                        batch_table = pa.table(
                            {
                                "signal_name": signal_name_array,
                                "datetime": pa.array(signalData.time[start:end]),
                                "data": pa.array(
                                    signalData.data[start:end], type=pa.float64()
                                ),
                                "animal": animal_array,
                                "deployment": deployment_array,
                                "logger": logger_array,
                                "recording": recording_array,
                            },
                            schema=DataSchema,
                        )

                        # Create a new file
                        file = Files.objects.create(
                            recording=metadata_models["recording"],
                            file_path=edf_file_path,
                            extension="edf",
                            type="data",
                            metadata=asdict(signalMetadata),
                        )

                        duckpond.write_to_delta(
                            data=batch_table,
                            schema=DataSchema,
                            mode="append",  # Use append mode for batching
                            partition_by=[
                                "logger",
                                "animal",
                                "deployment",
                                "recording",
                                "signal_name",
                            ],
                            name=file.file_path,
                            description="test",
                        )
                        del batch_table
                        gc.collect()

                    del signalData
                    gc.collect()

                    # Update progress bar
                    pbar.update(1)

        print("Upload complete.")
