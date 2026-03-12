---
applyTo: "**/*test*/**,**/test_*.py,**/*_test.py"
---

# Testing Instructions

## Test Framework

- Use `pytest` as the test runner.
- Place tests in a `tests/` directory mirroring the source structure.

## Running Tests

```powershell
# Full suite
uv run pytest

# Single test file
uv run pytest tests/test_ingestion.py

# Single test function
uv run pytest tests/test_ingestion.py::test_parse_amazon_export

# With coverage
uv run pytest --cov=bookcatalog --cov-report=term-missing
```

## Test Conventions

- Use fixtures for common setup (sample book data, mock API responses, temporary databases).
- Mock external API calls (vision AI, book metadata APIs) - tests must not hit real endpoints.
- Store test fixtures (sample images, export files, expected API responses) in `tests/fixtures/`.
- Test each pipeline stage independently and write integration tests for stage-to-stage handoffs.
- Name test files `test_<module>.py` and test functions `test_<behavior>`.

## What to Test

- Each ingestion source parses its input format correctly
- Research agent handles missing/partial metadata gracefully
- Storage backends write and read back records accurately
- Pipeline handles batch failures without losing successful records
