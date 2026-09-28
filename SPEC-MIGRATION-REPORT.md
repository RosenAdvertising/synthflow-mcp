# MCP 2026-07-28 migration

Synthflow MCP targets the `2026-07-28` wire protocol through the Python MCP
SDK requirement `mcp>=2.2,<3`. `uv.lock` resolves both `mcp` and `mcp-types`
to 2.2.0. The protocol changes and applicability decisions are mapped in
[SPEC-DELTA-2026-07-28.md](SPEC-DELTA-2026-07-28.md).

## Application changes

- The server uses SDK `MCPServer` and ships a stdio entry point. The SDK's
  in-process HTTP app is exercised by protocol tests; no HTTP entry point is
  shipped.
- Existing 17 tools, three resources, and three prompts remain registered.
  The SDK negotiates the modern revision and retains legacy `2025-11-25`
  negotiation.
- Four list tools enforce limits of 1 through 200 and one-based pages in their
  generated schemas. Client methods make one vendor request per call; returned
  ordering has not been verified against a live Synthflow account.
- SDK discovery, result envelopes, private zero-TTL cache hints, stable tool
  listing, HTTP headers, and protocol errors are covered by offline tests.
- Rejection logs carry reason or status without vendor response bodies. The
  verification command does not print account names or email addresses.

## Reproduce local checks

Use an environment installed from the lock, with the repository's `.venv`.
The placeholder key and keyring opt-out prevent the test harness from looking
up stored credentials. Tests use mocked vendor responses and an in-process
protocol transport.

```bash
SYNTHFLOW_MCP_USE_KEYRING=0 SYNTHFLOW_API_KEY=offline-test-placeholder .venv/bin/python -m pytest -q
SYNTHFLOW_MCP_USE_KEYRING=0 SYNTHFLOW_API_KEY=offline-test-placeholder .venv/bin/python tests/spec_check.py --mcp-only
uv run --offline --no-project --with ruff==0.8.5 ruff check synthflow_mcp/client.py synthflow_mcp/server.py synthflow_mcp/setup/verify.py tests/spec_check.py tests/test_spec_2026_07_28.py
uv lock --offline --check
```

These checks cover local protocol behavior and mocked vendor calls. Live
Synthflow responses, ordering, and deployed transport behavior remain untested.

## Open product decision

MCP 2.2.0 masks messages from tool exceptions other than `ToolError` and
`ResourceError`, returning a generic error to clients. Retaining that masking
limits information leakage; raising explicitly safe `ToolError` messages could
give clients more actionable feedback. Toby should decide which behavior to
use. This migration leaves the existing tool exception handling unchanged.
