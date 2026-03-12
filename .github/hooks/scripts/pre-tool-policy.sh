#!/usr/bin/env bash
# Pre-tool policy hook
# Validates that file changes don't introduce policy violations.

set -euo pipefail

# Block commits containing potential secrets
check_for_secrets() {
    local file="$1"
    if grep -qEi '(api_key|secret|password|token)\s*=\s*["\x27][^"\x27]+["\x27]' "$file" 2>/dev/null; then
        echo "POLICY VIOLATION: Potential hardcoded secret detected in $file"
        echo "Use environment variables or a secrets manager instead."
        exit 1
    fi
}

# Ensure Python files have type hints on function definitions
check_type_hints() {
    local file="$1"
    if [[ "$file" == *.py ]]; then
        if grep -Pn 'def \w+\([^)]*\)\s*:' "$file" | grep -v '\->' | grep -v '__' >/dev/null 2>&1; then
            echo "WARNING: Function(s) in $file missing return type hints."
        fi
    fi
}

if [ -n "${COPILOT_FILE:-}" ]; then
    check_for_secrets "$COPILOT_FILE"
    check_type_hints "$COPILOT_FILE"
fi
