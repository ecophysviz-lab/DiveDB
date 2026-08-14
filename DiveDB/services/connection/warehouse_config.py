"""
Warehouse configuration management for S3 vs local filesystem backends.
"""

import logging
import os
from typing import Literal, Optional, cast
from dataclasses import dataclass


def bucket_from_uri(uri: Optional[str]) -> Optional[str]:
    """Bucket name from an ``s3://bucket/prefix`` URI, or None if not an s3 URI.

    Paths are configured as complete s3:// URIs, so the bucket is read back out of
    them rather than being tracked as a separate variable.
    """
    if not uri or not uri.startswith("s3://"):
        return None
    remainder = uri[len("s3://") :].lstrip("/")
    return remainder.split("/", 1)[0] or None


@dataclass
class WarehouseConfig:
    """Configuration for warehouse backend (S3 or local filesystem)"""

    # Core warehouse settings
    warehouse_path: str
    use_s3: bool
    catalog_type: Literal["auto", "sql", "in-memory"] = "auto"

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
        catalog_type: str = "auto",
    ) -> "WarehouseConfig":
        """Create configuration from direct parameters"""

        # The backend is chosen by the endpoint and credentials. The bucket is not part
        # of the test: an s3:// warehouse_path already names it, and requiring a
        # separate S3_BUCKET meant a complete S3 config could silently fall back to a
        # local warehouse when only that one variable was missing.
        use_s3 = bool(s3_endpoint and s3_access_key and s3_secret_key)

        # Derive the bucket from the warehouse URI when not supplied explicitly.
        if use_s3 and not s3_bucket and warehouse_path:
            s3_bucket = bucket_from_uri(warehouse_path)

        if use_s3 and not (s3_bucket or warehouse_path):
            raise ValueError(
                "S3 backend selected but no bucket: pass an s3:// warehouse_path "
                "(e.g. S3_WAREHOUSE_PATH) or an explicit s3_bucket."
            )

        normalized_catalog_type = cast(
            Literal["auto", "sql", "in-memory"], catalog_type.strip().lower()
        )
        if normalized_catalog_type not in {"auto", "sql", "in-memory"}:
            raise ValueError("catalog_type must be one of: 'auto', 'sql', 'in-memory'")

        if use_s3:
            # S3 configuration — honour an explicit warehouse_path if provided,
            # otherwise fall back to the default prefix in the configured bucket.
            if warehouse_path:
                final_warehouse_path = warehouse_path
            else:
                final_warehouse_path = f"s3://{s3_bucket}/iceberg-warehouse"
            logging.info(
                f"Using S3 backend: {s3_endpoint}, warehouse: {final_warehouse_path}"
            )
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
            catalog_type=normalized_catalog_type,
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

        Each backend has one path variable, so the two never have to be kept in sync:

        - S3 backend (S3_ENDPOINT set):
            - S3_WAREHOUSE_PATH: full s3://bucket/prefix URI of the warehouse. The
              bucket is read from this URI; there is no separate bucket variable.
        - Local backend:
            - LOCAL_ICEBERG_PATH or CONTAINER_ICEBERG_PATH: filesystem path.

        Other variables:
        - S3_ENDPOINT: S3/Ceph endpoint URL (presence selects the S3 backend)
        - S3_ACCESS_KEY: S3 access key
        - S3_SECRET_KEY: S3 secret key
        - S3_REGION: S3 region (optional, defaults to us-east-1)
        - ICEBERG_CATALOG_TYPE: Catalog mode (auto, sql, in-memory)

        S3_BUCKET is still honoured if set, but is redundant with S3_WAREHOUSE_PATH.
        """

        # Check for S3 configuration first
        s3_endpoint = os.getenv("S3_ENDPOINT")
        s3_access_key = os.getenv("S3_ACCESS_KEY")
        s3_secret_key = os.getenv("S3_SECRET_KEY")
        s3_bucket = os.getenv("S3_BUCKET")
        s3_region = os.getenv("S3_REGION", "us-east-1")
        catalog_type = os.getenv("ICEBERG_CATALOG_TYPE", "auto")

        if s3_endpoint:
            # S3 backend: only S3_WAREHOUSE_PATH selects the prefix. A local
            # filesystem path would be meaningless here, so it is ignored.
            warehouse_path = os.getenv("S3_WAREHOUSE_PATH")
            if warehouse_path and not warehouse_path.startswith("s3://"):
                raise ValueError(
                    "S3_WAREHOUSE_PATH must be an s3:// URI, got: "
                    f"{warehouse_path!r}"
                )
        else:
            # Local backend (support both env var names for compatibility)
            warehouse_path = os.getenv("LOCAL_ICEBERG_PATH") or os.getenv(
                "CONTAINER_ICEBERG_PATH"
            )

        return cls.from_parameters(
            warehouse_path=warehouse_path,
            s3_endpoint=s3_endpoint,
            s3_access_key=s3_access_key,
            s3_secret_key=s3_secret_key,
            s3_bucket=s3_bucket,
            s3_region=s3_region,
            catalog_type=catalog_type,
        )
