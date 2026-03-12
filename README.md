# BookCatalog

AI-powered book cataloging system that automatically identifies, researches, and catalogs books from multiple input sources.

## How It Works

```
Ingest --> Identify --> Research --> Store
```

1. **Ingest** - Provide books via photo (snap a picture of a shelf or stack), Amazon purchase export, or manual entry.
2. **Identify** - Vision AI reads spines/covers from images; parsers extract titles from Amazon exports.
3. **Research** - An AI agent looks up full metadata (ISBN, author, publisher, page count, genre, synopsis, cover art) from a local Open Library database with 40M+ works.
4. **Store** - Writes complete book records to your chosen backend - SQLite, SQL Server, Microsoft Access, or Excel/CSV.

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)
- Node.js 20+ and npm

## Quick Setup

The setup script installs all dependencies and builds the local search database:

```powershell
.\scripts\Setup-BookCatalog.ps1
```

This will:

1. Install Python dependencies via `uv sync`
2. Install frontend dependencies via `npm install`
3. Create a `.env` file from `.env.example`
4. Download Open Library bulk dumps (~4.7 GB compressed)
5. Build a local SQLite search database with FTS5 indexing (~12 GB, 15-25 min)

### Setup Options

```powershell
# Full setup (default)
.\scripts\Setup-BookCatalog.ps1

# Skip the Open Library database (faster, uses API fallback instead)
.\scripts\Setup-BookCatalog.ps1 -SkipDb

# Only download and build the Open Library database
.\scripts\Setup-BookCatalog.ps1 -DbOnly

# Force rebuild the database even if it already exists
.\scripts\Setup-BookCatalog.ps1 -Force
```

## Running the Dev Servers

```powershell
.\scripts\Start-DevServer.ps1
```

This starts the FastAPI backend on http://localhost:8000 and the React frontend on http://localhost:5173.

```powershell
# Stop both servers
.\scripts\Start-DevServer.ps1 -Stop
```

## Open Library Search Database

BookCatalog uses a local copy of [Open Library's](https://openlibrary.org/) catalog data for fast, offline book matching. The database contains 15M+ authors and 40M+ works with full-text search via SQLite FTS5.

### Why local data?

Open Library [explicitly asks](https://openlibrary.org/developers/api) that their APIs not be used for bulk harvesting. Their monthly bulk dumps are the intended path for applications that need to search across the full catalog. The local database also gives us:

- Sub-second search (avg 156ms/query vs seconds per API call)
- No rate limiting or network dependency
- Complete catalog coverage (40M+ works vs API pagination limits)
- Works fully offline

### Manual database setup

If you prefer to run the steps individually instead of using the setup script:

```powershell
# 1. Download the bulk dumps (~4.7 GB, time depends on connection)
uv run python scripts/download_openlibrary.py

# 2. Build the SQLite database (~12 GB, takes 15-25 min)
uv run python scripts/build_openlibrary_db.py

# Rebuild from scratch if needed
uv run python scripts/build_openlibrary_db.py --force
```

The dumps are downloaded to `data/openlibrary/` (excluded from git). The database is built from:

- **Authors** (~0.5 GB compressed) - 15M+ author records
- **Works** (~2.9 GB compressed) - 40M+ work records with titles, authors, subjects, and publication dates

### Updating the database

Open Library publishes new dumps monthly. To update, delete the existing files and re-run:

```powershell
Remove-Item data\openlibrary\*.gz
Remove-Item data\openlibrary\openlibrary.db
.\scripts\Setup-BookCatalog.ps1 -DbOnly
```

### Skipping the database

The local database is optional. Without it, BookCatalog falls back to the Open Library API (slower, lower match rate). To skip:

```powershell
.\scripts\Setup-BookCatalog.ps1 -SkipDb
```

## Configuration

Copy `.env.example` to `.env` and edit as needed:

```ini
# OpenAI API key (required for LLM-powered title extraction, future feature)
OPENAI_API_KEY=sk-your-key-here

# Path to local Open Library database (auto-detected if in default location)
# OPENLIBRARY_DB_PATH=data/openlibrary/openlibrary.db
```

## Project Structure

```
bookcatalog/          # Python backend
  api/                # FastAPI routes and models
  ingestion/          # Input source parsers (Amazon, images, manual)
  research/           # Book matching (local FTS5 search, Open Library API)
  storage/            # Database backends
frontend/             # React + Vite frontend
scripts/              # Setup and utility scripts
  Setup-BookCatalog.ps1       # One-command project setup
  Start-DevServer.ps1        # Dev server launcher
  download_openlibrary.py    # Open Library dump downloader
  build_openlibrary_db.py    # SQLite + FTS5 database builder
data/openlibrary/     # Bulk dumps and database (not in git)
```

## License

[MIT](LICENSE)
