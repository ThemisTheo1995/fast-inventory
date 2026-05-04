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
uv run pytest src/tests
```

---

## 🧹 Linting & Formatting (Ruff)

### Lint

```bash
uv run ruff check src
```

### Fix issues automatically

```bash
uv run ruff check src --fix
```

### Format code

```bash
uv run ruff format src
```

---

## 📦 Common Commands

| Task             | Command                                              |
| ---------------- | ---------------------------------------------------- |
| Start API        | `uv run uvicorn erp.main:app --reload --app-dir src` |
| New migration    | `uv run alembic revision --autogenerate -m "msg"`    |
| Apply migrations | `uv run alembic upgrade head`                        |
| Rollback         | `uv run alembic downgrade -1`                        |
| Run tests        | `uv run pytest src/tests`                            |
| Lint             | `uv run ruff check src`                              |
| Format           | `uv run ruff format src`                             |

---

## ⚡ Tips

* `uv run` ensures commands use the correct environment without manual activation
* Keep imports relative to `src` (or configure PYTHONPATH if needed)
* Use `ruff` instead of multiple tools (`flake8`, `isort`, `black`)

---

## 🛠 Optional Improvements

* Add a `Makefile`:

```makefile
run:
	uv run uvicorn erp.main:app --reload --app-dir src

lint:
	uv run ruff check src

format:
	uv run ruff format src

test:
	uv run pytest src/tests

migrate:
	uv run alembic upgrade head
```

---

## 📄 License

Your license here.
