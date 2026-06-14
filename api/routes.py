"""HTTP routes for the adaptive learning loop.

Pattern, every mutating endpoint: load the session from the repository → call a ``services`` function
that mutates the dict → save the whole dict back → return it. The repository is resolved per request
(``get_default_repository``), so the store (Postgres / in-memory) is swappable via config.
"""
import logging
import uuid

from fastapi import APIRouter, HTTPException

from api.schemas import (
    CreateSessionRequest,
    GradeRequest,
    SessionMeta,
    SessionResponse,
    StartSessionResponse,
)
from persistence.repository import get_default_repository
from services.learning_service import LockedNodeError, grade, open_lesson, start_session

logger = logging.getLogger(__name__)
router = APIRouter()


def _load_or_404(repo, user_id: str, session_id: str) -> dict:
    ls = repo.get(user_id, session_id)
    if ls is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return ls


@router.post("/sessions", response_model=StartSessionResponse)
def create_session(req: CreateSessionRequest) -> StartSessionResponse:
    """Run orchestration for a query. Only the SCOUT route yields a persisted learning_session."""
    result = start_session(req.query, req.format_type)
    resp = StartSessionResponse(
        route=result["route"],
        final_content=result.get("final_content"),
        exercise=result.get("exercise"),
    )
    ls = result.get("learning_session")
    if ls is not None:
        session_id = uuid.uuid4().hex
        get_default_repository().save(req.user_id, session_id, ls, title=req.query)
        resp.session_id = session_id
        resp.learning_session = ls
    return resp


@router.get("/sessions/{user_id}", response_model=list[SessionMeta])
def list_sessions(user_id: str) -> list[SessionMeta]:
    return [SessionMeta(**m) for m in get_default_repository().list_sessions(user_id)]


@router.get("/sessions/{user_id}/{session_id}", response_model=SessionResponse)
def get_session(user_id: str, session_id: str) -> SessionResponse:
    repo = get_default_repository()
    ls = _load_or_404(repo, user_id, session_id)
    return SessionResponse(session_id=session_id, learning_session=ls)


@router.post("/sessions/{user_id}/{session_id}/lessons/{node_id}", response_model=SessionResponse)
def open_node_lesson(user_id: str, session_id: str, node_id: str) -> SessionResponse:
    repo = get_default_repository()
    ls = _load_or_404(repo, user_id, session_id)
    try:
        ls = open_lesson(ls, node_id)
    except LockedNodeError as e:
        # Server-side gate: a locked node cannot be opened even by a hand-crafted request.
        raise HTTPException(status_code=409, detail={"error": "locked", "pending": e.pending})
    repo.save(user_id, session_id, ls)
    return SessionResponse(session_id=session_id, learning_session=ls)


@router.post("/sessions/{user_id}/{session_id}/grade", response_model=SessionResponse)
def grade_node(user_id: str, session_id: str, node_id: str, req: GradeRequest) -> SessionResponse:
    """Grade a submission, capture mastery, and run adaptation; ``node_id`` is a query param."""
    repo = get_default_repository()
    ls = _load_or_404(repo, user_id, session_id)
    try:
        ls = grade(ls, node_id, req.solution)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    repo.save(user_id, session_id, ls)
    return SessionResponse(session_id=session_id, learning_session=ls)
