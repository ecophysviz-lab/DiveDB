"""
EDF Export Manager
"""

import duckdb


# TODO-clarify: spec says DuckDBPyConnection but get_delta_data returns a Relation 
# (and explicitly says it doesn't pull data into memory)---using a relation here 
# Followed proxy pattern to extend class: https://stackoverflow.com/questions/69313845/create-child-class-object-using-parent-class-instance
class DiveData():
    """EDF Export Manager"""
    def __init__(self, duckdb_relation: duckdb.DuckDBPyRelation):
        self.duckdb_relation = duckdb_relation
        self.recording_ids = duckdb_relation.unique('recording').df()['recording'].values

    def __getattr__(self, item):
        if hasattr(self.duckdb_relation, item):
            return getattr(self.duckdb_relation, item)

    def get_metadata(self):
        """Get metadata from postgres"""
        for recordingId in self.recording_ids:
            print("Recording: ", recordingId)
            # TODO - metadata fetch! failing to get it over in notebook...
            # animal_deployment_id 
                # animal_id
                # deployment_id 
            # logger_id

    # TODO-clarify: spec says output path, but we may 
    # need to generate multiple files so prob use outdir instead?
    def export_to_edf(self, outdir: str):
        """Export metadata plus signals to set of EDF files"""
        self.get_metadata() 
        print("Not yet implemented")

