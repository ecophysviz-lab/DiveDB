"""
EDF Export Manager
"""

import duckdb
import math
import numpy as np
from edfio import Edf, EdfSignal


# TODO-clarify: spec says DuckDBPyConnection but get_delta_data returns a Relation 
# (and explicitly says it doesn't pull data into memory)---using a relation here 
# Followed proxy pattern to extend class: https://stackoverflow.com/questions/69313845/create-child-class-object-using-parent-class-instance
class DiveData():
    """EDF Export Manager"""
    def __init__(self, duckdb_relation: duckdb.DuckDBPyRelation, conn: duckdb.DuckDBPyConnection):
        self.duckdb_relation = duckdb_relation
        self.recording_ids = [id for id in duckdb_relation.unique('recording').df()['recording'].values]
        # TODO-check: based on spec, required to set this here... Seems better to calculate metadata immediately and not save, though...
        self.conn = conn
        self.metadata = None

    def __getattr__(self, item):
        if hasattr(self.duckdb_relation, item):
            return getattr(self.duckdb_relation, item)

    def get_metadata(self):
        if self.metadata is not None:
            print("Warning: Overwriting existing metadata!")
        self.metadata = get_metadata(self)
    
    def export_to_edf(self, filepath: str):
        """Export metadata plus signals to set of EDF files"""
        export_to_edf(self, filepath)

#####
##### Utils
#####


def get_metadata(divedata: DiveData):
    """Get metadata from postgres"""
    metadata = {}
    for recording_id in divedata.recording_ids:
        # print("Recording: ", recording_id)
        recording_metadata = {}
        df = divedata.conn.sql("""
                            SELECT start_time, animal_deployment_id, logger_id
                            FROM Metadata.public.Recordings
                            WHERE Recordings.id = '2019-11-08_apfo-001a_apfo-001a_CC-35'
                        """).df()
        if df.shape[0] != 1:
            print("Oh no more than one item for this recording") # TODO-throw error 
        for col in list(['start_time', 'animal_deployment_id', 'logger_id']):
            recording_metadata[col] = df[col][0]
        metadata[recording_id] = recording_metadata
    return metadata


# TODO- maybe get rid of this depending on whether we still want to pass in filename, 
# rather than output directory
def get_filename(filename, i_recording, num_recordings):
    if num_recordings == 1 and filename.lower().endswith(".edf"):
        return filename 
    if num_recordings == 1:
        return filename + ".edf"
    prefix = filename[:-4] if filename.lower().endswith(".edf") else filename
    return prefix + "_" + str(i_recording + 1) + ".edf"


# TODO-clarify: spec says output path; when we generate multiple files, 
# how to handle? for now, appending an index...
def export_to_edf(data: DiveData, filepath: str) -> list:
    """Export metadata plus signals to set of EDF files"""
    edf_filepaths = []
    data.get_metadata()  # TODO-CHECK: always, or only if it's None already?
    df = data.duckdb_relation.df()  # TODO: filter down to specific recording_id before materializing?
    for (i, recording_id) in enumerate(data.metadata.keys()):
        metadata = data.metadata[recording_id]
        recording_filepath = get_filename(filepath, i, len(data.recording_ids))
        edf = create_edf(df, metadata)
        edf.write(recording_filepath)
        edf_filepaths.append(recording_filepath)
    return edf_filepaths


def create_edf(df, metadata):
    # Iterate through each signal (class + label) in the recording 
    signal_names = [n for n in list(df.columns)if n not in ['datetime', 'class', 'recording']]

    # Set up: Figure out what common max duration is
    max_duration_sec = 0
    for name in signal_names:
        df_sig = df[['datetime', name]]
        df_sig = df_sig[df_sig[name].notna()]
        df_sig = df_sig.sort_values(by=['datetime'])

        sampling_rate = df_sig['datetime'].diff()[1:].dt.total_seconds().unique()[0] #TODO-safety: handle correctly if there are any gaps filtered out (eg from nonna() earlier)
        sampling_frequency = int(1/sampling_rate) # TODO-safety: don't just blindly round o_O

        # start_time = df_sig['datetime'].values[0] # TODO - store this and sanity-check all signals start at the same time (or adjust!)

        sig_max_duration_sec = math.ceil(df.shape[0] / sampling_frequency)
        max_duration_sec = max(max_duration_sec, sig_max_duration_sec)

    signals = []
    for name in signal_names:
        df_sig = df[['datetime', 'class', name]]
        df_sig = df_sig[df_sig[name].notna()]
        df_sig = df_sig.sort_values(by=['datetime'])

        # TODO-safety: check that there's only one value after the unique, check that 
        # this is an integer value or whatever the EDF spec requires, etc
        sampling_rate = df_sig["datetime"].diff()[1:].dt.total_seconds().unique()[0]
        sampling_frequency = int(1/sampling_rate) # TODO-safety: don't just blindly round, see if we allow floating point values here also?? o_O
        # Safety skipping: make sure no gaps, make sure even sample spacing, set start time relative to overall recording

        # Need to figure out max signal length, then start time, then 
        # Lpad to the correct start time + lpad to the correct stop time (lol EDF)
        # TODO-future: instead of padding w/ 0, use some signal-specific value
        signal_data = np.zeros(max_duration_sec * sampling_frequency, dtype=np.float64)
        num_samples = len(df_sig[name].values)
        i_sample_start_offset = 0 #TODO - make sure this is set to the signal's offset
        signal_data[i_sample_start_offset:num_samples] = df_sig[name].values

        class_name = df_sig['class'].unique()[0]
        if class_name.startswith("sensor_data"):
            class_prefix = class_name[12:]
        elif class_name.startswith("derived_data"):
            class_prefix = "**" + class_name[13:]
        else:
            class_prefix = class_name

        # TODO-future safety: make sure signal labels are unique across recording/edf
        # TODO-future: pull into own function
        if class_name == name:
            label = class_prefix if len(class_prefix) <= 16 else class_prefix[0:16]  # lol EDF
        else:
            max_prefix_length = 16 - len(name) - 1  # lol EDF 
            # TODO handle case when prefix is now < 0
            class_prefix = class_prefix if len(class_prefix) <= max_prefix_length else class_prefix[0:max_prefix_length]
            label = class_prefix + "-" + name

        signal = EdfSignal(signal_data,
                            sampling_frequency=sampling_frequency, 
                            physical_dimension="TODO",
                            label=label)
        # TODO-add header metadata
        signals.append(signal)
    print(signals)
    return Edf(signals)
