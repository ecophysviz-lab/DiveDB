# DiveDB

DiveDB is designed to organize and analyze biologging data collected by any sensor on any marine mammal. By storing your data in a structured data lake, DiveDB enforces consistency, allowing you to query data across multiple dives, sensors, and animals. The primary goals of DiveDB include:

- **Metadata Management**: Utilizing the [Django](https://www.djangoproject.com/) framework to provide an admin interface for managing the metadata associated with each dive.
- **Data Reliability and Consistency**: Employing [Delta Lake](https://delta.io/) to bring ACID transactions to big data workloads, ensuring data reliability and consistency.
- **Analytical Query Workloads**: Using [DuckDB](https://duckdb.org/) for fast execution of analytical queries, making it ideal for data analysis tasks.
- **Interactive Data Visualization**: Building web-based dashboards with [Dash](https://dash.plotly.com/) to visualize data processed by the application.

Built entirely using open-source dependencies, DiveDB is designed to be a flexible and extensible application for managing and analyzing biologging data that can be run and deployed on any platform with Docker support.

DiveDB is currently in active development, and we welcome feedback and contributions. Please open an issue or submit a pull request if you have any suggestions or encounter any bugs.

## A Note on Docker 🐳

This project uses Docker to facilitate a consistent development and production environment. Docker allows you to package applications and their dependencies into a container, which can then be run on any system that has Docker installed. This helps in avoiding issues related to environment setup and dependency management. For more information on getting started with Docker, visit [Docker's official getting started guide](https://docs.docker.com/get-started/).

## Where to Store Your Data Lake

The data lake can be stored in a container on a remote server or locally. The path to the data lake is stored in the `.env` file as `CONTAINER_DELTA_LAKE_PATH`.

To store the data lake on a remote server, set the `CONTAINER_DELTA_LAKE_PATH` to the S3 connection string for the server. You'll also need to provide the following environment variables:
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_REGION
- AWS_ENDPOINT_URL

To store the data lake locally, set the `CONTAINER_DELTA_LAKE_PATH` to the path to the Delta Lake in the local file system.

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
   Ensure that the `DJANGO_SECRET_KEY` is set to a secure value.

1. **Start the Docker Daemon:**
   Start the Docker Desktop application (recommended) OR run `dockerd` in the terminal.

1. **Start the PostgreSQL Service:**
   Use the `docker-compose.development.yaml` file to start the PostgreSQL service.
   ```sh
   docker-compose -f docker-compose.development.yaml up -d metadata_database
   ```

1. **Create the Local PostgreSQL Database and User:**
   Set the user and password to any string. Make sure to update the `.env` file with the correct values.
   ```sh
   docker-compose -f docker-compose.development.yaml exec metadata_database psql -U postgres -c "CREATE DATABASE divedb;"
   docker-compose -f docker-compose.development.yaml exec metadata_database psql -U postgres -c "CREATE USER divedbuser WITH PASSWORD 'divedbpassword';"
   docker-compose -f docker-compose.development.yaml exec metadata_database psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE divedb TO divedbuser;"
   ```

1. **Start the Application:**
   Spin up the Django application and Jupyter notebook server. This will also start a Postgres database container if not already running.
   ```sh
   make up
   ```

1. **Run Migrations:**
   Run the migrations to create the tables in the database.
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

**Example:**
- A sample netCDF file is included in the repository: `oror-002_2024-01-16.nc` that meets the above requirements and can be used as a template for your own data.

## Reading Files from the Data Lake

We use [DuckDB](https://duckdb.org/) to read files from the data lake. To see how to read files from the data lake, refer to the [visualization_docs.ipynb](docs/visualization_docs.ipynb) notebook.

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
