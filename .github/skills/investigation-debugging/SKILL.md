---
name: investigation-debugging
description: Systematic investigation and debugging of issues in the bookcatalog pipeline. Use this when debugging pipeline failures, API issues, data corruption, or performance problems.
---

# Investigation & Debugging Skill

## When to Use

- A pipeline stage is producing incorrect or unexpected output
- External API integrations are failing or returning bad data
- Data is being lost or corrupted between pipeline stages
- Performance issues in batch processing

## Approach

### 1. Isolate the Stage

Determine which pipeline stage is involved by checking intermediate outputs:

```powershell
uv run python -m bookcatalog --verbose --input <test-input>
```

### 2. Test with Fixtures

Use saved fixtures to eliminate external API variability:

```powershell
uv run pytest tests/ -k "test_<relevant_stage>" -v
```

### 3. Check External APIs

If the issue involves an external service:

```python
# Quick API health check
from bookcatalog.research import metadata_client
result = metadata_client.lookup(isbn="978-0-13-468599-1")
print(result)
```

### 4. Database Inspection

For storage-related issues, verify the database state directly:

```powershell
sqlite3 bookcatalog.db ".schema"
sqlite3 bookcatalog.db "SELECT * FROM books ORDER BY created_at DESC LIMIT 5;"
```

## Key Files

- Pipeline orchestration: `bookcatalog/pipeline.py`
- Ingestion sources: `bookcatalog/ingestion/`
- Research providers: `bookcatalog/research/`
- Storage backends: `bookcatalog/storage/`
