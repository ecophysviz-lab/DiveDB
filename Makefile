.PHONY: up down build migrate makemigrations createsuperuser shell bash test test-dash importmetadata builddash

COMPOSE_CMD = docker compose -f docker-compose.development.yaml
EXEC_WEB = $(COMPOSE_CMD) exec web

up:
	$(COMPOSE_CMD) --env-file .env up

down:
	$(COMPOSE_CMD) down

build:
	$(COMPOSE_CMD) build

makemigrations:
	$(EXEC_WEB) python manage.py makemigrations

migrate:
	$(EXEC_WEB) python manage.py migrate

createsuperuser:
	$(EXEC_WEB) python manage.py createsuperuser

shell:
	$(EXEC_WEB) python manage.py shell

bash:
	$(EXEC_WEB) bash

test:
	$(EXEC_WEB) pytest

# TODO: Add tests for custom dash components
test-dash:
	$(EXEC_WEB) pytest dash/video_preview
	$(EXEC_WEB) pytest dash/three_js_orientation

importmetadata:
	$(EXEC_WEB) python scripts/import_from_notion.py

builddash:
	cd dash/three_js_orientation && npm i && npm run build && python setup.py sdist bdist_wheel && sleep 1 && pip install dist/three_js_orientation-0.0.1.tar.gz
	cd dash/video_preview && npm i && npm run build && python setup.py sdist bdist_wheel && sleep 1 && pip install dist/video_preview-0.0.1.tar.gz
