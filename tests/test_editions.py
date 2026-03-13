"""Tests for edition data integration in local search."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from bookcatalog.research.local_search import LocalBookSearch
from bookcatalog.research.models import BookMatch


@pytest.fixture()
def db_with_editions(tmp_path: Path) -> Path:
    """Create a small test database with works and editions tables."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))

    conn.executescript("""
        CREATE TABLE authors (
            key TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );

        CREATE TABLE works (
            key TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            authors TEXT,
            first_publish_year INTEGER,
            cover_id INTEGER,
            subjects TEXT,
            description TEXT,
            subtitle TEXT,
            subject_places TEXT,
            subject_people TEXT,
            subject_times TEXT,
            lc_classifications TEXT,
            dewey_number TEXT,
            first_sentence TEXT,
            links TEXT,
            excerpts TEXT
        );

        CREATE TABLE editions (
            key TEXT PRIMARY KEY,
            work_key TEXT,
            title TEXT,
            isbn_10 TEXT,
            isbn_13 TEXT,
            publishers TEXT,
            publish_date TEXT,
            number_of_pages INTEGER,
            physical_format TEXT,
            languages TEXT,
            cover_id INTEGER
        );

        CREATE INDEX idx_editions_work_key ON editions(work_key);

        INSERT INTO authors (key, name) VALUES
            ('/authors/OL1A', 'Stephen Crane');

        INSERT INTO works (key, title, authors, first_publish_year, description)
        VALUES
            ('/works/OL1W', 'The Red Badge of Courage', 'Stephen Crane',
             1895, 'A Civil War novel about a young soldier.');

        INSERT INTO editions (key, work_key, title, isbn_13, isbn_10,
                              publishers, number_of_pages, physical_format,
                              publish_date) VALUES
            ('/books/OL1M', '/works/OL1W', 'The Red Badge of Courage',
             '9780486264653', '0486264653', 'Dover Publications',
             96, 'Paperback', '1990'),
            ('/books/OL2M', '/works/OL1W', 'The Red Badge of Courage',
             '9780393960549', NULL, 'W.W. Norton',
             256, 'Paperback', '2008'),
            ('/books/OL3M', '/works/OL1W', 'The Red Badge of Courage',
             NULL, NULL, NULL, NULL, NULL, '1895');

        CREATE VIRTUAL TABLE books_fts USING fts5(
            title, authors, description,
            content='works', content_rowid='rowid',
            tokenize='porter unicode61'
        );

        INSERT INTO books_fts(rowid, title, authors, description)
        SELECT rowid, title, COALESCE(authors, ''), COALESCE(description, '')
        FROM works;
    """)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def db_without_editions(tmp_path: Path) -> Path:
    """Create a test database without an editions table."""
    db_path = tmp_path / "test_no_editions.db"
    conn = sqlite3.connect(str(db_path))

    conn.executescript("""
        CREATE TABLE authors (
            key TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );

        CREATE TABLE works (
            key TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            authors TEXT,
            first_publish_year INTEGER,
            cover_id INTEGER,
            subjects TEXT,
            description TEXT,
            subtitle TEXT,
            subject_places TEXT,
            subject_people TEXT,
            subject_times TEXT,
            lc_classifications TEXT,
            dewey_number TEXT,
            first_sentence TEXT,
            links TEXT,
            excerpts TEXT
        );

        INSERT INTO authors (key, name) VALUES
            ('/authors/OL1A', 'Stephen Crane');

        INSERT INTO works (key, title, authors, first_publish_year, description)
        VALUES
            ('/works/OL1W', 'The Red Badge of Courage', 'Stephen Crane',
             1895, 'A Civil War novel about a young soldier.');

        CREATE VIRTUAL TABLE books_fts USING fts5(
            title, authors, description,
            content='works', content_rowid='rowid',
            tokenize='porter unicode61'
        );

        INSERT INTO books_fts(rowid, title, authors, description)
        SELECT rowid, title, COALESCE(authors, ''), COALESCE(description, '')
        FROM works;
    """)
    conn.commit()
    conn.close()
    return db_path


