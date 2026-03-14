"""Local book search using SQLite FTS5 index over Open Library data.

Provides fast, offline book matching against a local copy of the
Open Library catalog. The database is built from bulk data dumps
using scripts/build_openlibrary_db.py.
"""

import logging
import sqlite3
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .models import BookMatch
from .product_filter import compute_product_score, is_likely_product

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "openlibrary" / "openlibrary.db"
)

# Scoring thresholds
HIGH_CONFIDENCE = 0.85
MODERATE_CONFIDENCE = 0.70

# Words to strip from FTS queries (not useful for title matching)
_NOISE_WORDS = frozenset({
    "by", "the", "a", "an", "of", "and", "in", "to", "for", "on",
    "with", "at", "from", "or", "is", "it", "as", "be", "was",
})


def _extract_input_author(input_lower: str) -> str | None:
    """Try to extract an author name from input like 'Title by Author'.

    Uses a simple heuristic: the last occurrence of ' by ' followed by
    text that looks like a person name (2+ words, mostly alphabetic).
    Returns None if no plausible author is found.

    Args:
        input_lower: Lowercased input string.

    Returns:
        Extracted author string, or None.
    """
    idx = input_lower.rfind(" by ")
    if idx < 0:
        return None
    candidate = input_lower[idx + 4:].strip()
    if not candidate:
        return None
    # Basic sanity check: author should have at least 2 words
    # and be mostly alphabetic (not "USB-C Hub 7-in-1")
    words = candidate.split()
    if len(words) < 2:
        return None
    alpha_chars = sum(1 for c in candidate if c.isalpha())
    if alpha_chars / max(len(candidate), 1) < 0.7:
        return None
    return candidate


def _tokenize_for_fts(text: str) -> list[str]:
    """Extract useful tokens from text for FTS5 queries.

    Removes punctuation, noise words, and short tokens.

    Args:
        text: Raw search string.

    Returns:
        List of clean tokens suitable for FTS5.
    """
    cleaned = ""
    for ch in text:
        if ch.isalnum() or ch == " ":
            cleaned += ch
        else:
            cleaned += " "

    tokens = cleaned.split()
    useful = [t for t in tokens if t.lower() not in _NOISE_WORDS and len(t) > 1]
    if not useful:
        useful = tokens
    return useful


def _build_fts_queries(text: str, max_tokens: int = 8) -> list[str]:
    """Build FTS5 query strings with cascading specificity.

    Returns queries from most specific to broadest:
    1. AND on title tokens only (if "by Author" detected)
    2. AND on all tokens (capped at max_tokens)
    3. OR on all tokens (capped at max_tokens)

    Capping tokens avoids broad OR queries against product descriptions
    that would scan too much of the FTS index and take seconds.

    Args:
        text: Raw search string.
        max_tokens: Maximum number of tokens to use in FTS queries.
            Longer inputs are truncated to this count.

    Returns:
        List of FTS5 query strings to try in order.
    """
    tokens = _tokenize_for_fts(text)
    if not tokens:
        return []

    # Cap tokens to limit query breadth
    tokens = tokens[:max_tokens]

    queries = []

    # If input looks like "Title by Author", extract title tokens
    input_lower = text.lower()
    by_idx = input_lower.rfind(" by ")
    if by_idx > 0:
        title_part = text[:by_idx]
        author_part = text[by_idx + 4:]
        title_tokens = _tokenize_for_fts(title_part)[:max_tokens]
        author_tokens = _tokenize_for_fts(author_part)[:max_tokens]

        if title_tokens and author_tokens:
            # Title AND + author AND: most specific
            title_q = " AND ".join(f'"{t}"' for t in title_tokens)
            author_q = " AND ".join(f'"{t}"' for t in author_tokens)
            queries.append(f"({title_q}) AND ({author_q})")

            # Title AND only: handles cases where author name in DB
            # differs slightly from input
            if len(title_tokens) >= 2:
                queries.append(title_q)

    # AND on all tokens
    quoted = [f'"{t}"' for t in tokens]
    if len(quoted) >= 2:
        queries.append(" AND ".join(quoted))

    # OR on all tokens: broadest fallback
    queries.append(" OR ".join(quoted))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)
    return unique


