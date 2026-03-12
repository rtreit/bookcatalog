"""Tests for the MCP book search server tools."""

import pytest

from bookcatalog.mcp.book_search import match_book, search_books

# Reset the module-level singleton before tests
import bookcatalog.mcp.book_search as bsm


@pytest.fixture(autouse=True)
def _reset_search():
    """Reset the module-level search singleton between tests."""
    bsm._search = None
    yield
    bsm._search = None


class FakeLocalSearch:
    """Minimal stub for LocalBookSearch."""

    def __init__(self) -> None:
        self._data = [
            {
                "title": "Dune",
                "authors": "Frank Herbert",
                "first_publish_year": 1965,
                "description": "A science fiction epic on Arrakis.",
                "subtitle": "Illustrated Edition",
                "first_sentence": "A beginning is the time for taking the most delicate care...",
            },
            {
                "title": "Foundation",
                "authors": "Isaac Asimov",
                "first_publish_year": 1951,
            },
        ]

    def search(self, query: str, limit: int = 5) -> list[dict]:
        return [r for r in self._data if query.lower() in r["title"].lower()][:limit]

    def match_title(self, title: str):
        from bookcatalog.research.models import BookMatch

        for r in self._data:
            if r["title"].lower() in title.lower():
                return BookMatch(
                    input_title=title,
                    matched_title=r["title"],
                    confidence=0.95,
                    title_similarity=0.90,
                    authors=[r["authors"]],
                    first_publish_year=r["first_publish_year"],
                    edition_count=1,
                    isbn=None,
                    decision="book",
                    raw_doc=r,
                )
        return None


def test_search_books_returns_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """search_books returns formatted results when books are found."""
    monkeypatch.setattr(bsm, "_search", FakeLocalSearch())

    result = search_books("Dune")
    assert "Dune" in result
    assert "Frank Herbert" in result
    assert "1965" in result
    assert "Description:" in result


def test_search_books_no_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """search_books returns a 'no books found' message for unknown queries."""
    monkeypatch.setattr(bsm, "_search", FakeLocalSearch())

    result = search_books("xyznonexistent")
    assert "No books found" in result


def test_match_book_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """match_book returns match details for a known title."""
    monkeypatch.setattr(bsm, "_search", FakeLocalSearch())

    result = match_book("Dune by Frank Herbert")
    assert "Dune" in result
    assert "Frank Herbert" in result
    assert "book" in result.lower()
    assert "Description:" in result


def test_match_book_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """match_book returns 'no match' for an unknown title."""
    monkeypatch.setattr(bsm, "_search", FakeLocalSearch())

    result = match_book("Logitech MX Master 3S Mouse")
    assert "No match found" in result
