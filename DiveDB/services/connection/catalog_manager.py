"""
Iceberg catalog management for both S3 and local filesystem backends.
"""

import atexit
import logging
import os
import tempfile
from typing import Dict, Optional, Tuple

import s3fs
from pyiceberg.catalog.sql import SqlCatalog

from .warehouse_config import WarehouseConfig


class CatalogManager:
    """Manages Iceberg catalog creation and configuration"""

    def __init__(self, config: WarehouseConfig):
        self.config = config
        self.catalog = self._create_catalog()
        if self.config.use_s3 and self._resolve_catalog_type() == "in-memory":
            self._populate_catalog_from_s3()

    def _create_catalog(self) -> SqlCatalog:
        """Create and configure the Iceberg catalog based on warehouse config"""

        if self.config.use_s3:
            return self._create_s3_catalog()
        else:
            return self._create_local_catalog()

    def _resolve_catalog_type(self) -> str:
        """Resolve catalog backend type from config."""
        catalog_type = self.config.catalog_type
        if catalog_type == "auto":
            if self.config.use_s3:
                return "in-memory"
            return "sql"
        return catalog_type

    def _create_s3_catalog(self) -> SqlCatalog:
        """Create S3-based catalog configuration for PyIceberg"""
        if self._resolve_catalog_type() == "in-memory":
            return self._create_s3_inmemory_catalog()

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

    def _create_s3_inmemory_catalog(self) -> SqlCatalog:
        """Create S3 catalog backed by an ephemeral temp-file SQLite database.

        Using a real file (instead of sqlite:///:memory:) avoids the
        SQLite-in-memory per-connection isolation issue that breaks
        multi-threaded access.  The temp file is removed on interpreter exit.
        """
        self._temp_catalog_dir = tempfile.mkdtemp(prefix="iceberg_catalog_")
        catalog_db_path = os.path.join(self._temp_catalog_dir, "catalog.db")

        # Best-effort cleanup when the process exits.
        def _cleanup():
            try:
                if os.path.exists(catalog_db_path):
                    os.remove(catalog_db_path)
                if os.path.isdir(self._temp_catalog_dir):
                    os.rmdir(self._temp_catalog_dir)
            except OSError:
                pass

        atexit.register(_cleanup)

        catalog = SqlCatalog(
            "s3_catalog_ephemeral",
            **{
                "uri": f"sqlite:///{catalog_db_path}",
                "warehouse": self.config.warehouse_path,
                "s3.endpoint": self.config.s3_endpoint,
                "s3.access-key-id": self.config.s3_access_key,
                "s3.secret-access-key": self.config.s3_secret_key,
                "s3.region": self.config.s3_region,
            },
        )
        logging.info(
            "Created ephemeral S3 catalog (temp db: %s) with warehouse: %s",
            catalog_db_path,
            self.config.warehouse_path,
        )
        return catalog

    def _get_s3_filesystem(self) -> s3fs.S3FileSystem:
        client_kwargs: Dict[str, str] = {}
        if self.config.s3_endpoint:
            client_kwargs["endpoint_url"] = self.config.s3_endpoint

        return s3fs.S3FileSystem(
            key=self.config.s3_access_key,
            secret=self.config.s3_secret_key,
            client_kwargs=client_kwargs,
        )

    def _read_version_hint(
        self, fs: s3fs.S3FileSystem, hint_path: str
    ) -> Optional[int]:
        try:
            with fs.open(hint_path, mode="r") as f:
                return int(f.read().strip())
        except Exception as e:
            logging.debug("Failed reading version hint %s: %s", hint_path, e)
            return None

    def _resolve_metadata_file(
        self, fs: s3fs.S3FileSystem, metadata_dir: str, version: Optional[int]
    ) -> Optional[str]:
        try:
            if version is not None:
                preferred = fs.glob(f"{metadata_dir}/{version:05d}-*.metadata.json")
                if preferred:
                    return preferred[0]

            # Fallback if version-hint is missing or stale.
            all_meta = sorted(fs.glob(f"{metadata_dir}/*.metadata.json"))
            if all_meta:
                return all_meta[-1]
        except Exception as e:
            logging.debug("Failed listing metadata files in %s: %s", metadata_dir, e)
        return None

    def _parse_table_from_hint_path(
        self, prefix: str, hint_path: str
    ) -> Optional[Tuple[str, str]]:
        relative = hint_path.removeprefix(prefix).lstrip("/")
        parts = relative.split("/")
        if len(parts) < 4:
            return None
        dataset_db, lake_name = parts[0], parts[1]
        if not dataset_db.endswith(".db"):
            return None
        return dataset_db[:-3], lake_name

    def _populate_catalog_from_s3(self) -> None:
        """Discover Iceberg tables in S3 and register them into the in-memory catalog."""
        fs = self._get_s3_filesystem()
        warehouse_prefix = self.config.warehouse_path.removeprefix("s3://").rstrip("/")
        hint_glob = f"{warehouse_prefix}/*.db/*/metadata/version-hint.text"

        try:
            hint_files = sorted(fs.glob(hint_glob))
        except Exception as e:
            logging.warning(
                "Could not list metadata in warehouse '%s': %s", warehouse_prefix, e
            )
            return

        registered = 0
        for hint_path in hint_files:
            parsed = self._parse_table_from_hint_path(warehouse_prefix, hint_path)
            if not parsed:
                continue
            dataset_name, lake_name = parsed
            metadata_dir = hint_path.rsplit("/", 1)[0]
            version = self._read_version_hint(fs, hint_path)
            metadata_path = self._resolve_metadata_file(fs, metadata_dir, version)
            if not metadata_path:
                logging.debug("No metadata file found for hint path: %s", hint_path)
                continue

            metadata_location = f"s3://{metadata_path}"
            identifier = f"{dataset_name}.{lake_name}"
            try:
                self.catalog.create_namespace_if_not_exists(dataset_name)
                self.catalog.register_table(identifier, metadata_location)
                registered += 1
                logging.info(
                    "Registered table %s from %s", identifier, metadata_location
                )
            except Exception as e:
                # Safe to ignore duplicates when re-registering.
                logging.debug(
                    "Could not register table %s from %s: %s",
                    identifier,
                    metadata_location,
                    e,
                )

        logging.info("S3 discovery complete: registered %d tables", registered)

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
