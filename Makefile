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
	uv run pytest src/tests/ --cov=src/erp --cov-report=term-missing --cov-report=json:coverage.json --cov-fail-under=80
	@uv run python -c 'import json, re, os; data = json.load(open("coverage.json")); pct = round(data["totals"]["percent_covered"]); color = "green" if pct >= 80 else ("yellow" if pct >= 60 else "red"); content = open("README.md").read(); new_content = re.sub(r"badge/coverage-\d+%25-[a-zA-Z]+", f"badge/coverage-{pct}%25-{color}", content); open("README.md", "w").write(new_content); os.remove("coverage.json") if os.path.exists("coverage.json") else None; print(f"Updated README.md coverage badge to {pct}% ({color})")'

migrate:
	uv run alembic upgrade head
