"""ORM models for persisted learning state.

One table, one blob: the entire ``learning_session`` dict lives in a single JSONB column keyed by
``(user_id, session_id)``. No normalized per-node tables for the MVP — the session is only ever read or
written as a whole, so a blob keeps the mapping trivial and the "swap the store, keep the logic"
property the loop was designed for.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from persistence.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LearningSessionRow(Base):
    __tablename__ = "learning_sessions"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    # The whole learning_session dict (skill_graph, node_state, lessons, …). Portable JSON dict.
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # A short human label for the session list (the original learning query / summary).
    title: Mapped[str] = mapped_column(String, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )
