# Post-commit lint hook
# Runs ruff on modified Python files after changes.

if (Get-Command ruff -ErrorAction SilentlyContinue) {
    $modifiedFiles = git diff --name-only --diff-filter=AM HEAD 2>$null | Where-Object { $_ -match '\.py$' }
    if ($modifiedFiles) {
        Write-Host "Running ruff on modified files..."
        $modifiedFiles | ForEach-Object { uv run ruff check --fix $_ }
    }
}
