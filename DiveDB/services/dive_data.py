"""
EDF Export Manager
"""

import duckdb


class DiveData(duckdb.DuckDBPyConnection):
    """EDF Export Manager"""

    def __init__(self):
        super(DiveData, self).__init__()
        self.animals = []
        self.deployments = []
        self.recordings = []
        self.loggers = []

    def get_metadata(self, query: str):
        """Get metadata from postgres"""
        self.animals.append("Foo")
        self.deployments.append("Foo")
        self.recordings.append("Foo")
        self.loggers.append("Foo")
        print("Not yet implemented!")

    def export_to_edf(self, outdir: str):
        """Export metadata plus signals to set of EDF files"""
        print("Not yet implemented!")
