.PHONY: up down build migrate createsuperuser shell bash test

up:
	docker compose -f docker-compose.development.yaml --env-file .env up --build

down:
	docker compose -f docker-compose.development.yaml down

build:
	docker compose -f docker-compose.development.yaml build

migrate:
	docker compose -f docker-compose.development.yaml exec web python manage.py migrate

createsuperuser:
	docker compose -f docker-compose.development.yaml exec web python manage.py createsuperuser

shell:
	docker compose -f docker-compose.development.yaml exec web python manage.py shell

bash:
	docker compose -f docker-compose.development.yaml exec web bash

test:
	docker compose -f docker-compose.development.yaml exec web pytest
