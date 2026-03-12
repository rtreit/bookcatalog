# Pre-tool policy hook
# Validates that file changes don't introduce policy violations.

param(
    [string]$File = $env:COPILOT_FILE
)

function Test-ForSecrets {
    param([string]$FilePath)
    if (Test-Path $FilePath) {
        $matches = rg -i '(api_key|secret|password|token)\s*=\s*["\x27][^"\x27]+["\x27]' $FilePath 2>$null
        if ($matches) {
            Write-Error "POLICY VIOLATION: Potential hardcoded secret detected in $FilePath"
            Write-Error "Use environment variables or a secrets manager instead."
            exit 1
        }
    }
}

function Test-TypeHints {
    param([string]$FilePath)
    if ($FilePath -match '\.py$' -and (Test-Path $FilePath)) {
        $missing = rg -n 'def \w+\([^)]*\)\s*:' $FilePath 2>$null | Where-Object { $_ -notmatch '->' -and $_ -notmatch '__' }
        if ($missing) {
            Write-Warning "Function(s) in $FilePath missing return type hints."
        }
    }
}

if ($File) {
    Test-ForSecrets -FilePath $File
    Test-TypeHints -FilePath $File
}
