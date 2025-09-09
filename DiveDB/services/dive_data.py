"""
Retrieved Data Manager
"""

import duckdb
import math
import numpy as np
import datetime
from pandas import Timestamp, Series
from edfio import Edf, EdfSignal, Recording, Patient, EdfAnnotation
import os.path
from pathlib import Path
import json
from typing import Dict, Optional
from .notion_orm import NotionORMManager


class DiveData:
    """Retrieved Data Manager"""

    def __init__(
        self,
        duckdb_relation: duckdb.DuckDBPyRelation,
        conn: duckdb.DuckDBPyConnection,
        notion_manager: Optional[NotionORMManager] = None,
        notion_db_map: Optional[Dict[str, str]] = None,
        notion_token: Optional[str] = None,
    ):
        self.duckdb_relation = duckdb_relation
        self.conn = conn

        # Initialize Notion ORM manager
        if notion_manager:
            self.notion_manager = notion_manager
        elif notion_db_map and notion_token:
            self.notion_manager = NotionORMManager(notion_db_map, notion_token)
        else:
            self.notion_manager = None

    def __getattr__(self, item):
        if hasattr(self.duckdb_relation, item):
            return getattr(self.duckdb_relation, item)

    def get_metadata(self):
        """Fetch logger id, animal id, and deployment id for each recording in `self.duckdb_relation`"""
        return get_metadata(self)

    def export_to_edf(self, output_dir: str):
        """Export data to a set of EDF files"""
        return export_to_edf(self, output_dir)


def get_metadata(divedata):
    """Get metadata from Notion"""
    if not divedata.notion_manager:
        raise Exception(
            "NotionORMManager not provided - cannot fetch metadata from Notion"
        )

    metadata = {}
    recording_ids = [
        id
        for id in divedata.duckdb_relation.unique("recording").df()["recording"].values
    ]

    # Get models for the Notion databases
    Recording = divedata.notion_manager.get_model("Recordings DB")
    Animal = divedata.notion_manager.get_model("Animals DB")
    Deployment = divedata.notion_manager.get_model("Deployments DB")

    for recording_id in recording_ids:
        recording_metadata = {}

        # Query Recordings database in Notion
        recording = Recording.objects.filter(id=recording_id).first()
        if not recording:
            raise Exception(f"Recording with id '{recording_id}' not found in Notion!")

        recording_metadata["logger_id"] = recording.logger_id
        recording_metadata["timezone"] = (
            recording.start_time.tzname()
            if hasattr(recording.start_time, "tzname")
            else None
        )
        recording_metadata["start_time"] = (
            recording.start_time.isoformat() if recording.start_time else None
        )

        # Query Animals database in Notion
        animal = Animal.objects.filter(id=recording.animal_id).first()
        if not animal:
            raise Exception(
                f"Animal with id '{recording.animal_id}' not found in Notion!"
            )

        # Query Deployments database in Notion
        deployment = Deployment.objects.filter(id=recording.deployment_id).first()
        if not deployment:
            raise Exception(
                f"Deployment with id '{recording.deployment_id}' not found in Notion!"
            )

        recording_metadata["animal_id"] = animal.id
        recording_metadata["deployment_id"] = deployment.id
        recording_metadata["recording_id"] = recording_id

        metadata[recording_id] = recording_metadata

    return metadata


def make_unique_edf_filename(
    output_dir, filename_prefix: str, max_suffix_int: int = 1000
):
    path_prefix = os.path.join(output_dir, filename_prefix)
    if not os.path.isfile(path_prefix + ".edf"):
        return path_prefix + ".edf"
    for i in range(1, max_suffix_int + 1):
        fname = path_prefix + "_" + str(i) + ".edf"
        if not os.path.isfile(fname):
            return fname
    raise Exception(
        f"Filepath already exists in directory ({path_prefix + '_' + str(max_suffix_int) + '.edf'})"
    )


def export_to_edf(data: DiveData, output_dir: str) -> list:
    """Export metadata plus signals to set of EDF files in `output_dir`"""
    edf_filepaths = []
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    metadata = data.get_metadata()
    for recording_id in metadata.keys():
        df = data.duckdb_relation.filter(f"recording='{recording_id}'").df()
        recording_metadata = metadata[recording_id]
        edf = construct_recording_edf(df, recording_metadata)
        edf_path = make_unique_edf_filename(output_dir, recording_id)
        edf.write(edf_path)
        edf_filepaths.append(edf_path)
    return edf_filepaths


def get_sampling_rate(timestamps: Series):
    """
    Calculate single sampling rate from input set of timestamps.

    Timestamps are assumed to be associated with a uniformly sampled, contiguous
    signal. If assumption is violated, output sampling rate will be wildly incorrect.
    No validation is performed to check for assumptions.
    """
    sample_diffs_sec = timestamps.diff()[1:].dt.total_seconds()
    sampling_interval_median = sample_diffs_sec.median()
    return 1 / sampling_interval_median


def get_pad_value_for_signal(signal_name):
    """
    Get signal-specific data padding value. Currently always returns zero!!!

    Pulled out as subfunction (and filed in issue tracker) to highlight this limitation.
    Should be implemented as signal-specific value, either specific to type of
    signal or derived from min/max value in signal data itself.
    """
    return np.float64(0)


