"""Agent API endpoints for chat and photo analysis."""

import base64
import logging

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The user's message to the agent.",
    )
    items: list[str] = Field(
        default_factory=list,
        description="Optional list of items to classify. If provided, the agent "
        "runs in batch classification mode.",
    )


class ClassifiedItem(BaseModel):
    input: str
    is_book: bool | None = None
    title: str | None = None
    authors: list[str] = []
    year: int | None = None
    confidence: float = 0.0
    decision: str = "unknown"
    reason: str = ""


class ChatResponse(BaseModel):
    results: list[ClassifiedItem] = []
    raw_response: str = ""
    model: str = ""
    error: str | None = None


class IdentifiedBook(BaseModel):
    extracted_title: str | None = None
    extracted_author: str | None = None
    matched_title: str | None = None
    matched_authors: list[str] = []
    year: int | None = None
    confidence: float = 0.0
    match_confidence: float | None = None
    notes: str = ""


class PhotoResponse(BaseModel):
    books: list[IdentifiedBook] = []
    total_identified: int = 0
    total_matched: int = 0
    error: str | None = None


@router.post("/chat", response_model=ChatResponse)
async def agent_chat(request: ChatRequest) -> ChatResponse:
    """Chat with the preprocessor agent.

    If items are provided, runs batch classification mode.
    Otherwise, processes the message as a general book query.
    """
    from bookcatalog.agents.preprocessor import run_preprocessor
    from bookcatalog.agents.config import PREPROCESSOR_MODEL

    items = request.items if request.items else [request.message]

    try:
        results = await run_preprocessor(items)
    except Exception as e:
        logger.exception("Preprocessor agent error")
        return ChatResponse(
            error=f"Agent error: {e}",
            model=PREPROCESSOR_MODEL,
        )

    classified = []
    for r in results:
        classified.append(
            ClassifiedItem(
                input=r.get("input", ""),
                is_book=r.get("is_book"),
                title=r.get("title"),
                authors=r.get("authors", []),
                year=r.get("year"),
                confidence=r.get("confidence", 0.0),
                decision=r.get("decision", "unknown"),
                reason=r.get("reason", ""),
            )
        )

    return ChatResponse(
        results=classified,
        model=PREPROCESSOR_MODEL,
    )


@router.post("/analyze-photo", response_model=PhotoResponse)
async def analyze_photo(file: UploadFile = File(...)) -> PhotoResponse:
    """Analyze a photo of books using the vision agent.

    Accepts JPEG, PNG, GIF, or WebP images up to 20 MB.
    """
    from bookcatalog.agents.vision import run_vision_agent
    from bookcatalog.agents.config import VISION_MODEL

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        return PhotoResponse(
            error=f"Unsupported image type: {file.content_type}. "
            f"Allowed: {', '.join(sorted(ALLOWED_IMAGE_TYPES))}",
        )

    image_data = await file.read()
    if len(image_data) > MAX_IMAGE_SIZE:
        return PhotoResponse(
            error=f"Image too large ({len(image_data)} bytes). "
            f"Maximum size: {MAX_IMAGE_SIZE} bytes.",
        )

    try:
        results = await run_vision_agent(
            image_data, media_type=file.content_type or "image/jpeg"
        )
    except Exception as e:
        logger.exception("Vision agent error")
        return PhotoResponse(error=f"Vision agent error: {e}")

    books = []
    for r in results:
        books.append(
            IdentifiedBook(
                extracted_title=r.get("extracted_title"),
                extracted_author=r.get("extracted_author"),
                matched_title=r.get("matched_title"),
                matched_authors=r.get("matched_authors", []),
                year=r.get("year"),
                confidence=r.get("confidence", 0.0),
                match_confidence=r.get("match_confidence"),
                notes=r.get("notes", ""),
            )
        )

    matched_count = sum(1 for b in books if b.matched_title)
    return PhotoResponse(
        books=books,
        total_identified=len(books),
        total_matched=matched_count,
    )
