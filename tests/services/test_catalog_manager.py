import fnmatch
import io

from DiveDB.services.connection.catalog_manager import CatalogManager
from DiveDB.services.connection.warehouse_config import WarehouseConfig


class FakeCatalog:
    def __init__(self):
        self.namespaces = []
        self.tables = []

    def create_namespace_if_not_exists(self, namespace):
        self.namespaces.append(namespace)

    def register_table(self, identifier, metadata_location):
        self.tables.append((identifier, metadata_location))


class FakeS3FS:
    def __init__(self, files):
        self.files = files

    def glob(self, pattern):
        return sorted([p for p in self.files if fnmatch.fnmatch(p, pattern)])

    def open(self, path, mode="r"):
        if "r" not in mode:
            raise ValueError("FakeS3FS only supports read mode")
        return io.StringIO(self.files[path])


def test_warehouse_config_catalog_type_from_environment(monkeypatch):
    monkeypatch.setenv("S3_ENDPOINT", "http://localhost:9000")
    monkeypatch.setenv("S3_ACCESS_KEY", "access")
    monkeypatch.setenv("S3_SECRET_KEY", "secret")
    monkeypatch.setenv("S3_BUCKET", "bucket")
    monkeypatch.setenv("ICEBERG_CATALOG_TYPE", "in-memory")

    config = WarehouseConfig.from_environment()

    assert config.use_s3 is True
    assert config.catalog_type == "in-memory"


def test_catalog_manager_resolve_catalog_type_auto_and_explicit():
    local_config = WarehouseConfig.from_parameters(
        warehouse_path="./local_iceberg_warehouse",
        catalog_type="auto",
    )
    local_manager = CatalogManager.__new__(CatalogManager)
    local_manager.config = local_config
    assert local_manager._resolve_catalog_type() == "sql"

    s3_auto_config = WarehouseConfig.from_parameters(
        warehouse_path="s3://bucket/warehouse",
        s3_endpoint="http://localhost:9000",
        s3_access_key="access",
        s3_secret_key="secret",
        s3_bucket="bucket",
        catalog_type="auto",
    )
    s3_auto_manager = CatalogManager.__new__(CatalogManager)
    s3_auto_manager.config = s3_auto_config
    assert s3_auto_manager._resolve_catalog_type() == "in-memory"

    s3_sql_config = WarehouseConfig.from_parameters(
        warehouse_path="s3://bucket/warehouse",
        s3_endpoint="http://localhost:9000",
        s3_access_key="access",
        s3_secret_key="secret",
        s3_bucket="bucket",
        catalog_type="sql",
    )
    s3_sql_manager = CatalogManager.__new__(CatalogManager)
    s3_sql_manager.config = s3_sql_config
    assert s3_sql_manager._resolve_catalog_type() == "sql"


def test_catalog_manager_populates_inmemory_catalog_from_s3(monkeypatch):
    fake_s3_files = {
        "bucket/published-iceberg-warehouse/demo.db/data/metadata/version-hint.text": "3",
        "bucket/published-iceberg-warehouse/demo.db/data/metadata/00003-abc.metadata.json": "",
        "bucket/published-iceberg-warehouse/demo.db/events/metadata/version-hint.text": "7",
        "bucket/published-iceberg-warehouse/demo.db/events/metadata/00007-def.metadata.json": "",
    }

    config = WarehouseConfig.from_parameters(
        warehouse_path="s3://bucket/published-iceberg-warehouse",
        s3_endpoint="http://localhost:9000",
        s3_access_key="access",
        s3_secret_key="secret",
        s3_bucket="bucket",
        catalog_type="in-memory",
    )

    fake_catalog = FakeCatalog()
    fake_fs = FakeS3FS(fake_s3_files)

    monkeypatch.setattr(
        CatalogManager, "_create_s3_inmemory_catalog", lambda self: fake_catalog
    )
    monkeypatch.setattr(CatalogManager, "_get_s3_filesystem", lambda self: fake_fs)

    manager = CatalogManager(config)

    assert manager.catalog is fake_catalog
    assert "demo" in fake_catalog.namespaces
    assert (
        "demo.data",
        "s3://bucket/published-iceberg-warehouse/demo.db/data/metadata/00003-abc.metadata.json",
    ) in fake_catalog.tables
    assert (
        "demo.events",
        "s3://bucket/published-iceberg-warehouse/demo.db/events/metadata/00007-def.metadata.json",
    ) in fake_catalog.tables
