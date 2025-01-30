"""
EDF Export Manager
"""

import duckdb
import math
import numpy as np
import datetime
from pandas import Timestamp, Series
from edfio import Edf, EdfSignal, Patient, Recording, EdfAnnotation
import os.path
from pathlib import Path
import json


# TODO-clarify: spec says DuckDBPyConnection but get_delta_data returns a Relation
# (and explicitly says it doesn't pull data into memory)---using a relation here
# Followed proxy pattern to extend class: 
# https://stackoverflow.com/questions/69313845/create-child-class-object-using-parent-class-instance
class DiveData():
    """EDF Export Manager"""
    def __init__(self, duckdb_relation: duckdb.DuckDBPyRelation, conn: duckdb.DuckDBPyConnection):
        self.duckdb_relation = duckdb_relation
        self.recording_ids = [id for id in duckdb_relation.unique('recording').df()['recording'].values]
        # TODO-check: based on spec, required to set this here... Seems better to
        # calculate metadata immediately and not save, though...
        self.conn = conn
        self.metadata = None

    def __getattr__(self, item):
        if hasattr(self.duckdb_relation, item):
            return getattr(self.duckdb_relation, item)

    def get_metadata(self):
        if self.metadata is not None:
            print("Warning: Overwriting existing metadata!")
        self.metadata = get_metadata(self)
    
    def export_to_edf(self, output_dir: str):
        """Export metadata plus signals to set of EDF files"""
        return export_to_edf(self, output_dir)

#####
# Utils
#####


def get_metadata(divedata: DiveData):
    """Get metadata from postgres"""
    metadata = {}
    for recording_id in divedata.recording_ids:
        recording_metadata = {}
        df = divedata.conn.sql(f"""
                            SELECT start_time, animal_deployment_id, logger_id
                            FROM Metadata.public.Recordings
                            WHERE Recordings.id = '{recording_id}'
                        """).df()
        if df.shape[0] != 1:
            raise(Exception("Multiple recording entries unexpectedly returned for single recording_id!"))
        recording_metadata['logger_id'] = df['logger_id'][0]

        animal_deployment_id = df['animal_deployment_id'][0]
        df = divedata.conn.sql(f"""
                            SELECT animal_id, deployment_id
                            FROM Metadata.public.Animal_Deployments
                            WHERE Animal_Deployments.id = '{animal_deployment_id}'
                        """).df()
        if df.shape[0] != 1:
            raise(Exception("Multiple deployment entries unexpectedly returned for single animal_deployment_id!"))
        recording_metadata['animal_id'] = df['animal_id'][0]
        recording_metadata['deployment_id'] = df['deployment_id'][0]
        recording_metadata['recording_id'] = recording_id
        metadata[recording_id] = recording_metadata
    return metadata


def make_unique_edf_filename(output_dir, filename_prefix: str, max_suffix_int: int = 1000):
    path_prefix = os.path.join(output_dir, filename_prefix)
    if not os.path.isfile(path_prefix + ".edf"):
        return path_prefix + ".edf"
    for i in range(1, max_suffix_int + 1):
        fname = path_prefix + "_" + str(i) + ".edf"
        if not os.path.isfile(fname):
            return fname
    raise Exception(f"Filepath already exists in directory ({path_prefix + ".edf"})")


def export_to_edf(data: DiveData, output_dir: str) -> list:
    """Export metadata plus signals to set of EDF files"""
    edf_filepaths = []
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    data.get_metadata()  # TODO-CHECK: always, or only if it's None already?
    for recording_id in data.metadata.keys():
        df = data.duckdb_relation.filter(f"recording='{recording_id}'").df()
        recording_metadata = data.metadata[recording_id]
        edf = construct_recording_edf(df, recording_metadata)
        edf_path = make_unique_edf_filename(output_dir, recording_id)
        edf.write(edf_path)
        edf_filepaths.append(edf_path)
    return edf_filepaths


# For now, assumes timestamps are contiguous and uniformly sampled
# Due to floating point differences when sampling rate was originally stored in
# timestamp format,
# TODO-file-future: If there are gaps in the timestamps, throw a warning (and/or
# support them)
# TODO-file-future: Check that sampling rate is uniform and isn't missing samples
def get_sampling_rate(timestamps: Series):
    sample_diffs_sec = timestamps.diff()[1:].dt.total_seconds()
    sampling_interval_median = sample_diffs_sec.median()
    return 1 / sampling_interval_median


# TODO-file-future: Should be on a per-signal basis, either hard-coded (eh) or passed in
# by the user (better) or gleaned from the db (best, but requires storing in db!)
def get_pad_value_for_signal(signal_name):
    print(f"Warning: Signal-specific padding value not yet implemented for `{signal_name}` (default: `0`)")
    return np.float64(0)


