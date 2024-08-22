# Use the official Python image from the Docker Hub
FROM python:3.12
WORKDIR /app

COPY ./requirements.txt /app/requirements.txt
RUN pip3 install -r requirements.txt --break-system-packages

COPY . /app
COPY ./jupyter_notebook_config.py /root/.jupyter/jupyter_notebook_config.py
RUN prefect config set PREFECT_API_URL=http://localhost:4200/api
RUN prefect config set PREFECT_RESULTS_PERSIST_BY_DEFAULT=true
# RUN prefect config set PREFECT_SERVER_API_HOST=http://prefect/api

# Expose the port for Jupyter Notebook
EXPOSE 8888

# Start Jupyter Notebook
CMD ["jupyter", "notebook", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root"]