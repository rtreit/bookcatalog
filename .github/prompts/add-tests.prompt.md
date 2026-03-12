---
mode: agent
description: Add tests for a specified module or feature in the book catalog project.
---

# Add Tests

Add comprehensive tests for the following area: ${{ input }}

## Steps

1. Identify the module or feature to test
2. Check for existing tests and fixtures in `tests/`
3. Create test file following the `test_<module>.py` naming convention
4. Write tests covering:
   - Happy path with valid input
   - Edge cases (empty input, malformed data, missing fields)
   - Error handling (API failures, invalid file formats, connection errors)
5. Mock all external API calls - use fixtures from `tests/fixtures/` or create new ones
6. Run the tests with `pytest` to verify they pass
7. Check coverage with `pytest --cov=bookcatalog` to identify gaps
