"""Request/response models for the API boundary.

The ``learning_session`` itself is passed through as an open dict (``data``) — it is the persisted blob
and its shape is owned by the services layer, not re-declared here (which would drift). These models
only type the thin request envelopes and list metadata.
"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    format_type: str = "B"


class GradeRequest(BaseModel):
    solution: str


class IngestResponse(BaseModel):
    filename: str
    chunks: int


class SessionMeta(BaseModel):
    session_id: str
    title: str
    updated_at: Optional[str] = None


class StartSessionResponse(BaseModel):
    route: str
    session_id: Optional[str] = None
    learning_session: Optional[dict[str, Any]] = None
    final_content: Optional[str] = None
    exercise: Optional[dict[str, Any]] = None


class SessionResponse(BaseModel):
    session_id: str
    learning_session: dict[str, Any]
