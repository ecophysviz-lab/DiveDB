# DiveDB

DiveDB is designed to organize and analyze biologging data collected by any sensor on any marine mammal. By storing your data in a structured data lake, DiveDB enforces consistency, allowing you to query data across multiple dives, sensors, and animals. The primary goals of DiveDB include:

- **Metadata Management**: Utilizing the [Django](https://www.djangoproject.com/) framework to provide an admin interface for managing the metadata associated with each dive.
- **Data Reliability and Consistency**: Employing [Delta Lake](https://delta.io/) to bring ACID transactions to big data workloads, ensuring data reliability and consistency.
- **Analytical Query Workloads**: Using [DuckDB](https://duckdb.org/) for fast execution of analytical queries, making it ideal for data analysis tasks.
- **Interactive Data Visualization**: Building web-based dashboards with [Dash](https://dash.plotly.com/) to visualize data processed by the application.

Built entirely using open-source dependencies, DiveDB is designed to be a flexible and extensible application for managing and analyzing biologging data that can be run and deployed on any platform with Docker support.

DiveDB is currently in active development, and we welcome feedback and contributions. Please open an issue or submit a pull request if you have any suggestions or encounter any bugs.

<img width="1430" alt="Screenshot of dive data visualization" src="https://github.com/user-attachments/assets/84841ce3-a86f-47dc-b2bb-28097287797b">

## Table of Contents
- [A Note on Docker 🐳](#a-note-on-docker-)
- [Getting Started](#getting-started)
- [Where to Store Your Data Lake](#where-to-store-your-data-lake)
- [Delta Lake Schemas in DiveDB](#delta-lake-schemas-in-divedb)
  - [DataLake Schema](#1-datalake-schema)
  - [PointEventsLake Schema](#2-pointeventslake-schema)
  - [StateEventsLake Schema](#3-stateeventslake-schema)
- [Metadata Models in DiveDB](#metadata-models-in-divedb)
  - [LoggersWiki Model](#1-loggerswiki-model)
  - [Loggers Model](#2-loggers-model)
  - [Animals Model](#3-animals-model)
  - [Deployments Model](#4-deployments-model)
  - [AnimalDeployments Model](#5-animaldeployments-model)
  - [Recordings Model](#6-recordings-model)
  - [Files Model](#7-files-model)
  - [MediaUpdates Model](#8-mediaupdates-model)
- [Creating Django Migrations](#creating-django-migrations)
- [Uploading Files to the Data Lake](#uploading-files-to-the-data-lake)
- [Reading Files from the Data Lake](#reading-files-from-the-data-lake)
- [Using Dash to Visualize DiveDB Data](#using-dash-to-visualize-divedb-data)
  - [Key Components](#key-components)
  - [How to Use](#how-to-use)
  - [Example Data](#example-data)
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
   Ensure that the `DJANGO_SECRET_KEY` is set to a secure value. You can generate a random secret key using `openssl rand -base64 32`.

1. **Start the Docker Daemon:**
   Start the Docker Desktop application (recommended) OR run `dockerd` in the terminal.

1. **Start the PostgreSQL Service:**
   Create a directory for the PostgreSQL data mount.
   ```sh
   mkdir data/pg_data # Create the directory if it doesn't exist
   ```
   Once this directory is created, it must be empty to be used by the PostgreSQL container. To make sure it's empty, you can run `rm -rf data/pg_data/*`. 
   Use the `docker-compose.development.yaml` file to start the PostgreSQL service.
   ```sh
   docker compose -f docker-compose.development.yaml up -d postgres
   ```

1. **Create the Local PostgreSQL Database and User:**
   Set the user and password to any string. Make sure to update the `.env` file with the correct values. This can later be used instead of the root postgres user to access the database.
   ```sh
   docker compose -f docker-compose.development.yaml exec postgres psql -U postgres -c "CREATE DATABASE divedb;"
   docker compose -f docker-compose.development.yaml exec postgres psql -U postgres -c "CREATE USER divedbuser WITH PASSWORD 'divedbpassword';"
   docker compose -f docker-compose.development.yaml exec postgres psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE divedb TO divedbuser;"
   ```

1. **Start the Application:**
   Spin up the Django application and Jupyter notebook server. This will also start a Postgres database container if not already running. Leave this running while you work on the project.
   ```sh
   make up
   ```

1. **Run Migrations:**
   Run the migrations to create the tables in the database. Run this command in a new terminal window.
   ```sh
   make migrate
   ```

1. **Create a Superuser:**
   Create a superuser to access the admin interface. These credentials can then be used to log in to the Django admin interface.
   ```sh
   make createsuperuser
   ```

1. **Access the Application:**
   To access the Django admin interface, open your web browser and go to `http://localhost:8000`. To access the Jupyter notebook server, open your web browser and go to `http://localhost:8888` or connect to kernel `http://localhost:8888/jupyter` in a Jupyter client.

## Where to Store Your Data Lake

The data lake can be stored in a container on a remote server or locally. The path to the data lake is stored in the `.env` file as `CONTAINER_DELTA_LAKE_PATH`.

To store the data lake on a remote server, set the `CONTAINER_DELTA_LAKE_PATH` to the S3 connection string for the server. You'll also need to provide the following environment variables:
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_REGION
- AWS_ENDPOINT_URL

To store the data lake locally, set the `CONTAINER_DELTA_LAKE_PATH` to the path to the Delta Lake in the local file system.

## Delta Lake Schemas in DiveDB

The `DuckPond` class in `duck_pond.py` manages three distinct Delta Lakes, each with its own schema. These schemas define the structure of the data stored in the Delta Lakes and are crucial for ensuring data consistency and reliability.

### 1. DataLake Schema

The `DataLake` schema is designed to store general data collected from various sensors. It includes the following fields:

- **animal**: The identifier for the animal from which data is collected (string).
- **deployment**: The deployment identifier (string).
- **recording**: The recording session identifier (string).
- **group**: The group or category of the data (string).
- **class**: The class of the data (string).
- **label**: The label associated with the data (string).
- **datetime**: The timestamp of the data point (timestamp with microsecond precision, UTC).
- **value**: A struct containing:
  - **float**: A floating-point value (nullable).
  - **string**: A string value (nullable).
  - **boolean**: A boolean value (nullable).
  - **int**: An integer value (nullable).

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

These schemas are defined using the `pyarrow` library and are used to enforce data structure and integrity within the Delta Lakes managed by the `DuckPond` class.

## Metadata Models in DiveDB

The `models.py` file in the `metadata` app defines several Django models that represent the core entities in the DiveDB application. These models are used to store and manage metadata related to diving projects, animals, loggers, deployments, recordings, and files.

### 1. LoggersWiki Model

The `LoggersWiki` model contains metadata for a logger, including:

- **description**: A text field for a detailed description of the logger (nullable).
- **tags**: An array of text fields for tagging the logger.
- **projects**: An array of text fields for associating the logger with projects.

### 2. Loggers Model

The `Loggers` model represents a logger attached to diving vertebrates. It includes:

- **id**: The primary key identifier for the logger.
- **wiki**: A one-to-one relationship with `LoggersWiki` (nullable).
- **icon_url**: A URL field for the logger's icon (nullable).
- **serial_no**: The serial number of the logger (nullable).
- **manufacturer**: The manufacturer of the logger (nullable).
- **manufacturer_name**: The name of the manufacturer (nullable).
- **ptt**: The PTT identifier (nullable).
- **type**: The type of logger (nullable).
- **type_name**: The name of the logger type (nullable).
- **notes**: Additional notes about the logger (nullable).
- **owner**: The owner of the logger (nullable).

### 3. Animals Model

The `Animals` model represents an animal in a diving project. It includes:

- **id**: The primary key identifier for the animal.
- **project_id**: The identifier for the project the animal is part of.
- **common_name**: The common name of the animal.
- **scientific_name**: The scientific name of the animal.
- **lab_id**: The laboratory identifier (nullable).
- **birth_year**: The birth year of the animal (nullable).
- **sex**: The sex of the animal (nullable).
- **domain_ids**: Domain identifiers associated with the animal (nullable).

### 4. Deployments Model

The `Deployments` model represents a boat trip to collect data. It includes:

- **id**: The primary key identifier for the deployment.
- **domain_deployment_id**: Domain-specific deployment identifier (nullable).
- **animal_age_class**: The age class of the animal (nullable).
- **animal_age**: The age of the animal (nullable).
- **deployment_type**: The type of deployment (nullable).
- **deployment_name**: The name of the deployment.
- **rec_date**: The date of the recording.
- **deployment_latitude**: The latitude of the deployment location (nullable).
- **deployment_longitude**: The longitude of the deployment location (nullable).
- **deployment_location**: The location of the deployment (nullable).
- **departure_datetime**: The departure date and time (nullable).
- **recovery_latitude**: The latitude of the recovery location (nullable).
- **recovery_longitude**: The longitude of the recovery location (nullable).
- **recovery_location**: The location of the recovery (nullable).
- **arrival_datetime**: The arrival date and time (nullable).
- **animal**: The identifier for the animal involved in the deployment.
- **start_time**: The start time of the deployment (nullable).
- **start_time_precision**: The precision of the start time (nullable).
- **timezone**: The timezone of the deployment.

### 5. AnimalDeployments Model

The `AnimalDeployments` model represents an animal within a deployment. It includes:

- **deployment**: A foreign key to the `Deployments` model.
- **animal**: A foreign key to the `Animals` model.

### 6. Recordings Model

The `Recordings` model represents a recording of data from a logger. It includes:

- **id**: The primary key identifier for the recording.
- **name**: The name of the recording.
- **animal_deployment**: A foreign key to the `AnimalDeployments` model.
- **logger**: A foreign key to the `Loggers` model.
- **start_time**: The start time of the recording.
- **actual_start_time**: The actual start time of the recording (nullable).
- **end_time**: The end time of the recording (nullable).
- **start_time_precision**: The precision of the start time (nullable).
- **timezone**: The timezone of the recording (nullable).
- **quality**: The quality of the recording (nullable).
- **attachment_location**: The location of the logger attachment (nullable).
- **attachment_type**: The type of logger attachment (nullable).

### 7. Files Model

The `Files` model represents media and data files. It includes:

- **extension**: The file extension.
- **type**: The type of file (media or data).
- **delta_path**: The path to the file in the Delta Lake (nullable).
- **recording**: A foreign key to the `Recordings` model.
- **metadata**: JSON field for additional metadata (nullable).
- **start_time**: The start time of the file (nullable).
- **uploaded_at**: The upload timestamp (nullable).
- **file**: The file field for storing the file in OpenStack storage.

### 8. MediaUpdates Model

The `MediaUpdates` model represents an update to a media file. It includes:

- **file**: A foreign key to the `Files` model.
- **update_type**: The type of update applied to the media file.
- **update_factor**: A factor associated with the update.

These models are defined using Django's ORM and are used to manage the metadata and relationships between different entities in the DiveDB application.

## Creating Django Migrations

Django migrations are a way of propagating changes you make to your models (adding a field, deleting a model, etc.) into your database schema. Follow these steps to create and apply migrations:

1. **Make Changes to Your Models:**
   Modify your Django models in the [`models.py`](DiveDB/server/metadata/models.py) file as needed.

2. **Create Migrations:**
   After making changes to your models, create a new migration file by running the following command:
   ```sh
   make makemigrations
   ```
   This command will generate a migration file in the `migrations` directory of the app where changes were made.

3. **Apply Migrations:**
   To apply the migrations and update your database schema, run:
   ```sh
   make migrate
   ```
   This command will apply all unapplied migrations to your database.

4. **Check Migration Status:**
   To see which migrations have been applied and which are pending, use:
   ```sh
   make bash
   python manage.py showmigrations
   ```

5. **Rollback Migrations (if needed):**
   If you need to undo a migration, you can roll back to a previous state by specifying the migration name:
   ```sh
   make bash
   python manage.py migrate <app_name> <migration_name>
   ```
   Replace `<app_name>` with the name of your app and `<migration_name>` with the name of the migration you want to roll back to.

By following these steps, you can effectively manage changes to your database schema using Django's migration system.

## Uploading Files to the Data Lake

To see how to upload files to the data lake, refer to the [visualization_docs.ipynb](docs/visualization_docs.ipynb) notebook.

### Requirements
For any files to be uploaded to the data lake, they must be in netCDF format and meet the following requirements:

**Dimensions & Coordinates**<br>
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

## Using Dash to Visualize DiveDB Data

DiveDB provides a powerful visualization tool using [Dash](https://dash.plotly.com/), a Python framework for building analytical web applications. The [data_visualization.py](dash/data_visualization.py) script is an example of how to create interactive visualizations of biologging data stored in DiveDB.

### Key Components

- **Dash Application**: The script initializes a Dash application that serves as the main interface for data visualization.
- **Plotly Graphs**: Interactive plots are created using Plotly, allowing users to explore sensor and derived data over time.
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

   - **Interactive Plots**: The application includes a series of interactive plots generated using Plotly. These plots display various sensor and derived data signals, such as ECG, temperature, and depth. You can zoom into specific time ranges and explore the data in detail.

1. **Control Playback**: Use the play and pause buttons to control the playback of the data and video. The playhead slider allows you to navigate through the data timeline.

1. **Customize Visualization**: The script is designed to be flexible. You can modify the data sources, add new sensors, or change the visualization parameters to suit your needs.

### Example Data

The script uses example data from the DiveDB, specifically focusing on the animal with ID "apfo-001a". Ensure that your data is structured similarly to leverage the full capabilities of the visualization tool.

The example netCDF file can be downloaded here: [https://figshare.com/ndownloader/files/50061330](https://figshare.com/ndownloader/files/50061330). Follow the steps in the [Uploading Files to the Data Lake](#uploading-files-to-the-data-lake) section to upload the file to the data lake and then visualize it using the steps above.

By following these steps, you can effectively use Dash to visualize and analyze biologging data from DiveDB, gaining insights into the behavior and environment of marine mammals.

## Additional Commands

- **To Stop the Containers:**
  ```sh
  make down
  ```

- **To Rebuild the Docker Image:**
  ```sh
  make build
  ```

- **To Access the Django Shell in Docker:**
  ```sh
  make shell
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
