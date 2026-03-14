"""Book matching API endpoints."""

import logging
import time

from fastapi import APIRouter
from pydantic import BaseModel, Field

from bookcatalog.research import (
    LocalBookSearch,
    OpenLibraryClient,
    preprocess_input,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Try to initialize local search at module load; fall back to API if unavailable.
_local_search: LocalBookSearch | None = None
try:
    _local_search = LocalBookSearch()
    logger.info("Local Open Library database loaded successfully")
except FileNotFoundError:
    logger.warning(
        "Local Open Library database not found, falling back to API. "
        "Run: uv run python scripts/download_openlibrary.py && "
        "uv run python scripts/build_openlibrary_db.py"
    )


class MatchRequest(BaseModel):
    titles: list[str] = Field(
        ...,
        min_length=1,
        max_length=2000,
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
    use_local: bool = Field(
        default=True,
        description="Use local database if available. Falls back to API if not.",
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
    source: str = Field(
        description="Data source used: 'local' or 'api'",
    )


@router.post("/match", response_model=MatchResponse)
async def match_titles(request: MatchRequest) -> MatchResponse:
    """Match a list of strings to books.

    Uses the local Open Library database for instant matching when available.
    Falls back to the Open Library API if the local database is not built.
    """
    cleaned = preprocess_input(request.titles, delimiter=request.delimiter)
    if not cleaned:
        return MatchResponse(
            results=[], total=0, matched_count=0, unmatched_count=0,
            elapsed_seconds=0, max_concurrent=request.max_concurrent,
            source="none",
        )

    t0 = time.monotonic()

    if request.use_local and _local_search is not None:
        matches = _local_search.match_titles(cleaned)
        source = "local"
        logger.info(
            "Local search: matched %d/%d titles in %.3fs",
            sum(1 for m in matches if m is not None),
            len(cleaned),
            time.monotonic() - t0,
        )
    else:
        client = OpenLibraryClient(max_concurrent=request.max_concurrent)
        matches = await client.match_titles(cleaned)
        source = "api"
        logger.info(
            "API search: matched %d/%d titles in %.1fs (%d concurrent)",
            sum(1 for m in matches if m is not None),
            len(cleaned),
            time.monotonic() - t0,
            client.max_concurrent,
        )

    elapsed = round(time.monotonic() - t0, 2)

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
        max_concurrent=request.max_concurrent,
        source=source,
    )
