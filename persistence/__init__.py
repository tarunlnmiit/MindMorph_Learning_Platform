"""Postgres persistence for the adaptive learning loop (P1 #6).

A ``learning_session`` dict is stored verbatim as a JSONB blob keyed by ``(user_id, session_id)`` — it
maps 1:1 to the in-memory state, so there is near-zero mapping code. Access goes through the
``LearningSessionRepository`` (Repository pattern) so the storage engine stays an implementation detail
the rest of the app never sees.
"""
