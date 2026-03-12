"""Tests for the conversational book assistant."""

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from bookcatalog.agents import preprocessor
from bookcatalog.agents.preprocessor import _parse_response, run_preprocessor


class TestParseResponse:
    """Tests for structured response parsing."""

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
            {
                "input": "Dune",
                "is_book": True,
                "title": "Dune",
                "authors": ["Frank Herbert"],
                "year": 1965,
                "confidence": 0.98,
                "decision": "book",
                "reason": "Novel",
            },
            {
                "input": "USB Cable",
                "is_book": False,
                "title": None,
                "authors": [],
                "year": None,
                "confidence": 0.99,
                "decision": "not_a_book",
                "reason": "Electronics",
            },
        ]
        content = json.dumps(items)
        result = _parse_response(content, ["Dune", "USB Cable"])
        assert len(result) == 2
        assert result[0]["is_book"] is True
        assert result[1]["is_book"] is False


class TestPreprocessorAgent:
    """Tests for run_preprocessor input normalization and response handling."""

    @pytest.mark.asyncio
    async def test_run_preprocessor_with_message_history(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Message history is passed through to the agent invocation."""
        captured: dict[str, Any] = {}

        async def fake_invoke_agent(
            model: Any,
            tools: list[Any],
            messages: list[dict[str, str]],
        ) -> dict[str, Any]:
            captured["messages"] = messages
            return {
                "raw_response": "Frank Herbert also wrote the Dune sequels.",
                "results": [],
            }

        monkeypatch.setattr(preprocessor, "ChatOpenAI", lambda **_: object())
        monkeypatch.setattr(preprocessor, "_invoke_agent", fake_invoke_agent)

        response = await run_preprocessor(
            messages=[
                {"role": "user", "content": "Tell me about Dune."},
                {"role": "assistant", "content": "It is a classic science fiction novel."},
                {"role": "user", "content": "Tell me more about that author."},
            ],
            tools=[],
        )

        assert response["raw_response"] == "Frank Herbert also wrote the Dune sequels."
        assert response["results"] == []
        assert captured["messages"][-1]["content"] == "Tell me more about that author."

    @pytest.mark.asyncio
    async def test_run_preprocessor_with_legacy_items(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Legacy item lists are converted into a single classification message."""
        captured: dict[str, Any] = {}

        async def fake_invoke_agent(
            model: Any,
            tools: list[Any],
            messages: list[dict[str, str]],
        ) -> dict[str, Any]:
            captured["messages"] = messages
            return {
                "raw_response": "I found one likely book.",
                "results": [
                    {
                        "input": "Dune by Frank Herbert",
                        "is_book": True,
                        "title": "Dune",
                        "authors": ["Frank Herbert"],
                        "year": 1965,
                        "confidence": 0.95,
                        "decision": "book",
                        "reason": "Matched in local catalog.",
                    },
                ],
            }

        monkeypatch.setattr(preprocessor, "ChatOpenAI", lambda **_: object())
        monkeypatch.setattr(preprocessor, "_invoke_agent", fake_invoke_agent)

        response = await run_preprocessor(
            items=["Dune by Frank Herbert", "USB-C Hub Adapter"],
            tools=[],
        )

        assert response["results"][0]["title"] == "Dune"
        assert "Please classify the following items" in captured["messages"][0]["content"]
        assert "USB-C Hub Adapter" in captured["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_run_preprocessor_uses_native_tools_by_default(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Native agent tools are loaded when no explicit tools are passed."""
        captured: dict[str, Any] = {}

        async def fake_invoke_agent(
            model: Any,
            tools: list[Any],
            messages: list[dict[str, str]],
        ) -> dict[str, Any]:
            captured["tools"] = tools
            captured["messages"] = messages
            return {
                "raw_response": "Found a likely match.",
                "results": [],
            }

        fake_tools = [object(), object(), object()]
        monkeypatch.setattr(preprocessor, "ChatOpenAI", lambda **_: object())
        monkeypatch.setattr(preprocessor, "_invoke_agent", fake_invoke_agent)
        monkeypatch.setattr(preprocessor, "get_agent_tools", lambda: fake_tools)

        response = await run_preprocessor(messages=[{"role": "user", "content": "Dune"}])

        assert response["raw_response"] == "Found a likely match."
        assert captured["tools"] == fake_tools
        assert captured["messages"] == [{"role": "user", "content": "Dune"}]

    @pytest.mark.asyncio
    async def test_invoke_agent_extracts_prose_and_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Structured JSON is parsed while prose is preserved for chat display."""

        class FakeMessage:
            def __init__(self, content: str) -> None:
                self.content = content

        fake_agent = AsyncMock()
        fake_agent.ainvoke.return_value = {
            "messages": [
                FakeMessage(
                    "I found one book and one non-book.\n\n```json\n"
                    '[{"input":"Dune","is_book":true,"title":"Dune","authors":["Frank Herbert"],'
                    '"year":1965,"confidence":0.98,"decision":"book","reason":"Matched"},'
                    '{"input":"USB-C Cable","is_book":false,"title":null,"authors":[],'
                    '"year":null,"confidence":0.99,"decision":"not_a_book","reason":"Accessory"}]'
                    "\n```"
                ),
            ],
        }

        monkeypatch.setattr(preprocessor, "create_agent", lambda *args, **kwargs: fake_agent)

        response = await preprocessor._invoke_agent(
            model=object(),
            tools=[],
            messages=[{"role": "user", "content": "Dune\nUSB-C Cable"}],
        )

        assert response["raw_response"] == "I found one book and one non-book."
        assert len(response["results"]) == 2
        assert response["results"][0]["title"] == "Dune"
        assert response["results"][1]["decision"] == "not_a_book"
