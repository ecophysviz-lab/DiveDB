# Use the official Python image from the Docker Hub
FROM python:3.12

WORKDIR /app
RUN apt update && apt install -y python3-pip git libpq-dev

COPY ./requirements.txt /app/requirements.txt
RUN pip3 install -r requirements.txt --break-system-packages
RUN prefect config set PREFECT_RESULTS_PERSIST_BY_DEFAULT=true
RUN prefect config set PREFECT_SERVER_API_HOST=0.0.0.0
RUN prefect config set PREFECT_UI_URL=http://0.0.0.0:4200/prefect
# RUN prefect config set PREFECT_API_URL=http://0.0.0.0:4200/prefect/api

# Pass the startup script as arguments to Tini
COPY . /app
# RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["bash"]
CMD ["/app/entrypoint.sh"]
