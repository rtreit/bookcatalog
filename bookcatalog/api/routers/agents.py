"""Agent API endpoints for chat, photo analysis, and benchmarking."""

import logging
from typing import Any

from fastapi import APIRouter, File, Form, UploadFile
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
    model: str | None = Field(
        default=None,
        max_length=100,
        description="Optional model override for the chat agent.",
    )

    @model_validator(mode="after")
    def validate_message_content(self) -> "ChatRequest":
        """Require either a legacy message or message history."""
        if self.message is not None and not self.message.strip():
            raise ValueError("message must not be empty")

        if not self.messages and self.message is None:
            raise ValueError("Either message or messages must be provided")

        if self.model is not None:
            cleaned_model = self.model.strip()
            self.model = cleaned_model or None

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
    model: str = ""
    error: str | None = None


class BenchmarkModelRequest(BaseModel):
    """Configuration for one benchmarked model run."""

    model: str = Field(min_length=1, max_length=100)
    reasoning_effort: str | None = Field(default=None, max_length=20)
    verbosity: str | None = Field(default=None, max_length=20)


class PhotoBenchmarkRequest(BaseModel):
    """Request payload for photo benchmark runs."""

    case_id: str = Field(min_length=1, max_length=100)
    models: list[BenchmarkModelRequest] = Field(min_length=1, max_length=8)


@router.post("/chat", response_model=ChatResponse)
async def agent_chat(request: ChatRequest) -> ChatResponse:
    """Chat with the conversational book assistant."""
    from bookcatalog.agents.preprocessor import (
        normalize_classified_result,
        run_preprocessor,
    )
    from bookcatalog.agents.config import PREPROCESSOR_MODEL

    selected_model = request.model or PREPROCESSOR_MODEL

    try:
        if request.messages:
            response = await run_preprocessor(
                messages=request.messages,
                model_name=selected_model,
            )
        elif request.items:
            response = await run_preprocessor(
                items=request.items,
                model_name=selected_model,
            )
        else:
            response = await run_preprocessor(
                messages=[
                    {"role": "user", "content": request.message or ""},
                ],
                model_name=selected_model,
            )
    except Exception as e:
        logger.exception("Preprocessor agent error")
        return ChatResponse(
            error=f"Agent error: {e}",
            message="",
            raw_response="",
            model=selected_model,
        )

    classified = []
    for r in response.get("results", []):
        normalized = normalize_classified_result(r)
        classified.append(
            ClassifiedItem(
                input=normalized["input"],
                is_book=normalized["is_book"],
                title=normalized["title"],
                authors=normalized["authors"],
                year=normalized["year"],
                confidence=normalized["confidence"],
                decision=normalized["decision"],
                reason=normalized["reason"],
            )
        )

    return ChatResponse(
        results=classified,
        message=response.get("raw_response", ""),
        raw_response=response.get("raw_response", ""),
        model=selected_model,
    )


@router.post("/analyze-photo", response_model=PhotoResponse)
async def analyze_photo(
    file: UploadFile = File(...),
    model: str | None = Form(default=None),
) -> PhotoResponse:
    """Analyze a photo of books using the vision agent.

    Accepts JPEG, PNG, GIF, or WebP images up to 20 MB.
    """
    from bookcatalog.agents.config import VISION_MODEL
    from bookcatalog.agents.vision import run_vision_agent

    selected_model = (model or "").strip() or VISION_MODEL

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        return PhotoResponse(
            error=f"Unsupported image type: {file.content_type}. "
            f"Allowed: {', '.join(sorted(ALLOWED_IMAGE_TYPES))}",
            model=selected_model,
        )

    image_data = await file.read()
    if len(image_data) > MAX_IMAGE_SIZE:
        return PhotoResponse(
            error=f"Image too large ({len(image_data)} bytes). "
            f"Maximum size: {MAX_IMAGE_SIZE} bytes.",
            model=selected_model,
        )

    try:
        results = await run_vision_agent(
            image_data,
            media_type=file.content_type or "image/jpeg",
            model_name=selected_model,
        )
    except Exception as e:
        logger.exception("Vision agent error")
        return PhotoResponse(error=f"Vision agent error: {e}", model=selected_model)

    if len(results) == 1 and results[0].get("error"):
        raw_response = str(results[0].get("raw_response") or "").strip()
        error_text = raw_response or str(results[0]["error"])
        if len(error_text) > 300:
            error_text = f"{error_text[:297].rstrip()}..."
        return PhotoResponse(
            error=f"Vision agent response error: {error_text}",
            model=selected_model,
        )

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
        model=selected_model,
    )


@router.get("/model-options")
async def model_options() -> dict[str, Any]:
    """Return shared model picker metadata for the frontend."""
    from bookcatalog.agents.model_options import get_model_picker_options

    return get_model_picker_options()


@router.get("/benchmark-cases")
async def benchmark_cases() -> dict[str, Any]:
    """Return available photo benchmark cases and recommended models."""
    from bookcatalog.agents.vision_benchmark import list_benchmark_cases

    return list_benchmark_cases()


@router.post("/benchmark-photo")
async def benchmark_photo(request: PhotoBenchmarkRequest) -> dict[str, Any]:
    """Run a built-in photo benchmark across one or more models."""
    from bookcatalog.agents.vision_benchmark import run_photo_benchmark

    try:
        return await run_photo_benchmark(
            case_id=request.case_id,
            models=[model.model_dump() for model in request.models],
        )
    except (FileNotFoundError, ValueError) as exc:
        logger.warning("Photo benchmark request failed: %s", exc)
        return {"error": str(exc), "runs": []}
    except Exception as exc:
        logger.exception("Photo benchmark error")
        return {"error": f"Photo benchmark error: {exc}", "runs": []}
