# AI Agent Documentation - DiveDB Services

> **Purpose**: Token-efficient reference for AI agents working on the DiveDB data lake services.

## Quick Reference

- **Project**: Apache Iceberg data lake with Notion metadata integration for biologging data
- **Entry Point**: `DuckPond.from_environment()` (duck_pond.py:384)
- **Tech Stack**: DuckDB, Apache Iceberg, PyArrow, xarray, Notion API, requests
- **Key Dependencies**: `NotionORMManager`, `ImmichService`, `DataUploader`
- **Config**: Environment variables (ICEBERG_PATH, S3 config, NOTION credentials)

## Architecture Overview

### Service Flow

```
DataUploader → DuckPond → Iceberg Tables → DuckDB Views → DiveData
                    ↓
            NotionORMManager (metadata enrichment)
                    ↓
            ImmichService (media assets)
```

### Data Storage

- **Iceberg Tables**: Dataset-specific partitioned tables (data, events)
- **DuckDB Views**: Dataset-specific views (`{dataset}_Data`, `{dataset}_Events`)
- **Notion Integration**: Metadata loaded into DuckDB tables for joins
- **Storage Backends**: Local filesystem or S3/Ceph

### Initialization Pattern

1. `WarehouseConfig.from_environment()` → Config object
2. `CatalogManager(config)` → Iceberg catalog
3. `DuckDBConnection(config)` → DuckDB connection with extensions
4. `NotionIntegration(notion_manager, duckdb_connection)` → Notion loader
5. `DatasetManager(config, catalog_manager, duckdb_connection)` → Dataset lifecycle
6. `DuckPond(...)` → Combines all components

## File Map

| File | Purpose | Key Exports | Lines |
|------|---------|-------------|-------|
| `duck_pond.py` | Main data lake interface | `DuckPond` | 1691 |
| `notion_orm.py` | Notion database ORM | `NotionORMManager`, `NotionModel` | 512 |
| `data_uploader.py` | NetCDF upload and validation | `DataUploader`, `NetCDFValidationError` | 705 |
| `dive_data.py` | Query results wrapper | `DiveData` | 319 |
| `immich_service.py` | Media asset management | `ImmichService` | 400 |
| `connection/warehouse_config.py` | Backend configuration | `WarehouseConfig` | 99 |
| `connection/catalog_manager.py` | Iceberg catalog management | `CatalogManager` | 82 |
| `connection/duckdb_connection.py` | DuckDB connection manager | `DuckDBConnection` | 93 |
| `connection/dataset_manager.py` | Dataset lifecycle management | `DatasetManager` | 447 |
| `connection/notion_integration.py` | Notion database loader | `NotionIntegration` | 490 |
| `utils/directory_utils.py` | Directory utilities | `get_tmpdir()` | 10 |
| `utils/netcdf_conversions.py` | NetCDF conversion helpers | `matlab_datenum_to_datetime_vectorized()`, `infer_date_format()` | 146 |
| `utils/openstack.py` | OpenStack Swift client | `SwiftClient` | 71 |
| `utils/storage.py` | Storage abstraction | `OpenStackStorage` | 25 |
| `utils/timing.py` | Timing context manager | `TimingContext` | 17 |

## Module Reference

### duck_pond.py

**Purpose**: Main data lake interface for querying and writing biologging data

**Key Classes**:
- `DuckPond`: Primary interface for data operations

**Key Methods**:
- `from_environment(**kwargs)` → DuckPond - Factory method from env vars
- `get_data(dataset, labels, animal_ids, deployment_ids, recording_ids, groups, classes, date_range, frequency, limit, pivoted, apply_timezone_offset, add_timestamp_column, use_cache)` → pd.DataFrame | DiveData - Query data with optional resampling and caching
- `get_events(dataset, animal_ids, deployment_ids, recording_ids, event_keys, date_range, limit, apply_timezone_offset, add_timestamp_columns)` → pd.DataFrame - Query events
- `get_available_channels(dataset, include_metadata, pack_groups, load_metadata)` → List[Dict] - Discover channels with metadata
- `get_channels_metadata(dataset, channel_ids)` → Dict[str, Dict] - Lazy metadata loading
- `get_all_datasets_and_deployments()` → Dict[str, List[Dict]] - All datasets with deployments
- `estimate_data_size(dataset, labels, animal_ids, deployment_ids, recording_ids, groups, classes, date_range)` → int - Row count estimate
- `write_signal_data(dataset, metadata, times, group, class_name, label, values)` → int - Write signal data
- `write_to_iceberg(data, lake, dataset, mode, skip_view_refresh)` → None - Write PyArrow table
- `get_deployment_timezone_offset(deployment_id)` → float - Timezone offset in hours
- `get_view_name(dataset, table_type)` → str - Quoted view name

