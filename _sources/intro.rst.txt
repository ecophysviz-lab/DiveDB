Introduction
============

What is DiveDB?
---------------

DiveDB is an Apache Iceberg data lake designed to organize and analyze biologging data
collected by any sensor on any marine mammal. By storing data in a structured,
partitioned data lake, DiveDB enforces consistency across multiple dives, sensors,
and animals, enabling fast cross-deployment analytical queries.

Built entirely on open-source dependencies — DuckDB, Apache Iceberg, PyArrow, xarray,
and Notion — DiveDB is designed to be flexible, extensible, and deployable on any
platform with Docker support.

Primary goals:

- **Metadata Management**: Notion databases provide a collaborative interface for
  managing dive metadata (animals, loggers, deployments, recordings).
- **Data Reliability**: Apache Iceberg brings ACID transactions to big-data workloads.
- **Analytical Queries**: DuckDB executes fast analytical SQL over Iceberg tables.
- **Interactive Visualization**: Plotly Dash dashboards visualize biologging signals,
  events, and synchronized video.

Key Components
--------------

DuckPond
~~~~~~~~

``DuckPond`` is the primary interface to the data lake. It combines an Iceberg catalog,
a DuckDB connection, Notion metadata integration, and dataset lifecycle management into
a single object.

Typical entry point::

    from DiveDB.services import DuckPond, NotionORMManager

    duck_pond = DuckPond.from_environment(
        notion_manager=NotionORMManager(db_map, token)
    )

DataUploader
~~~~~~~~~~~~

``DataUploader`` handles validation and ingest of NetCDF files into Iceberg tables.
It validates file structure, processes signal data in configurable batches, and
refreshes DuckDB views after upload.

NotionORMManager
~~~~~~~~~~~~~~~~

``NotionORMManager`` provides ORM-like read access to Notion databases. It maps
Notion database IDs to Python model classes, supports chainable ``filter()`` queries,
and auto-injects relationship traversal methods.

DiveData
~~~~~~~~

``DiveData`` wraps a DuckDB relation returned by ``get_data(pivoted=False)``. It
delegates to DuckDB relation methods (``df()``, ``filter()``, etc.) and adds Notion
metadata enrichment and EDF export.

ImmichService
~~~~~~~~~~~~~

``ImmichService`` integrates with an Immich photo/video server to discover deployment
media albums, retrieve asset metadata and playback URLs, and format video options for
React/Dash components.

Architecture Overview
---------------------

**Data flow**::

    NetCDF Files
         |
         v
    DataUploader  ──validates──►  NetCDFValidationError
         |
         v
    DuckPond.write_signal_data / write_to_iceberg
         |
         v
    Iceberg Tables  ({dataset}.data, {dataset}.events)
         |
         v
    DuckDB Views  ("{dataset}_Data", "{dataset}_Events")
         |
         v
    DuckPond.get_data / get_events
         |
         ├──► pd.DataFrame (pivoted=True)
         └──► DiveData wrapper (pivoted=False)
                    |
                    └──► EDF export

    Notion Databases
         |
         v
    NotionIntegration.load_notion_databases()
         |
         v
    DuckDB in-memory tables (metadata joins)
         |
         v
    Channel metadata enrichment, timezone offsets, organism icons

    ImmichService
         |
         v
    Media discovery by deployment ID → video URLs for Dash UI

**Initialization sequence**::

    WarehouseConfig.from_environment()   # S3 vs local filesystem
             |
             v
    CatalogManager(config)               # Iceberg SqlCatalog
             |
             v
    DuckDBConnection(config)             # DuckDB + iceberg/httpfs extensions
             |
             v
    NotionIntegration(notion_manager, duckdb_connection)
             |
             v
    DatasetManager(config, catalog, duckdb_conn)
             |
             v
    DuckPond(...)                        # All components combined

Quick Start
-----------

**1. Configure environment**

Copy ``.env.example`` to ``.env`` and set:

.. code-block:: bash

    # Notion credentials
    NOTION_API_KEY=secret_...
    NOTION_ANIMAL_DB=...
    NOTION_DEPLOYMENT_DB=...

    # Local Iceberg warehouse (development)
    CONTAINER_ICEBERG_PATH=/app/iceberg_warehouse
    LOCAL_ICEBERG_PATH=./local_iceberg_warehouse

    # Or S3/Ceph backend (production)
    S3_ENDPOINT=https://your-s3-endpoint.com
    S3_ACCESS_KEY=your-access-key
    S3_SECRET_KEY=your-secret-key
    S3_BUCKET=your-iceberg-bucket
    S3_REGION=us-east-1

**2. Start the environment**

.. code-block:: bash

    git clone https://github.com/ecophysviz-lab/DiveDB.git
    cd DiveDB
    cp .env.example .env   # fill in credentials
    make up                # starts Jupyter + Docker services

**3. Initialize DuckPond**

.. code-block:: python

    from DiveDB.services import DuckPond, NotionORMManager

    notion_manager = NotionORMManager(db_map, token)
    duck_pond = DuckPond.from_environment(notion_manager=notion_manager)

**4. Upload a NetCDF file**

.. code-block:: python

    from DiveDB.services import DataUploader

    uploader = DataUploader(duck_pond=duck_pond)
    uploader.upload_netcdf(
        netcdf_file_path="data.nc",
        metadata={
            "dataset": "my-dataset",
            "animal": "apfo-001a",
            "deployment": "2019-11-08_apfo-001",
        },
    )

**5. Query data**

.. code-block:: python

    df = duck_pond.get_data(
        dataset="my-dataset",
        deployment_ids=["2019-11-08_apfo-001"],
        labels=["depth", "temperature"],
        frequency=1,   # resample to 1 Hz
        pivoted=True,
    )

Storage Backends
----------------

Local Filesystem (Development)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Set ``LOCAL_ICEBERG_PATH`` (host path) and ``CONTAINER_ICEBERG_PATH`` (container path)
in ``.env``. DiveDB creates a SQLite catalog database and stores Iceberg data files
on the local filesystem. No additional configuration is required.

S3 / Ceph Backend (Production)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When all five S3 environment variables are present (``S3_ENDPOINT``, ``S3_ACCESS_KEY``,
``S3_SECRET_KEY``, ``S3_BUCKET``, ``S3_REGION``), DiveDB automatically:

- Configures the Iceberg catalog to use S3 storage
- Loads DuckDB's ``httpfs`` extension for remote file access
- Sets S3 credentials in DuckDB for query execution
- Stores data under ``s3://your-bucket/iceberg-warehouse/``

The backend selection is handled transparently by ``WarehouseConfig.from_environment()``
and requires no changes to application code.
