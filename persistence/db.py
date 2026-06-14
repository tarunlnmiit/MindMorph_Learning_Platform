"""SQLAlchemy engine + session factory, built from ``config.DATABASE_URL``.

Engine creation is lazy so importing this module never opens a connection (tests that mock the
repository, or agent code that never touches the DB, stay free of a live Postgres dependency).
"""
import logging
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = logging.getLogger(__name__)

_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


class Base(DeclarativeBase):
    """Declarative base for all persistence models."""


def get_engine() -> Engine:
    """Return the process-wide engine, creating it on first use from ``config.DATABASE_URL``."""
    global _engine
    if _engine is None:
        from config import DATABASE_URL

        logger.info("persistence: creating engine for %s", DATABASE_URL.rsplit("@", 1)[-1])
        _engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
    return _engine


def get_sessionmaker() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionLocal


def create_all() -> None:
    """Create tables directly from the models (test/dev convenience; production uses Alembic)."""
    from persistence import models  # noqa: F401 — ensure models register on Base.metadata

    Base.metadata.create_all(get_engine())