# Correctness note: The start time relative to the start of the recording (and therefore
# other signals) may be off by as much as 1/sampling_rate seconds. ¯\_(ツ)_/¯
# Nothing we can do---such is the life of conforming to the EDF spec!
def get_signal_offset_index(signal_starttime: datetime, sampling_rate,
                            recording_starttime: datetime):
    # We know (by definition of how the recording start time was constructed) that
    # the difference here will always be positive
    offset_sec = (recording_starttime - signal_starttime).total_seconds()
    i = round(offset_sec * sampling_rate)
    return i


# Conform to EDF spec naming requirements
# TODO-file-future: Define specific rules for constructing signal name from class and label
# TODO-file-future: Validate that signal names are unique within file
def signal_name(signal_class_name, signal_name):
    if signal_class_name.startswith("sensor_data"):
        class_prefix = signal_class_name[12:]
    elif signal_class_name.startswith("derived_data"):
        class_prefix = "derived_" + signal_class_name[13:]
    else:
        class_prefix = signal_class_name

    if signal_class_name == signal_name:
        label = class_prefix if len(class_prefix) <= 16 else class_prefix[0:16]  # lol EDF
    else:
        max_prefix_length = 16 - len(signal_name) - 1  # lol EDF limits
        if max_prefix_length < 0:
            max_prefix_length = 0
        class_prefix = class_prefix if len(class_prefix) <= max_prefix_length else class_prefix[0:max_prefix_length]
        label = class_prefix + "-" + signal_name
        if len(label) > 16:
            label = label[0:16]
    return label


# TODO-file-future: Handle differently (or don't return at all! might be feature creep)
def data_processing_details(signal_class_name):
    if signal_class_name.startswith("derived_data"):
        return "derived"
    elif signal_class_name.startswith("sensor_data"):
        return "sensor"
    else:
        return ""


# TODO-file-future: Should be on a per-signal basis, either hard-coded (eh) or passed in
# by the user (better) or gleaned from the db (best, but requires storing in db!)
def get_physical_dimension(signal_name):
    return "Unknown"


# Assumes we've been passed a single recording and that all signals in it are valid and continuous
# TODO-future-file: validate that individual signals are not discontinuous
def construct_recording_edf(df, metadata):
    # Iterate through each signal (class + label) in the recording 
    signal_names = [n for n in list(df.columns)if n not in ['datetime', 'class', 'recording']]

    # EDF signals must all be the same length within an EDF record
    # (in seconds, irrespective of sampling rate)---so figure out what those bounds 
    # are before doing anything else
    all_timestamps = df.sort_values('datetime')['datetime']
    recording_start_datetime = Timestamp(all_timestamps.iloc[0]).to_pydatetime()
    recording_end_datetime = Timestamp(all_timestamps.iloc[-1]).to_pydatetime()

    # For EDF reasons, round the total duration up so to the nearest second
    recording_duration_sec = math.ceil((recording_end_datetime - recording_start_datetime).total_seconds())

    signals = []
    for name in signal_names:
        df_sig = df[['datetime', 'class', name]]
        df_sig = df_sig[df_sig[name].notna()]
        df_sig = df_sig.sort_values(by=['datetime'])

        # Construct the signal data, padded relative to the overall recording
        timestamps = df_sig.sort_values('datetime')['datetime']
        sampling_rate = get_sampling_rate(timestamps)
        signal_start_datetime = Timestamp(timestamps.iloc[0]).to_pydatetime()
        i_start_sample = get_signal_offset_index(signal_start_datetime,
                                                 sampling_rate, recording_start_datetime)
        pad_value = get_pad_value_for_signal(name)
        signal_data = np.full(math.ceil(recording_duration_sec * sampling_rate), pad_value,
                              dtype=np.float64)
        signal_data[i_start_sample:timestamps.size] = df_sig[name].values

        # Assemble the signal metadata
        signal_class = df_sig['class'].unique()[0]
        label = signal_name(signal_class, name)
        physical_dimension = get_physical_dimension(name)
        processing_details_str = data_processing_details(signal_class)
        
        signal = EdfSignal(signal_data,
                           sampling_frequency=sampling_rate,
                           label=label,
                           physical_dimension=physical_dimension,
                           prefiltering=processing_details_str)
        signals.append(signal)

    # Construct the full EDF!
    edf = Edf(signals, starttime=recording_start_datetime.time())
    edf.recording = Recording(startdate=recording_start_datetime.date())

    # Add additional metadata
    # We do this by adding an annotation, because the EDF metadata fields are human
    # (and EEG) specific, and have arbitrary (short) character limits. Safer 
    # to pack it all into an annotation!
    metadata_str = json.dumps(metadata)
    edf.add_annotations([EdfAnnotation(0, None, metadata_str),])

    return edf
