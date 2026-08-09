# MCP specification delta: 2025-11-25 to 2026-07-28

Research date: 2026-08-09. Sources are limited to the official MCP
specification and Python SDK documentation.

## Current target and migration release

This repository currently targets MCP `2025-11-25`:

- `pyproject.toml` declares `mcp>=1.28.1,<2`, and `uv.lock` resolves MCP Python
  SDK 1.28.1.
- `synthflow_mcp/server.py` constructs v1 `FastMCP` without overriding protocol
  negotiation, so the SDK default is authoritative.
- The server calls `mcp.run()` with no transport argument and therefore ships
  stdio only. It has no HTTP or browser application.
- There were no committed protocol tests or spec guard before this migration.

The official changelog says `2026-07-28` follows `2025-11-25`
([spec changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)).
The official SDK documentation says v2 speaks `2026-07-28`, retains legacy
client support, renames `FastMCP` to `MCPServer`, and moves transport settings
to `run()` or the app builders
([SDK v2 overview](https://py.sdk.modelcontextprotocol.io/whats-new/),
[v1-to-v2 migration guide](https://py.sdk.modelcontextprotocol.io/migration/)).
This migration pins the first stable v2 release, `mcp==2.0.0`, exactly.

Verdicts below mean:

- **AFFECTS-US**: this server exposes or relies on the changed surface. The SDK
  may implement the wire behavior, but the migration must pin, configure, or
  test it.
- **NOT-APPLICABLE**: the feature or direction is not implemented here. It will
  not be added merely because the revision permits it.

## Protocol negotiation and lifecycle

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| Protocol-level sessions and `Mcp-Session-Id` are removed for the modern revision. Cross-call application state uses explicit handles. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | The stdio server must accept independent modern requests. It keeps no MCP session or cross-call application state. A raw HTTP conformance test also proves the SDK does not emit a modern session header. |
| Modern requests remove `initialize` / `notifications/initialized` and carry version, capabilities, and recommended identity metadata on every request/result. Version mismatch uses `UnsupportedProtocolVersionError`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | SDK v2's dual-era dispatcher must serve modern self-describing requests while retaining the legacy handshake. |
| Servers MUST implement `server/discover` with supported versions, capabilities, and identity. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | This is required for every modern server; discovery must report Synthflow's tools, resources, and prompts. |
| Every result requires `resultType`, normally `"complete"`, or `"input_required"` for multi-round-trip requests. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | Tool, resource, prompt, list, and discovery results all use the revised result envelope. |
| Server-initiated requests are replaced by Multi Round-Trip Requests (MRTR). [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | No tool, resource, or prompt uses sampling, roots, elicitation, or another server-to-client request. |
| `ping`, `logging/setLevel`, and `notifications/roots/list_changed` are removed; protocol log opt-in becomes per-request metadata. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | The server implements none of these methods and uses no MCP logging notifications. Application diagnostics go to stderr. |

## Transports and notifications

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| Streamable HTTP POST requires `Mcp-Method` and named operations require `Mcp-Name`; `x-mcp-header` can bind selected parameters to HTTP headers. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | The shipped entry point is stdio only and no tool declares `x-mcp-header`. The migration nevertheless raw-wire tests the SDK v2 ASGI app's required headers to guard future transport enablement. |
| The standalone HTTP GET stream and resource subscribe/unsubscribe methods are replaced by `subscriptions/listen`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | The high-level server advertises SDK-managed list-change/resource-subscription capabilities for its existing primitives. SDK v2 maps those declarations to the modern mechanism; no publisher, bus, or new application behavior is added. |
| SSE resumability and redelivery (`Last-Event-ID` and SSE event IDs) are removed. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | The server has no HTTP event stream, event store, or redelivery dependency. |
| Legacy HTTP+SSE is formally deprecated. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | The server exposes stdio only. |

## Capabilities and extensions

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| Client and server capabilities gain an `extensions` field. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | Discovery exposes this shape. The server must not claim an extension it does not implement. |
| Experimental core tasks move to `io.modelcontextprotocol/tasks` with redesigned methods. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | There are no task handlers or task-augmented tools, and SDK v2 does not implement this extension. |
| Roots, Sampling, and Logging are deprecated. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | None is declared or used. |
| Sampling `includeContext` values `"thisServer"` and `"allServers"` are deprecated. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | Sampling is not used. |

## Tools, resources, prompts, and cache semantics

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| List results and `resources/read` require `ttlMs` and `cacheScope`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | The server exposes 17 tools, three resources, and three prompts. SDK v2's conservative private, zero-TTL defaults must be present on all applicable results. |
| `tools/list` SHOULD be deterministic. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | Decorator registration order is stable and repeated listings must return the same 17 tool names. |
| Tool schemas accept JSON Schema 2020-12, and `structuredContent` may be any JSON value. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | SDK v2 owns schema generation and validation. Tests must prove generated object schemas, including bounded list limits, remain valid. |
| Resource-not-found changes from `-32002` to Invalid Params `-32602`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | The server publishes three static resources; an unknown URI must now return `-32602`. |
| URL-mode elicitation drops its completion notification and `elicitationId`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | The server performs no elicitation. |
| Generated schema numeric minimum, maximum, and default types are corrected. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#other-schema-changes) | **NOT-APPLICABLE** | The repository neither vendors the MCP schema nor validates directly against that generated meta-schema. SDK v2 absorbs the correction. |

## Authorization and security

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| Authorization servers should return RFC 9207 `iss`; MCP clients validate it before code redemption. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | This stdio server is neither an MCP authorization server nor an MCP OAuth client. Its Synthflow API key is downstream vendor authentication. |
| Dynamic Client Registration clients must send `application_type`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | The code does not register an MCP client. |
| Persisted MCP client credentials are bound to their authorization-server issuer. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | The credential store contains only a Synthflow vendor API key, not MCP client registrations. |
| Dynamic Client Registration is deprecated in favor of Client ID Metadata Documents. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | The server neither hosts DCR nor acts as a registered MCP client. |

## Errors, metadata, and observability

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| MCP reserves `-32020..-32099`; header mismatch, missing capability, and unsupported version use `-32020`, `-32021`, and `-32022`; unknown methods use `-32601`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | Version and unknown-method behavior applies to the server. Raw-wire SDK tests also cover the reachable header-mismatch code without enabling HTTP in production. No operation requires a new optional client capability, so no artificial `-32021` route is added. |
| `_meta` formally carries W3C `traceparent`, `tracestate`, and `baggage`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | The server has no MCP trace-context integration. This migration does not add an observability feature. |

Governance and SEP workflow changes do not alter this server's runtime or wire
behavior. The feature-lifecycle change is honored by not adopting deprecated
Roots, Sampling, Logging, HTTP+SSE, or DCR.
