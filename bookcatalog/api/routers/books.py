"""Book matching API endpoints."""

import logging
import time

from fastapi import APIRouter
from pydantic import BaseModel, Field

from bookcatalog.research import OpenLibraryClient, OpenLibraryError, preprocess_input

logger = logging.getLogger(__name__)

router = APIRouter()


class MatchRequest(BaseModel):
    titles: list[str] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="List of title strings to match against Open Library.",
    )
    delimiter: str | None = Field(
        default=None,
        description="If set, split each line on this delimiter before matching. "
        'Use "|" for Amazon order strings.',
    )
    max_concurrent: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of concurrent Open Library requests.",
    )


class MatchedBook(BaseModel):
    input_title: str
    matched: bool
    matched_title: str | None = None
    decision: str | None = None
    confidence: float | None = None
    title_similarity: float | None = None
    authors: list[str] = []
    first_publish_year: int | None = None
    edition_count: int | None = None
    isbn: str | None = None


class MatchResponse(BaseModel):
    results: list[MatchedBook]
    total: int
    matched_count: int
    unmatched_count: int
    elapsed_seconds: float
    max_concurrent: int


@router.post("/match", response_model=MatchResponse)
async def match_titles(request: MatchRequest) -> MatchResponse:
    """Match a list of strings to books via Open Library (concurrently)."""
    cleaned = preprocess_input(request.titles, delimiter=request.delimiter)
    if not cleaned:
        return MatchResponse(
            results=[], total=0, matched_count=0, unmatched_count=0,
            elapsed_seconds=0, max_concurrent=request.max_concurrent,
        )

    client = OpenLibraryClient(max_concurrent=request.max_concurrent)
    t0 = time.monotonic()
    matches = await client.match_titles(cleaned)
    elapsed = round(time.monotonic() - t0, 2)
    logger.info(
        "Matched %d titles in %.1fs (%.1fs avg, %d concurrent)",
        len(cleaned), elapsed, elapsed / len(cleaned) if cleaned else 0,
        client.max_concurrent,
    )

    results: list[MatchedBook] = []
    for title, match in zip(cleaned, matches):
        if match:
            results.append(
                MatchedBook(
                    input_title=title,
                    matched=True,
                    matched_title=match.matched_title,
                    decision=match.decision,
                    confidence=match.confidence,
                    title_similarity=match.title_similarity,
                    authors=match.authors,
                    first_publish_year=match.first_publish_year,
                    edition_count=match.edition_count,
                    isbn=match.isbn,
                )
            )
        else:
            results.append(MatchedBook(input_title=title, matched=False))

    matched_count = sum(1 for r in results if r.matched)
    return MatchResponse(
        results=results,
        total=len(results),
        matched_count=matched_count,
        unmatched_count=len(results) - matched_count,
        elapsed_seconds=elapsed,
        max_concurrent=client.max_concurrent,
    )
