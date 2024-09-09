"""
Data Uploader
"""

import os
import edfio
import django
from django.core.files import File
from DiveDB.services.metadata_manager import MetadataManager
from DiveDB.services.duck_pond import DuckPond
import numpy as np
import gc
import pyarrow as pa
from tqdm import tqdm
import xarray as xr

# import pyarrow.compute as pc
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from DiveDB.services.utils.openstack import SwiftClient

duckpond = DuckPond()
swift_client = SwiftClient()

django_prefix = os.environ.get("DJANGO_PREFIX", "DiveDB")
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", f"{django_prefix}.server.django_app.settings"
)
django.setup()

from DiveDB.server.metadata.models import Files, Recordings  # noqa: E402


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
        # Keep schema in order of partitions
        pa.field("logger", pa.string()),
        pa.field("signal_name", pa.string()),
        pa.field("animal", pa.string()),
        pa.field("deployment", pa.string()),
        pa.field("recording", pa.string()),
        pa.field("data_labels", pa.string()),
        pa.field("datetime", pa.timestamp("us", tz="UTC")),
        pa.field("values", pa.list_(pa.float64())),
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

    def _read_edf_signal(self, edf: edfio.Edf, signal_name: str):
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
        batch_size: int = 10000000,  # The smaller the batch size, the slower and the more memory efficient. 10M stays comfortably under 8GB of RAM.
        metadata: dict = None,
    ):
        """
        Uploads EDF data to the database and DuckPond.

        Parameters:
        edf_file_paths (list[str]): List of paths to EDF files.
        csv_metadata_path (str): Path to the CSV file containing metadata.
        csv_metadata_map (dict, optional): Mapping for CSV metadata. Defaults to None.
        signals (list[str], optional): List of signals to process. Defaults to "all".
        batch_size (int, optional): Size of data batches for processing. Defaults to 20,000,000.
        metadata (dict, optional): Metadata dictionary. Defaults to None.
            Required keys:
                - animal: Animal ID (int)
                - deployment: Deployment Name (str)
                - logger: Logger ID (int)
                - recording: Recording Name (str)

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
        if not metadata:
            metadata_manager = MetadataManager()
            metadata_models = metadata_manager.get_metadata_models(
                csv_metadata_path, csv_metadata_map
            )
            metadata = {
                "animal": metadata_models["animal"].id,
                "deployment": metadata_models["deployment"].deployment_name,
                "logger": metadata_models["logger"].id,
                "recording": metadata_models["recording"].name,
            }

        # Calculate total number of signals to process
        total_signals = 0
        for edf_file_path in edf_file_paths:
            edf = edfio.read_edf(edf_file_path, lazy_load_data=True)
            total_signals += len(signals if signals != "all" else edf.signals)

        # Create a new file record
        file = Files.objects.create(
            recording=Recordings.objects.get(name=metadata["recording"]),
            extension="edf",
            type="data",
            # TODO: Add metadata to the file object
            metadata=asdict(edf.annotations),
        )

        # Initialize progress bar
        print(f"Processing {total_signals} signals in {len(edf_file_paths)} files.")
        with tqdm(total=total_signals, desc="Processing signals") as pbar:
            for edf_file_path in edf_file_paths:
                edf = edfio.read_edf(edf_file_path, lazy_load_data=True)
                edf_signals = (
                    edf.signals
                    if signals == "all"
                    else filter(lambda signal: signal.label in signals, edf.signals)
                )
                for signal in edf_signals:
                    signalData, signalMetadata = self._read_edf_signal(
                        edf, signal.label
                    )

                    # Process data in batches
                    for start in range(0, signalData.signal_length, batch_size):
                        end = min(start + batch_size, signalData.signal_length)
                        length = end - start

                        # Create repeated arrays using list multiplication
                        signal_name_array = pa.array(
                            [signalData.signal_name] * length, type=pa.string()
                        )
                        animal_array = pa.array(
                            [metadata["animal"]] * length, type=pa.string()
                        )
                        deployment_array = pa.array(
                            [metadata["deployment"]] * length,
                            type=pa.string(),
                        )
                        logger_array = pa.array(
                            [metadata["logger"]] * length, type=pa.string()
                        )
                        recording_array = pa.array(
                            [metadata["recording"]] * length, type=pa.string()
                        )
                        data_labels_array = pa.array(
                            ["value"] * length, type=pa.string()
                        )
                        values_array = pa.array(
                            [[v] for v in signalData.data[start:end]],
                            type=pa.list_(pa.float64()),
                        )

                        # Create PyArrow table with repeated and direct data columns
                        batch_table = pa.table(
                            {
                                "signal_name": signal_name_array,
                                "animal": animal_array,
                                "deployment": deployment_array,
                                "logger": logger_array,
                                "recording": recording_array,
                                "data_labels": data_labels_array,
                                "datetime": pa.array(
                                    signalData.time[start:end],
                                    type=pa.timestamp("us", tz="UTC"),
                                ),
                                "values": values_array,
                            },
                            schema=DataSchema,
                        )

                        duckpond.write_to_delta(
                            data=batch_table,
                            schema=DataSchema,
                            mode="overwrite",
                            partition_by=[
                                "logger",
                                "animal",
                                "deployment",
                                "recording",
                                "signal_name",
                                "data_labels",
                            ],
                            name=file.file_path if file else "Test",
                            description="test",
                            schema_mode="overwrite",
                        )
                        del batch_table
                        gc.collect()

                    del signalData
                    gc.collect()

                    # Update progress bar
                    pbar.update(1)

        print("Upload complete.")

    def upload_netcdf(
        self, netcdf_file_path: str, metadata: dict, batch_size: int = 1000000
    ):
        """
        Uploads a netCDF file to the database and DuckPond.

        Parameters:
        netcdf_file_path (str): Path to the netCDF file.
        metadata (dict): Metadata dictionary.
            Required keys:
                - animal: Animal ID (int)
                - deployment: Deployment Name (str)
                - logger: Logger ID (int)
                - recording: Recording Name (str)
        batch_size (int, optional): Size of data batches for processing. Defaults to 10,000,000.
        """
        ds = xr.open_dataset(netcdf_file_path)

        # Create a new file record
        print(
            f"Creating file record for {os.path.basename(netcdf_file_path)} and uploading to OpenStack..."
        )
        with open(netcdf_file_path, "rb") as f:
            file_object = File(f, name=os.path.basename(netcdf_file_path))
            file = Files.objects.create(
                recording=Recordings.objects.get(name=metadata["recording"]),
                file=file_object,
                extension="nc",
                type="data",
                metadata={
                    key: (
                        value.item()
                        if isinstance(value, (np.integer, np.floating))
                        else value
                    )
                    for key, value in ds.attrs.items()
                },
            )

        total_vars = len(ds.data_vars)

        print(f"Processing {total_vars} variables in the netCDF file.")
        with tqdm(total=total_vars, desc="Processing variables") as pbar:
            # Upload each variable in the netCDF file
            for var_name, var_data in ds.data_vars.items():
                for start in range(0, var_data.shape[0], batch_size):
                    end = min(start + batch_size, var_data.shape[0])
                    length = end - start

                    # Get the corresponding time coordinate, assuming time is always the first dimension
                    time_coord = var_data.dims[0]
                    times = pa.array(
                        ds.coords[time_coord].values[start:end],
                        type=pa.timestamp("us", tz="UTC"),
                    )

                    values = [list(row) for row in var_data.values[start:end]]
                    # Unpack variable names from the second dimension
                    if "variables" in var_data.attrs:
                        if isinstance(var_data.attrs["variables"], (list, np.ndarray)):
                            labels = "___".join(var_data.attrs["variables"])
                        else:
                            labels = var_data.attrs["variables"]
                    else:
                        labels = "___".join(
                            f"var_{i}" for i in range(var_data.shape[1])
                        )

                    # Create the batch table
                    batch_table = pa.table(
                        {
                            "logger": pa.array(
                                [metadata["logger"]] * length, type=pa.string()
                            ),
                            "signal_name": pa.array(
                                [var_name] * length, type=pa.string()
                            ),
                            "animal": pa.array(
                                [metadata["animal"]] * length, type=pa.string()
                            ),
                            "deployment": pa.array(
                                [metadata["deployment"]] * length, type=pa.string()
                            ),
                            "recording": pa.array(
                                [metadata["recording"]] * length, type=pa.string()
                            ),
                            "data_labels": pa.array(
                                [labels] * length, type=pa.string()
                            ),
                            "datetime": times,
                            "values": pa.array(values, type=pa.list_(pa.float64())),
                        },
                        schema=DataSchema,
                    )

                    duckpond.write_to_delta(
                        data=batch_table,
                        schema=DataSchema,
                        mode="append",
                        partition_by=[
                            "logger",
                            "animal",
                            "deployment",
                            "recording",
                            "signal_name",
                            "data_labels",
                        ],
                        name=file.file.name,
                        description="test",
                    )

                    del batch_table
                    gc.collect()

                # Update progress bar
                pbar.update(1)

        print("Upload complete.")
