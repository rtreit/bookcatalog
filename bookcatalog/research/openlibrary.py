"""Open Library API client for book search and title matching."""

import asyncio
import logging
import re
from difflib import SequenceMatcher

import httpx

from .exceptions import OpenLibraryError
from .models import BookMatch

logger = logging.getLogger(__name__)

SEARCH_URL = "https://openlibrary.org/search.json"

# Defaults
DEFAULT_TIMEOUT = 20
DEFAULT_RESULT_LIMIT = 5
DEFAULT_REQUEST_DELAY = 0.2
DEFAULT_MAX_CONCURRENT = 5
MAX_RETRIES = 3
RETRY_BACKOFF = 1.0

# Confidence thresholds
HIGH_CONFIDENCE = 0.90
MODERATE_CONFIDENCE = 0.80

# Confidence bonuses for metadata completeness
BONUS_ISBN = 0.03
BONUS_AUTHOR = 0.02
BONUS_PUBLISH_YEAR = 0.01
BONUS_MULTIPLE_EDITIONS = 0.02
MIN_EDITIONS_FOR_BONUS = 2


def normalize_title(title: str) -> str:
    """Normalize a book title for fuzzy comparison.

    Strips bracketed/parenthetical noise, normalizes punctuation and whitespace,
    and lowercases the result.

    Args:
        title: Raw title string.

    Returns:
        Cleaned, lowercased title suitable for comparison.
    """
    if not title:
        return ""
    s = title.lower().strip()
    s = re.sub(r"\[[^\]]*\]", " ", s)
    s = re.sub(r"\([^)]*\)", " ", s)
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9:,\-' ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_main_title(title: str) -> str | None:
    """Extract the main title before a subtitle separator (colon or dash).

    Returns None if there is no subtitle or the main part is too short
    (less than 3 words) to be a useful search query on its own.

    Args:
        title: Normalized or raw title string.

    Returns:
        The main title portion, or None if splitting is not useful.
    """
    for sep in [":", " - "]:
        if sep in title:
            main = title.split(sep, 1)[0].strip()
            if len(main.split()) >= 3:
                return main
    return None


def _title_similarity(a: str, b: str) -> float:
    """Compute similarity ratio between two normalized title strings."""
    return SequenceMatcher(None, a, b).ratio()


