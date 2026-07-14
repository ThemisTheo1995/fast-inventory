.PHONY: run lint format test test-cov migrate

run:
	uv run uvicorn erp.main:app --reload

lint:
	uv run ruff check .

format:
	uv run ruff format .

test:
	uv run pytest

test-cov:
	uv run pytest src/tests/ \
		--cov=src/erp \
		--cov-report=term-missing \
		--cov-fail-under=80 \

migrate:
	uv run alembic upgrade head
