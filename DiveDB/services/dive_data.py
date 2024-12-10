"""
EDF Export Manager
"""

import duckdb
from DiveDB.services.duck_pond import DuckPond


# TODO-clarify: spec says DuckDBPyConnection but get_delta_data returns a Relation 
# (and explicitly says it doesn't pull data into memory)---using a relation here 
# Followed proxy pattern to extend class: https://stackoverflow.com/questions/69313845/create-child-class-object-using-parent-class-instance
class DiveData():
    """EDF Export Manager"""
    def __init__(self, duckdb_relation: duckdb.DuckDBPyRelation, duckpond: DuckPond):
        self.duckdb_relation = duckdb_relation
        self.duckpond = duckpond  # TODO-check: okay to set this here? Or better to calculate metadata immediately and not save...?
        self.recording_ids = [id for id in duckdb_relation.unique('recording').df()['recording'].values]
        self.metadata = None

    def __getattr__(self, item):
        if hasattr(self.duckdb_relation, item):
            return getattr(self.duckdb_relation, item)

    def get_metadata(self):
        self.metadata = get_metadata(self, self.duckpond).copy()  # TODO-question: if this isn't empty, should we refresh it??
    
    # TODO-clarify: spec says output path; when we generate multiple files, 
    # how to handle? for now, appending an index...
    def export_to_edf(self, filepath: str):
        """Export metadata plus signals to set of EDF files"""
        export_to_edf(self, filepath)

#####
##### Utils
#####


def get_metadata(divedata: DiveData, duckpond):
    """Get metadata from postgres"""
    metadata = {}
    for recording_id in divedata.recording_ids:
        print("Recording: ", recording_id)
        recording_metadata = {}
        df = duckpond.conn.sql("""
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


def _get_adjusted_filename(filename, i_recording, num_recordings):
    if num_recordings == 1 and filename.lower().endswith(".edf"):
        return filename 
    if num_recordings == 1:
        return filename + ".edf"
    prefix = filename[:-4] if filename.lower().endswith(".edf") else filename 
    return prefix + "_" + str(i_recording + 1) + ".edf"


def export_to_edf(data: DiveData, filepath: str) -> list:
    """Export metadata plus signals to set of EDF files"""
    edf_filepaths = []
    data.get_metadata()
    for (i, recording_id) in enumerate(data.metadata.keys()):
        metadata = data.metadata[recording_id]
        recording_filepath = _get_adjusted_filename(filepath, i, len(data.recording_ids))
        print(i, recording_filepath, recording_id, metadata)
        
        # First let's figure out how this EDF is going to be structured---don't 
        # materialize the signals yet!! 
        max_duration_sec = 0
        # TODO- pull in from notebook

        # Now let's go through and materialize the signals one at a time 
        # TODO- pull in from notebook

        edf_filepaths.append(recording_filepath)

    return edf_filepaths
