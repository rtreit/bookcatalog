"""Tests for the preprocessor agent."""

import json

import pytest

from bookcatalog.agents.preprocessor import _parse_response, run_preprocessor


class TestParseResponse:
    """Tests for _parse_response JSON parsing."""

    def test_valid_json_array(self) -> None:
        """Parses a valid JSON array correctly."""
        content = json.dumps([
            {
                "input": "Dune by Frank Herbert",
                "is_book": True,
                "title": "Dune",
                "authors": ["Frank Herbert"],
                "year": 1965,
                "confidence": 0.98,
                "decision": "book",
                "reason": "Classic science fiction novel",
            },
        ])
        result = _parse_response(content, ["Dune by Frank Herbert"])
        assert len(result) == 1
        assert result[0]["is_book"] is True
        assert result[0]["title"] == "Dune"
        assert result[0]["decision"] == "book"

    def test_json_with_code_fences(self) -> None:
        """Strips markdown code fences before parsing."""
        inner = json.dumps([{"input": "test", "is_book": False}])
        content = f"```json\n{inner}\n```"
        result = _parse_response(content, ["test"])
        assert len(result) == 1
        assert result[0]["is_book"] is False

    def test_invalid_json_returns_fallback(self) -> None:
        """Returns error entries for unparseable responses."""
        result = _parse_response("not valid json at all", ["item1", "item2"])
        assert len(result) == 2
        assert all(r["decision"] == "error" for r in result)

    def test_multiple_items(self) -> None:
        """Parses multiple items correctly."""
        items = [
            {"input": "Dune", "is_book": True, "title": "Dune",
             "authors": ["Frank Herbert"], "year": 1965,
             "confidence": 0.98, "decision": "book", "reason": "Novel"},
            {"input": "USB Cable", "is_book": False, "title": None,
             "authors": [], "year": None,
             "confidence": 0.99, "decision": "not_a_book", "reason": "Electronics"},
        ]
        content = json.dumps(items)
        result = _parse_response(content, ["Dune", "USB Cable"])
        assert len(result) == 2
        assert result[0]["is_book"] is True
        assert result[1]["is_book"] is False


class TestPreprocessorAgent:
    """Integration tests for run_preprocessor with mocked tools."""

    @pytest.mark.asyncio
    async def test_with_mock_tools(self) -> None:
        """Agent produces classification results with mocked tools."""
        from langchain_core.tools import tool

        @tool
        def match_book(title: str) -> str:
            """Match a book title."""
            if "dune" in title.lower():
                return "Matched: Dune | Authors: Frank Herbert | Decision: book | Confidence: 95%"
            return f"No match found for: {title}"

        @tool
        def search_books(query: str, max_results: int = 5) -> str:
            """Search for books."""
            if "dune" in query.lower():
                return "Title: Dune | Authors: Frank Herbert | Year: 1965"
            return f"No books found for: {query}"

        # Use a model name that exists (the test will actually call the API
        # if OPENAI_API_KEY is set, otherwise it will fail gracefully).
        # For CI, we skip this test.
        import os
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set, skipping live agent test")

        items = ["Dune by Frank Herbert", "USB-C Hub Adapter"]
        results = await run_preprocessor(items, tools=[match_book, search_books])
        assert isinstance(results, list)
        assert len(results) >= 1
