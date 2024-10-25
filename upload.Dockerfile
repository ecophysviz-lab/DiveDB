# Use the official Python image from the Docker Hub
FROM python:3.12

# Set the working directory in the container
WORKDIR /app

# Copy the rest of the application code into the container
COPY . /app/

# Create the data directory
RUN mkdir -p data

# Install the dependencies
RUN pip install .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose the port the app runs on
EXPOSE 8000

# Set the DJANGO_PREFIX environment variable
ENV DJANGO_PREFIX=DiveDB

# Set the GOOGLE_APPLICATION_CREDENTIALS environment variable
ENV GOOGLE_APPLICATION_CREDENTIALS=brave-sonar-390402-7644b983ce44.json

# Set the CONTAINER_DELTA_LAKE_PATH environment variable
ENV CONTAINER_DELTA_LAKE_PATH=s3://divedb-delta-lakes-dryad-10-21

# Command to run your script
CMD ["python", "scripts/import_from_dryad.py"]