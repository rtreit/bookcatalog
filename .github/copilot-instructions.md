# Copilot Instructions

## Project Overview

AI-powered book cataloging system. Users provide input (photos of book stacks, Amazon purchase exports, manual entry) and AI agents research each book's details, then populate a database with structured catalog records.

## Style Rules

- Never use emojis in code or documentation unless explicitly directed.
- Never use em dashes. Use regular hyphens, commas, or separate sentences instead.

## Language & Tooling

- **Language:** Python 3.13+
- **Package manager:** Always use `uv` for dependency management, virtual environments, and running scripts. Never use pip, pip-tools, or other package managers directly.
- **License:** MIT

## Development Environment

- **OS:** Windows
- **Shell:** Always use PowerShell (`pwsh`) for scripting tasks. Never use bash or sh.
- **Search:** Use `rg` (ripgrep) instead of `grep` for all text search operations.

## Key Concepts

- **Book ingestion:** Multiple input sources - image recognition (vision AI for book spines/covers), Amazon order CSV/HTML export parsing, and manual entry.
- **Book research agent:** Given a title/author hint from ingestion, autonomously looks up full metadata (ISBN, publisher, page count, genre, synopsis, cover image URL, etc.).
- **Storage backends:** Pluggable - support Microsoft Access (.accdb), SQLite/SQL Server, and spreadsheet export (Excel/CSV).
- **Pipeline:** Ingest → Identify → Research → Store. Each stage should be independently testable.
