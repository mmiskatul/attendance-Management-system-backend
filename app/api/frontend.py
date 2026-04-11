"""Frontend routes for the embedded admin UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse


router = APIRouter(tags=["frontend"], include_in_schema=False)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
INDEX_FILE = FRONTEND_DIR / "index.html"


@router.get("/")
async def frontend_index() -> FileResponse:
    """Serve the embedded admin frontend."""

    return FileResponse(INDEX_FILE)