class TestEditionEnrichment:
    """Tests for edition data enrichment in match results."""

    def test_match_includes_isbn(self, db_with_editions: Path) -> None:
        """match_title populates ISBN from the best edition."""
        search = LocalBookSearch(db_with_editions)
        match = search.match_title("The Red Badge of Courage")

        assert match is not None
        assert match.isbn is not None
        # Should pick an ISBN-13
        assert match.isbn.startswith("978")

    def test_match_includes_publisher(self, db_with_editions: Path) -> None:
        """match_title populates publisher from the best edition."""
        search = LocalBookSearch(db_with_editions)
        match = search.match_title("The Red Badge of Courage")

        assert match is not None
        assert match.publisher is not None
        assert len(match.publisher) > 0

    def test_match_includes_page_count(self, db_with_editions: Path) -> None:
        """match_title populates page count from the best edition."""
        search = LocalBookSearch(db_with_editions)
        match = search.match_title("The Red Badge of Courage")

        assert match is not None
        assert match.number_of_pages is not None
        assert match.number_of_pages > 0

    def test_match_includes_edition_count(self, db_with_editions: Path) -> None:
        """match_title reports the total number of editions."""
        search = LocalBookSearch(db_with_editions)
        match = search.match_title("The Red Badge of Courage")

        assert match is not None
        assert match.edition_count == 3

    def test_match_includes_physical_format(self, db_with_editions: Path) -> None:
        """match_title populates physical format from the best edition."""
        search = LocalBookSearch(db_with_editions)
        match = search.match_title("The Red Badge of Courage")

        assert match is not None
        assert match.physical_format is not None

    def test_best_edition_prefers_isbn13(self, db_with_editions: Path) -> None:
        """The enrichment picks an edition with ISBN-13 over one without."""
        search = LocalBookSearch(db_with_editions)
        match = search.match_title("The Red Badge of Courage")

        assert match is not None
        # Both editions with ISBN-13 have publishers and pages,
        # so the one with both isbn_13 + isbn_10 scores highest
        assert match.isbn == "9780486264653"

    def test_graceful_without_editions_table(
        self, db_without_editions: Path
    ) -> None:
        """match_title works when editions table does not exist."""
        search = LocalBookSearch(db_without_editions)
        match = search.match_title("The Red Badge of Courage")

        assert match is not None
        assert match.matched_title == "The Red Badge of Courage"
        assert match.isbn is None
        assert match.edition_count == 0

    def test_stats_include_editions(self, db_with_editions: Path) -> None:
        """get_stats reports edition count."""
        search = LocalBookSearch(db_with_editions)
        stats = search.get_stats()

        assert stats["editions"] == 3

    def test_stats_without_editions_table(
        self, db_without_editions: Path
    ) -> None:
        """get_stats reports 0 editions when table is missing."""
        search = LocalBookSearch(db_without_editions)
        stats = search.get_stats()

        assert stats["editions"] == 0


class TestBookMatchModel:
    """Tests for the updated BookMatch dataclass."""

    def test_default_edition_fields(self) -> None:
        """New edition fields default to None."""
        match = BookMatch(
            input_title="Test",
            matched_title="Test",
            confidence=0.9,
            title_similarity=0.9,
            authors=["Author"],
            first_publish_year=2000,
            edition_count=0,
            isbn=None,
        )
        assert match.publisher is None
        assert match.number_of_pages is None
        assert match.publish_date is None
        assert match.physical_format is None

    def test_edition_fields_populated(self) -> None:
        """BookMatch accepts edition fields."""
        match = BookMatch(
            input_title="Test",
            matched_title="Test",
            confidence=0.9,
            title_similarity=0.9,
            authors=["Author"],
            first_publish_year=2000,
            edition_count=5,
            isbn="9780486264653",
            publisher="Dover",
            number_of_pages=96,
            publish_date="1990",
            physical_format="Paperback",
        )
        assert match.isbn == "9780486264653"
        assert match.publisher == "Dover"
        assert match.number_of_pages == 96
        assert match.physical_format == "Paperback"
