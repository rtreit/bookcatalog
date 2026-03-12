---
name: book-research
description: Researching and enriching book metadata from partial information (title fragments, author names, cover images) into complete catalog records. Use this when working on book lookup, metadata enrichment, or catalog record creation.
---

# Book Research Skill

## When to Use

- Adding a new book metadata API provider
- Improving book identification accuracy from vision AI output
- Handling edge cases in book lookup (multiple editions, international titles, anthologies)
- Building fallback chains across multiple metadata sources

## Metadata Sources

### Open Library API

- Free, no API key required
- Good coverage for older/classic titles
- Endpoint: `https://openlibrary.org/api/books`

### Google Books API

- Free tier with generous limits
- Strong coverage, includes previews and ratings
- Requires API key

### ISBN Lookup Services

- Use ISBN as the canonical identifier when available
- Validate ISBN format (ISBN-10 and ISBN-13) before querying

## Research Strategy

1. **Extract hints** - Get whatever the ingestion stage provides (partial title, author, ISBN barcode)
2. **Normalize** - Clean up OCR artifacts, fix common misspellings, standardize author name format
3. **Query primary source** - Try the most reliable API first
4. **Fallback** - If primary returns incomplete data, try secondary sources
5. **Merge** - Combine results from multiple sources, preferring the most complete/authoritative data
6. **Validate** - Cross-check key fields (does the ISBN match the title/author?)

## Output Schema

A complete book record should include:

| Field | Required | Source |
|-------|----------|--------|
| title | Yes | API lookup |
| author(s) | Yes | API lookup |
| isbn_13 | Preferred | API lookup / barcode scan |
| isbn_10 | Optional | API lookup |
| publisher | Yes | API lookup |
| publish_date | Yes | API lookup |
| page_count | Optional | API lookup |
| genre/subjects | Optional | API lookup |
| synopsis | Optional | API lookup |
| cover_image_url | Optional | API lookup |
| language | Optional | API lookup |
