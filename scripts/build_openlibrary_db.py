"""Build SQLite database with FTS5 index from Open Library data dumps.

Reads the gzipped TSV dump files (authors + works + editions), extracts
relevant fields from each JSON record, and builds a searchable SQLite
database with full-text search via FTS5.

Usage:
    uv run python scripts/build_openlibrary_db.py               # build (skip if exists)
    uv run python scripts/build_openlibrary_db.py --force        # rebuild from scratch
    uv run python scripts/build_openlibrary_db.py --editions-only  # add editions to existing DB
"""

import gzip
import json
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "openlibrary"
DB_PATH = DATA_DIR / "openlibrary.db"

BATCH_SIZE = 10_000
PROGRESS_INTERVAL = 100_000


def create_schema(conn: sqlite3.Connection) -> None:
    """Create the SQLite schema used for Open Library data.

    Args:
        conn: SQLite connection.
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS authors (
            key TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS works (
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

        CREATE TABLE IF NOT EXISTS editions (
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
    """)


def load_authors(conn: sqlite3.Connection, gz_path: Path) -> int:
    """Load authors from gzipped TSV dump into the authors table.

    Args:
        conn: SQLite connection.
        gz_path: Path to ol_dump_authors_latest.txt.gz.

    Returns:
        Number of authors loaded.
    """
    print(f"\nLoading authors from {gz_path.name}...")
    start = time.monotonic()
    count = 0
    batch: list[tuple[str, str]] = []

    with gzip.open(gz_path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.split("\t", 4)
            if len(parts) < 5:
                continue
            try:
                data = json.loads(parts[4])
            except (json.JSONDecodeError, IndexError):
                continue

            key = parts[1].strip()
            name = data.get("name", "")
            if isinstance(name, dict):
                # Some records have name as {"type": "/type/text", "value": "..."}
                name = name.get("value", "")
            name = str(name).strip()
            if not name:
                continue

            batch.append((key, name))
            count += 1

            if len(batch) >= BATCH_SIZE:
                conn.executemany(
                    "INSERT OR IGNORE INTO authors (key, name) VALUES (?, ?)",
                    batch,
                )
                batch = []

            if count % PROGRESS_INTERVAL == 0:
                elapsed = time.monotonic() - start
                rate = count / elapsed
                print(f"  {count:>12,} authors ({rate:,.0f}/sec)")

    if batch:
        conn.executemany(
            "INSERT OR IGNORE INTO authors (key, name) VALUES (?, ?)",
            batch,
        )
    conn.commit()

    elapsed = time.monotonic() - start
    print(f"  Loaded {count:,} authors in {elapsed:.1f}s ({count / elapsed:,.0f}/sec)")
    return count


def _resolve_author_names(
    author_entries: list,
    author_lookup: dict[str, str],
) -> str | None:
    """Resolve author key references to comma-separated names."""
    names: list[str] = []
    for entry in author_entries:
        author_ref = entry.get("author", {})
        if isinstance(author_ref, dict):
            author_key = author_ref.get("key", "")
        elif isinstance(author_ref, str):
            author_key = author_ref
        else:
            continue
        name = author_lookup.get(author_key)
        if name:
            names.append(name)
    return ", ".join(names) if names else None


_YEAR_RE = re.compile(r"\b(\d{4})\b")


def _extract_year(date_str: str | None) -> int | None:
    """Extract a 4-digit year from a date string."""
    if not date_str:
        return None
    m = _YEAR_RE.search(str(date_str))
    if m:
        year = int(m.group(1))
        if 1000 <= year <= 2100:
            return year
    return None


def _extract_text_field(value: Any) -> str | None:
    """Extract text from either a plain string or Open Library text object.

    Args:
        value: Raw field value from the works JSON record.

    Returns:
        Clean text value, or None when unavailable.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("value")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _join_list_field(values: Any, limit: int = 10) -> str | None:
    """Join a list field into a semicolon-separated string.

    Args:
        values: Raw field value from the works JSON record.
        limit: Maximum number of items to keep.

    Returns:
        Semicolon-separated string, or None when unavailable.
    """
    if not isinstance(values, list) or not values:
        return None
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    if not cleaned:
        return None
    return "; ".join(cleaned[:limit])


def _serialize_json_field(value: Any) -> str | None:
    """Serialize a complex JSON field for SQLite storage.

    Args:
        value: Raw JSON-serializable value.

    Returns:
        Compact JSON string, or None when value is empty.
    """
    if value in (None, "", [], {}):
        return None
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def load_works(conn: sqlite3.Connection, gz_path: Path) -> int:
    """Load works from gzipped TSV dump, resolving author references.

    Args:
        conn: SQLite connection (must have authors table populated).
        gz_path: Path to ol_dump_works_latest.txt.gz.

    Returns:
        Number of works loaded.
    """
    print(f"\nLoading works from {gz_path.name}...")

    # Build author key -> name lookup from already-loaded authors
    print("  Building author lookup from database...")
    author_lookup: dict[str, str] = dict(
        conn.execute("SELECT key, name FROM authors").fetchall()
    )
    print(f"  {len(author_lookup):,} authors in lookup")

    start = time.monotonic()
    count = 0
    skipped = 0
    batch: list[
        tuple[
            str,
            str,
            str | None,
            int | None,
            int | None,
            str | None,
            str | None,
            str | None,
            str | None,
            str | None,
            str | None,
            str | None,
            str | None,
            str | None,
            str | None,
            str | None,
        ]
    ] = []

    with gzip.open(gz_path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.split("\t", 4)
            if len(parts) < 5:
                continue
            try:
                data = json.loads(parts[4])
            except (json.JSONDecodeError, IndexError):
                continue

            key = parts[1].strip()
            title = data.get("title", "")
            if isinstance(title, dict):
                title = title.get("value", "")
            title = str(title).strip()
            if not title:
                skipped += 1
                continue

            authors_str = _resolve_author_names(
                data.get("authors", []),
                author_lookup,
            )

            first_publish_year = _extract_year(
                data.get("first_publish_date")
            )

            covers = data.get("covers", [])
            cover_id = covers[0] if covers and isinstance(covers[0], int) else None

            subjects_str = _join_list_field(data.get("subjects"))
            description = _extract_text_field(data.get("description"))
            subtitle = _extract_text_field(data.get("subtitle"))
            subject_places = _join_list_field(data.get("subject_places"))
            subject_people = _join_list_field(data.get("subject_people"))
            subject_times = _join_list_field(data.get("subject_times"))
            lc_classifications = _join_list_field(data.get("lc_classifications"))
            dewey_number = _join_list_field(data.get("dewey_number"))
            first_sentence = _extract_text_field(data.get("first_sentence"))
            links = _serialize_json_field(data.get("links"))
            excerpts = _serialize_json_field(data.get("excerpts"))

            batch.append(
                (
                    key,
                    title,
                    authors_str,
                    first_publish_year,
                    cover_id,
                    subjects_str,
                    description,
                    subtitle,
                    subject_places,
                    subject_people,
                    subject_times,
                    lc_classifications,
                    dewey_number,
                    first_sentence,
                    links,
                    excerpts,
                )
            )
            count += 1

            if len(batch) >= BATCH_SIZE:
                conn.executemany(
                    "INSERT OR IGNORE INTO works "
                    "("
                    "key, title, authors, first_publish_year, cover_id, subjects, "
                    "description, subtitle, subject_places, subject_people, "
                    "subject_times, lc_classifications, dewey_number, "
                    "first_sentence, links, excerpts"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    batch,
                )
                batch = []

            if count % PROGRESS_INTERVAL == 0:
                elapsed = time.monotonic() - start
                rate = count / elapsed
                print(
                    f"  {count:>12,} works ({rate:,.0f}/sec, {skipped:,} skipped)"
                )

    if batch:
        conn.executemany(
            "INSERT OR IGNORE INTO works "
            "("
            "key, title, authors, first_publish_year, cover_id, subjects, "
            "description, subtitle, subject_places, subject_people, "
            "subject_times, lc_classifications, dewey_number, "
            "first_sentence, links, excerpts"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
    conn.commit()

    elapsed = time.monotonic() - start
    print(
        f"  Loaded {count:,} works in {elapsed:.1f}s "
        f"({count / elapsed:,.0f}/sec), {skipped:,} skipped"
    )
    return count


def load_editions(conn: sqlite3.Connection, gz_path: Path) -> int:
    """Load editions from gzipped TSV dump into the editions table.

    Extracts ISBN, publisher, page count, and other edition-level metadata,
    linking each edition to its parent work via work_key.

    Args:
        conn: SQLite connection.
        gz_path: Path to ol_dump_editions_latest.txt.gz.

    Returns:
        Number of editions loaded.
    """
    print(f"\nLoading editions from {gz_path.name}...")
    start = time.monotonic()
    count = 0
    skipped = 0
    batch: list[
        tuple[
            str,
            str | None,
            str | None,
            str | None,
            str | None,
            str | None,
            str | None,
            int | None,
            str | None,
            str | None,
            int | None,
        ]
    ] = []

    with gzip.open(gz_path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.split("\t", 4)
            if len(parts) < 5:
                continue
            try:
                data = json.loads(parts[4])
            except (json.JSONDecodeError, IndexError):
                continue

            key = parts[1].strip()

            # Resolve work key from the "works" reference list
            work_refs = data.get("works", [])
            work_key: str | None = None
            if work_refs and isinstance(work_refs, list):
                ref = work_refs[0]
                if isinstance(ref, dict):
                    work_key = ref.get("key")
                elif isinstance(ref, str):
                    work_key = ref

            title = _extract_text_field(data.get("title"))

            isbn_10 = _join_list_field(data.get("isbn_10"), limit=5)
            isbn_13 = _join_list_field(data.get("isbn_13"), limit=5)

            publishers = _join_list_field(data.get("publishers"), limit=3)
            publish_date = _extract_text_field(data.get("publish_date"))

            number_of_pages = data.get("number_of_pages")
            if not isinstance(number_of_pages, int):
                # Some records store page count as a string
                try:
                    number_of_pages = int(number_of_pages) if number_of_pages else None
                except (ValueError, TypeError):
                    number_of_pages = None

            physical_format = _extract_text_field(data.get("physical_format"))

            languages = data.get("languages", [])
            if isinstance(languages, list):
                lang_keys = []
                for lang in languages:
                    if isinstance(lang, dict):
                        lang_key = lang.get("key", "")
                        # Strip /languages/ prefix for readability
                        lang_keys.append(lang_key.replace("/languages/", ""))
                    elif isinstance(lang, str):
                        lang_keys.append(lang)
                languages_str = "; ".join(lang_keys) if lang_keys else None
            else:
                languages_str = None

            covers = data.get("covers", [])
            cover_id = covers[0] if covers and isinstance(covers[0], int) else None

            batch.append((
                key,
                work_key,
                title,
                isbn_10,
                isbn_13,
                publishers,
                publish_date,
                number_of_pages,
                physical_format,
                languages_str,
                cover_id,
            ))
            count += 1

            if len(batch) >= BATCH_SIZE:
                conn.executemany(
                    "INSERT OR IGNORE INTO editions "
                    "(key, work_key, title, isbn_10, isbn_13, publishers, "
                    "publish_date, number_of_pages, physical_format, "
                    "languages, cover_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    batch,
                )
                batch = []

            if count % PROGRESS_INTERVAL == 0:
                elapsed = time.monotonic() - start
                rate = count / elapsed
                print(
                    f"  {count:>12,} editions ({rate:,.0f}/sec, {skipped:,} skipped)"
                )

    if batch:
        conn.executemany(
            "INSERT OR IGNORE INTO editions "
            "(key, work_key, title, isbn_10, isbn_13, publishers, "
            "publish_date, number_of_pages, physical_format, "
            "languages, cover_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
    conn.commit()

    elapsed = time.monotonic() - start
    print(
        f"  Loaded {count:,} editions in {elapsed:.1f}s "
        f"({count / elapsed:,.0f}/sec), {skipped:,} skipped"
    )
    return count


def build_fts_index(conn: sqlite3.Connection) -> None:
    """Create and populate the FTS5 full-text search index.

    Args:
        conn: SQLite connection.
    """
    print("\nBuilding FTS5 search index...")
    start = time.monotonic()

    # Drop and recreate to ensure clean state
    conn.execute("DROP TABLE IF EXISTS books_fts")
    conn.execute("""
        CREATE VIRTUAL TABLE books_fts USING fts5(
            title,
            authors,
            description,
            content='works',
            content_rowid='rowid',
            tokenize='porter unicode61'
        )
    """)

    conn.execute("""
        INSERT INTO books_fts(rowid, title, authors, description)
        SELECT rowid, title, COALESCE(authors, ''), COALESCE(description, '')
        FROM works
    """)
    conn.commit()

    elapsed = time.monotonic() - start
    print(f"  FTS5 index built in {elapsed:.1f}s")


def create_indexes(conn: sqlite3.Connection) -> None:
    """Create secondary indexes for common lookups.

    Args:
        conn: SQLite connection.
    """
    print("\nCreating secondary indexes...")
    start = time.monotonic()
    conn.execute("CREATE INDEX IF NOT EXISTS idx_works_title ON works(title)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_editions_work_key ON editions(work_key)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_editions_isbn_13 ON editions(isbn_13)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_editions_isbn_10 ON editions(isbn_10)"
    )
    conn.commit()
    elapsed = time.monotonic() - start
    print(f"  Indexes created in {elapsed:.1f}s")


def main() -> None:
    """Build the local Open Library SQLite database from dump files."""
    authors_path = DATA_DIR / "ol_dump_authors_latest.txt.gz"
    works_path = DATA_DIR / "ol_dump_works_latest.txt.gz"
    editions_path = DATA_DIR / "ol_dump_editions_latest.txt.gz"

    editions_only = "--editions-only" in sys.argv

    if editions_only:
        if not DB_PATH.exists():
            print("ERROR: No existing database found. Run a full build first.")
            sys.exit(1)
        if not editions_path.exists():
            print(f"ERROR: Missing dump file: {editions_path}")
            print("Run: uv run python scripts/download_openlibrary.py editions")
            sys.exit(1)

        overall_start = time.monotonic()
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-2000000")
        conn.execute("PRAGMA temp_store=MEMORY")

        create_schema(conn)
        # Clear existing editions for a clean reload
        conn.execute("DELETE FROM editions")
        conn.commit()
        load_editions(conn, editions_path)
        create_indexes(conn)

        edition_count = conn.execute("SELECT COUNT(*) FROM editions").fetchone()[0]
        db_size = DB_PATH.stat().st_size / 1e9
        overall_elapsed = time.monotonic() - overall_start

        print(f"\n{'=' * 40}")
        print(f"  Editions added in {overall_elapsed / 60:.1f} min")
        print(f"  Editions: {edition_count:,}")
        print(f"  DB size:  {db_size:.2f} GB")
        print(f"  Path:     {DB_PATH}")
        print(f"{'=' * 40}")

        conn.close()
        return

    for p in [authors_path, works_path]:
        if not p.exists():
            print(f"ERROR: Missing dump file: {p}")
            print("Run: uv run python scripts/download_openlibrary.py")
            sys.exit(1)

    if DB_PATH.exists():
        if "--force" not in sys.argv:
            size_gb = DB_PATH.stat().st_size / 1e9
            print(f"Database already exists: {DB_PATH} ({size_gb:.2f} GB)")
            print("Use --force to rebuild from scratch")
            sys.exit(0)
        print(f"Removing existing database: {DB_PATH}")
        DB_PATH.unlink()

    overall_start = time.monotonic()

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-2000000")  # ~2GB page cache
    conn.execute("PRAGMA temp_store=MEMORY")

    create_schema(conn)
    load_authors(conn, authors_path)
    load_works(conn, works_path)

    if editions_path.exists():
        load_editions(conn, editions_path)

    build_fts_index(conn)
    create_indexes(conn)

    # Summary
    author_count = conn.execute("SELECT COUNT(*) FROM authors").fetchone()[0]
    work_count = conn.execute("SELECT COUNT(*) FROM works").fetchone()[0]
    edition_count = conn.execute("SELECT COUNT(*) FROM editions").fetchone()[0]
    db_size = DB_PATH.stat().st_size / 1e9
    overall_elapsed = time.monotonic() - overall_start

    print(f"\n{'=' * 40}")
    print(f"  Database built in {overall_elapsed / 60:.1f} min")
    print(f"  Authors:  {author_count:,}")
    print(f"  Works:    {work_count:,}")
    print(f"  Editions: {edition_count:,}")
    print(f"  DB size:  {db_size:.2f} GB")
    print(f"  Path:     {DB_PATH}")
    print(f"{'=' * 40}")

    conn.close()


if __name__ == "__main__":
    main()
