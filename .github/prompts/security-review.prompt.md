---
mode: agent
description: Perform a security review of the book catalog codebase or a specific change.
---

# Security Review

Review the following for security concerns: ${{ input }}

## Review Checklist

1. **Secrets** — Scan for hardcoded API keys, tokens, passwords, or connection strings
2. **Input validation** — Verify all user inputs are validated:
   - Image files: type, size, and content validation
   - Amazon exports: sanitized before parsing
   - Manual entries: validated against expected schemas
3. **SQL injection** — Confirm all database queries use parameterized statements
4. **File handling** — Check for path traversal, unrestricted uploads, and temp file cleanup
5. **Dependencies** — Run `pip-audit` or `safety check` for known vulnerabilities
6. **Logging** — Ensure sensitive data (API keys, personal book history) is not logged
7. **Error messages** — Verify error responses don't leak internal details or stack traces to users

Report findings with severity (Critical / High / Medium / Low) and recommended fixes.
