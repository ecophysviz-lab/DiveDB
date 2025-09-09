"""
Warehouse configuration management for S3 vs local filesystem backends.
"""

import logging
import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class WarehouseConfig:
    """Configuration for warehouse backend (S3 or local filesystem)"""

    # Core warehouse settings
    warehouse_path: str
    use_s3: bool

    # S3 configuration (None if using local filesystem)
    s3_endpoint: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_region: str = "us-east-1"

    @classmethod
    def from_parameters(
        cls,
        warehouse_path: Optional[str] = None,
        s3_endpoint: Optional[str] = None,
        s3_access_key: Optional[str] = None,
        s3_secret_key: Optional[str] = None,
        s3_bucket: Optional[str] = None,
        s3_region: str = "us-east-1",
    ) -> "WarehouseConfig":
        """Create configuration from direct parameters"""

        # Determine if we should use S3 backend
        use_s3 = bool(s3_endpoint and s3_access_key and s3_secret_key and s3_bucket)

        if use_s3:
            # S3 configuration
            final_warehouse_path = f"s3://{s3_bucket}/iceberg-warehouse"
            logging.info(f"Using S3 backend: {s3_endpoint}")
        else:
            # Local filesystem configuration
            if not warehouse_path:
                warehouse_path = "./local_iceberg_warehouse"
                logging.info(
                    "No warehouse_path provided, using default: ./local_iceberg_warehouse"
                )
            final_warehouse_path = warehouse_path
            logging.info(f"Using local filesystem backend: {final_warehouse_path}")

        return cls(
            warehouse_path=final_warehouse_path,
            use_s3=use_s3,
            s3_endpoint=s3_endpoint,
            s3_access_key=s3_access_key,
            s3_secret_key=s3_secret_key,
            s3_bucket=s3_bucket,
            s3_region=s3_region,
        )

    @classmethod
    def from_environment(cls) -> "WarehouseConfig":
        """
        Create configuration from environment variables.

        Environment variables:
        - LOCAL_ICEBERG_PATH or CONTAINER_ICEBERG_PATH: Path for local filesystem warehouse
        - S3_ENDPOINT: S3/Ceph endpoint URL
        - S3_ACCESS_KEY: S3 access key
        - S3_SECRET_KEY: S3 secret key
        - S3_BUCKET: S3 bucket name
        - S3_REGION: S3 region (optional, defaults to us-east-1)
        """

        # Check for S3 configuration first
        s3_endpoint = os.getenv("S3_ENDPOINT")
        s3_access_key = os.getenv("S3_ACCESS_KEY")
        s3_secret_key = os.getenv("S3_SECRET_KEY")
        s3_bucket = os.getenv("S3_BUCKET")
        s3_region = os.getenv("S3_REGION", "us-east-1")

        # Check for local warehouse path (support both env var names for compatibility)
        warehouse_path = os.getenv("LOCAL_ICEBERG_PATH") or os.getenv(
            "CONTAINER_ICEBERG_PATH"
        )

        return cls.from_parameters(
            warehouse_path=warehouse_path if not s3_endpoint else None,
            s3_endpoint=s3_endpoint,
            s3_access_key=s3_access_key,
            s3_secret_key=s3_secret_key,
            s3_bucket=s3_bucket,
            s3_region=s3_region,
        )
