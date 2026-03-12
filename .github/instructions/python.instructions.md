---
applyTo: "**/*.py"
---

# Python Instructions

## Style & Formatting

- Use `ruff` for linting and formatting.
- Target Python 3.13+.
- Use type hints on all function signatures (parameters and return types).
- Prefer `pathlib.Path` over `os.path` for file operations.

## Project Structure Conventions

- One class per file for major components (ingestion sources, storage backends, research providers).
- Use `__init__.py` to define public APIs for each package.
- Configuration via environment variables, loaded through a central config module.

## Error Handling

- Define custom exception classes for each pipeline stage (e.g., `IngestionError`, `ResearchError`, `StorageError`).
- External API calls must handle timeouts, rate limits, and transient errors with retries.
- Never silently swallow exceptions - log at minimum.

## Dependencies

- Always use `uv` for dependency management (`uv add`, `uv remove`, `uv sync`).
- Use `python-dotenv` for local environment variable loading.
- Prefer standard library where feasible; justify new dependencies.
