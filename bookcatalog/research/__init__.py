"""Book research providers for metadata lookup and matching."""

from .exceptions import OpenLibraryError, ResearchError
from .local_search import LocalBookSearch
from .models import BookMatch
from .openlibrary import OpenLibraryClient, extract_main_title, normalize_title
from .preprocessing import preprocess_input, split_order_items
from .product_filter import compute_product_score, is_likely_product

__all__ = [
    "BookMatch",
    "LocalBookSearch",
    "OpenLibraryClient",
    "OpenLibraryError",
    "ResearchError",
    "compute_product_score",
    "extract_main_title",
    "is_likely_product",
    "normalize_title",
    "preprocess_input",
    "split_order_items",
]
