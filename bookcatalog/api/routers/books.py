"""Book matching API endpoints."""

import logging
import re
import time
from typing import Any

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


class DebugMatchRequest(BaseModel):
    titles: list[str] = Field(
        ...,
        min_length=1,
        max_length=200,
        description="List of title strings to debug-match.",
    )


@router.post("/debug-match")
async def debug_match_titles(request: DebugMatchRequest) -> dict:
    """Run match with full debug trace for each title.

    Returns detailed information about every processing stage:
    product filtering, FTS search queries, candidate scoring,
    edition enrichment, and the final decision.
    """
    if _local_search is None:
        return {"error": "Local database not available", "results": []}

    t0 = time.monotonic()
    results = []
    for title in request.titles:
        trace = _local_search.match_title_debug(title)
        results.append(trace)

    return {
        "results": results,
        "total": len(results),
        "elapsed_seconds": round(time.monotonic() - t0, 2),
    }


@router.get("/test-orders")
async def get_test_orders() -> dict:
    """Return the list of known test orders for the debug dashboard."""
    from tests.test_amazon_list import ORDERS

    return {"orders": ORDERS, "total": len(ORDERS)}


# ---------------------------------------------------------------------------
# Tool execution endpoints - same tools the LLM agents use
# ---------------------------------------------------------------------------


class SearchToolRequest(BaseModel):
    query: str = Field(..., description="Title, author, or free-text query.")
    max_results: int = Field(
        default=10, ge=1, le=50, description="Maximum results to return."
    )


class MatchToolRequest(BaseModel):
    title: str = Field(..., description="Title string to match.")
    author: str | None = Field(
        default=None, description="Optional author name hint."
    )


@router.post("/tools/search")
async def tool_search_books(request: SearchToolRequest) -> dict[str, Any]:
    """Execute search_books, the same FTS search tool the LLM uses.

    Returns raw result rows from the local Open Library database along
    with timing information.
    """
    if _local_search is None:
        return {"error": "Local database not available", "results": []}

    t0 = time.monotonic()
    results = _local_search.search(request.query, limit=request.max_results)
    elapsed_ms = round((time.monotonic() - t0) * 1000, 1)

    return {
        "tool": "search_books",
        "query": request.query,
        "max_results": request.max_results,
        "results": results,
        "result_count": len(results),
        "elapsed_ms": elapsed_ms,
    }


@router.post("/tools/match")
async def tool_match_book(request: MatchToolRequest) -> dict[str, Any]:
    """Execute match_book, the same title matcher the LLM uses.

    Returns the matched book details along with raw document data and timing.
    """
    if _local_search is None:
        return {"error": "Local database not available"}

    t0 = time.monotonic()
    match = _local_search.match_title(
        request.title, author_hint=request.author
    )
    elapsed_ms = round((time.monotonic() - t0) * 1000, 1)

    if match is None:
        return {
            "tool": "match_book",
            "title": request.title,
            "author": request.author,
            "matched": False,
            "elapsed_ms": elapsed_ms,
        }

    return {
        "tool": "match_book",
        "title": request.title,
        "author": request.author,
        "matched": True,
        "matched_title": match.matched_title,
        "decision": match.decision,
        "confidence": match.confidence,
        "title_similarity": match.title_similarity,
        "authors": match.authors,
        "first_publish_year": match.first_publish_year,
        "edition_count": match.edition_count,
        "isbn": match.isbn,
        "publisher": match.publisher,
        "number_of_pages": match.number_of_pages,
        "physical_format": match.physical_format,
        "raw_doc": match.raw_doc,
        "elapsed_ms": elapsed_ms,
    }


@router.get("/tools/stats")
async def tool_get_stats() -> dict[str, Any]:
    """Execute get_database_stats, the same stats tool the LLM uses.

    Returns database counts and timing information.
    """
    if _local_search is None:
        return {"error": "Local database not available"}

    t0 = time.monotonic()
    stats = _local_search.get_stats()
    elapsed_ms = round((time.monotonic() - t0) * 1000, 1)

    return {
        "tool": "get_database_stats",
        "stats": stats,
        "elapsed_ms": elapsed_ms,
    }


