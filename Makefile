.PHONY: up down build migrate makemigrations createsuperuser shell bash test test-dash importmetadata build-all-dash run-dash build-bash

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

build-all-dash:
	$(MAKE) build-bash component=three_js_orientation
	$(MAKE) build-bash component=video_preview

watch-dash-components:
	fswatch dash/video_preview/src/lib dash/three_js_orientation/src/lib --event=Updated | \
	while read -r path event; do \
		component_name=$$(echo "$$path" | sed 's|.*/dash/\([^/]*\)/.*|\1|'); \
		echo "Change detected in $$path. Rebuilding $$component_name..."; \
		$(MAKE) build-bash component="$$component_name" SKIP_NPM=1; \
	done

run-dash:
	python dash/data_visualization.py

build-bash:
	@echo "Building $(component)..."
	@cd dash/$(component) && \
	$(if $(SKIP_NPM),,echo "  → Installing npm dependencies..." && npm i $(if $(DEBUG),,> /dev/null 2>&1) && ) \
	echo "  → Building JavaScript..." && \
	npm run build $(if $(DEBUG),,> /dev/null 2>&1) && \
	echo "  → Building Python package..." && \
	python setup.py sdist bdist_wheel $(if $(DEBUG),,> /dev/null 2>&1) && \
	sleep 1 && \
	echo "  → Installing Python package..." && \
	pip install dist/$(component)-0.0.1.tar.gz $(if $(DEBUG),,> /dev/null 2>&1) && \
	echo "  ✓ $(component) build complete"