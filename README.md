# DiveDB

[![Quality control badge](https://github.com/ecophysviz-lab/DiveDB/actions/workflows/quality-control.yml/badge.svg)](https://github.com/ecophysviz-lab/DiveDB/actions/workflows/quality-control.yml)

DiveDB is designed to organize and analyze biologging data collected by any signal on any marine mammal. By storing your data in a structured data lake, DiveDB enforces consistency, allowing you to query data across multiple dives, signals, and animals. The primary goals of DiveDB include:

- **Metadata Management**: Utilizing [Notion](https://www.notion.so/) databases to provide a collaborative interface for managing the metadata associated with each dive.
- **Data Reliability and Consistency**: Employing [Apache Iceberg](https://iceberg.apache.org/) to bring ACID transactions to big data workloads, ensuring data reliability and consistency.
- **Analytical Query Workloads**: Using [DuckDB](https://duckdb.org/) for fast execution of analytical queries, making it ideal for data analysis tasks.
- **Interactive Data Visualization**: Building web-based dashboards with [Dash](https://dash.plotly.com/) to visualize data processed by the application.

Built entirely using open-source dependencies, DiveDB is designed to be a flexible and extensible application for managing and analyzing biologging data that can be run and deployed on any platform with Docker support.

DiveDB is currently in active development, and we welcome feedback and contributions. Please open an issue or submit a pull request if you have any suggestions or encounter any bugs.

<img width="2348" height="1346" alt="Screenshot 2025-08-18 at 3 43 43 PM" src="https://github.com/user-attachments/assets/0597ef30-91da-4030-9220-7aea4dba0c62" />


## Table of Contents
- [A Note on Docker 🐳](#a-note-on-docker-)
- [Getting Started](#getting-started)
- [Where to Store Your Data Lake](#where-to-store-your-data-lake)
- [Iceberg Schemas in DiveDB](#iceberg-schemas-in-divedb)
  - [DataLake Schema](#1-datalake-schema)
  - [PointEventsLake Schema](#2-pointeventslake-schema)
  - [StateEventsLake Schema](#3-stateeventslake-schema)
- [Notion Metadata Structure](#notion-metadata-structure)
  - [Animal Database](#1-animal-database)
  - [Recording Database](#2-recording-database)
  - [Logger Database](#3-logger-database)
  - [Deployment Database](#4-deployment-database)
- [Uploading Files to the Data Lake](#uploading-files-to-the-data-lake)
- [Reading Files from the Data Lake](#reading-files-from-the-data-lake)
- [Using Dash to Visualize DiveDB Data](#using-dash-to-visualize-divedb-data)
  - [Key Components](#key-components)
  - [How to Use](#how-to-use)
  - [Example Data](#example-data)
- [Notion ORM Integration](#notion-orm-integration)
  - [Key Features](#key-features)
  - [Quick Start](#quick-start)
  - [Property Type Mapping](#property-type-mapping)
  - [Limitations](#limitations)
- [Additional Commands](#additional-commands)
- [Additional Steps for Development of DiveDB](#additional-steps-for-development-of-divedb)

## A Note on Docker 🐳

This project uses Docker to facilitate a consistent development and production environment. Docker allows you to package applications and their dependencies into a container, which can then be run on any system that has Docker installed. This helps in avoiding issues related to environment setup and dependency management. For more information on getting started with Docker, visit [Docker's official getting started guide](https://docs.docker.com/get-started/).

## Getting Started

To create a local analysis environment, follow these steps:

1. **Clone the Repository:**
   ```sh
   git clone https://github.com/ecophysviz-lab/DiveDB.git
   cd DiveDB
   ```

1. **Set Up the Environment Variables:**
   Copy the `.env.example` file to `.env` and update the values as needed:
   ```sh
   cp .env.example .env
   ```
   Ensure that you set up the Notion API credentials and database IDs for metadata management.

1. **Start the Docker Daemon:**
   Start the Docker Desktop application (recommended) OR run `dockerd` in the terminal.
   ```

1. **Start the Jupyter Environment:**
   Spin up the Jupyter notebook server. Leave this running while you work on the project.
   ```sh
   make up
   ```

1. **Access the Environment:**
   To access the Jupyter notebook server, open your web browser and go to `http://localhost:8888` or connect to kernel `http://localhost:8888/jupyter` in a Jupyter client.

## Where to Store Your Iceberg Warehouse

The Iceberg data warehouse can be stored locally or on remote object storage. The path to the warehouse is configured in the `.env` file as `CONTAINER_ICEBERG_PATH`.

### Local Storage (Development)
For local development, set the warehouse path to a local directory:
```bash
CONTAINER_ICEBERG_PATH=/app/iceberg_warehouse
LOCAL_ICEBERG_PATH=./local_iceberg_warehouse
```

### Remote Storage - S3/Ceph Backend
To store the warehouse on S3-compatible object storage (AWS S3, Ceph, MinIO, etc.), provide the following environment variables:

```bash
# S3/Ceph Configuration
S3_ENDPOINT=https://your-s3-endpoint.com  # Ceph/S3 endpoint URL
S3_ACCESS_KEY=your-access-key               # S3 access key
S3_SECRET_KEY=your-secret-key               # S3 secret key  
S3_BUCKET=your-iceberg-bucket               # S3 bucket name
S3_REGION=us-east-1                         # S3 region (optional)
```

When S3 configuration is provided, DuckPond will automatically:
- Configure the Iceberg catalog for S3 storage
- Load DuckDB's S3 extensions (httpfs)
- Set up S3 credentials for data access
- Store data at `s3://your-bucket/iceberg-warehouse/`

**Note:** Ensure your S3 bucket exists and your credentials have read/write permissions.

**Migration Note:** This project has migrated from Delta Lake to Apache Iceberg for improved performance, schema evolution, and better partitioning capabilities.

## Iceberg Schemas in DiveDB

The `DuckPond` class in `duck_pond.py` manages three distinct Iceberg tables, each with its own schema. These schemas use a wide format approach for better performance and query flexibility.

### 1. Data Table Schema (Wide Format)

The `data` table stores signal data using a wide schema approach instead of nested structs. This provides better query performance and easier analytics:

- **dataset**: High-level dataset identifier (required, string)
- **animal**: The identifier for the animal from which data is collected (required, string)
- **deployment**: The deployment identifier (required, string)
- **recording**: The recording session identifier (optional, string)
- **group**: The group or category of the data (required, string)
- **class**: The class of the data (required, string)
- **label**: The label associated with the data (required, string)
- **datetime**: The timestamp of the data point (required, timestamp with microsecond precision)
- **val_dbl**: Floating-point values (optional, double)
- **val_int**: Integer values (optional, long)
- **val_bool**: Boolean values (optional, boolean)
- **val_str**: String values (optional, string)
- **data_type**: Indicates which value column contains the data (required, string: 'double', 'int', 'bool', 'str')

### 2. PointEventsLake Schema

The `PointEventsLake` schema is used to store discrete events that occur at specific points in time. It includes the following fields:

- **animal**: The identifier for the animal (string).
- **deployment**: The deployment identifier (string).
- **recording**: The recording session identifier (string).
- **group**: The group or category of the event (string).
- **event_key**: A unique key for the event (string).
- **datetime**: The timestamp of the event (timestamp with microsecond precision, UTC).
- **short_description**: A brief description of the event (nullable string).
- **long_description**: A detailed description of the event (nullable string).
- **event_data**: Additional data related to the event (string).

### 3. StateEventsLake Schema

The `StateEventsLake` schema is designed to store events that have a duration, with a start and end time. It includes the following fields:

- **animal**: The identifier for the animal (string).
- **deployment**: The deployment identifier (string).
- **recording**: The recording session identifier (string).
- **group**: The group or category of the event (string).
- **event_key**: A unique key for the event (string).
- **datetime_start**: The start timestamp of the event (timestamp with microsecond precision, UTC).
- **datetime_end**: The end timestamp of the event (timestamp with microsecond precision, UTC).
- **short_description**: A brief description of the event (string).
- **long_description**: A detailed description of the event (string).
- **event_data**: Additional data related to the event (string).

These schemas are defined using the `pyarrow` library and are used to enforce data structure and integrity within the Iceberg data lake managed by the `DuckPond` class.

## Notion Metadata Structure

DiveDB uses Notion databases to manage metadata associated with diving projects, animals, loggers, deployments, and recordings. The metadata is organized across several interconnected Notion databases that can be accessed through the Notion ORM integration.

### 1. Animal Database

The Animal database contains information about individual animals in diving projects:

- **Animal ID**: Unique identifier for the animal
- **Common Name**: The common name of the animal species
- **Scientific Name**: The scientific name of the animal species
- **Lab ID**: Laboratory identifier (optional)
- **Birth Year**: The birth year of the animal (optional)
- **Sex**: The sex of the animal (optional)
- **Project ID**: The identifier for the project the animal is part of
- **Domain IDs**: Domain identifiers associated with the animal (optional)

### 1. Recording Database

The Recording database represents recordings of data from loggers:

- **Recording ID**: Unique identifier for the recording
- **Name**: The name of the recording
- **Animal**: Link to the associated animal
- **Logger**: Link to the associated logger
- **Start Time**: The start time of the recording
- **End Time**: The end time of the recording (optional)
- **Timezone**: The timezone of the recording (optional)
- **Quality**: The quality of the recording (optional)
- **Attachment Location**: The location of the logger attachment (optional)
- **Attachment Type**: The type of logger attachment (optional)

### 1. Logger Database

The Logger database contains information about loggers attached to diving vertebrates:

- **Logger ID**: Unique identifier for the logger
- **Serial Number**: The serial number of the logger (optional)
- **Manufacturer**: The manufacturer of the logger (optional)
- **PTT**: The PTT identifier (optional)
- **Type**: The type of logger (optional)
- **Notes**: Additional notes about the logger (optional)
- **Owner**: The owner of the logger (optional)

### 1. Deployment Database

The Deployment database represents field deployments for data collection:

- **Deployment ID**: Unique identifier for the deployment
- **Deployment Name**: The name of the deployment
- **Recording Date**: The date of the recording
- **Animal**: Link to the associated animal
- **Deployment Location**: The location of the deployment (optional)
- **Deployment Coordinates**: Latitude and longitude of deployment (optional)
- **Recovery Location**: The location of the recovery (optional)
- **Recovery Coordinates**: Latitude and longitude of recovery (optional)
- **Timezone**: The timezone of the deployment

The Notion ORM integration allows you to query and access this metadata programmatically, providing a flexible interface for managing dive metadata collaboratively while maintaining data relationships and integrity.

## Uploading Files to the Data Lake

To see how to upload files to the data lake, refer to the [upload_docs.ipynb](docs/upload_docs.ipynb) notebook.

### Requirements
For any files to be uploaded to the data lake, they must be in netCDF format and meet the following requirements:

**Dimensions & Coordinates**
  Track the date and time associated with collected data.
  Label classed data nested in arrays (e.g., ax, ay, az values for accelerometer data).

* **Sampling Dimensions:**
  Suffix: _samples
  Prefix: Related data variable or group name.
  Type: Array of datetime64 values.

* **Labeling Dimensions:**
  Suffix: _variables
  Type: Array of string values.

  **Usage:** All dimensions are used as coordinates for selecting specific values with Xarray.

**Data Variables**<br>
  Each data variable must be associated with a sampling dimension.
  May also be associated with a labeling dimension.

* **Flat List Variables:**
  No labeling dimension.
  Attribute: variable with the variable's name.

* **Nested List Variables:**
  Requires a labeling dimension.
  Attribute: variables with the variables' names (duplicates the dimension).

**Validation:**
- We have a validation function in `DataUploader.validate_netcdf` that checks if a netCDF file meets the above requirements and provides helpful error messages if not. See [validate_netcdf in data_uploader.py](DiveDB/services/data_uploader.py).

**Example:**
- An example netCDF file can be downloaded here: [https://figshare.com/ndownloader/files/50061330](https://figshare.com/ndownloader/files/50061330) that meets the above requirements and can be used as a template for your own data.

## Reading Files from the Data Lake

We use [DuckDB](https://duckdb.org/) to read files from the data lake. To see how to read files from the data lake, refer to the [visualization_docs.ipynb](docs/visualization_docs.ipynb) notebook.

## Exporting data as EDF files

We use [EDF](https://en.wikipedia.org/wiki/European_Data_Format) to export signal data from the data lake. To see how to select and export data, refer to the [querying_docs.ipynb](docs/querying_docs.ipynb) notebook.

## Using Dash to Visualize DiveDB Data

DiveDB provides a powerful visualization tool using [Dash](https://dash.plotly.com/), a Python framework for building analytical web applications. The [data_visualization.py](dash/data_visualization.py) script is an example of how to create interactive visualizations of biologging data stored in DiveDB.

### Key Components

- **Dash Application**: The script initializes a Dash application that serves as the main interface for data visualization.
- **Plotly Graphs**: Interactive plots are created using Plotly, allowing users to explore signal and derived data over time.
- **Three.js Orientation**: The `three_js_orientation` component is used to render a 3D model, providing a visual representation of the animal's orientation based on the data.
- **Video Preview**: The `video_preview` component allows users to view synchronized video footage alongside the data plots.

### How to Use

1. **Set Up Environment**: Ensure that your environment is configured with the necessary dependencies. You can use Docker to maintain a consistent setup.

1. **Upload Example Data**: Upload the example netCDF file to the data lake using the steps in the [Uploading Files to the Data Lake](#uploading-files-to-the-data-lake) section.

1. **Download Example Video**: Download the example video from [here](https://figshare.com/ndownloader/files/50061327).

1. **Run the Dash Application**: Execute the `data_visualization.py` script to start the Dash server. This will launch a web application accessible via your browser.

   ```sh
   python dash/data_visualization.py
   ```

1. **Explore the Data**: Once the application is running, you can interact with the following components:

   - **3D Model Viewer**: The `three_js_orientation` component displays a 3D model of the animal. It uses data from the DiveDB to animate the model's orientation in real-time. You can adjust the active time using the playhead slider to see how the orientation changes over time.

   - **Video Synchronization**: The `video_preview` component provides a video player that is synchronized with the data plots. This allows you to view video footage alongside the data, providing context to the visualized events.

   - **Interactive Plots**: The application includes a series of interactive plots generated using Plotly. These plots display various signal and derived data signals, such as ECG, temperature, and depth. You can zoom into specific time ranges and explore the data in detail.

1. **Control Playback**: Use the play and pause buttons to control the playback of the data and video. The playhead slider allows you to navigate through the data timeline.

1. **Customize Visualization**: The script is designed to be flexible. You can modify the data sources, add new signals, or change the visualization parameters to suit your needs.

### Example Data

The script uses example data from the DiveDB, specifically focusing on the animal with ID "apfo-001a". Ensure that your data is structured similarly to leverage the full capabilities of the visualization tool.

The example netCDF file can be downloaded here: [https://figshare.com/ndownloader/files/50061330](https://figshare.com/ndownloader/files/50061330). Follow the steps in the [Uploading Files to the Data Lake](#uploading-files-to-the-data-lake) section to upload the file to the data lake and then visualize it using the steps above.

By following these steps, you can effectively use Dash to visualize and analyze biologging data from DiveDB, gaining insights into the behavior and environment of marine mammals.

## Notion ORM Integration

DiveDB includes a lightweight, read-only Python wrapper for the Notion API that provides ORM-like access to Notion databases. This integration simplifies querying and parsing Notion data structures into Python-native objects.

### Key Features

- Model Definition: Maps Notion databases to Python classes
- Schema Introspection: Auto-detects database schemas
- Query Builder: Pythonic query syntax (e.g., `Animal.objects.filter(Status="Active")`)
- Property Type Conversion: Maps Notion types to Python types (e.g., Date → datetime)
- Relationship Support: Navigate between related database records
- Pagination Handling: Automatic handling of paginated responses

### Quick Start

```python
from DiveDB.services.notion_orm import NotionORMManager

# Initialize with database IDs and token
db_map = {
    "Animal DB": os.getenv("NOTION_ANIMAL_DB"),
    "Recording DB": os.getenv("NOTION_RECORDING_DB")
}
notion_orm = NotionORMManager(db_map=db_map, token=os.getenv("NOTION_API_KEY"))

# Get model class and query data
Animal = notion_orm.get_model("Animal DB")
animal = Animal.get_animal({"Animal ID": "mian-013"})

# Access relationships
recordings = animal.get_recordings()
for recording in recordings:
    print(f"Recording ID: {recording.id}")
    print(f"Start time: {recording.Start_Time}")
```

### Property Type Mapping

| Notion Type | Python Type |
|-------------|-------------|
| Title | str |
| Rich Text | str |
| Number | float/int |
| Select | str |
| Multi-select | list[str] |
| Date | datetime |
| Checkbox | bool |
| Relation | list (lazy-loaded) |

### Limitations

- Read-only access (no create/update/delete operations)
- No real-time sync or webhooks
- Subject to Notion API rate limits

## Immich Integration

DiveDB includes an integration with [Immich](https://immich.app/), an open-source photo and video management system. This integration enables seamless access to media assets (images and videos) associated with datasets stored in Immich albums.

### Key Features

- **Deployment Media Discovery**: Search for media assets using deployment IDs (mapped to Immich album names)
- **Metadata Retrieval**: Access detailed metadata including EXIF data, timestamps, geolocation, and tags
- **Playback URL Generation**: Generate authenticated URLs for media playback in Dash dashboards

### Quick Start

```python
from immich_integration import ImmichService

# Initialize service (uses environment variables)
immich = ImmichService()

# Search for media by deployment ID (album name)
media_result = immich.find_media_by_deployment_id("DepID_2019-11-08_apfo-001")
if media_result["success"]:
    assets = media_result["data"]
    print(f"Found {len(assets)} media assets")

# Get detailed metadata and URLs for specific media
details_result = immich.get_media_details(asset_id="asset-uuid-here")
if details_result["success"]:
    metadata = details_result["data"]["metadata"]
    urls = details_result["data"]["urls"]
    print(f"Original URL: {urls['authenticated_original']}")
```

### Environment Variables

Configure the following in your `.env` file:

```bash
# Immich API Configuration
IMMICH_API_KEY=your_immich_api_key_here
IMMICH_BASE_URL=https://your-immich-instance.com/api
```

### Integration with Dash

The Immich service is designed to work seamlessly with DiveDB's Dash visualization components, enabling media playback synchronized with biologging data timelines.

## Additional Commands

- **To Stop the Containers:**
  ```sh
  make down
  ```

- **To Rebuild the Docker Image:**
  ```sh
  make build
  ```

- **To Enter the Docker Container with Bash in Docker:**
  ```sh
  make bash
  ```

## Additional Steps for Development of DiveDB
1. **Install Pre-commit Hooks:**
   ```sh
   pip install pre-commit
   pre-commit install
   ```

1. **To Run Tests:**
   ```sh
   # Run in Docker
   make test
   # or run natively
   pip install -r requirements.txt
   pytest
   ```