**Data Flow**:
1. Query → Build SQL → Execute via DuckDB → Return DataFrame or DiveData
2. Write → PyArrow Table → Iceberg append/overwrite → Refresh views
3. Metadata → NotionIntegration → Signal DB → Channel metadata enrichment

**Resampling**:
- `_wrap_query_with_resampling()` - SQL-level resampling (downsample/upsample)
- `_estimate_label_frequency()` - Native frequency estimation
- `_build_downsample_query()` - Every Nth row selection
- `_build_upsample_query()` - Time grid with forward-fill

### notion_orm.py

**Purpose**: ORM-like interface for Notion databases

**Key Classes**:
- `NotionORMManager`: Database manager with model factory
- `NotionModel`: Base model class with property parsing
- `ModelObjects`: Query manager for models

**Key Methods**:
- `NotionORMManager.__init__(db_map, token)` - Initialize with database map
- `get_model(model_name)` → Type[NotionModel] - Get or create model class
- `ModelObjects.all()` → List[NotionModel] - Get all records
- `ModelObjects.filter(**kwargs)` → ModelObjects - Filter records (chainable)
- `ModelObjects.first()` → Optional[NotionModel] - Get first result
- `NotionModel._from_notion_page(page_data)` → NotionModel - Parse Notion page

**Property Types Supported**:
- title, rich_text, number, select, multi_select, date, relation, checkbox, url, email, phone_number, formula, files

**Relationship Methods**:
- Auto-injected `get_{related_db}()` methods for relation properties
- Traverses Notion relations to load related records

**Database Map**:
- Maps database names to Notion database IDs
- Common databases: Deployment DB, Recording DB, Logger DB, Animal DB, Asset DB, Dataset DB, Signal DB, Standardized Channel DB

### data_uploader.py

**Purpose**: NetCDF file validation and upload to Iceberg data lake

**Key Classes**:
- `DataUploader`: Main uploader class
- `NetCDFValidationError`: Validation exception

**Key Methods**:
- `__init__(duck_pond)` - Initialize with DuckPond instance
- `validate_netcdf(ds)` → bool - Validate NetCDF structure (raises NetCDFValidationError)
- `upload_netcdf(netcdf_file_path, metadata, batch_size, rename_map, skip_validation)` → None - Upload NetCDF file
- `get_logger(logger_data)` → Logger - Get logger from Notion
- `get_recording(recording_data)` → Recording - Get recording from Notion
- `get_deployment(deployment_data)` → Deployment - Get deployment from Notion
- `get_animal(animal_data)` → Animal - Get animal from Notion

**NetCDF Requirements**:
- Dimensions: `*_samples` (datetime64), `*_variables` (str)
- Data variables: Must have `variable` (1D) or `variables` (2D) attribute
- Event data: `event_data_*` variables with `event_data_samples` coordinate

**Upload Process**:
1. Load NetCDF → Validate structure
2. Process events → Write to events lake
3. Process signals → Batch write to data lake
4. Refresh views → Update DuckDB views

**Metadata Structure**:
```python
{
    "dataset": str,  # Required
    "animal": str,    # Required
    "deployment": str, # Required
    "recording": str   # Optional
}
```

### dive_data.py

**Purpose**: Wrapper for query results with EDF export capabilities

**Key Classes**:
- `DiveData`: Query results wrapper

**Key Methods**:
- `__init__(duckdb_relation, conn, notion_manager, notion_db_map, notion_token)` - Initialize wrapper
- `get_metadata()` → Dict - Fetch logger/animal/deployment metadata from Notion
- `export_to_edf(output_dir)` → List[str] - Export to EDF files

**Features**:
- Delegates to DuckDB relation methods (`df()`, `filter()`, etc.)
- Metadata enrichment via Notion ORM
- EDF export with signal padding and alignment

### immich_service.py

**Purpose**: Immich photo/video management integration

**Key Classes**:
- `ImmichService`: Media asset service

**Key Methods**:
- `__init__(api_key, base_url)` - Initialize with API credentials
- `find_media_by_deployment_id(deployment_id, media_type, shared)` → Dict - Find media by album name
- `get_media_details(asset_id)` → Dict - Get asset metadata and URLs
- `create_asset_share_link(asset_id, expires_hours)` → Dict - Create temporary share link
- `prepare_video_options_for_react(media_result, expires_hours)` → Dict - Format videos for React components
- `test_connection()` → Dict - Test API connection

