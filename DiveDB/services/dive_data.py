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

        # TODO: go through self.duckdb_relation, pull out the relevant:
        self.animal_ids = ["FOO"]
        # self.deployment_ids = deployment_ids
        # self.recording_ids = recording_ids
        # self.logger_ids = logger_ids
        
        self.animal_metadata = {}
        # self.deployment_metadata = {}
        # self.recording_metadata = {}
        # self.logger_metadata = {}

    def __getattr__(self, item):
        if hasattr(self.duckdb_relation, item):
            return getattr(self.duckdb_relation, item)

    def get_metadata(self):
        """Get metadata from postgres"""
        self.animals.append("Foo")
        self.deployments.append("Foo")
        self.recordings.append("Foo")
        self.loggers.append("Foo")
        print("Not yet implemented!")

    # TODO-clarify: spec says output path, but we may 
    # need to generate multiple files so prob use outdir instead?
    def export_to_edf(self, outdir: str):
        """Export metadata plus signals to set of EDF files"""
        self.get_metadata() 
        print("Not yet implemented")
