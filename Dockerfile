# Use the official Python image from the Docker Hub
FROM python:3.12

# Set the working directory in the container
WORKDIR /app

# Copy the rest of the application code into the container
COPY . /app/

# Install the dependencies
RUN pip install --no-cache-dir .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose the port the app runs on
EXPOSE 8000

# Set the DJANGO_PREFIX environment variable
ENV DJANGO_PREFIX=src.DiveDB

# Run the Django application
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
