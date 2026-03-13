# BookCatalog Setup Script
# Installs dependencies and builds the local Open Library search database.
#
# Usage:
#   .\scripts\Setup-BookCatalog.ps1           # full setup
#   .\scripts\Setup-BookCatalog.ps1 -SkipDb   # skip Open Library download/build
#   .\scripts\Setup-BookCatalog.ps1 -DbOnly   # only download/build Open Library
#   .\scripts\Setup-BookCatalog.ps1 -Force     # rebuild database even if it exists

param(
    [switch]$SkipDb,
    [switch]$DbOnly,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "--- $Message" -ForegroundColor Cyan
}

function Test-Command {
    param([string]$Name)
    $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------

Write-Step "Checking prerequisites"

$missing = @()

if (-not (Test-Command "python")) {
    $missing += "Python 3.13+ (https://python.org)"
}
else {
    $pyVer = python --version 2>&1
    Write-Host "  Python:  $pyVer"
}

if (-not (Test-Command "uv")) {
    $missing += "uv (https://docs.astral.sh/uv/getting-started/installation/)"
}
else {
    $uvVer = uv --version 2>&1
    Write-Host "  uv:      $uvVer"
}

if (-not $DbOnly) {
    if (-not (Test-Command "node")) {
        $missing += "Node.js 20+ (https://nodejs.org)"
    }
    else {
        $nodeVer = node --version 2>&1
        Write-Host "  Node.js: $nodeVer"
    }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "Missing required tools:" -ForegroundColor Red
    foreach ($tool in $missing) {
        Write-Host "  - $tool" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "Install the missing tools and run this script again." -ForegroundColor Yellow
    exit 1
}

Write-Host "  All prerequisites met." -ForegroundColor Green

# ---------------------------------------------------------------------------
# Python dependencies
# ---------------------------------------------------------------------------

if (-not $DbOnly) {
    Write-Step "Installing Python dependencies"
    uv sync
    Write-Host "  Done." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Frontend dependencies
# ---------------------------------------------------------------------------

if (-not $DbOnly) {
    Write-Step "Installing frontend dependencies"
    Set-Location (Join-Path $root "frontend")
    npm install --no-fund --no-audit
    Set-Location $root
    Write-Host "  Done." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Environment file
# ---------------------------------------------------------------------------

if (-not $DbOnly) {
    $envFile = Join-Path $root ".env"
    if (-not (Test-Path $envFile)) {
        Write-Step "Creating .env from .env.example"
        Copy-Item (Join-Path $root ".env.example") $envFile
        Write-Host "  Created .env - edit it to add your API keys." -ForegroundColor Yellow
    }
    else {
        Write-Host ""
        Write-Host "  .env already exists, skipping." -ForegroundColor DarkGray
    }
}

# ---------------------------------------------------------------------------
# Open Library database
# ---------------------------------------------------------------------------

if (-not $SkipDb) {
    $dbPath = Join-Path $root "data" "openlibrary" "openlibrary.db"
    $dbExists = Test-Path $dbPath

    if ($dbExists -and -not $Force) {
        Write-Step "Open Library database already exists"
        $size = (Get-Item $dbPath).Length / 1GB
        Write-Host "  Path: $dbPath"
        Write-Host "  Size: $([math]::Round($size, 1)) GB"
        Write-Host "  To rebuild, run with -Force."
    }
    else {
        Write-Step "Downloading Open Library bulk dumps"
        Write-Host "  This downloads ~13 GB of compressed data from openlibrary.org"
        Write-Host "  (authors, works, and editions)."
        Write-Host "  Download time depends on your connection speed."
        Write-Host ""
        uv run python scripts/download_openlibrary.py

        Write-Step "Building SQLite search database"
        Write-Host "  This parses 90M+ records and builds an FTS5 full-text index."
        Write-Host "  Expect this to take 30-60 minutes and produce a ~20+ GB database."
        Write-Host ""
        if ($Force) {
            uv run python scripts/build_openlibrary_db.py --force
        }
        else {
            uv run python scripts/build_openlibrary_db.py
        }

        Write-Host ""
        Write-Host "  Database ready." -ForegroundColor Green
    }
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Edit .env with your API keys (if needed)"
Write-Host "  2. Start the dev servers:"
Write-Host "       .\scripts\Start-DevServer.ps1" -ForegroundColor White
Write-Host "  3. Open http://localhost:5173 in your browser"
Write-Host ""
