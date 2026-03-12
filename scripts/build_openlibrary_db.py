"""Build SQLite database with FTS5 index from Open Library data dumps.

Reads the gzipped TSV dump files (authors + works), extracts relevant
fields from each JSON record, and builds a searchable SQLite database
with full-text search via FTS5.

Usage:
    uv run python scripts/build_openlibrary_db.py           # build (skip if exists)
    uv run python scripts/build_openlibrary_db.py --force    # rebuild from scratch
"""

import gzip
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "openlibrary"
DB_PATH = DATA_DIR / "openlibrary.db"

BATCH_SIZE = 10_000
PROGRESS_INTERVAL = 100_000


def create_schema(conn: sqlite3.Connection) -> None:
    """Create tables and FTS5 virtual table."""
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
            subjects TEXT
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
    batch: list[tuple[str, str, str | None, int | None, int | None, str | None]] = []

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

            subjects = data.get("subjects", [])
            # Store first 10 subjects as semicolon-separated string
            if subjects and isinstance(subjects, list):
                subjects_str = "; ".join(str(s) for s in subjects[:10])
            else:
                subjects_str = None

            batch.append(
                (key, title, authors_str, first_publish_year, cover_id, subjects_str)
            )
            count += 1

            if len(batch) >= BATCH_SIZE:
                conn.executemany(
                    "INSERT OR IGNORE INTO works "
                    "(key, title, authors, first_publish_year, cover_id, subjects) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
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
            "(key, title, authors, first_publish_year, cover_id, subjects) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            batch,
        )
    conn.commit()

    elapsed = time.monotonic() - start
    print(
        f"  Loaded {count:,} works in {elapsed:.1f}s "
        f"({count / elapsed:,.0f}/sec), {skipped:,} skipped"
    )
    return count


def build_fts_index(conn: sqlite3.Connection) -> None:
    """Create and populate the FTS5 full-text search index."""
    print("\nBuilding FTS5 search index...")
    start = time.monotonic()

    # Drop and recreate to ensure clean state
    conn.execute("DROP TABLE IF EXISTS books_fts")
    conn.execute("""
        CREATE VIRTUAL TABLE books_fts USING fts5(
            title,
            authors,
            content='works',
            content_rowid='rowid',
            tokenize='porter unicode61'
        )
    """)

    conn.execute("""
        INSERT INTO books_fts(rowid, title, authors)
        SELECT rowid, title, COALESCE(authors, '') FROM works
    """)
    conn.commit()

    elapsed = time.monotonic() - start
    print(f"  FTS5 index built in {elapsed:.1f}s")


def create_indexes(conn: sqlite3.Connection) -> None:
    """Create secondary indexes for common lookups."""
    print("\nCreating secondary indexes...")
    start = time.monotonic()
    conn.execute("CREATE INDEX IF NOT EXISTS idx_works_title ON works(title)")
    conn.commit()
    elapsed = time.monotonic() - start
    print(f"  Indexes created in {elapsed:.1f}s")


def main() -> None:
    authors_path = DATA_DIR / "ol_dump_authors_latest.txt.gz"
    works_path = DATA_DIR / "ol_dump_works_latest.txt.gz"

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
    build_fts_index(conn)
    create_indexes(conn)

    # Summary
    author_count = conn.execute("SELECT COUNT(*) FROM authors").fetchone()[0]
    work_count = conn.execute("SELECT COUNT(*) FROM works").fetchone()[0]
    db_size = DB_PATH.stat().st_size / 1e9
    overall_elapsed = time.monotonic() - overall_start

    print(f"\n{'=' * 40}")
    print(f"  Database built in {overall_elapsed / 60:.1f} min")
    print(f"  Authors: {author_count:,}")
    print(f"  Works:   {work_count:,}")
    print(f"  DB size: {db_size:.2f} GB")
    print(f"  Path:    {DB_PATH}")
    print(f"{'=' * 40}")

    conn.close()


if __name__ == "__main__":
    main()
