"""
DuckDB connection management with extension loading and S3 configuration.
"""

import logging
import duckdb

from .warehouse_config import WarehouseConfig


class DuckDBConnection:
    """Manages DuckDB connection, extensions, and database configuration"""

    def __init__(self, config: WarehouseConfig):
        self.config = config
        self.conn = self._create_connection()
        self._load_extensions()
        if self.config.use_s3:
            self._configure_s3_settings()

    def _create_connection(self) -> duckdb.DuckDBPyConnection:
        """Create DuckDB connection with optimizations"""
        conn = duckdb.connect()

        # Enable DuckDB object cache for faster repeated parquet scans
        try:
            conn.execute("PRAGMA enable_object_cache;")
            logging.debug("Enabled DuckDB object cache")
        except Exception as e:
            logging.debug(f"Unable to enable DuckDB object cache: {e}")

        return conn

    def _load_extensions(self):
        """Install and load required DuckDB extensions"""
        try:
            self.conn.execute("INSTALL iceberg;")
            self.conn.execute("LOAD iceberg;")
            logging.debug("Loaded DuckDB Iceberg extension")

            if self.config.use_s3:
                # Install and load S3 extension for DuckDB
                self.conn.execute("INSTALL httpfs;")  # Required for S3
                self.conn.execute("LOAD httpfs;")
                logging.info("Loaded DuckDB S3 extensions")
        except Exception as e:
            logging.warning(f"Could not load extensions: {e}")

    def _configure_s3_settings(self):
        """Configure DuckDB S3 settings for Ceph/MinIO compatibility"""
        if not self.config.use_s3:
            return

        try:
            # Configure DuckDB S3 settings for Ceph compatibility
            self.conn.execute(
                f"SET s3_endpoint='{self.config.s3_endpoint.replace('https://', '')}';"
            )
            self.conn.execute(f"SET s3_access_key_id='{self.config.s3_access_key}';")
            self.conn.execute(
                f"SET s3_secret_access_key='{self.config.s3_secret_key}';"
            )
            self.conn.execute(f"SET s3_region='{self.config.s3_region}';")
            # Additional settings for Ceph/MinIO compatibility
            self.conn.execute("SET s3_use_ssl=true;")  # Enable SSL for security
            self.conn.execute("SET s3_url_style='path';")  # Path-style URLs for Ceph

            logging.info(
                f"Configured DuckDB S3 settings for Ceph compatibility: {self.config.s3_endpoint}"
            )
        except Exception as e:
            logging.warning(f"Failed to configure S3 settings: {e}")

    def execute(self, query: str):
        """Execute a SQL query"""
        return self.conn.execute(query)

    def sql(self, query: str):
        """Execute a SQL query and return results"""
        return self.conn.sql(query)

    def register(self, name: str, df):
        """Register a DataFrame as a table"""
        return self.conn.register(name, df)

    def close(self):
        """Close the DuckDB connection"""
        self.conn.close()

    def __getattr__(self, name):
        """Delegate any unknown attributes to the underlying DuckDB connection"""
        return getattr(self.conn, name)
