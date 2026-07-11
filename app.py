"""
FastAPI backend entrypoint.

The implementation lives in `app/main.py` because the `app/` package name
shadows a root-level `app.py` module in Python imports.

Run:
    uvicorn app.main:app --reload
"""

from app.main import app

__all__ = ["app"]
