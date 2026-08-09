# MCP 2026-07-28 migration report

## Result

`synthflow-mcp` now targets MCP `2026-07-28`, up from `2025-11-25`. The
direct SDK dependency changed from `mcp>=1.28.1,<2` (locked to 1.28.1) to the
exact migration release `mcp==2.0.0`. The refreshed lock includes the SDK v2
dependency split, including `mcp-types==2.0.0` and `httpx2`.

The authoritative change analysis and official-source links are in
[`SPEC-DELTA-2026-07-28.md`](SPEC-DELTA-2026-07-28.md). No deployment, live
Synthflow account, or remote Git repository was touched.

## Implementation

- Replaced the removed v1 `FastMCP` surface with SDK v2 `MCPServer`.
- Preserved stdio as the only shipped transport; the existing `mcp.run()` entry
  point requires no v2 transport arguments.
- Preserved the 17 tools, three resources, three prompts, API-key credential
  precedence, retry posture, and stateless application model.
- Kept dual-era behavior supplied by SDK v2: modern clients negotiate
  `2026-07-28`, while legacy clients still negotiate `2025-11-25`.
- Added 1–200 JSON Schema bounds to all four list-tool limits and a lower bound
  to their one-based page numbers.
- Added PII-free reason/status logs for missing credentials, rejected vendor
  requests, exhausted/error responses, non-JSON responses, rate limits, and
  verification failure.
- Removed vendor response bodies from raised API errors and stopped the verify
  command from printing account names or email addresses.
- Added an explicit core Ruff policy for the declared Python 3.10 floor.

## AFFECTS-US mapping

| AFFECTS-US item | Handling | Conventional commit |
| --- | --- | --- |
| Sessionless modern protocol | SDK v2 modern dispatcher; raw HTTP discovery proves no session header | `feat: migrate server to MCP 2026-07-28`; `test: prove MCP 2026-07-28 conformance` |
| Per-request version/capability metadata and legacy compatibility | Raw modern requests plus modern/legacy in-memory negotiation | `test: prove MCP 2026-07-28 conformance` |
| Required `server/discover` | Exact supported version, identity, capabilities, cache hints, and result type asserted | `test: prove MCP 2026-07-28 conformance` |
| Required `resultType` | Discovery, every list category, resource read, prompt get, successful tool call, and validation tool error asserted | `test: prove MCP 2026-07-28 conformance` |
| Modern HTTP routing headers | Although production remains stdio, the SDK app is raw-wire tested with `MCP-Protocol-Version`, `Mcp-Method`, and `Mcp-Name`, including mismatch/omission errors | `test: prove MCP 2026-07-28 conformance` |
| Existing SDK subscription declarations | Existing prompt/resource/tool declarations retained; no publisher, event store, or custom bus added | `feat: migrate server to MCP 2026-07-28`; `test: prove MCP 2026-07-28 conformance` |
| Capability `extensions` | Discovery proves no unused extension is advertised | `test: prove MCP 2026-07-28 conformance` |
| Required cache hints | SDK v2 conservative defaults (`ttlMs: 0`, `cacheScope: private`) asserted for all list/read categories | `test: prove MCP 2026-07-28 conformance` |
| Deterministic tools | Two independent listings assert the same ordered set of 17 names | `test: prove MCP 2026-07-28 conformance` |
| JSON Schema 2020-12 and structured result behavior | Generated object schemas and bounded list inputs asserted; invalid limits stay complete tool errors | `feat: migrate server to MCP 2026-07-28`; `test: prove MCP 2026-07-28 conformance` |
| Resource-not-found `-32602` | Unknown resource URI regression asserts Invalid Params | `test: prove MCP 2026-07-28 conformance` |
| New reserved error allocation | Header mismatch `-32020`, unsupported version `-32022`, and unknown method `-32601` asserted | `test: prove MCP 2026-07-28 conformance` |

## Test inventory

The pre-migration locked environment installed successfully but the repository
contained no committed test files: `pytest -q` collected **0 tests** and exited
with pytest's no-tests status. The post-migration locked environment reports:

- `uv run --frozen pytest -q`: **14 passed**.
- `uv run --frozen python tests/spec_check.py --mcp-only`: **PASS**, exactly
  `2026-07-28`.
- `ruff check .`: **all checks passed**.
- `ruff format --check .`: **14 files already formatted**.

The conformance suite covers discovery, sessionlessness, modern and legacy
negotiation, required headers, all cacheable categories, result types,
deterministic discovery, schema limits, all four vendor list methods, resource
errors, protocol error codes, rejection logging, and PII-safe CLI/error output.

## Canary sibling checks

- **A — FIXED:** all four list tools now expose schema-enforced 1–200 limits.
  Each client method is regression-tested to make exactly one vendor request,
  so no auto-pagination can exceed the requested total. The repository has no
  Synthflow API contract documenting an order/sort query parameter; no
  unsupported parameter was invented. Returned ordering is method-verified
  only because the task supplied no credentials and the allowed network scope
  excludes live Synthflow documentation/API calls.
- **B — FIXED:** every application rejection path in the HTTP client and verify
  command now logs a PII-free event and reason/status. Keyring failures remain
  fallback paths, not rejections: they deliberately continue to environment or
  file storage.
- **C — N/A:** this repository serves stdio and has no browser pages, Origin
  validation, or CSP handoff.
- **D — FIXED:** the sweep found the verify command printing account
  name/email and raw exception details. It now prints only a generic identity
  confirmation/error; vendor bodies are not included in API exceptions. Tests
  prove synthetic secrets, names, and email addresses do not reach logs or CLI
  output.

## Judgment calls and remaining verification

- Cache policy stays the SDK v2 conservative private, zero-TTL default; no
  retention or sharing behavior was introduced.
- Production remains stdio. Streamable HTTP exists only as the SDK-owned test
  harness used to exercise the revision's transport rules.
- No MRTR, tasks, extensions, roots, sampling, elicitation, protocol logging,
  auth server, or OAuth client feature was added.
- No live Synthflow request was made because no credentials were needed or
  supplied. Vendor method names, pagination forwarding, and output safety are
  verified offline; live returned ordering remains the only method-verified
  caveat.

## Git handoff

The runtime sandbox denied writes to the repository's `.git` directory, so the
branch and commits were built in a writable alternate Git database. The
portable bundle named in the external fan-out report contains branch
`spec-2026-07-28` with complete history and must be imported into the primary
repository. It was not pushed.
