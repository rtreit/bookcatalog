"""MCP server that exposes book search as a tool.

This server wraps the local Open Library FTS5 search, making it available
to LangGraph agents via the Model Context Protocol.

Usage:
    uv run python -m bookcatalog.mcp.book_search
"""

from mcp.server.fastmcp import FastMCP

from bookcatalog.research.local_search import LocalBookSearch

mcp = FastMCP("BookSearch")

_search: LocalBookSearch | None = None


def _get_search() -> LocalBookSearch:
    global _search
    if _search is None:
        _search = LocalBookSearch()
    return _search


@mcp.tool()
def search_books(query: str, max_results: int = 5) -> str:
    """Search the Open Library catalog for books matching a query.

    Use this to look up book titles, find books by author, or verify
    whether a given string refers to a real book.

    Args:
        query: A book title, author name, or search phrase.
        max_results: Maximum number of results to return (default 5).

    Returns:
        A formatted string with matching books and their metadata.
    """
    search = _get_search()
    results = search.search(query, limit=max_results)

    if not results:
        return f"No books found for: {query}"

    lines = []
    for row in results:
        title = row["title"]
        authors = row.get("authors", "")
        year = row.get("first_publish_year", "")
        parts = [f"Title: {title}"]
        if authors:
            parts.append(f"Authors: {authors}")
        if year:
            parts.append(f"Year: {year}")
        lines.append(" | ".join(parts))

    return "\n".join(lines)


@mcp.tool()
def match_book(title: str) -> str:
    """Match a single string to the best book in the Open Library catalog.

    Returns detailed match information including confidence score and
    classification (book, likely_book, or no match).

    Args:
        title: The string to match (e.g. "Dune by Frank Herbert").

    Returns:
        Match result with title, authors, confidence, and classification.
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
    return " | ".join(parts)


if __name__ == "__main__":
    mcp.run(transport="stdio")
