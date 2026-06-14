"""Streamlit-free service layer for the adaptive learning loop.

The interactive loop (scout → lesson → grade → mastery → adapt) was originally implemented inline in
``app.py`` as functions that mutated ``st.session_state``. This package extracts that logic so it
operates on a plain ``learning_session`` dict, letting both the Streamlit UI and the FastAPI service
call identical code paths. State shape is unchanged — see ``learning_service.new_learning_session``.
"""
