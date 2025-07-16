.PHONY: up down build migrate makemigrations createsuperuser shell bash test test-dash importmetadata builddash

COMPOSE_CMD = docker compose -f docker-compose.development.yaml

up:
	$(COMPOSE_CMD) --env-file .env up

down:
	$(COMPOSE_CMD) down

build:
	$(COMPOSE_CMD) build

bash:
	$(COMPOSE_CMD) exec jupyter bash

builddash:
	cd dash/three_js_orientation && npm i && npm run build && python setup.py sdist bdist_wheel && sleep 1 && pip install dist/three_js_orientation-0.0.1.tar.gz
	cd dash/video_preview && npm i && npm run build && python setup.py sdist bdist_wheel && sleep 1 && pip install dist/video_preview-0.0.1.tar.gz
