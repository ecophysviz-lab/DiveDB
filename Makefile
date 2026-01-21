.PHONY: up down build migrate makemigrations createsuperuser shell bash test test-dash importmetadata build-all-dash dash dash-nocache build-dash clean-cache clear-cache

COMPOSE_CMD = docker compose -f docker-compose.development.yaml

up:
	$(COMPOSE_CMD) --env-file .env up

down:
	$(COMPOSE_CMD) down

build:
	$(COMPOSE_CMD) build

bash:
	$(COMPOSE_CMD) exec jupyter bash

test:
	pytest

build-all-dash:
	$(MAKE) build-dash component=three_js_orientation
	$(MAKE) build-dash component=video_preview

watch-dash-components:
	fswatch dash/video_preview/src/lib dash/three_js_orientation/src/lib --event=Updated | \
	while read -r path event; do \
		component_name=$$(echo "$$path" | sed 's|.*/dash/\([^/]*\)/.*|\1|'); \
		echo "Change detected in $$path. Rebuilding $$component_name..."; \
		$(MAKE) build-dash component="$$component_name" SKIP_NPM=1; \
	done

build-css:
	cd dash && npm run build-css

watch-css:
	cd dash && npm run watch-css

dash:
	$(MAKE) build-css
	DASH_USE_CACHE=true python dash/data_visualization.py

dash-nocache:
	DASH_USE_CACHE=false python dash/data_visualization.py

build-dash:
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

logging-on:
	export DASH_LOG_LEVEL=DEBUG && \
	export DASH_LOG_DATA_VIZ=DEBUG && \
	export DASH_LOG_CALLBACKS=DEBUG && \
	export DASH_LOG_SELECTION=DEBUG && \
	export DASH_LOG_LAYOUT=DEBUG

logging-off:
	export DASH_LOG_LEVEL=WARNING && \
	export DASH_LOG_DATA_VIZ=WARNING && \
	export DASH_LOG_CALLBACKS=WARNING && \
	export DASH_LOG_SELECTION=WARNING && \
	export DASH_LOG_LAYOUT=WARNING

clean-cache:
	@echo "Cleaning DuckPond cache files older than 1 day..."
	@python -c "from DiveDB.services.utils.cache_utils import cleanup_old_cache_files; cleanup_old_cache_files('.cache/duckpond', 86400)"
	@echo "✓ Cache cleanup complete"

clear-cache:
	@echo "Clearing all cache files..."
	@python -c "from DiveDB.services.utils.cache_utils import clear_all_caches; result = clear_all_caches(); print('\n'.join(f'  {k}: {v} files' for k,v in result.items()))"
	@echo "✓ All caches cleared"