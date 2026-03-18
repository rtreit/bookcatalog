"""Tests for reusable book entry API endpoints."""

from fastapi.testclient import TestClient

from bookcatalog.api.main import app
from bookcatalog.research.models import BookMatch

client = TestClient(app)


class FakeLocalSearch:
    """Minimal fake local search service for API tests."""

    def __init__(self) -> None:
        self.entry_requests: list[dict[str, object]] = []

    def match_titles(self, titles: list[str]) -> list[BookMatch | None]:
        return [
            BookMatch(
                input_title=titles[0],
                matched_title="Dune",
                confidence=0.97,
                title_similarity=0.97,
                authors=["Frank Herbert"],
                first_publish_year=1965,
                edition_count=3,
                isbn="9780441172719",
                decision="book",
                raw_doc={"key": "/works/OL123W"},
            )
        ]

    def resolve_book_entry(
        self,
        work_key: str | None = None,
        title: str | None = None,
        authors: list[str] | None = None,
        edition_limit: int = 12,
    ) -> dict[str, object] | None:
        self.entry_requests.append({
            "work_key": work_key,
            "title": title,
            "authors": authors or [],
            "edition_limit": edition_limit,
        })
        return {
            "found": True,
            "work_key": work_key or "/works/OL123W",
            "title": title or "Dune",
            "subtitle": None,
            "authors": authors or ["Frank Herbert"],
            "first_publish_year": 1965,
            "cover_id": 123,
            "cover_image_url": "https://covers.openlibrary.org/b/id/123-L.jpg",
            "description": "Science fiction classic.",
            "first_sentence": "A beginning is the time...",
            "subjects": ["Science fiction"],
            "subject_places": [],
            "subject_people": [],
            "subject_times": [],
            "lc_classifications": ["PS3558.E63"],
            "dewey_numbers": ["813.54"],
            "links": [{"title": "Open Library", "url": "https://openlibrary.org/works/OL123W"}],
            "excerpts": ["Fear is the mind-killer."],
            "openlibrary_url": "https://openlibrary.org/works/OL123W",
            "edition_count": 3,
            "best_edition": {
                "key": "/books/OL1M",
                "title": "Dune",
                "isbn_10": ["0441172717"],
                "isbn_13": ["9780441172719"],
                "sample_isbn": "9780441172719",
                "publishers": ["Ace"],
                "publish_date": "1987",
                "number_of_pages": 412,
                "physical_format": "Paperback",
                "languages": ["eng"],
                "cover_id": 123,
                "cover_image_url": "https://covers.openlibrary.org/b/id/123-L.jpg",
            },
            "editions": [],
        }

    def match_title(
        self,
        input_title: str,
        limit: int = 10,
        author_hint: str | None = None,
    ) -> BookMatch | None:
        return BookMatch(
            input_title=input_title,
            matched_title="Dune",
            confidence=0.96,
            title_similarity=0.96,
            authors=["Frank Herbert"],
            first_publish_year=1965,
            edition_count=3,
            isbn="9780441172719",
            decision="book",
            raw_doc={"key": "/works/OL123W"},
        )

    def match_title_debug(
        self,
        input_title: str,
        limit: int = 10,
        author_hint: str | None = None,
    ) -> dict[str, object]:
        return {
            "input_title": input_title,
            "total_elapsed_ms": 12.3,
            "stages": {
                "product_filter": {
                    "elapsed_ms": 1.1,
                    "score": 0.0,
                    "threshold": 0.4,
                    "is_product": False,
                    "verdict": "PASSED (not a product)",
                },
                "result": {
                    "matched": True,
                    "work_key": "/works/OL123W",
                    "decision": "book",
                    "confidence": 0.96,
                    "matched_title": "Dune",
                    "authors": ["Frank Herbert"],
                    "first_publish_year": 1965,
                    "reason": "",
                },
            },
        }


class TestBookApi:
    """Tests for /api/books endpoints used by the entry viewer."""

    def test_match_includes_work_key(self, monkeypatch) -> None:
        """Match results expose the work key for downstream entry lookups."""
        fake_search = FakeLocalSearch()
        monkeypatch.setattr("bookcatalog.api.routers.books._local_search", fake_search)

        response = client.post("/api/books/match", json={
            "titles": ["Dune"],
            "use_local": True,
        })

        assert response.status_code == 200
        data = response.json()
        assert data["results"][0]["work_key"] == "/works/OL123W"

    def test_entry_lookup_by_work_key(self, monkeypatch) -> None:
        """Entry API resolves directly by work key."""
        fake_search = FakeLocalSearch()
        monkeypatch.setattr("bookcatalog.api.routers.books._local_search", fake_search)

        response = client.post("/api/books/entry", json={
            "work_key": "/works/OL123W",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["found"] is True
        assert data["work_key"] == "/works/OL123W"
        assert fake_search.entry_requests[0]["work_key"] == "/works/OL123W"

    def test_entry_lookup_by_title_and_author(self, monkeypatch) -> None:
        """Entry API can resolve an entry when only title/author is known."""
        fake_search = FakeLocalSearch()
        monkeypatch.setattr("bookcatalog.api.routers.books._local_search", fake_search)

        response = client.post("/api/books/entry", json={
            "title": "Dune",
            "authors": ["Frank Herbert"],
        })

        assert response.status_code == 200
        data = response.json()
        assert data["found"] is True
        assert data["title"] == "Dune"
        assert fake_search.entry_requests[0]["title"] == "Dune"
        assert fake_search.entry_requests[0]["authors"] == ["Frank Herbert"]

    def test_match_tool_includes_work_key(self, monkeypatch) -> None:
        """Tool match results expose work keys for the shared entry viewer."""
        fake_search = FakeLocalSearch()
        monkeypatch.setattr("bookcatalog.api.routers.books._local_search", fake_search)

        response = client.post("/api/books/tools/match", json={
            "title": "Dune",
            "author": "Frank Herbert",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["matched"] is True
        assert data["work_key"] == "/works/OL123W"

    def test_debug_match_includes_work_key(self, monkeypatch) -> None:
        """Debug match responses surface work keys for clickable matched titles."""
        fake_search = FakeLocalSearch()
        monkeypatch.setattr("bookcatalog.api.routers.books._local_search", fake_search)

        response = client.post("/api/books/debug-match", json={
            "titles": ["Dune"],
        })

        assert response.status_code == 200
        data = response.json()
        assert data["results"][0]["stages"]["result"]["work_key"] == "/works/OL123W"
