"""Custom exceptions for the research pipeline stage."""


class ResearchError(Exception):
    """Base exception for book research operations."""


class OpenLibraryError(ResearchError):
    """Error communicating with the Open Library API."""