def get_signal_offset_index(
    signal_starttime: datetime, signal_sampling_rate, recording_starttime: datetime
):
    """
    Calculate the sample index for the offset padding between a signal's start time
    relative to its recording's start time.

    Correctness note: The resultant sample offset relative to the start of the
    `recording_starttime` (and therefore also other signals) may be off by as much
    as 1 / sampling_rate seconds. ¯\\_(ツ)_/¯
    Nothing we can do---such is the life of conforming to the EDF spec!
    """
    # By definition of how the recording start time was constructed,
    # the offset_sec will always be positive
    offset_sec = (recording_starttime - signal_starttime).total_seconds()
    i = round(offset_sec * signal_sampling_rate)
    return i


def get_edf_label_for_signal(signal_class_name, signal_name):
    """
    Return a signal label that conforms to EDF spec label length requirements (<17 characters)

    Adds class name as prefix to signal name, e.g. for multichannel sensor output,
    where each channel is an individual signal in the resultant EDF (e.g. for
    accelerometer x, y, and z signals).
    """
    if signal_class_name.startswith("sensor_data"):
        class_prefix = signal_class_name[12:]
    elif signal_class_name.startswith("derived_data"):
        class_prefix = "derived_" + signal_class_name[13:]
    else:
        class_prefix = signal_class_name

    if signal_class_name == signal_name:
        label = (
            class_prefix if len(class_prefix) <= 16 else class_prefix[0:16]
        )  # lol EDF
    else:
        max_prefix_length = 16 - len(signal_name) - 1  # lol EDF limits
        if max_prefix_length < 0:
            max_prefix_length = 0
        class_prefix = (
            class_prefix
            if len(class_prefix) <= max_prefix_length
            else class_prefix[0:max_prefix_length]
        )
        label = class_prefix + "-" + signal_name
        if len(label) > 16:
            label = label[0:16]
    return label


def data_processing_details(signal_class_name):
    if signal_class_name.startswith("derived_data"):
        return "derived"
    elif signal_class_name.startswith("sensor_data"):
        return "sensor"
    else:
        return ""


def get_physical_dimension(signal_name):
    """
    Return the physical dimension of a signal. Currently always returns `Unknown`!!!

    Pulled out as subfunction (and filed in issue tracker) to highlight this limitation.
    It *should* be specified per-signal basis, either hard-coded based on type of signal
    (mvp, correctness risk) or passed in by the user (annoying but less correctness risk)
    or gleaned from the db (best! but does not yet exist in db)
    """
    return "Unknown"


def construct_recording_edf(multisignal_data_df, metadata):
    """
    Return an `edfio.Edf` constructed from an input table of timestamps from
    multiple sensor signals belonging to a single recording.

    Assumes and does not validate that input is (a) from a single recording and
    (b) each signal is uniformly sampled and continuous (i.e., no gaps).
    """
    # EDF signals must all be the same length within an EDF record
    # (in seconds, irrespective of sampling rate)---so figure out what those bounds
    # are for the overall recording so that we can pad each signal appropriately
    all_timestamps = multisignal_data_df.sort_values("datetime")["datetime"]
    recording_start_datetime = Timestamp(all_timestamps.iloc[0]).to_pydatetime()
    recording_end_datetime = Timestamp(all_timestamps.iloc[-1]).to_pydatetime()

    # To meet EDF requirement, round the total duration (up) to the nearest second
    recording_duration_sec = math.ceil(
        (recording_end_datetime - recording_start_datetime).total_seconds()
    )

    # Iterate through each signal in the recording
    signals = []
    signal_names = [
        n
        for n in list(multisignal_data_df.columns)
        if n not in ["datetime", "class", "recording"]
    ]
    for name in signal_names:
        df_sig = multisignal_data_df[["datetime", "class", name]]
        df_sig = df_sig[df_sig[name].notna()]
        df_sig = df_sig.sort_values(by=["datetime"])

        # Construct the signal data, padded relative to the overall recording
        timestamps = df_sig.sort_values("datetime")["datetime"]
        sampling_rate = get_sampling_rate(timestamps)
        signal_start_datetime = Timestamp(timestamps.iloc[0]).to_pydatetime()
        i_start_sample = get_signal_offset_index(
            signal_start_datetime, sampling_rate, recording_start_datetime
        )
        pad_value = get_pad_value_for_signal(name)
        signal_data = np.full(
            math.ceil(recording_duration_sec * sampling_rate),
            pad_value,
            dtype=np.float64,
        )
        signal_data[i_start_sample : timestamps.size] = df_sig[name].values

        # Assemble the signal metadata
        signal_class = df_sig["class"].unique()[0]
        label = get_edf_label_for_signal(signal_class, name)
        physical_dimension = get_physical_dimension(name)
        processing_details_str = data_processing_details(signal_class)

        signal = EdfSignal(
            signal_data,
            sampling_frequency=sampling_rate,
            label=label,
            physical_dimension=physical_dimension,
            prefiltering=processing_details_str,
        )
        signals.append(signal)

    # Construct the full EDF!
    edf = Edf(signals, starttime=recording_start_datetime.time())
    edf.recording = Recording(startdate=recording_start_datetime.date())

    # Add additional metadata
    # We do this by adding an annotation, because the EDF metadata fields are human
    # (and EEG) specific, and have arbitrary (short) character limits. Safer
    # to pack it all into an annotation!
    metadata_str = json.dumps(metadata)
    edf.add_annotations(
        [
            EdfAnnotation(0, None, metadata_str),
        ]
    )
    subject_code = metadata["animal_id"]
    edf.patient = Patient(code=subject_code.replace(" ", "_"))
    return edf
