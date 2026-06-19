<p align="center">
  <img src="https://img.shields.io/badge/coverage-91%25-green?style=for-the-badge" alt="Coverage">
  <img src="https://img.shields.io/badge/License-Apache_2.0-D22128.svg?style=for-the-badge&logo=apache" alt="License">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.13-3776AB.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python Version">
  <img src="https://img.shields.io/badge/FastAPI-005571.svg?style=for-the-badge&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/uv-Package%20Manager-DE5FE9.svg?style=for-the-badge&logo=astral&logoColor=white" alt="uv Package Manager">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1.svg?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Alembic-Migrations-D32F2F.svg?style=for-the-badge&logo=alembic&logoColor=white" alt="Alembic">
  <img src="https://img.shields.io/badge/Pydantic-V2-E92063.svg?style=for-the-badge&logo=pydantic&logoColor=white" alt="Pydantic">
</p>

---

# ERP FastAPI Project

## 📁 Project Structure

```text
erp/
│── .env
│── .gitignore
│── pyproject.toml
│── src/
│   ├── alembic/
│   ├── erp/
│   │   ├── main.py
│   │   └── ... (application modules)
│   └── tests/
```

---

## ⚙️ Setup (uv)

### 1. Install uv (if not installed)

```bash
pip install uv
```

---

### 2. Create virtual environment & install deps

```bash
uv venv
source .venv/bin/activate   # macOS / Linux
.venv\Scripts\activate      # Windows

uv pip install -r pyproject.toml
```

> If you're using lockfiles:

```bash
uv pip sync uv.lock
```

---

## 🔐 Environment Variables

Create a `.env` file:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/erp_db
```

---

## 🚀 Running the FastAPI App

From project root:

```bash
uv run uvicorn erp.main:app --reload --app-dir src
```

Docs:

* http://127.0.0.1:8000/docs

---

## 🧱 Database Migrations (Alembic)

### 1. Run migrations

```bash
uv run alembic upgrade head
```

---

### 2. Create a migration

```bash
uv run alembic revision --autogenerate -m "your message"
```

---

### 3. Rollback

```bash
uv run alembic downgrade -1
```

---

### 4. Alembic config notes

Make sure:

**`alembic/env.py`**

```python
from erp.db.base import Base  # adjust path
target_metadata = Base.metadata
```

**`alembic.ini`**

```ini
sqlalchemy.url = ${DATABASE_URL}
```

---

## 🧪 Running Tests

```bash
uv run pytest tests
```

---

## 🧹 Linting & Formatting (Ruff)

### Lint

```bash
uv run ruff check
```

### Fix issues automatically

```bash
uv run ruff check --fix
```

### Format code

```bash
uv run ruff format
```

---

## 📦 Common Commands

| Task             | Command                                              |
| ---------------- | ---------------------------------------------------- |
| Start API        | `uv run uvicorn erp.main:app --reload --app-dir src` |
| New migration    | `uv run alembic revision --autogenerate -m "msg"`    |
| Apply migrations | `uv run alembic upgrade head`                        |
| Rollback         | `uv run alembic downgrade -1`                        |
| Run tests        | `uv run pytest tests`                            |
| Run coverage     | `uv run pytest --cov=src/erp`                    |
| Lint             | `uv run ruff check`                              |
| Format           | `uv run ruff format`                             |

---

## ⚡ Tips

* `uv run` ensures commands use the correct environment without manual activation
* Use `ruff` instead of multiple tools (`flake8`, `isort`, `black`)

---

## 🛠 Optional Improvements

* Add a `Makefile`:

```makefile
run:
	uv run uvicorn erp.main:app --reload --app-dir src

lint:
	uv run ruff check

format:
	uv run ruff format

test:
	uv run pytest tests

migrate:
	uv run alembic upgrade head
```

---

## 📄 License

This project is licensed under the Apache License 2.0.

You are free to use, modify, distribute, and use this software commercially, provided that you comply with the terms of the license.

See the `LICENSE` file for the full license text.

Copyright (c) 2026 [C. Themis Theodoratos]