class OpenLibraryClient:
    """Async client for searching and matching books via the Open Library API.

    Args:
        timeout: HTTP request timeout in seconds.
        max_concurrent: Maximum number of concurrent API requests.
        high_threshold: Confidence at or above this is classified as "book".
        moderate_threshold: Confidence at or above this (with supporting
            metadata) is classified as "likely_book".
    """

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        high_threshold: float = HIGH_CONFIDENCE,
        moderate_threshold: float = MODERATE_CONFIDENCE,
    ) -> None:
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.high_threshold = high_threshold
        self.moderate_threshold = moderate_threshold
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def _search_with_client(
        self,
        http: httpx.AsyncClient,
        title: str,
        limit: int = DEFAULT_RESULT_LIMIT,
    ) -> list[dict]:
        """Search Open Library using a shared HTTP client."""
        last_exc: Exception | None = None
        async with self._semaphore:
            for attempt in range(MAX_RETRIES):
                try:
                    response = await http.get(
                        SEARCH_URL,
                        params={"title": title, "limit": limit},
                    )
                    response.raise_for_status()
                    return response.json().get("docs", [])
                except httpx.HTTPStatusError as exc:
                    last_exc = exc
                    if exc.response.status_code >= 500 and attempt < MAX_RETRIES - 1:
                        delay = RETRY_BACKOFF * (2 ** attempt)
                        logger.warning(
                            "Open Library returned %d for '%s', retrying in %.1fs",
                            exc.response.status_code, title, delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    break
                except httpx.HTTPError as exc:
                    last_exc = exc
                    break

        raise OpenLibraryError(f"Open Library search failed: {last_exc}") from last_exc

    async def search(self, title: str, limit: int = DEFAULT_RESULT_LIMIT) -> list[dict]:
        """Search Open Library by title with retry on transient errors.

        Args:
            title: The book title to search for.
            limit: Maximum number of results to return.

        Returns:
            List of document dicts from the Open Library API.

        Raises:
            OpenLibraryError: If the API request fails after retries.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as http:
            return await self._search_with_client(http, title, limit)

    def _score_match(self, input_title: str, doc: dict) -> BookMatch:
        """Score a single Open Library document against the input title."""
        raw_title = doc.get("title", "") or ""
        input_norm = normalize_title(input_title)
        doc_norm = normalize_title(raw_title)

        # Compare against both the full input and the main title (before subtitle),
        # and use the higher similarity score
        title_score = _title_similarity(input_norm, doc_norm)
        main = extract_main_title(input_norm)
        if main:
            main_score = _title_similarity(main, doc_norm)
            title_score = max(title_score, main_score)

        edition_count = doc.get("edition_count", 0) or 0
        authors = list(doc.get("author_name", [])[:3])
        isbn_list = doc.get("isbn") or []

        confidence = title_score
        if isbn_list:
            confidence += BONUS_ISBN
        if authors:
            confidence += BONUS_AUTHOR
        if doc.get("first_publish_year"):
            confidence += BONUS_PUBLISH_YEAR
        if edition_count >= MIN_EDITIONS_FOR_BONUS:
            confidence += BONUS_MULTIPLE_EDITIONS
        confidence = min(confidence, 1.0)

        return BookMatch(
            input_title=input_title,
            matched_title=raw_title,
            confidence=round(confidence, 4),
            title_similarity=round(title_score, 4),
            authors=authors,
            first_publish_year=doc.get("first_publish_year"),
            edition_count=edition_count,
            isbn=isbn_list[0] if isbn_list else None,
            raw_doc=doc,
        )

    async def match_title(
        self,
        title: str,
        limit: int = DEFAULT_RESULT_LIMIT,
        _http: httpx.AsyncClient | None = None,
    ) -> BookMatch | None:
        """Match a string to a book title via Open Library.

        Searches Open Library, scores each result against the input, and
        returns the best match if it meets confidence thresholds.

        Args:
            title: The string to match (can be noisy, e.g. from OCR or an
                Amazon order export).
            limit: Maximum number of search results to evaluate.
            _http: Shared HTTP client (internal use by match_titles).

        Returns:
            A BookMatch with decision "book" or "likely_book", or None if
            no result meets the confidence thresholds.

        Raises:
            OpenLibraryError: If the API request fails.
        """
        if _http:
            docs = await self._search_with_client(_http, title, limit)
        else:
            docs = await self.search(title, limit=limit)

        # Fallback: if no results, try searching with just the main title
        # (strip subtitle after colon or dash)
        if not docs:
            main = extract_main_title(normalize_title(title))
            if main:
                logger.debug("Retrying with main title: %s", main)
                if _http:
                    docs = await self._search_with_client(_http, main, limit)
                else:
                    docs = await self.search(main, limit=limit)

        if not docs:
            logger.debug("No results from Open Library for: %s", title)
            return None

        scored = [self._score_match(title, doc) for doc in docs]
        scored.sort(key=lambda m: m.confidence, reverse=True)
        best = scored[0]

        if best.confidence >= self.high_threshold:
            best.decision = "book"
            return best

        if (
            best.confidence >= self.moderate_threshold
            and best.edition_count >= 1
            and best.authors
        ):
            best.decision = "likely_book"
            return best

        logger.debug(
            "No confident match for '%s' (best: %.2f '%s')",
            title,
            best.confidence,
            best.matched_title,
        )
        return None

    async def _match_title_safe(
        self,
        http: httpx.AsyncClient,
        title: str,
        limit: int = DEFAULT_RESULT_LIMIT,
    ) -> BookMatch | None:
        """Wrapper around match_title that catches errors per title."""
        try:
            return await self.match_title(title, limit=limit, _http=http)
        except OpenLibraryError:
            logger.exception("Open Library lookup failed for: %s", title)
            return None

    async def match_titles(
        self,
        titles: list[str],
        limit: int = DEFAULT_RESULT_LIMIT,
    ) -> list[BookMatch | None]:
        """Match multiple strings concurrently.

        Uses a shared HTTP client with connection pooling for all requests.
        All titles are searched in parallel (up to max_concurrent at a time).
        Individual failures are logged and returned as None rather than
        crashing the entire batch.

        Args:
            titles: List of strings to match.
            limit: Maximum number of search results per title.

        Returns:
            List of BookMatch results (or None) in the same order as input.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as http:
            tasks = [self._match_title_safe(http, t, limit=limit) for t in titles]
            return list(await asyncio.gather(*tasks))
