"""Tests for native LangChain book search tools."""

from __future__ import annotations

import pytest

import bookcatalog.agents.tools as tools_module


@pytest.fixture(autouse=True)
def _reset_search() -> None:
    """Reset the module-level search singleton between tests."""
    tools_module._search = None


class FakeLocalSearch:
    """Minimal stub for ``LocalBookSearch``."""

    def __init__(self) -> None:
        self._data = [
            {
                "title": "Dune",
                "authors": "Frank Herbert",
                "first_publish_year": 1965,
                "description": "A science fiction novel set on Arrakis.",
                "subtitle": "Deluxe Edition",
                "subject_people": "Paul Atreides",
                "subject_places": "Arrakis",
                "subject_times": "Far future",
                "lc_classifications": "PS3558.E63",
                "dewey_number": "813.54",
                "first_sentence": "In the week before their departure to Arrakis...",
                "subjects": "Science fiction; Politics",
            }
        ]

    def search(self, query: str, limit: int = 5) -> list[dict[str, object]]:
        return [row for row in self._data if query.lower() in row["title"].lower()][:limit]

    def match_title(self, title: str):  # noqa: ANN001
        from bookcatalog.research.models import BookMatch

        row = self._data[0]
        if "dune" not in title.lower():
            return None
        return BookMatch(
            input_title=title,
            matched_title=str(row["title"]),
            confidence=0.96,
            title_similarity=0.92,
            authors=[str(row["authors"])],
            first_publish_year=int(row["first_publish_year"]),
            edition_count=12,
            isbn="9780441172719",
            publisher="Chilton Books",
            number_of_pages=412,
            physical_format="Hardcover",
            decision="book",
            raw_doc=row,
        )

    def get_stats(self) -> dict[str, int]:
        return {"works": 123, "authors": 45, "editions": 0}


def test_search_books_tool_returns_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """The native search tool includes enriched metadata in the output."""
    monkeypatch.setattr(tools_module, "_search", FakeLocalSearch())

    result = tools_module.search_books.invoke({"query": "Dune", "max_results": 1})

    assert "Dune" in result
    assert "Description:" in result
    assert "Subtitle:" in result
    assert "Places:" in result
    assert "Dewey:" in result


def test_match_book_tool_returns_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """The native match tool includes enriched metadata in the output."""
    monkeypatch.setattr(tools_module, "_search", FakeLocalSearch())

    result = tools_module.match_book.invoke({"title": "Dune by Frank Herbert"})

    assert "Matched: Dune" in result
    assert "Description:" in result
    assert "First sentence:" in result
    assert "ISBN: 9780441172719" in result
    assert "Publisher: Chilton Books" in result
    assert "Pages: 412" in result
    assert "Format: Hardcover" in result
    assert "Editions: 12" in result


def test_get_database_stats_tool_returns_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """The native stats tool returns a readable database summary."""
    monkeypatch.setattr(tools_module, "_search", FakeLocalSearch())

    result = tools_module.get_database_stats.invoke({})

    assert "123 works indexed" in result
    assert "45 authors indexed" in result
