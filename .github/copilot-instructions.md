# Copilot Instructions

## Project Overview

AI-powered book cataloging system. Users provide input (photos of book stacks, Amazon purchase exports, manual entry) and AI agents research each book's details, then populate a database with structured catalog records.

## Language & Tooling

- **Language:** Python
- **License:** MIT

## Key Concepts

- **Book ingestion:** Multiple input sources — image recognition (vision AI for book spines/covers), Amazon order CSV/HTML export parsing, and manual entry.
- **Book research agent:** Given a title/author hint from ingestion, autonomously looks up full metadata (ISBN, publisher, page count, genre, synopsis, cover image URL, etc.).
- **Storage backends:** Pluggable — support Microsoft Access (.accdb), SQLite/SQL Server, and spreadsheet export (Excel/CSV).
- **Pipeline:** Ingest → Identify → Research → Store. Each stage should be independently testable.
