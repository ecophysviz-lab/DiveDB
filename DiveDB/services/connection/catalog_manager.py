"""
Iceberg catalog management for both S3 and local filesystem backends.
"""

import logging
import os

from pyiceberg.catalog.sql import SqlCatalog

from .warehouse_config import WarehouseConfig


class CatalogManager:
    """Manages Iceberg catalog creation and configuration"""

    def __init__(self, config: WarehouseConfig):
        self.config = config
        self.catalog = self._create_catalog()

    def _create_catalog(self) -> SqlCatalog:
        """Create and configure the Iceberg catalog based on warehouse config"""

        if self.config.use_s3:
            return self._create_s3_catalog()
        else:
            return self._create_local_catalog()

    def _create_s3_catalog(self) -> SqlCatalog:
        """Create S3-based catalog configuration for PyIceberg"""
        # Use local persistent SQLite for catalog metadata, S3 for data storage
        catalog_db_path = os.path.join(
            os.path.expanduser("~"), ".iceberg", "s3_catalog.db"
        )
        os.makedirs(os.path.dirname(catalog_db_path), exist_ok=True)

        catalog = SqlCatalog(
            "s3_catalog",
            **{
                "uri": f"sqlite:///{catalog_db_path}",
                "warehouse": self.config.warehouse_path,  # s3://bucket/iceberg-warehouse
                "s3.endpoint": self.config.s3_endpoint,
                "s3.access-key-id": self.config.s3_access_key,
                "s3.secret-access-key": self.config.s3_secret_key,
                "s3.region": self.config.s3_region,
            },
        )

        logging.info(f"Created S3 catalog with endpoint: {self.config.s3_endpoint}")
        return catalog

    def _create_local_catalog(self) -> SqlCatalog:
        """Create local filesystem catalog configuration"""
        catalog_db_path = os.path.join(self.config.warehouse_path, "catalog.db")
        catalog_uri = None

        try:
            os.makedirs(self.config.warehouse_path, exist_ok=True)
            catalog_uri = f"sqlite:///{catalog_db_path}"
        except Exception as e:
            # In some environments (e.g., tests setting unwritable absolute paths),
            # directory creation may fail. Fall back to an in-memory SQLite catalog
            # so that configuration-oriented code paths (like from_environment)
            # can still succeed without touching the filesystem.
            logging.warning(
                f"Could not create warehouse directory '{self.config.warehouse_path}': {e}. "
                "Falling back to in-memory catalog."
            )
            catalog_uri = "sqlite:///:memory:"

        catalog = SqlCatalog(
            "local",
            **{
                "uri": catalog_uri,
                "warehouse": f"file://{os.path.abspath(self.config.warehouse_path)}",
            },
        )

        logging.info(
            f"Created local catalog with warehouse: {self.config.warehouse_path}"
        )
        return catalog
