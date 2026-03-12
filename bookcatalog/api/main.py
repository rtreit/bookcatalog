"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import books

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


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok"}
