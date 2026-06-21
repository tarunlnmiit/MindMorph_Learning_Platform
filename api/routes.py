"""HTTP routes for the adaptive learning loop.

Pattern, every mutating endpoint: load the session from the repository → call a ``services`` function
that mutates the dict → save the whole dict back → return it. The repository is resolved per request
(``get_default_repository``), so the store (Postgres / in-memory) is swappable via config.
"""
import logging
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from api.schemas import (
    AssessmentAnswersRequest,
    CreateSessionRequest,
    GradeRequest,
    IngestResponse,
    SessionMeta,
    SessionResponse,
    StartSessionResponse,
)
from persistence.repository import get_default_repository
from services.learning_service import (
    LockedNodeError,
    grade,
    grade_assessment,
    open_lesson,
    start_session,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Generation (orchestration / lesson compose / adaptation) is LLM-backed and can fail transiently —
# rate limits (Groq TPM), timeouts, malformed model output. Surface those as a clean 503 with a safe
# message (the real error is logged server-side, never leaked to the client) so the UI can show
# "try again" instead of a raw 500.
GEN_FAILED = "The learning service is busy or rate-limited. Please try again in a moment."


def _service_unavailable(what: str, exc: Exception) -> HTTPException:
    logger.exception("api: %s failed", what)
    return HTTPException(status_code=503, detail=GEN_FAILED)


def _load_or_404(repo, user_id: str, session_id: str) -> dict:
    ls = repo.get(user_id, session_id)
    if ls is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return ls


@router.post("/sessions", response_model=StartSessionResponse)
def create_session(req: CreateSessionRequest) -> StartSessionResponse:
    """Run orchestration for a query. Only the SCOUT route yields a persisted learning_session."""
    try:
        result = start_session(req.query, req.format_type)
    except Exception as e:
        raise _service_unavailable("start_session", e)
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
        ls = open_lesson(ls, node_id, user_id=user_id)
    except LockedNodeError as e:
        # Server-side gate: a locked node cannot be opened even by a hand-crafted request.
        raise HTTPException(status_code=409, detail={"error": "locked", "pending": e.pending})
    except Exception as e:
        # Lesson compose is LLM-backed (content + exercise) — transient failure ⇒ 503, not 500.
        raise _service_unavailable("open_lesson", e)
    repo.save(user_id, session_id, ls)
    return SessionResponse(session_id=session_id, learning_session=ls)


@router.post("/users/{user_id}/knowledge", response_model=IngestResponse)
async def ingest_material(user_id: str, file: UploadFile = File(...)) -> IngestResponse:
    """Ingest a user's PDF into their personal RAG store; its chunks ground future lessons (P2 #9)."""
    name = file.filename or "upload.pdf"
    if not name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported.")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    from rag import registry

    try:
        chunks = registry.ingest_pdf(user_id, data, name)
    except ValueError as e:
        # Unreadable / image-only PDF — client error, not a server fault.
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise _service_unavailable("ingest_material", e)
    return IngestResponse(filename=name, chunks=chunks)


@router.post("/sessions/{user_id}/{session_id}/assessment", response_model=SessionResponse)
def grade_session_assessment(
    user_id: str, session_id: str, req: AssessmentAnswersRequest
) -> SessionResponse:
    """Grade the onboarding diagnostic quiz; correct answers pre-seed mastered nodes (P2 #8)."""
    repo = get_default_repository()
    ls = _load_or_404(repo, user_id, session_id)
    try:
        ls = grade_assessment(ls, req.answers)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise _service_unavailable("grade_assessment", e)
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
    except Exception as e:
        # Grading itself is deterministic, but adaptation/regeneration is LLM-backed — guard anyway.
        raise _service_unavailable("grade", e)
    repo.save(user_id, session_id, ls)
    return SessionResponse(session_id=session_id, learning_session=ls)
