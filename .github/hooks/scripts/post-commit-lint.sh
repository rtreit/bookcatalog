#!/usr/bin/env bash
# Post-commit lint hook
# Runs linting on modified Python files after changes.

set -euo pipefail

# Find recently modified Python files and run ruff if available
if command -v ruff &>/dev/null; then
    modified_files=$(git diff --name-only --diff-filter=AM HEAD 2>/dev/null | grep '\.py$' || true)
    if [ -n "$modified_files" ]; then
        echo "Running ruff on modified files..."
        echo "$modified_files" | xargs ruff check --fix || true
    fi
fi
