"""Native LangChain tools for local book search.

These tools run in the same process as the chat and vision agents. This avoids
MCP subprocess overhead for internal agent tool calls.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from bookcatalog.research.local_search import LocalBookSearch

_search: LocalBookSearch | None = None


def _get_search() -> LocalBookSearch:
    """Return the shared local book search instance."""
    global _search
    if _search is None:
        _search = LocalBookSearch()
    return _search


def _truncate_text(value: str | None, max_length: int = 200) -> str:
    """Truncate text for readable tool output.

    Args:
        value: Raw text to truncate.
        max_length: Maximum number of characters to keep.

    Returns:
        Truncated text with trailing ellipsis when needed.
    """
    if not value:
        return ""
    text = value.strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3].rstrip()}..."


def _append_optional_part(parts: list[str], label: str, value: Any) -> None:
    """Append a labeled value when it is present.

    Args:
        parts: Output string parts being assembled.
        label: Label prefix for the value.
        value: Value to render.
    """
    if value is None:
        return

    text = str(value).strip()
    if text:
        parts.append(f"{label}: {text}")


def _format_search_row(row: dict[str, Any]) -> str:
    """Format a search row for tool output.

    Args:
        row: Search result row from ``LocalBookSearch.search``.

    Returns:
        Human-readable single-line summary.
    """
    parts = [f"Title: {row['title']}"]
    _append_optional_part(parts, "Authors", row.get("authors"))
    _append_optional_part(parts, "Subtitle", row.get("subtitle"))
    _append_optional_part(parts, "Year", row.get("first_publish_year"))
    _append_optional_part(
        parts,
        "Description",
        _truncate_text(row.get("description", "")),
    )
    _append_optional_part(
        parts,
        "First sentence",
        _truncate_text(row.get("first_sentence", "")),
    )
    _append_optional_part(parts, "Subjects", row.get("subjects"))
    _append_optional_part(parts, "People", row.get("subject_people"))
    _append_optional_part(parts, "Places", row.get("subject_places"))
    _append_optional_part(parts, "Times", row.get("subject_times"))
    _append_optional_part(parts, "LC classifications", row.get("lc_classifications"))
    _append_optional_part(parts, "Dewey", row.get("dewey_number"))
    return " | ".join(parts)


def _format_match_metadata(match_data: dict[str, Any]) -> list[str]:
    """Format optional metadata from a matched book.

    Args:
        match_data: Raw matched document metadata.

    Returns:
        List of formatted metadata strings.
    """
    parts: list[str] = []
    _append_optional_part(parts, "Subtitle", match_data.get("subtitle"))
    _append_optional_part(
        parts,
        "Description",
        _truncate_text(match_data.get("description", "")),
    )
    _append_optional_part(
        parts,
        "First sentence",
        _truncate_text(match_data.get("first_sentence", "")),
    )
    _append_optional_part(parts, "Subjects", match_data.get("subjects"))
    _append_optional_part(parts, "People", match_data.get("subject_people"))
    _append_optional_part(parts, "Places", match_data.get("subject_places"))
    _append_optional_part(parts, "Times", match_data.get("subject_times"))
    _append_optional_part(
        parts,
        "LC classifications",
        match_data.get("lc_classifications"),
    )
    _append_optional_part(parts, "Dewey", match_data.get("dewey_number"))
    return parts


@tool
def search_books(query: str, max_results: int = 5) -> str:
    """Search the local Open Library database for books by title, author, or subject.

    The database indexes work-level metadata: title, authors, subtitle,
    first_publish_year, subjects, description, first_sentence, LC/Dewey
    classifications. Edition-level data (ISBN, publisher, page count) is
    available through the match_book tool.

    Args:
        query: Title, author, or free-text query.
        max_results: Maximum number of results to return (1-20).

    Returns:
        Human-readable search results.
    """
    search = _get_search()
    results = search.search(query, limit=max_results)

    if not results:
        return f"No books found for: {query}"

    return "\n".join(_format_search_row(row) for row in results)


@tool
def match_book(title: str) -> str:
    """Match a single title to the best local catalog entry.

    Returns work-level metadata (title, authors, year, subjects, description)
    plus edition-level data when available (ISBN, publisher, page count, format).

    Args:
        title: Input title string to match.

    Returns:
        Human-readable match details.
    """
    search = _get_search()
    match = search.match_title(title)

    if match is None:
        return f"No match found for: {title}"

    parts = [
        f"Matched: {match.matched_title}",
        f"Authors: {', '.join(match.authors)}",
        f"Decision: {match.decision}",
        f"Confidence: {match.confidence:.0%}",
    ]
    if match.first_publish_year:
        parts.append(f"Year: {match.first_publish_year}")
    if match.isbn:
        parts.append(f"ISBN: {match.isbn}")
    if match.publisher:
        parts.append(f"Publisher: {match.publisher}")
    if match.number_of_pages:
        parts.append(f"Pages: {match.number_of_pages}")
    if match.physical_format:
        parts.append(f"Format: {match.physical_format}")
    if match.edition_count:
        parts.append(f"Editions: {match.edition_count}")

    raw_doc = match.raw_doc or {}
    parts.extend(_format_match_metadata(raw_doc))
    return " | ".join(parts)


@tool
def get_database_stats() -> str:
    """Return high-level statistics about the local Open Library database.

    Returns:
        Human-readable summary of database counts.
    """
    search = _get_search()
    stats = search.get_stats()
    parts = [
        f"Local catalog stats: {stats['works']} works indexed",
        f"{stats['authors']} authors indexed",
    ]
    if stats.get("editions"):
        parts.append(f"{stats['editions']} editions indexed (with ISBNs)")
    else:
        parts.append("no editions loaded yet (run build with --editions-only)")
    return ", ".join(parts) + "."


def get_agent_tools() -> list[Any]:
    """Return the native LangChain tools used by internal agents.

    Returns:
        List of decorated LangChain tools.
    """
    return [search_books, match_book, get_database_stats]
