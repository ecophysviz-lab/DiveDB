IMAGE_NAME = geospatial-backend-implementation
DEV_MOUNTS = -v ${HOME}/TestData:/app/data \
	-v /cccr-lab:/cccr-lab \
	-v ${HOME}/coastal-resilience-utilities/coastal_resilience_utilities:/usr/local/lib/python3.12/dist-packages/coastal_resilience_utilities \
	-v ${HOME}/GeospatialBackend/GeospatialBackend:/usr/local/lib/python3.12/dist-packages/GeospatialBackend \
	-v ${HOME}/crl-datacube/crl_datacube:/usr/local/lib/python3.12/dist-packages/crl_datacube 

docker-build:
	docker build -t $(IMAGE_NAME) \
		.

docker-dev:
	docker build -t $(IMAGE_NAME) \
		.

	docker run \
		-v ${PWD}:/app \
		${DEV_MOUNTS} \
		--env-file .env \
		--env-file .data.env \
		-p 4200:4200 \
		$(EXTRA_DOCKER_ARGS) \
		$(IMAGE_NAME) $(EXTRA_IMAGE_ARGS)


with-env:
	export $(shell cat .env | xargs) && $(MAKE) $(ARGS)


run-python:
	docker build -t $(IMAGE_NAME) \
		--build-arg GITHUB_USERNAME=$(GITHUB_USERNAME) \
		--build-arg GITHUB_TOKEN=$(GITHUB_TOKEN) \
		.
	docker run -it \
		-v ${PWD}:/app \
		--entrypoint python3 \
		$(IMAGE_NAME) -m $(FILE)