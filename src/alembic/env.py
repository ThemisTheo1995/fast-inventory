from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from erp.core.config import get_settings
from erp.model_registry import metadata as target_metadata

config = context.config
settings = get_settings()

# Check if the URL was already injected (e.g., by conftest.py during tests)
current_url = config.get_main_option("sqlalchemy.url")


if not current_url or current_url.startswith("driver://"):
    config.set_main_option("sqlalchemy.url", str(settings.DATABASE_URL))


if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # --- PRODUCTION UPGRADES ---
        compare_type=True,  # Detects changes like String(50) -> String(100)
        compare_server_default=True,  # Detects changes to default values
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # --- PRODUCTION UPGRADES ---
            compare_type=True,  # Detects changes like String(50) -> String(100)
            compare_server_default=True,  # Detects changes to default values
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
