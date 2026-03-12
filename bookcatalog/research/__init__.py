"""Book research providers for metadata lookup and matching."""

from .exceptions import OpenLibraryError, ResearchError
from .local_search import LocalBookSearch
from .models import BookMatch
from .openlibrary import OpenLibraryClient, extract_main_title, normalize_title
from .preprocessing import preprocess_input, split_order_items

__all__ = [
    "BookMatch",
    "LocalBookSearch",
    "OpenLibraryClient",
    "OpenLibraryError",
    "ResearchError",
    "extract_main_title",
    "normalize_title",
    "preprocess_input",
    "split_order_items",
]
