# DiveDB

This is a Django project that uses Docker for containerization.

## Getting Started

To start local development, follow these steps:

1. **Clone the repository:**
   ```sh
   git clone https://github.com/yourusername/divedb.git
   cd divedb
   ```

2. **Build and start the Docker containers using docker-compose:**
   ```sh
   docker-compose -f docker-compose.development.yaml up --build -d
   ```

3. **Run migrations:**
   ```sh
   docker-compose -f docker-compose.development.yaml exec web python manage.py migrate
   ```

4. **Create a superuser:**
   ```sh
   docker-compose -f docker-compose.development.yaml exec web python manage.py createsuperuser
   ```

5. **Access the application:**
   Open your web browser and go to `http://localhost:8000`.

6. **Install pre-commit hooks:**
   ```sh
   pre-commit install
   ```

## Additional Commands

- **To stop the containers:**
  ```sh
  docker-compose -f docker-compose.development.yaml down
  ```

- **To rebuild the Docker image:**
  ```sh
  docker-compose -f docker-compose.development.yaml build
  ```

- **To access the Django shell:**
  ```sh
  docker-compose -f docker-compose.development.yaml exec web python manage.py shell
  ```

- **To enter the Docker container with bash:**
  ```sh
  docker-compose -f docker-compose.development.yaml exec web bash
  ```

- **To run tests:**
  ```sh
  docker-compose -f docker-compose.development.yaml exec web pytest
  <!-- OR -->
  pip install -r requirements.txt
  pytest
  ```
