# DiveDB

This is a Django project that uses Docker for containerization.

## Getting Started

To start local development, follow these steps:

1. **Clone the repository:**
   ```sh
   git clone https://github.com/yourusername/divedb.git
   cd divedb
   ```

1. **Install pre-commit hooks:**
   ```sh
   pip install pre-commit
   pre-commit install
   ```

1. **Create the local PostgreSQL database and user:**
   ```sh
   psql -U postgres -c "CREATE DATABASE divedb;"
   psql -U postgres -c "CREATE USER divedbuser WITH PASSWORD 'divedbpassword';"
   psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE divedb TO divedbuser;"
   ```

1. **Set up the environment variables:**
   Copy the `.env.example` file to `.env` and update the values as needed:
   ```sh
   cp .env.example .env
   ```
   Make sure to set the `DJANGO_SECRET_KEY` to a secure value.

1. **Start the application:**
   ```sh
   # Spin up Docker
   make up
   # or run natively
   python manage.py runserver
   ```

1. **Run migrations:**
   ```sh
   # Run in Docker
   make migrate
   # or run natively
   python manage.py migrate
   ```

1. **Create a superuser:**
   ```sh
   # Run in Docker
   make createsuperuser
   # or run natively
   python manage.py createsuperuser
   ```

1. **Import data from Notion:**
   ```sh
   # Run in Docker
   make import_from_notion
   # or run natively
   python scripts/import_from_notion.py
   ```

1. **Access the application:**
   Open your web browser and go to `http://localhost:8000`.

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

- **To run tests:**
  ```sh
  # Run in Docker
  make test
  # or run natively
  pip install -r requirements.txt
  pytest
  ```

## Deployment

The application is deployed on a Nautilus using Kubernetes.  It is currently deployed in the `jkb-lab` namespace.

The deployment has a Postgres database with attached persistent volume, a django application, and a jupyter notebook server.  Images for deployment are stored in `ghcr.io`, with an associated Github Actions workflow to push new images to the repository (`.github/workflows/docker-build.yml`).

Configuration files:
1. `.env.github` for USER and TOKEN
2. `.env.nautilus` for NAUTILUS_NAMESPACE

Set K8s default namespace with `./deployment/set-default-namespace.sh`.

Precursor scripts (don't typically need to be run once created)
1. Run `./deployment/secrets.sh` and `./deployment/ghcr.secrets.sh` to create the relevant secrets in the Kubernetes cluster
2. Run `./deployment/misc/build.sh` to create the persistent volume for the deltalake storage.  This only needs to be run if the storage changes (e.g. size).

Build images by opening a Pull Request and triggering the Github Actions workflow.

Deploy each service independently with `deployment/<service>/build.sh`.