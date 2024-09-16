import os
import sys

# Add the parent directory to the system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from DiveDB.services.metadata_manager import MetadataManager  # noqa: E402


def main():
    """
    Imports data from Notion into the Metadata database.
    """
    metadata_manager = MetadataManager()  # Instantiate MetadataManager

    metadata_manager.reset_from_notion(metadata_manager.model_names.LOGGER)
    metadata_manager.reset_from_notion(metadata_manager.model_names.ANIMAL)
    metadata_manager.reset_from_notion(metadata_manager.model_names.DEPLOYMENT)
    metadata_manager.reset_from_notion(metadata_manager.model_names.RECORDING)


if __name__ == "__main__":
    main()
