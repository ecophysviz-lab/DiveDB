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
        self.recording_ids = duckdb_relation.unique('recording').df()['recording'].values

    def __getattr__(self, item):
        if hasattr(self.duckdb_relation, item):
            return getattr(self.duckdb_relation, item)

    def get_metadata(self):
        self.metadata = get_metadata(self.relation, self.duckpond)
    
    # TODO-clarify: spec says output path, but we may 
    # need to generate multiple files so prob use outdir instead?
    def export_to_edf(self, outdir: str):
        """Export metadata plus signals to set of EDF files"""
        self.get_metadata() 
        print("Not yet implemented")


def get_metadata(relation, duckpond):
    """Get metadata from postgres"""
    metadata = {}
    for recording_id in relation.recording_ids:
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
