.PHONY: dev dev-api dev-web db db-down migrate migrate-create test test-api lint-api

# ── Infrastructure ──────────────────────────────────────────────────────────
db:
	docker compose up -d postgres postgres_test

db-down:
	docker compose down

# ── Backend ─────────────────────────────────────────────────────────────────
dev-api:
	cd apps/api && uv run fastapi dev app/main.py

migrate:
	cd apps/api && uv run alembic upgrade head

migrate-create:
	cd apps/api && uv run alembic revision --autogenerate -m "$(name)"

test-api:
	cd apps/api && uv run pytest -v

lint-api:
	cd apps/api && uv run ruff check . && uv run ruff format --check .

# ── Frontend ─────────────────────────────────────────────────────────────────
dev-web:
	cd apps/web && npm run dev

# ── Combined ─────────────────────────────────────────────────────────────────
dev:
	make db
	@echo ""
	@echo "Run in separate terminals:"
	@echo "  make dev-api"
	@echo "  make dev-web"