**Environment Variables**:
- `IMMICH_API_KEY`: API authentication key
- `IMMICH_BASE_URL`: Base URL for Immich API

**Return Format**:
- All methods return `{"success": bool, "data": ..., "error": ...}` dicts
- Video options include share URLs, thumbnails, metadata

### connection/warehouse_config.py

**Purpose**: Backend configuration (S3 vs local filesystem)

**Key Classes**:
- `WarehouseConfig`: Configuration dataclass

**Key Methods**:
- `from_parameters(warehouse_path, s3_endpoint, s3_access_key, s3_secret_key, s3_bucket, s3_region)` → WarehouseConfig - Create from params
- `from_environment()` → WarehouseConfig - Create from env vars

**Environment Variables**:
- `LOCAL_ICEBERG_PATH` or `CONTAINER_ICEBERG_PATH`: Local warehouse path
- `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`, `S3_REGION`: S3 config

**Backend Selection**:
- S3 if all S3 env vars present
- Local filesystem otherwise

### connection/catalog_manager.py

**Purpose**: Iceberg catalog creation and configuration

**Key Classes**:
- `CatalogManager`: Catalog manager

**Key Methods**:
- `__init__(config)` - Initialize with warehouse config
- `_create_catalog()` → SqlCatalog - Create catalog (S3 or local)
- `_create_s3_catalog()` → SqlCatalog - S3 catalog with SQLite metadata
- `_create_local_catalog()` → SqlCatalog - Local catalog

**Catalog Types**:
- S3: SQLite catalog DB + S3 data storage
- Local: SQLite catalog DB + local filesystem storage

### connection/duckdb_connection.py

**Purpose**: DuckDB connection management with extensions

**Key Classes**:
- `DuckDBConnection`: Connection manager

**Key Methods**:
- `__init__(config)` - Initialize connection
- `_create_connection()` → DuckDBPyConnection - Create with optimizations
- `_load_extensions()` → None - Install/load iceberg and httpfs extensions
- `_configure_s3_settings()` → None - Configure S3 credentials for DuckDB
- `close()` → None - Close connection

**Extensions**:
- `iceberg`: Required for Iceberg table access
- `httpfs`: Required for S3 backend

### connection/dataset_manager.py

**Purpose**: Dataset lifecycle management (create, discover, initialize, remove)

**Key Classes**:
- `DatasetManager`: Dataset manager

**Key Methods**:
- `__init__(config, catalog_manager, duckdb_connection)` - Initialize manager
- `initialize_datasets(datasets)` → None - Initialize specific datasets or discover all
- `ensure_dataset_initialized(dataset)` → None - Ensure dataset tables/views exist
- `get_all_datasets()` → List[str] - List all initialized datasets
- `dataset_exists(dataset)` → bool - Check if dataset initialized
- `remove_dataset(dataset)` → None - Remove dataset (use with caution)
- `_create_dataset_views(dataset)` → None - Create DuckDB views for dataset

**Dataset Structure**:
- Each dataset has two Iceberg tables: `{dataset}.data`, `{dataset}.events`
- Views created: `"{dataset}_Data"`, `"{dataset}_Events"`
- Partitioning: animal, deployment, class, label

**Lake Schemas**:
- `data`: dataset, animal, deployment, recording, group, class, label, datetime, val_dbl, val_int, val_bool, val_str, data_type
- `events`: dataset, animal, deployment, recording, group, event_key, datetime_start, datetime_end, short_description, long_description, event_data

### connection/notion_integration.py

**Purpose**: Notion database loading and metadata mapping

**Key Classes**:
- `NotionIntegration`: Notion loader

**Key Methods**:
- `__init__(notion_manager, duckdb_connection, parallelism)` - Initialize loader
- `load_notion_databases()` → None - Load all Notion databases into DuckDB
- `load_standardized_channels_df()` → Optional[pd.DataFrame] - Load Standardized Channel DB
- `load_signal_metadata_map(channel_ids)` → Dict[str, Dict] - Load channel metadata mapping
- `get_metadata_mappings(channel_ids)` → Tuple[Dict, Dict, Dict] - Get channel/signal mappings
- `list_notion_tables()` → List[str] - List loaded Notion tables

**Metadata Mapping**:
- `channel_id_to_signal_id`: Channel ID → Signal DB ID
- `original_alias_to_channel_id`: Alias → Standardized Channel ID
- `signal_metadata_map`: Signal ID → Metadata dict

