# DiveDB

This is a Django project that uses Docker for containerization.

## Getting Started

To start local development, follow these steps:

1. **Clone the repository:**
   ```sh
   git clone https://github.com/yourusername/divedb.git
   cd divedb
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
   docker compose -f docker-compose.development.yaml up --build -d
   # or run natively
   python manage.py runserver
   ```

1. **Run migrations:**
   ```sh
   # Run in Docker
   docker compose -f docker-compose.development.yaml exec web python manage.py migrate
   # or run natively
   python manage.py migrate
   ```

1. **Create a superuser:**
   ```sh
   # Run in Docker
   docker compose -f docker-compose.development.yaml exec web python manage.py createsuperuser
   # or run natively
   python manage.py createsuperuser
   ```

1. **Access the application:**
   Open your web browser and go to `http://localhost:8000`.

1. **Install pre-commit hooks:**
   ```sh
   pre-commit install
   ```

## Additional Commands

- **To stop the containers:**
  ```sh
  docker compose -f docker-compose.development.yaml down
  ```

- **To rebuild the Docker image:**
  ```sh
  docker compose -f docker-compose.development.yaml build
  ```

- **To access the Django shell:**
  ```sh
  docker compose -f docker-compose.development.yaml exec web python manage.py shell
  ```

- **To enter the Docker container with bash:**
  ```sh
  docker compose -f docker-compose.development.yaml exec web bash
  ```

- **To run tests:**
  ```sh
  docker compose -f docker-compose.development.yaml exec web pytest
  <!-- OR -->
  pip install -r requirements.txt
  pytest
  ```
