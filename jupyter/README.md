DATA_FOLDER=/GeospatialServicesData_Dev
MOUNT_PATH=/app/data

docker build -t jupyter .
docker run \
    -p 8888:8888 \
    -e MOUNT_PATH=$MOUNT_PATH \
    -v $(pwd)/notebooks:/app/notebooks \
    -v $DATA_FOLDER:$MOUNT_PATH \
    -v $(pwd)/jupyter_notebook_config.py:/root/.jupyter/jupyter_notebook_config.py \
    jupyter
