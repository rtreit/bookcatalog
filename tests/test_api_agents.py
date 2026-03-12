"""Tests for the agents API endpoints."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from bookcatalog.api.main import app

client = TestClient(app)


class TestHealthEndpoint:
    """Verify the health check still works after adding agents router."""

    def test_health_ok(self) -> None:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestChatEndpoint:
    """Tests for POST /api/agents/chat."""

    @patch("bookcatalog.agents.preprocessor.run_preprocessor", new_callable=AsyncMock)
    def test_chat_with_items(self, mock_preprocessor: AsyncMock) -> None:
        """Chat endpoint classifies a list of items."""
        mock_preprocessor.return_value = {
            "raw_response": "I found one book and one non-book.",
            "results": [
                {
                    "input": "Dune by Frank Herbert",
                    "is_book": True,
                    "title": "Dune",
                    "authors": ["Frank Herbert"],
                    "year": 1965,
                    "confidence": 0.98,
                    "decision": "book",
                    "reason": "Science fiction novel by Frank Herbert",
                },
                {
                    "input": "USB-C Cable",
                    "is_book": False,
                    "title": None,
                    "authors": [],
                    "year": None,
                    "confidence": 0.99,
                    "decision": "not_a_book",
                    "reason": "Electronics accessory",
                },
            ],
        }

        response = client.post("/api/agents/chat", json={
            "message": "Classify these",
            "items": ["Dune by Frank Herbert", "USB-C Cable"],
        })

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2
        assert data["message"] == "I found one book and one non-book."
        assert data["raw_response"] == "I found one book and one non-book."
        assert data["results"][0]["decision"] == "book"
        assert data["results"][0]["title"] == "Dune"
        assert data["results"][1]["decision"] == "not_a_book"
        assert data["error"] is None
        mock_preprocessor.assert_awaited_once_with(
            items=["Dune by Frank Herbert", "USB-C Cable"]
        )

    @patch("bookcatalog.agents.preprocessor.run_preprocessor", new_callable=AsyncMock)
    def test_chat_single_message(self, mock_preprocessor: AsyncMock) -> None:
        """Chat with a single message (no items list)."""
        mock_preprocessor.return_value = {
            "raw_response": "Yes. The Great Gatsby is a novel by F. Scott Fitzgerald.",
            "results": [],
        }

        response = client.post("/api/agents/chat", json={
            "message": "Is The Great Gatsby a book?",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Yes. The Great Gatsby is a novel by F. Scott Fitzgerald."
        assert data["results"] == []
        mock_preprocessor.assert_awaited_once_with(messages=[
            {"role": "user", "content": "Is The Great Gatsby a book?"},
        ])

    @patch("bookcatalog.agents.preprocessor.run_preprocessor", new_callable=AsyncMock)
    def test_chat_with_message_history(self, mock_preprocessor: AsyncMock) -> None:
        """Chat endpoint forwards multi-turn message history."""
        mock_preprocessor.return_value = {
            "raw_response": "Frank Herbert also wrote Dune Messiah and Children of Dune.",
            "results": [],
        }

        response = client.post("/api/agents/chat", json={
            "messages": [
                {"role": "user", "content": "Tell me about Dune."},
                {"role": "assistant", "content": "Dune is a science fiction novel by Frank Herbert."},
                {"role": "user", "content": "Tell me more about that author."},
            ],
        })

        assert response.status_code == 200
        data = response.json()
        assert data["message"].startswith("Frank Herbert also wrote")
        mock_preprocessor.assert_awaited_once_with(messages=[
            {"role": "user", "content": "Tell me about Dune."},
            {"role": "assistant", "content": "Dune is a science fiction novel by Frank Herbert."},
            {"role": "user", "content": "Tell me more about that author."},
        ])

    @patch("bookcatalog.agents.preprocessor.run_preprocessor", new_callable=AsyncMock)
    def test_chat_agent_error(self, mock_preprocessor: AsyncMock) -> None:
        """Chat endpoint handles agent errors gracefully."""
        mock_preprocessor.side_effect = RuntimeError("API key expired")

        response = client.post("/api/agents/chat", json={
            "message": "test",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is not None
        assert "API key expired" in data["error"]
        assert data["message"] == ""
        assert data["raw_response"] == ""

    def test_chat_empty_message_rejected(self) -> None:
        """Empty messages are rejected by validation."""
        response = client.post("/api/agents/chat", json={
            "message": "",
        })
        assert response.status_code == 422

    def test_chat_missing_message_and_history_rejected(self) -> None:
        """A request must include either message or messages."""
        response = client.post("/api/agents/chat", json={})
        assert response.status_code == 422


class TestAnalyzePhotoEndpoint:
    """Tests for POST /api/agents/analyze-photo."""

    @patch("bookcatalog.agents.vision.run_vision_agent", new_callable=AsyncMock)
    def test_analyze_valid_image(self, mock_vision: AsyncMock) -> None:
        """Photo endpoint analyzes a valid image."""
        mock_vision.return_value = [
            {
                "extracted_title": "Dune",
                "extracted_author": "Frank Herbert",
                "matched_title": "Dune",
                "matched_authors": ["Frank Herbert"],
                "year": 1965,
                "confidence": 0.95,
                "match_confidence": 0.98,
                "notes": "Spine text visible",
            },
        ]

        response = client.post(
            "/api/agents/analyze-photo",
            files={"file": ("books.jpg", b"\xff\xd8\xff\xe0test", "image/jpeg")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_identified"] == 1
        assert data["total_matched"] == 1
        assert data["books"][0]["matched_title"] == "Dune"

    def test_analyze_unsupported_type(self) -> None:
        """Photo endpoint rejects unsupported file types."""
        response = client.post(
            "/api/agents/analyze-photo",
            files={"file": ("doc.pdf", b"fake pdf content", "application/pdf")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is not None
        assert "Unsupported image type" in data["error"]

    @patch("bookcatalog.agents.vision.run_vision_agent", new_callable=AsyncMock)
    def test_analyze_agent_error(self, mock_vision: AsyncMock) -> None:
        """Photo endpoint handles vision agent errors."""
        mock_vision.side_effect = RuntimeError("Vision model unavailable")

        response = client.post(
            "/api/agents/analyze-photo",
            files={"file": ("test.jpg", b"\xff\xd8\xff\xe0test", "image/jpeg")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is not None
        assert "Vision model unavailable" in data["error"]

    @patch("bookcatalog.agents.vision.run_vision_agent", new_callable=AsyncMock)
    def test_analyze_no_matches(self, mock_vision: AsyncMock) -> None:
        """Photo endpoint handles images with no recognized books."""
        mock_vision.return_value = [
            {
                "extracted_title": "Unclear text",
                "extracted_author": None,
                "matched_title": None,
                "matched_authors": [],
                "year": None,
                "confidence": 0.2,
                "match_confidence": None,
                "notes": "Image too blurry to read",
            },
        ]

        response = client.post(
            "/api/agents/analyze-photo",
            files={"file": ("blurry.png", b"\x89PNG\r\n\x1a\ntest", "image/png")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_identified"] == 1
        assert data["total_matched"] == 0


class TestSampleMCPServer:
    """Tests for the sample MCP server tools."""

    def test_word_count(self) -> None:
        from bookcatalog.mcp.sample_server import word_count
        assert word_count("hello world foo") == "3 words"

    def test_reverse_text(self) -> None:
        from bookcatalog.mcp.sample_server import reverse_text
        assert reverse_text("hello") == "olleh"

    def test_get_current_time(self) -> None:
        from bookcatalog.mcp.sample_server import get_current_time
        result = get_current_time()
        # Should be an ISO timestamp
        assert "T" in result
        assert len(result) > 10