# ---------------------------------------------------------------------------
# Agent graph visualization
# ---------------------------------------------------------------------------


def _sanitize_mermaid(raw: str) -> str:
    """Clean up LangGraph mermaid output for browser rendering.

    LangGraph's draw_mermaid() wraps node labels in HTML ``<p>`` tags,
    includes a YAML front-matter config block that conflicts with
    client-side mermaid.initialize(), and applies classDef styles that
    assume a light background. We strip all of these and apply
    dark-theme compatible styles.
    """
    # Strip YAML front-matter (---\nconfig:...\n---)
    cleaned = re.sub(r"^---\n.*?\n---\n", "", raw, flags=re.DOTALL)
    # Strip HTML tags from node labels
    cleaned = re.sub(r"</?p>", "", cleaned)
    # Replace LangGraph's light-theme classDefs with dark-theme versions
    cleaned = re.sub(
        r"classDef default [^\n]+",
        "classDef default fill:#2d2b55,stroke:#818cf8,color:#e2e8f0,stroke-width:2px",
        cleaned,
    )
    cleaned = re.sub(
        r"classDef first [^\n]+",
        "classDef first fill:#1e293b,stroke:#6366f1,color:#a5b4fc,stroke-width:2px",
        cleaned,
    )
    cleaned = re.sub(
        r"classDef last [^\n]+",
        "classDef last fill:#1e293b,stroke:#6366f1,color:#a5b4fc,stroke-width:2px",
        cleaned,
    )
    return cleaned


@router.get("/agent-graph")
async def get_agent_graphs() -> dict[str, Any]:
    """Return mermaid diagrams for both LLM agent graphs.

    Generates the graph by instantiating each agent with create_agent
    and calling get_graph().draw_mermaid(). Returns the graph structure
    for both the preprocessor (chat) agent and the vision agent.
    """
    from bookcatalog.agents.config import (
        OPENAI_API_KEY,
        PREPROCESSOR_MODEL,
        VISION_MODEL,
    )
    from bookcatalog.agents.tools import get_agent_tools

    graphs: dict[str, Any] = {}
    tools = get_agent_tools()
    tool_names = [t.name for t in tools]

    try:
        from langchain.agents import create_agent
        from langchain_openai import ChatOpenAI

        # Preprocessor (chat) agent
        preprocessor_agent = create_agent(
            ChatOpenAI(
                model=PREPROCESSOR_MODEL,
                api_key=OPENAI_API_KEY,
                temperature=0,
            ),
            tools,
            system_prompt="(graph export only)",
        )
        preprocessor_graph = preprocessor_agent.get_graph()
        graphs["preprocessor"] = {
            "name": "Preprocessor (Chat) Agent",
            "model": PREPROCESSOR_MODEL,
            "mermaid": _sanitize_mermaid(preprocessor_graph.draw_mermaid()),
            "recursion_limit": 12,
            "tools": tool_names,
        }

        # Vision agent
        vision_agent = create_agent(
            ChatOpenAI(
                model=VISION_MODEL,
                api_key=OPENAI_API_KEY,
                temperature=0,
            ),
            tools,
            system_prompt="(graph export only)",
        )
        vision_graph = vision_agent.get_graph()
        graphs["vision"] = {
            "name": "Vision (Photo Import) Agent",
            "model": VISION_MODEL,
            "mermaid": _sanitize_mermaid(vision_graph.draw_mermaid()),
            "recursion_limit": 20,
            "tools": tool_names,
        }
    except Exception as exc:
        logger.exception("Failed to generate agent graphs")
        return {"error": str(exc), "graphs": {}}

    return {"graphs": graphs, "tool_names": tool_names}
