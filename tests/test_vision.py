"""Tests for the vision agent."""

import json
from typing import Any

import pytest

from bookcatalog.agents.vision import _parse_vision_response, run_vision_agent


class TestParseVisionResponse:
    """Tests for _parse_vision_response JSON parsing."""

    def test_valid_response(self) -> None:
        """Parses a valid JSON array of identified books."""
        content = json.dumps([
            {
                "extracted_title": "Dune",
                "extracted_author": "Frank Herbert",
                "matched_title": "Dune",
                "matched_authors": ["Frank Herbert"],
                "year": 1965,
                "confidence": 0.95,
                "match_confidence": 0.98,
                "notes": "Spine text clearly visible",
            },
        ])
        result = _parse_vision_response(content)
        assert len(result) == 1
        assert result[0]["extracted_title"] == "Dune"
        assert result[0]["matched_title"] == "Dune"
        assert result[0]["confidence"] == 0.95

    def test_with_code_fences(self) -> None:
        """Strips markdown code fences before parsing."""
        inner = json.dumps([
            {"extracted_title": "1984", "confidence": 0.9,
             "matched_title": "1984", "matched_authors": ["George Orwell"],
             "year": 1949, "match_confidence": 0.97, "notes": ""}
        ])
        content = f"```json\n{inner}\n```"
        result = _parse_vision_response(content)
        assert len(result) == 1
        assert result[0]["extracted_title"] == "1984"

    def test_invalid_json(self) -> None:
        """Returns error entry for unparseable responses."""
        result = _parse_vision_response("I can see some books but...")
        assert len(result) == 1
        assert "error" in result[0]

    def test_multiple_books(self) -> None:
        """Parses multiple identified books."""
        books = [
            {"extracted_title": "Dune", "extracted_author": "Frank Herbert",
             "matched_title": "Dune", "matched_authors": ["Frank Herbert"],
             "year": 1965, "confidence": 0.95, "match_confidence": 0.98,
             "notes": ""},
            {"extracted_title": "Foundation", "extracted_author": "Asimov",
             "matched_title": "Foundation", "matched_authors": ["Isaac Asimov"],
             "year": 1951, "confidence": 0.80, "match_confidence": 0.92,
             "notes": "Partially obscured"},
        ]
        result = _parse_vision_response(json.dumps(books))
        assert len(result) == 2

    def test_no_match(self) -> None:
        """Handles books identified but not matched."""
        content = json.dumps([
            {"extracted_title": "Unknown Book", "extracted_author": None,
             "matched_title": None, "matched_authors": [],
             "year": None, "confidence": 0.3, "match_confidence": None,
             "notes": "Title partially obscured, could not read clearly"},
        ])
        result = _parse_vision_response(content)
        assert len(result) == 1
        assert result[0]["matched_title"] is None

    def test_none_content(self) -> None:
        """Handles None content gracefully instead of raising AttributeError."""
        result = _parse_vision_response(None)
        assert len(result) == 1
        assert "error" in result[0]

    def test_empty_content(self) -> None:
        """Handles empty string content gracefully."""
        result = _parse_vision_response("")
        assert len(result) == 1
        assert "error" in result[0]


class TestVisionAgent:
    """Integration tests for run_vision_agent with mocked tools."""

    @pytest.mark.asyncio
    async def test_with_mock_tools(self) -> None:
        """Vision agent processes an image with mocked tools."""
        import os

        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set, skipping live vision test")

        from langchain_core.tools import tool

        @tool
        def match_book(title: str) -> str:
            """Match a book title."""
            return f"Matched: {title} | Authors: Test Author | Decision: book | Confidence: 90%"

        @tool
        def search_books(query: str, max_results: int = 5) -> str:
            """Search for books."""
            return f"Title: {query} | Authors: Test | Year: 2000"

        # Create a tiny 1x1 pixel JPEG for testing
        # This is a valid minimal JPEG (red pixel)
        import base64
        tiny_jpeg = base64.b64decode(
            "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkS"
            "Ew8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJ"
            "CQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
            "MjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEA"
            "AAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIh"
            "MUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6"
            "Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZ"
            "mqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx"
            "8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREA"
            "AgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAV"
            "YnLRChYkNOEl8RcYI4Q/RFhHRUYnJCk4OTtDREVGR0hJSlNUVVZXWFlaY2RlZmdo"
            "aWpzdHV2d3h5eoOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPE"
            "xcbHyMnK0tPU1dbX2Nna4eLj5OXm5+jp6vLz9PX29/j5+v/aAAwDAQACEQMRAD8A"
            "9+ooooA//9k="
        )

        results = await run_vision_agent(
            tiny_jpeg, media_type="image/jpeg", tools=[match_book, search_books]
        )
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_run_vision_agent_uses_native_tools_by_default(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Native agent tools are loaded when no explicit tools are passed."""
        captured: dict[str, Any] = {}

        async def fake_invoke(
            model: Any,
            tools: list[Any],
            image_data: bytes,
            media_type: str,
        ) -> list[dict[str, Any]]:
            captured["tools"] = tools
            captured["image_data"] = image_data
            captured["media_type"] = media_type
            return [{"matched_title": "Dune"}]

        fake_tools = [object()]
        monkeypatch.setattr("bookcatalog.agents.vision.ChatOpenAI", lambda **_: object())
        monkeypatch.setattr("bookcatalog.agents.vision._invoke_vision_agent", fake_invoke)
        monkeypatch.setattr("bookcatalog.agents.vision.get_agent_tools", lambda: fake_tools)

        result = await run_vision_agent(b"image-bytes", media_type="image/png")

        assert result == [{"matched_title": "Dune"}]
        assert captured["tools"] == fake_tools
        assert captured["image_data"] == b"image-bytes"
        assert captured["media_type"] == "image/png"
