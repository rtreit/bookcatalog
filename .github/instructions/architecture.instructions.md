---
applyTo: "**"
---

# Architecture Instructions

## Pipeline Architecture

The bookcatalog system follows a four-stage pipeline:

```
Ingest → Identify → Research → Store
```

1. **Ingest** - Accepts input from multiple sources (images, Amazon exports, manual entry) and produces raw candidate records (partial title/author guesses).
2. **Identify** - Normalizes and deduplicates candidates. For image sources, this involves vision AI interpretation. For Amazon exports, this is parsing and field extraction.
3. **Research** - Takes identified candidates and queries book metadata APIs (Open Library, Google Books, etc.) to fill in complete details: ISBN, publisher, page count, genre, synopsis, cover image URL.
4. **Store** - Writes finalized book records to the configured storage backend(s).

## Design Principles

- Each pipeline stage has a defined interface so stages can be tested and replaced independently.
- Storage backends are pluggable - adding a new backend means implementing one interface.
- External API calls (vision AI, metadata lookups) are behind abstractions to support mocking in tests and swapping providers.
- Batch operations support progress tracking and partial failure handling (one bad book shouldn't stop a batch of 50).