**Parallel Loading**:
- Uses concurrent.futures for parallel Notion API calls
- Default parallelism: 8

### utils/directory_utils.py

**Purpose**: Directory utilities

**Key Functions**:
- `get_tmpdir(base)` → str - Create unique temporary directory

### utils/netcdf_conversions.py

**Purpose**: NetCDF conversion utilities

**Key Functions**:
- `matlab_datenum_to_datetime_vectorized(matlab_serial_dates)` → np.ndarray - Convert MATLAB datenum to datetime
- `infer_date_format(date_str, possible_formats)` → str - Infer date format from string

### utils/openstack.py

**Purpose**: OpenStack Swift client (legacy, not actively maintained)

**Key Classes**:
- `SwiftClient`: Swift client wrapper

**Environment Variables**:
- `OPENSTACK_AUTH_URL`, `OPENSTACK_APPLICATION_CREDENTIAL_ID`, `OPENSTACK_APPLICATION_CREDENTIAL_SECRET`

### utils/storage.py

**Purpose**: Storage abstraction layer

**Key Classes**:
- `OpenStackStorage`: OpenStack storage interface

**Key Methods**:
- `_open(name, mode)` → bytes - Get object binary
- `_save(name, content)` → str - Save object
- `exists(name)` → bool - Check if object exists
- `url(name)` → str - Get object URL

### utils/timing.py

**Purpose**: Timing utilities

**Key Classes**:
- `TimingContext`: Context manager for timing operations

**Usage**:
```python
with TimingContext("operation_name"):
    # code to time
```

## Data Structures

### DuckPond Query Result

**DataFrame Format** (pivoted=True):
```python
pd.DataFrame({
    "datetime": pd.Timestamp,
    "label1": float,
    "label2": float,
    ...
})
```

**DiveData Format** (pivoted=False):
```python
DiveData(
    duckdb_relation=DuckDBPyRelation,
    conn=DuckDBPyConnection,
    notion_manager=NotionORMManager
)
```

### Channel Metadata Structure

```python
{
    "kind": "variable" | "group",
    "group": str,
    "class": str,
    "label": str,
    "channel_id": str,
    "parent_signal": str,
    "y_label": str,
    "y_description": str,
    "y_units": str,
    "line_label": str,
    "color": str,
    "icon": str,
    "channels": List[Dict],  # For groups
    "coverage": {"available": int, "present": int}  # For groups
}
```

### Deployment Metadata Structure

```python
{
    "deployment": str,
    "animal": str,
    "deployment_date": str,
    "min_date": str,
    "max_date": str,
    "sample_count": int,
    "icon_url": str
}
```

### Video Options Structure

```python
{
    "id": str,
    "filename": str,
    "fileCreatedAt": str,
    "shareUrl": str,
    "originalUrl": str,
    "thumbnailUrl": str,
    "metadata": {
        "duration": str,
        "originalFilename": str,
        "type": str
    }
}
```

## Integration Points

### DuckPond ↔ NotionORM

**Metadata Enrichment**:
- `DuckPond.notion_manager` → `NotionORMManager` instance
- `get_available_channels()` → Loads Signal DB metadata via `NotionIntegration`
- `get_channels_metadata()` → Lazy-loads metadata for specific channels
- `get_deployment_timezone_offset()` → Queries Deployments table in DuckDB

**Notion Tables Loaded**:
- Standardized Channel DB → Channel metadata
- Signal DB → Signal definitions
- Deployment DB → Deployment metadata
- Animal DB → Animal metadata
- Asset DB → Animal icons

### DataUploader → DuckPond

**Data Ingestion**:
- `DataUploader.duck_pond` → `DuckPond` instance
- `upload_netcdf()` → Calls `write_signal_data()` and `write_to_iceberg()`
- Validates NetCDF structure before upload
- Batches writes for performance

### DuckPond → DiveData

**Query Results**:
- `get_data(pivoted=False)` → Returns `DiveData` wrapper
- `DiveData` delegates to DuckDB relation methods
- Supports metadata enrichment via Notion

### Dash App Integration

**Services Used**:
- `DuckPond.from_environment()` → Data queries
- `NotionORMManager()` → Metadata access
- `ImmichService()` → Video/media access

**Typical Flow**:
1. Load datasets/deployments → `get_all_datasets_and_deployments()`
2. Query data → `get_data()` with filters
3. Load channels → `get_available_channels()`
4. Load videos → `ImmichService.find_media_by_deployment_id()`
5. Load events → `get_events()`

## Common Patterns

### Initializing DuckPond

