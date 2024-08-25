"""
Data Uploader
"""

# import edfio
from services.metadata_manager import MetadataManager


class DataUploader:
    """Data Uploader"""

    def upload_edf(
        self,
        file_paths: list[str],
        csv_metadata_path: str,
        csv_metadata_map: dict = None,
        channels: list[str] = "all",
    ):
        """Upload EDF data"""

        metadata_manager = MetadataManager()
        metadata_models = metadata_manager.get_metadata_models(
            csv_metadata_path, csv_metadata_map
        )
        return metadata_models
