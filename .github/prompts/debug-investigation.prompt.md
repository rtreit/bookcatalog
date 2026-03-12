---
mode: agent
description: Investigate and debug an issue in the book catalog pipeline.
---

# Debug Investigation

Investigate the following issue: ${{ input }}

## Investigation Steps

1. **Reproduce** — Determine the minimal input or steps to trigger the problem
2. **Locate** — Identify which pipeline stage is affected (ingest, identify, research, store)
3. **Trace data flow** — Follow the data from input through each stage, checking transformations
4. **Check external dependencies** — If the issue involves vision AI or book metadata APIs, verify:
   - API response format hasn't changed
   - Rate limits aren't being hit
   - Authentication is still valid
5. **Check storage** — If the issue is in the store stage, verify:
   - Database connection and permissions
   - Schema matches expected format
   - Data types are compatible
6. **Root cause** — Identify the underlying issue and propose a fix
7. **Verify** — Confirm the fix resolves the issue without regressions