```python
from DiveDB.services import DuckPond, NotionORMManager

# From environment
duck_pond = DuckPond.from_environment(
    notion_manager=NotionORMManager(db_map, token)
)

# With explicit config
duck_pond = DuckPond(
    warehouse_path="./warehouse",
    notion_manager=notion_manager
)
```

### Querying Data

```python
# Get data with filters
df = duck_pond.get_data(
    dataset="my-dataset",
    deployment_ids=["2019-11-08_apfo-001"],
    labels=["depth", "temperature"],
    date_range=("2019-11-08", "2019-11-09"),
    frequency=1,  # Resample to 1 Hz
    pivoted=True
)

# Get events
events_df = duck_pond.get_events(
    dataset="my-dataset",
    deployment_ids=["2019-11-08_apfo-001"],
    date_range=("2019-11-08", "2019-11-09")
)
```

### Discovering Channels

```python
# Get all available channels with metadata
channels = duck_pond.get_available_channels(
    dataset="my-dataset",
    include_metadata=True,
    pack_groups=True,
    load_metadata=True
)

# Lazy-load metadata for specific channels
metadata = duck_pond.get_channels_metadata(
    dataset="my-dataset",
    channel_ids=["depth", "temperature"]
)
```

### Uploading NetCDF

```python
from DiveDB.services import DataUploader, DuckPond

duck_pond = DuckPond.from_environment()
uploader = DataUploader(duck_pond=duck_pond)

uploader.upload_netcdf(
    netcdf_file_path="data.nc",
    metadata={
        "dataset": "my-dataset",
        "animal": "apfo-001a",
        "deployment": "2019-11-08_apfo-001",
        "recording": "recording-001"  # Optional
    },
    batch_size=5_000_000,
    rename_map={"old_name": "new_name"}  # Optional
)
```

### Writing Signal Data

```python
import pyarrow as pa

times = pa.array([...], type=pa.timestamp("us"))
values = [1.0, 2.0, 3.0, ...]

duck_pond.write_signal_data(
    dataset="my-dataset",
    metadata={"animal": "apfo-001a", "deployment": "2019-11-08_apfo-001"},
    times=times,
    group="sensor_data",
    class_name="depth_sensor",
    label="depth",
    values=values
)
```

### Using Notion ORM

```python
from DiveDB.services import NotionORMManager

manager = NotionORMManager(db_map, token)

# Get model
Deployment = manager.get_model("Deployment")

# Query
deployment = Deployment.objects.filter(deployment_id="2019-11-08_apfo-001").first()

# Access properties
print(deployment.time_zone)
print(deployment.animal_id)

# Traverse relations
animal = deployment.get_animal()[0]  # Auto-injected method
```

### Using Immich Service

```python
from DiveDB.services import ImmichService

immich = ImmichService()  # Uses env vars

# Find media
result = immich.find_media_by_deployment_id(
    deployment_id="2019-11-08_apfo-001",
    media_type="VIDEO"
)

# Prepare for React
video_options = immich.prepare_video_options_for_react(result)
```

## Maintenance Guidelines

### When to Update This Documentation

- **New Files**: Add entry to File Map table
- **New Methods**: Document in Module Reference → Key Methods section
- **New Data Structures**: Add to Data Structures section
- **New Integration Points**: Add to Integration Points section
- **Architecture Changes**: Update Architecture Overview section
- **New Patterns**: Add to Common Patterns section

### Documentation Standards

1. **Keep it Token-Efficient**:
   - Use tables for structured data
   - Use bullet lists over prose
   - Function signatures only, no implementation details
   - Reference file paths and line numbers, not code
   - High-level architecture, not low-level implementation

2. **What to Include**:
   - File purposes and key exports
   - Function signatures and return types
   - Data flow and integration points
   - Important architectural decisions

3. **What to Exclude**:
   - Implementation details (how functions work internally)
   - Code examples (except for data structures)
   - Step-by-step procedures
   - Detailed parameter explanations

4. **Front-Load Important Info**:
   - Quick Reference at top
   - Most common patterns first
   - Detailed reference sections follow

### Update Checklist

When making changes, check if documentation needs updates:

- [ ] New method added → Add to Module Reference (signature only)
- [ ] New file created → Add to File Map table
- [ ] Function signature changed → Update Module Reference
- [ ] Data structure changed → Update Data Structures section
- [ ] Integration point changed → Update Integration Points
- [ ] New major pattern → Add to Common Patterns (high-level only)

**Remember**: Document "what" and "where", not "how". Keep entries under 2 lines.

