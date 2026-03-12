"""FastAPI application entry point."""

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import agents, books

# Ensure pywin32 paths are available (uvicorn's reload worker may skip .pth processing)
if sys.platform == "win32":
    _site_packages = Path(sys.prefix) / "Lib" / "site-packages"
    for _subdir in ["win32", "win32\\lib", "Pythonwin"]:
        _p = str(_site_packages / _subdir)
        if _p not in sys.path and (_site_packages / _subdir).exists():
            sys.path.insert(0, _p)

app = FastAPI(
    title="BookCatalog API",
    description="API for the AI-powered book cataloging system.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(books.router, prefix="/api/books", tags=["books"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok"}
