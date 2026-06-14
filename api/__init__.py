"""FastAPI service exposing the adaptive learning loop over HTTP (P1 #6).

Each endpoint loads the ``learning_session`` from the repository, drives a ``services`` function, and
saves the result — so the API holds no per-request state and the same code runs from Streamlit. This
HTTP surface is what lets an out-of-process client (the Next.js frontend, Phase B) consume the loop.
"""
