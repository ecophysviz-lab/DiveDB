# DiveDB

DiveDB is designed to organize and analyze biologging data collected by any sensor on any marine mammal. By storing your data in a structured data lake, DiveDB enforces consistency allowing you to query data across multiple dives, sensors, and animals. The primary goals of DiveDB include:

- **Metadata Management**: Utilizing the [Django](https://www.djangoproject.com/) framework to handle to provide an admin interface for managing the metadata associated with each dive.
- **Data Reliability and Consistency**: Employing [Delta Lake](https://delta.io/) to bring ACID transactions to big data workloads, ensuring data reliability and consistency.
- **Analytical Query Workloads**: Using [DuckDB](https://duckdb.org/) for fast execution of analytical queries, making it ideal for data analysis tasks.
- **Interactive Data Visualization**: Building web-based dashboards with [Dash](https://dash.plotly.com/) to visualize data processed by the application.

Built entirely using open source dependencies, DiveDB is designed to be a flexible and extensible application for managing and analyzing biologging data that can be run and deployed on any platform with Docker support.

DiveDB is currently in active development and interested in feedback and contributions. Please open an issue or submit a pull request if you have any suggestions or find any bugs.

## A note on Docker 🐳

This project uses Docker to facilitate a consistent development and production environment. Docker allows you to package applications and their dependencies into a container, which can then be run on any system that has Docker installed. This helps in avoiding issues related to environment setup and dependency management. For more information on getting started with Docker, visit [Docker's official getting started guide](https://docs.docker.com/get-started/).

## Getting Started

To create a local analysis environment, follow these steps:

1. **Clone the repository:**
   ```sh
   git clone https://github.com/ecophysviz-lab/DiveDB.git
   cd DiveDB
   ```

1. **Set up the environment variables:**
   Copy the `.env.example` file to `.env` and update the values as needed:
   ```sh
   cp .env.example .env
   ```
   Make sure to set the `DJANGO_SECRET_KEY` to a secure value.

1. **Start the PostgreSQL service:**
   Use the `docker-compose.development.yaml` file to start the PostgreSQL service.
   ```sh
   docker-compose -f docker-compose.development.yaml up -d metadata_database
   ```

1. **Create the local PostgreSQL database and user:**
   Set the user and password to any string. Make sure to update the `.env` file with the correct values.
   ```sh
   docker-compose -f docker-compose.development.yaml exec metadata_database psql -U postgres -c "CREATE DATABASE divedb;"
   docker-compose -f docker-compose.development.yaml exec metadata_database psql -U postgres -c "CREATE USER divedbuser WITH PASSWORD 'divedbpassword';"
   docker-compose -f docker-compose.development.yaml exec metadata_database psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE divedb TO divedbuser;"
   ```

1. **Start the application:**
   Spin up the Django application and Jupyter notebook server. This will also start a Postgres database container if not already running.
   ```sh
   make up
   ```

1. **Run migrations:**
   Run the migrations to create the tables in the database.
   ```sh
   make migrate
   ```

1. **Create a superuser:**
   Create a superuser to access the admin interface. These credentials can then be used to log in to the Django admin interface.
   ```sh
   make createsuperuser
   ```

1. **Access the application:**
   To access the Django admin interface, open your web browser and go to `http://localhost:8000`. To access the Jupyter notebook server, open your web browser and go to `http://localhost:8888` or connect to kernal `http://localhost:8888/jupyter` in a Jupyter client.

## Additional Commands

- **To stop the containers:**
  ```sh
  make down
  ```

- **To rebuild the Docker image:**
  ```sh
  make build
  ```

- **To access the Django shell in Docker:**
  ```sh
  make shell
  ```

- **To enter the Docker container with bash in Docker:**
  ```sh
  make bash
  ```

## Additional Steps for Development of DiveDB
1. **Install pre-commit hooks:**
   ```sh
   pip install pre-commit
   pre-commit install
   ```

1. **To run tests:**
   ```sh
   # Run in Docker
   make test
   # or run natively
   pip install -r requirements.txt
   pytest
   ```