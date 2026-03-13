"""Data models for book research results."""

from dataclasses import dataclass, field


@dataclass
class BookMatch:
    """Result of matching an input string to a book via a metadata provider.

    Attributes:
        input_title: The original string used to search.
        matched_title: The title returned by the metadata provider.
        confidence: Overall confidence score (0.0 to 1.0).
        title_similarity: Raw title similarity ratio before bonus adjustments.
        authors: List of author names (up to 3).
        first_publish_year: Year the book was first published, if known.
        edition_count: Number of known editions.
        isbn: A sample ISBN (ISBN-13 preferred) from the result, if available.
        publisher: Publisher name from the best edition, if available.
        number_of_pages: Page count from the best edition, if available.
        publish_date: Publication date string from the best edition, if available.
        physical_format: Format (Hardcover, Paperback, etc.), if available.
        decision: Classification result - "book", "likely_book", or "unclassified".
        raw_doc: The full document from the metadata provider for downstream use.
    """

    input_title: str
    matched_title: str
    confidence: float
    title_similarity: float
    authors: list[str]
    first_publish_year: int | None
    edition_count: int
    isbn: str | None
    publisher: str | None = None
    number_of_pages: int | None = None
    publish_date: str | None = None
    physical_format: str | None = None
    decision: str = "unclassified"
    raw_doc: dict = field(default_factory=dict, repr=False)
