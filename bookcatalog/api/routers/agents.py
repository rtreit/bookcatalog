"""Agent API endpoints for chat and photo analysis."""

import logging

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel, Field, model_validator

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


class ChatRequest(BaseModel):
    """Request payload for the conversational book assistant."""

    message: str | None = Field(
        default=None,
        max_length=10000,
        description="Legacy single-turn user message.",
    )
    items: list[str] = Field(
        default_factory=list,
        description="Optional legacy list of items to classify.",
    )
    messages: list[dict[str, str]] = Field(
        default_factory=list,
        description="Full conversation history as role/content objects.",
    )

    @model_validator(mode="after")
    def validate_message_content(self) -> "ChatRequest":
        """Require either a legacy message or message history."""
        if self.message is not None and not self.message.strip():
            raise ValueError("message must not be empty")

        if not self.messages and self.message is None:
            raise ValueError("Either message or messages must be provided")

        return self


class ClassifiedItem(BaseModel):
    input: str
    is_book: bool | None = None
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    confidence: float = 0.0
    decision: str = "unknown"
    reason: str = ""


class ChatResponse(BaseModel):
    results: list[ClassifiedItem] = Field(default_factory=list)
    message: str = ""
    raw_response: str = ""
    model: str = ""
    error: str | None = None


class IdentifiedBook(BaseModel):
    extracted_title: str | None = None
    extracted_author: str | None = None
    matched_title: str | None = None
    matched_authors: list[str] = Field(default_factory=list)
    year: int | None = None
    confidence: float = 0.0
    match_confidence: float | None = None
    notes: str = ""


class PhotoResponse(BaseModel):
    books: list[IdentifiedBook] = Field(default_factory=list)
    total_identified: int = 0
    total_matched: int = 0
    error: str | None = None


@router.post("/chat", response_model=ChatResponse)
async def agent_chat(request: ChatRequest) -> ChatResponse:
    """Chat with the conversational book assistant."""
    from bookcatalog.agents.preprocessor import run_preprocessor
    from bookcatalog.agents.config import PREPROCESSOR_MODEL

    try:
        if request.messages:
            response = await run_preprocessor(messages=request.messages)
        elif request.items:
            response = await run_preprocessor(items=request.items)
        else:
            response = await run_preprocessor(messages=[
                {"role": "user", "content": request.message or ""},
            ])
    except Exception as e:
        logger.exception("Preprocessor agent error")
        return ChatResponse(
            error=f"Agent error: {e}",
            message="",
            raw_response="",
            model=PREPROCESSOR_MODEL,
        )

    classified = []
    for r in response.get("results", []):
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
        message=response.get("raw_response", ""),
        raw_response=response.get("raw_response", ""),
        model=PREPROCESSOR_MODEL,
    )


@router.post("/analyze-photo", response_model=PhotoResponse)
async def analyze_photo(file: UploadFile = File(...)) -> PhotoResponse:
    """Analyze a photo of books using the vision agent.

    Accepts JPEG, PNG, GIF, or WebP images up to 20 MB.
    """
    from bookcatalog.agents.vision import run_vision_agent

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
