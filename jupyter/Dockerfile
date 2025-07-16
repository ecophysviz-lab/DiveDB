# Use the official Python image from the Docker Hub
FROM python:3.12
WORKDIR /app

# Copy pyproject.toml and install dependencies
COPY ../pyproject.toml /app/pyproject.toml
RUN pip3 install -e ".[dev]"

# Copy the rest of the application
COPY . /app

COPY ./jupyter_notebook_config.py /root/.jupyter/jupyter_notebook_config.py

# Expose the port for Jupyter Notebook
EXPOSE 8888

# Start Jupyter Notebook
CMD ["jupyter", "notebook", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root"]