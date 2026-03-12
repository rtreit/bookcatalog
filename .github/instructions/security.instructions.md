---
applyTo: "**"
---

# Security Instructions

## Secrets Management

- API keys (vision AI, book metadata APIs, database credentials) must be stored in environment variables.
- Use `.env` files for local development - these are already in `.gitignore`.
- Never log full API keys; mask or omit them in log output.

## Input Validation

- Validate image file types and sizes before passing to vision AI.
- Sanitize Amazon export file content - treat as untrusted input.
- Parameterize all SQL queries; never use string interpolation for query building.

## File Handling

- Validate file paths to prevent directory traversal attacks.
- Set maximum file size limits for uploaded images.
- Process images in a temporary directory, cleaned up after use.

## Dependencies

- Regularly audit dependencies for known vulnerabilities (`uv pip audit` or `safety`).
- Pin dependency versions via `uv.lock` to avoid supply chain attacks via malicious updates.