def _title_similarity(a: str, b: str) -> float:
    """Compute normalized similarity between two title strings."""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


class LocalBookSearch:
    """Search for books in a local SQLite database built from Open Library dumps.

    Args:
        db_path: Path to the SQLite database. Defaults to
            data/openlibrary/openlibrary.db relative to project root.

    Raises:
        FileNotFoundError: If the database file does not exist.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Open Library database not found: {self.db_path}\n"
                "Run: uv run python scripts/download_openlibrary.py && "
                "uv run python scripts/build_openlibrary_db.py"
            )
        self._conn = sqlite3.connect(
            str(self.db_path), check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search for books matching a free-text query.

        Uses AND-first strategy: tries an AND query first for speed and
        precision, falls back to OR for broader recall if needed.

        Args:
            query: Search string (title, author, or combination).
            limit: Maximum results to return.

        Returns:
            List of work dicts with keys including key, title, authors,
            first_publish_year, cover_id, subjects, description, subtitle,
            subject_people, subject_places, subject_times,
            lc_classifications, dewey_number, first_sentence, and rank.
        """
        fts_queries = _build_fts_queries(query)
        if not fts_queries:
            return []

        for fts_query in fts_queries:
            try:
                rows = self._conn.execute(
                    """
                    SELECT w.key, w.title, w.authors, w.first_publish_year,
                           w.cover_id, w.subjects, w.description, w.subtitle,
                           w.subject_people, w.subject_places, w.subject_times,
                           w.lc_classifications, w.dewey_number, w.first_sentence,
                           rank
                    FROM books_fts
                    JOIN works w ON books_fts.rowid = w.rowid
                    WHERE books_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (fts_query, limit),
                ).fetchall()
            except Exception:
                continue

            if rows:
                return [dict(r) for r in rows]

        return []

    def get_stats(self) -> dict[str, int]:
        """Return basic counts for the local Open Library database."""
        works_count = self._conn.execute(
            "SELECT COUNT(*) FROM works"
        ).fetchone()[0]
        authors_count = self._conn.execute(
            "SELECT COUNT(*) FROM authors"
        ).fetchone()[0]
        editions_count = 0
        try:
            editions_count = self._conn.execute(
                "SELECT COUNT(*) FROM editions"
            ).fetchone()[0]
        except sqlite3.OperationalError:
            pass
        return {
            "works": int(works_count),
            "authors": int(authors_count),
            "editions": int(editions_count),
        }

    def match_title(
        self,
        input_title: str,
        limit: int = 10,
        author_hint: str | None = None,
    ) -> BookMatch | None:
        """Match an input string to a book in the local database.

        Searches using FTS5 with multiple query strategies, then scores
        each result by title similarity and metadata. Handles compound
        titles like "Series: Subtitle by Author" by searching for both
        the full title and subtitle separately.

        Args:
            input_title: Raw input string (e.g., from Amazon order export).
            limit: Number of FTS5 candidates to evaluate per strategy.
            author_hint: Optional author name from an external source (e.g.,
                vision agent). Used to prefer results with matching authors.

        Returns:
            BookMatch with decision "book" or "likely_book", or None
            if no confident match is found.
        """
        # Build search variants for better recall
        search_queries = [input_title]

        # If "by Author" present, also search title-only
        input_lower = input_title.lower()
        by_idx = input_lower.rfind(" by ")
        title_part = input_title
        if by_idx > 0:
            title_part = input_title[:by_idx].strip()
            if title_part:
                search_queries.append(title_part)

        # If title has subtitle (colon or dash separator), search subtitle
        # AND the main title separately
        for sep in [":", " - "]:
            if sep in title_part:
                parts = title_part.split(sep, 1)
                main_title = parts[0].strip()
                subtitle = parts[1].strip()
                if main_title and len(main_title) > 2:
                    search_queries.append(main_title)
                if subtitle and len(subtitle) > 3:
                    search_queries.append(subtitle)

        # If author hint provided, also search with title + author
        if author_hint and author_hint.strip():
            search_queries.append(f"{input_title} {author_hint}")

        # Collect unique candidates from all search variants
        seen_keys: set[str] = set()
        all_candidates: list[dict] = []
        for query in search_queries:
            results = self.search(query, limit=limit)
            for r in results:
                key = r.get("key", "")
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_candidates.append(r)

        if not all_candidates:
            logger.debug("No local results for: %s", input_title)
            return None

        best_match: BookMatch | None = None
        best_score = 0.0

        for result in all_candidates:
            score = self._score_result(
                input_title, result, author_hint=author_hint
            )
            if score > best_score:
                best_score = score
                result_title = result.get("title", "")
                authors_str = result.get("authors") or ""
                authors = [a.strip() for a in authors_str.split(",") if a.strip()]

                best_match = BookMatch(
                    input_title=input_title,
                    matched_title=result_title,
                    confidence=round(score, 4),
                    title_similarity=round(
                        _title_similarity(input_title, result_title), 4
                    ),
                    authors=authors[:3],
                    first_publish_year=result.get("first_publish_year"),
                    edition_count=0,
                    isbn=None,
                    raw_doc=result,
                )

        if best_match is None:
            return None

        if best_match.confidence >= HIGH_CONFIDENCE:
            best_match.decision = "book"
            self._enrich_with_edition(best_match)
            return best_match

        if best_match.confidence >= MODERATE_CONFIDENCE and best_match.authors:
            best_match.decision = "likely_book"
            self._enrich_with_edition(best_match)
            return best_match

        logger.debug(
            "No confident local match for '%s' (best: %.2f '%s')",
            input_title,
            best_match.confidence,
            best_match.matched_title,
        )
        return None

    def match_title_debug(
        self,
        input_title: str,
        limit: int = 10,
        author_hint: str | None = None,
    ) -> dict[str, Any]:
        """Match a title with full debug trace of every processing stage.

        Returns a dict with timing and detail for each stage:
        product_filter, fts_search, scoring, edition_enrichment, and result.

        Args:
            input_title: Raw input string.
            limit: Number of FTS5 candidates per strategy.
            author_hint: Optional author name for disambiguation.

        Returns:
            Dict with keys: input_title, stages, total_elapsed_ms.
        """
        t_start = time.perf_counter()
        stages: dict[str, Any] = {}

        # -- Stage 1: Product filter --
        t0 = time.perf_counter()
        product_score = compute_product_score(input_title)
        is_product = is_likely_product(input_title)
        stages["product_filter"] = {
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
            "score": round(product_score, 4),
            "threshold": 0.40,
            "is_product": is_product,
            "verdict": "SKIPPED (product)" if is_product else "PASSED (not a product)",
        }

        if is_product:
            stages["result"] = {
                "matched": False,
                "decision": None,
                "reason": "Filtered as non-book product",
            }
            return {
                "input_title": input_title,
                "stages": stages,
                "total_elapsed_ms": round(
                    (time.perf_counter() - t_start) * 1000, 2
                ),
            }

        # -- Stage 2: Build search queries --
        search_queries: list[str] = [input_title]
        input_lower = input_title.lower()
        by_idx = input_lower.rfind(" by ")
        title_part = input_title
        if by_idx > 0:
            title_part = input_title[:by_idx].strip()
            if title_part:
                search_queries.append(title_part)
        for sep in [":", " - "]:
            if sep in title_part:
                parts = title_part.split(sep, 1)
                main_title = parts[0].strip()
                subtitle = parts[1].strip()
                if main_title and len(main_title) > 2:
                    search_queries.append(main_title)
                if subtitle and len(subtitle) > 3:
                    search_queries.append(subtitle)
        if author_hint and author_hint.strip():
            search_queries.append(f"{input_title} {author_hint}")

        # -- Stage 3: FTS search --
        t0 = time.perf_counter()
        fts_details: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        all_candidates: list[dict] = []

        for query_text in search_queries:
            fts_queries = _build_fts_queries(query_text)
            for fts_q in fts_queries:
                tq = time.perf_counter()
                try:
                    rows = self._conn.execute(
                        """
                        SELECT w.key, w.title, w.authors, w.first_publish_year,
                               w.cover_id, w.subjects, w.description, w.subtitle,
                               w.subject_people, w.subject_places, w.subject_times,
                               w.lc_classifications, w.dewey_number, w.first_sentence,
                               rank
                        FROM books_fts
                        JOIN works w ON books_fts.rowid = w.rowid
                        WHERE books_fts MATCH ?
                        ORDER BY rank
                        LIMIT ?
                        """,
                        (fts_q, limit),
                    ).fetchall()
                    new_rows = []
                    for r in rows:
                        key = r["key"]
                        if key not in seen_keys:
                            seen_keys.add(key)
                            new_rows.append(dict(r))
                            all_candidates.append(dict(r))
                    fts_details.append({
                        "source_query": query_text,
                        "fts_query": fts_q,
                        "elapsed_ms": round(
                            (time.perf_counter() - tq) * 1000, 2
                        ),
                        "results_returned": len(rows),
                        "new_unique": len(new_rows),
                    })
                except Exception as exc:
                    fts_details.append({
                        "source_query": query_text,
                        "fts_query": fts_q,
                        "elapsed_ms": round(
                            (time.perf_counter() - tq) * 1000, 2
                        ),
                        "error": str(exc),
                        "results_returned": 0,
                        "new_unique": 0,
                    })

        stages["fts_search"] = {
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
            "search_variants": search_queries,
            "queries": fts_details,
            "total_unique_candidates": len(all_candidates),
        }

        if not all_candidates:
            stages["scoring"] = {"elapsed_ms": 0, "candidates": []}
            stages["result"] = {
                "matched": False,
                "decision": None,
                "reason": "No FTS candidates found",
            }
            return {
                "input_title": input_title,
                "stages": stages,
                "total_elapsed_ms": round(
                    (time.perf_counter() - t_start) * 1000, 2
                ),
            }

        # -- Stage 4: Score each candidate --
        t0 = time.perf_counter()
        scored_candidates: list[dict[str, Any]] = []

        for result in all_candidates:
            score = self._score_result(
                input_title, result, author_hint=author_hint
            )
            result_title = (result.get("title") or "").strip()
            result_authors_str = result.get("authors") or ""
            authors_list = [
                a.strip() for a in result_authors_str.split(",") if a.strip()
            ]
            title_sim = round(
                _title_similarity(input_title, result_title), 4
            )

            scored_candidates.append({
                "work_key": result.get("key", ""),
                "title": result_title,
                "authors": authors_list[:3],
                "first_publish_year": result.get("first_publish_year"),
                "score": round(score, 4),
                "title_similarity": title_sim,
                "subjects": (result.get("subjects") or "")[:200],
                "description": (result.get("description") or "")[:300],
                "cover_id": result.get("cover_id"),
            })

        scored_candidates.sort(key=lambda c: c["score"], reverse=True)

        stages["scoring"] = {
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
            "author_hint": author_hint,
            "candidates": scored_candidates,
        }

        # -- Stage 5: Decision + edition enrichment --
        best = scored_candidates[0]
        best_score = best["score"]
        best_result = all_candidates[0]
        for c in all_candidates:
            if c.get("key") == best["work_key"]:
                best_result = c
                break

        authors_str = best_result.get("authors") or ""
        authors = [a.strip() for a in authors_str.split(",") if a.strip()]

        match_obj = BookMatch(
            input_title=input_title,
            matched_title=best["title"],
            confidence=round(best_score, 4),
            title_similarity=best["title_similarity"],
            authors=authors[:3],
            first_publish_year=best_result.get("first_publish_year"),
            edition_count=0,
            isbn=None,
            raw_doc=best_result,
        )

        decision = None
        reason = ""
        if best_score >= HIGH_CONFIDENCE:
            decision = "book"
            reason = f"Score {best_score:.4f} >= HIGH_CONFIDENCE ({HIGH_CONFIDENCE})"
            match_obj.decision = "book"
        elif best_score >= MODERATE_CONFIDENCE and authors:
            decision = "likely_book"
            reason = (
                f"Score {best_score:.4f} >= MODERATE_CONFIDENCE "
                f"({MODERATE_CONFIDENCE}) and has authors"
            )
            match_obj.decision = "likely_book"
        else:
            parts = []
            if best_score < MODERATE_CONFIDENCE:
                parts.append(
                    f"Score {best_score:.4f} < MODERATE_CONFIDENCE "
                    f"({MODERATE_CONFIDENCE})"
                )
            if not authors:
                parts.append("No authors on best candidate")
            reason = "; ".join(parts)

        # Edition enrichment
        t0 = time.perf_counter()
        edition_info: dict[str, Any] = {"edition_count": 0}
        if decision:
            self._enrich_with_edition(match_obj)
            edition_info = {
                "edition_count": match_obj.edition_count,
                "isbn": match_obj.isbn,
                "publisher": match_obj.publisher,
                "number_of_pages": match_obj.number_of_pages,
                "publish_date": match_obj.publish_date,
                "physical_format": match_obj.physical_format,
            }
        stages["edition_enrichment"] = {
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
            **edition_info,
        }

        stages["result"] = {
            "matched": decision is not None,
            "decision": decision,
            "confidence": round(best_score, 4),
            "matched_title": best["title"],
            "authors": authors[:3],
            "first_publish_year": best_result.get("first_publish_year"),
            "reason": reason,
        }

        return {
            "input_title": input_title,
            "stages": stages,
            "total_elapsed_ms": round(
                (time.perf_counter() - t_start) * 1000, 2
            ),
        }

    def _enrich_with_edition(self, match: BookMatch) -> None:
        """Look up edition data for a matched work and populate BookMatch fields.

        Prefers editions with ISBN-13, then ISBN-10. Among those, prefers
        editions with more metadata (page count, publisher).

        Args:
            match: BookMatch to enrich in place.
        """
        work_key = (match.raw_doc or {}).get("key")
        if not work_key:
            return

        try:
            rows = self._conn.execute(
                "SELECT isbn_13, isbn_10, publishers, number_of_pages, "
                "publish_date, physical_format "
                "FROM editions WHERE work_key = ? "
                "LIMIT 50",
                (work_key,),
            ).fetchall()
        except sqlite3.OperationalError:
            # editions table may not exist yet
            return

        if not rows:
            return

        match.edition_count = len(rows)

        # Score each edition by metadata completeness
        best_edition = None
        best_score = -1
        for row in rows:
            score = 0
            if row["isbn_13"]:
                score += 3
            if row["isbn_10"]:
                score += 2
            if row["number_of_pages"]:
                score += 1
            if row["publishers"]:
                score += 1
            if score > best_score:
                best_score = score
                best_edition = row

        if best_edition is None:
            return

        isbn = best_edition["isbn_13"] or best_edition["isbn_10"]
        if isbn:
            # Take just the first ISBN from the semicolon-separated list
            match.isbn = isbn.split(";")[0].strip()

        if best_edition["publishers"]:
            match.publisher = best_edition["publishers"].split(";")[0].strip()

        match.number_of_pages = best_edition["number_of_pages"]
        match.publish_date = best_edition["publish_date"]
        match.physical_format = best_edition["physical_format"]

    def _score_result(
        self,
        input_title: str,
        result: dict,
        author_hint: str | None = None,
    ) -> float:
        """Score a search result against the input string.

        Uses title similarity as the base score, with adjustments for
        author presence in the input and metadata completeness. Applies
        a penalty when the input specifies an author that does not match
        the result's author.

        Args:
            input_title: The raw input string.
            result: A dict from the search results.
            author_hint: Optional external author hint (e.g., from vision agent)
                for stronger disambiguation.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        result_title = (result.get("title") or "").strip()
        result_authors = (result.get("authors") or "").strip()
        input_lower = input_title.lower().strip()

        # Try to extract an author hint from the input ("Title by Author")
        input_author = _extract_input_author(input_lower)
        title_for_comparison = input_lower
        if input_author:
            # Remove " by Author" to get a clean title for comparison
            idx = input_lower.rfind(" by ")
            if idx > 0:
                title_for_comparison = input_lower[:idx].strip()

        # Base score: title similarity (use clean title if we extracted author)
        title_sim = _title_similarity(title_for_comparison, result_title)

        # Also try the raw input in case the author extraction was wrong
        raw_sim = _title_similarity(input_lower, result_title)
        title_sim = max(title_sim, raw_sim)

        # For compound titles like "Series: Subtitle", also compare
        # just the subtitle and the main title against the result
        for sep in [":", " - "]:
            if sep in title_for_comparison:
                parts = title_for_comparison.split(sep, 1)
                main_title = parts[0].strip()
                subtitle = parts[1].strip()
                if main_title and len(main_title) > 2:
                    main_sim = _title_similarity(main_title, result_title)
                    title_sim = max(title_sim, main_sim)
                if subtitle and len(subtitle) > 3:
                    sub_sim = _title_similarity(subtitle, result_title)
                    title_sim = max(title_sim, sub_sim)

        # If result has authors, try matching without each author name
        # for an even fairer comparison
        if result_authors:
            for author_part in result_authors.lower().split(","):
                author_part = author_part.strip()
                if not author_part:
                    continue
                for sep in (" by ", " - "):
                    pattern = f"{sep}{author_part}"
                    if pattern in input_lower:
                        cleaned = input_lower.replace(pattern, "").strip()
                        if cleaned:
                            alt_sim = _title_similarity(cleaned, result_title)
                            title_sim = max(title_sim, alt_sim)

        score = title_sim

        # Author match/mismatch: if the input specifies an author,
        # reward matches and penalize mismatches
        if input_author and result_authors:
            result_author_lower = result_authors.lower()
            # Check if any significant part of the input author appears
            # in the result authors (handles partial matches like
            # "Tolkien" matching "J.R.R. Tolkien")
            author_parts = [p.strip() for p in input_author.split() if len(p) > 2]
            matching_parts = sum(
                1 for p in author_parts if p in result_author_lower
            )
            if author_parts:
                author_match_ratio = matching_parts / len(author_parts)
                if author_match_ratio > 0.5:
                    score += 0.05  # strong author match bonus
                else:
                    score -= 0.15  # author mismatch penalty

        # External author hint (from vision agent or other source).
        # Stronger than inline "by Author" since it comes from a
        # separate identification step.
        if author_hint and result_authors:
            hint_lower = author_hint.lower().strip()
            result_author_lower = result_authors.lower()
            hint_parts = [p.strip() for p in hint_lower.split() if len(p) > 2]
            matching = sum(1 for p in hint_parts if p in result_author_lower)
            if hint_parts:
                ratio = matching / len(hint_parts)
                if ratio > 0.5:
                    score += 0.10  # strong external author match
                else:
                    score -= 0.20  # external author mismatch
        elif author_hint and not result_authors:
            # Hint was given but this candidate has no authors at all -
            # slight penalty since we cannot verify
            score -= 0.05

        # Metadata completeness bonuses
        if result_authors:
            score += 0.03
        if result.get("first_publish_year"):
            score += 0.02
        if result.get("cover_id"):
            score += 0.01
        if result.get("subjects"):
            score += 0.01

        return max(0.0, min(score, 1.0))

    def match_titles(
        self,
        titles: list[str],
        limit: int = 10,
        skip_products: bool = True,
    ) -> list[BookMatch | None]:
        """Match multiple input strings against the local database.

        When skip_products is True, uses a fast heuristic pre-filter to skip
        items that look like commercial products (electronics, clothing, etc.)
        rather than book titles. This avoids expensive FTS queries for items
        that are very unlikely to be books.

        Args:
            titles: List of raw input strings.
            limit: Number of FTS5 candidates to evaluate per title.
            skip_products: If True, skip items that look like products.

        Returns:
            List of BookMatch results (or None) in the same order as input.
        """
        results: list[BookMatch | None] = []
        skipped = 0
        for title in titles:
            if skip_products and is_likely_product(title):
                results.append(None)
                skipped += 1
            else:
                results.append(self.match_title(title, limit=limit))
        if skipped:
            logger.info("Pre-filter skipped %d/%d items as products", skipped, len(titles))
        return results

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> "LocalBookSearch":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
