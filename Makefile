.PHONY: up down logs reset backend-shell db-shell

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

reset:
	docker compose down -v

backend-shell:
	docker compose exec backend bash

db-shell:
	docker compose exec db psql -U postgres -d rag_gap
