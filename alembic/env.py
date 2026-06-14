"""Alembic environment — online migrations only, URL + metadata sourced from the app.

Pulls the connection URL from ``config.DATABASE_URL`` and the target schema from
``persistence.db.Base.metadata`` so migrations and the app never drift on either.
"""
import os
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure the project root is importable when Alembic runs from its own dir.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from config import DATABASE_URL
from persistence.db import Base
from persistence import models  # noqa: F401 — register tables on Base.metadata

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
