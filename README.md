# Synthflow MCP server

[![CI](https://github.com/RosenAdvertising/synthflow-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/RosenAdvertising/synthflow-mcp/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-F59E0B.svg)](LICENSE)
[![MCP 2026-07-28](https://img.shields.io/badge/MCP-2026--07--28-7C3AED.svg)](https://modelcontextprotocol.io)
[![17 tools](https://img.shields.io/badge/tools-17-22C55E.svg)](https://github.com/RosenAdvertising/synthflow-mcp)

Connect Claude and other MCP clients to Synthflow to manage voice agents, phone numbers, calls, transcripts and knowledge bases.

Synthflow MCP server is a [Model Context Protocol](https://modelcontextprotocol.io) server for [Synthflow](https://synthflow.ai), the voice AI platform. It registers 17 tools that read and write Synthflow data. It runs over stdio by default, for desktop clients such as Claude Desktop, and offers an opt-in stateless Streamable HTTP mode that implements MCP specification 2026-07-28. Synthflow credentials stay on the machine that runs the server: they come from the setup command and your operating system's keyring, never from the client.

## Features

- **Agents**: list, look up, create, update and delete voice agents.
- **Phone numbers**: list, look up and provision numbers, and assign an agent to a number.
- **Calls**: list and look up calls, read full transcripts, and start an outbound call.
- **Knowledge bases**: list and create knowledge bases.
- **Analytics**: read account analytics and usage, optionally for a date range.

## Tools

The server registers 17 tools.

| Tool | What it does |
| --- | --- |
| `who_am_i` | Account analytics and usage summary. |
| `list_agents` | List voice agents. |
| `get_agent` | Get an agent by ID. |
| `create_agent` | Create a voice agent (outbound, inbound or widget). |
| `update_agent` | Update an agent's name, prompt or voice. |
| `delete_agent` | Delete an agent. |
| `list_phone_numbers` | List provisioned numbers. |
| `get_phone_number` | Get a number by ID. |
| `provision_phone_number` | Provision a new number. |
| `assign_agent_to_number` | Assign an agent to a phone number. |
| `list_calls` | List calls, optionally filtered by agent. |
| `get_call` | Get a call by ID. |
| `get_call_transcript` | Get the full transcript for a call. |
| `initiate_call` | Start an outbound call. |
| `list_knowledge_bases` | List knowledge bases. |
| `create_knowledge_base` | Create a knowledge base. |
| `get_analytics` | Get analytics, optionally for a date range (YYYY-MM-DD). |

### Prompts and resources

The server also registers three prompts and three resources.

| Prompt | What it does |
| --- | --- |
| `setup_offhours_intake_agent` | Step-by-step guide to configure an inbound agent for off-hours intake. |
| `triage_recent_calls` | Reviews and triages recent calls for one agent (`agent_id`). |
| `review_agent_performance` | Analyzes analytics to assess agent effectiveness and call quality. |

| Resource | What it provides |
| --- | --- |
| `synthflow://agents` | All voice agents in the account, as JSON reference data. |
| `synthflow://phone_numbers` | All provisioned phone numbers, as JSON reference data. |
| `synthflow://security-notes` | Security notes for the server. |

## Requirements

- Python 3.10 or later.
- A Synthflow account with an API key (in Synthflow: **Settings → API**).
- An MCP client such as Claude Desktop.

## Installation

Install [uv](https://docs.astral.sh/uv/), then clone the repository and install its locked dependencies:

```bash
git clone https://github.com/RosenAdvertising/synthflow-mcp.git
cd synthflow-mcp
uv sync --locked
```

## Configuration

Run the setup command once. It prompts for your API key, saves it (see [Credential storage](#credential-storage)) and verifies the connection:

```bash
uv run synthflow-mcp-setup
```

Check the connection at any time:

```bash
uv run synthflow-mcp-verify
```

Restart the MCP server after changing the key. Server messages that say to run `synthflow-mcp-setup` mean `uv run synthflow-mcp-setup` from your clone.

The server reads these variables:

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `SYNTHFLOW_API_KEY` | Yes (saved by setup) | Keyring, then `~/.synthflow-mcp/.env` | Synthflow API key. A value already in the process environment is used as is, and keyring and file lookup are skipped. |
| `SYNTHFLOW_MCP_USE_KEYRING` | No | `1` | Set to `0`, `false`, `no` or `off` to skip the operating system keyring and use the `.env` file. |

### Credential storage

By default your API key (`SYNTHFLOW_API_KEY`) is stored in your operating system's native secret store via the cross-platform [`keyring`](https://github.com/jaraco/keyring) library:

| OS | Backend |
| --- | --- |
| macOS | Keychain |
| Windows | Credential Manager |
| Linux | Secret Service (GNOME Keyring / KWallet) |

The secret is saved under the service name `synthflow-mcp`. Nothing is written to disk in clear text. To update the key, re-run `uv run synthflow-mcp-setup`.

**File fallback.** On a host with no keyring backend (for example a headless Linux box without Secret Service), or if you set `SYNTHFLOW_MCP_USE_KEYRING=0`, the key falls back to a `~/.synthflow-mcp/.env` file with `0600` permissions:

```text
SYNTHFLOW_API_KEY=your_api_key_here
```

On Windows, the file is stored in the user's profile and protected by Windows' default per-user access rules. On POSIX, files are created with `0600` permissions and writes fail closed if private permissions cannot be established.

**Read order.** A value set in the process environment is used as is. When `SYNTHFLOW_API_KEY` is not set, the server reads the OS keyring, then the `~/.synthflow-mcp/.env` file, once at startup. A key exported in your shell therefore overrides the keyring and the file, and the keyring entry written by setup is used only while the variable is unset.

**Pluggable backend.** `keyring` lets you point at any secret store. For example, install [`keyrings.cryptfile`](https://pypi.org/project/keyrings.cryptfile/) for an encrypted file backend, or a cloud backend, then select it with the standard `PYTHON_KEYRING_BACKEND` environment variable or a `keyringrc.cfg`. See the [keyring configuration docs](https://github.com/jaraco/keyring#configuring).

## Usage with Claude Desktop

Add the server to Claude Desktop's configuration file (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "synthflow": {
      "command": "uv",
      "args": ["run", "--locked", "--directory", "/absolute/path/to/synthflow-mcp", "synthflow-mcp"]
    }
  }
}
```

Replace `/absolute/path/to/synthflow-mcp` with the path of your clone, then restart Claude Desktop. Any other stdio MCP client uses the same command and arguments.

## HTTP mode

Stdio is the default. Set `SYNTHFLOW_MCP_TRANSPORT=streamable-http` to serve the stateless Streamable HTTP transport from MCP specification 2026-07-28 at `/mcp`. Each request stands alone: no initialization handshake and no `Mcp-Session-Id`. Clients on earlier protocol versions are served on the same endpoint.

> **Security: this endpoint has no authentication and no TLS.** Anyone who can reach the port can run every tool, including write and delete tools, with this server's vendor credentials. Keep the default loopback bind (`127.0.0.1`), or put the server behind an authenticating TLS proxy on a private network. `SYNTHFLOW_MCP_ALLOWED_HOSTS` and `SYNTHFLOW_MCP_ALLOWED_ORIGINS` protect against browser DNS rebinding, not against direct callers. A proxy in front of it needs connection and idle timeouts: a legacy-style `GET /mcp` with `Accept: text/event-stream` holds a stream open until the client disconnects.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SYNTHFLOW_MCP_TRANSPORT` | `stdio` | `stdio` or `streamable-http`. An empty value selects `stdio`. |
| `SYNTHFLOW_MCP_HOST` | `127.0.0.1` | Bind address. An empty value selects `127.0.0.1`. Exactly `127.0.0.1`, `localhost` and `::1` use the SDK's built-in Host and Origin checks; any other spelling requires `SYNTHFLOW_MCP_ALLOWED_HOSTS`. |
| `PORT` | `8080` | Port; must be an integer. |
| `SYNTHFLOW_MCP_ALLOWED_HOSTS` | unset | Comma-separated `Host` header values accepted on a non-loopback bind, such as `mcp.example.com:8080` or `mcp.example.com:*`. |
| `SYNTHFLOW_MCP_ALLOWED_ORIGINS` | unset | Comma-separated `Origin` values accepted on a non-loopback bind, such as `https://client.example.com`. Requests without an `Origin` header are accepted. |

Synthflow credentials come from the same configuration as stdio (see [Configuration](#configuration)), never from the request.

```bash
SYNTHFLOW_MCP_TRANSPORT=streamable-http PORT=8080 uv run --locked synthflow-mcp
```

Point the MCP client at `http://127.0.0.1:8080/mcp`.

## Error handling

A failed tool call returns an MCP error result (`isError`) with a fixed message. The server never passes a Synthflow response body, a request URL, a credential or a rejected input value back to the client.

| Situation | What the tool returns |
| --- | --- |
| Credentials missing | "No Synthflow API key found (SYNTHFLOW_API_KEY). Run synthflow-mcp-setup, then restart the MCP server." |
| Authentication rejected (HTTP 401) | "Synthflow authentication failed. Check the API key and run synthflow-mcp-setup to replace it; restart the MCP server after setup." |
| Access denied (HTTP 403) | "Synthflow access denied: the connected account lacks permission for this action (or the authorization expired; re-run synthflow-mcp-setup if so)." |
| Not found (HTTP 404) | "Synthflow item was not found (HTTP 404)." |
| Rate limited (HTTP 429) | After the retries below: "Synthflow rate limit reached (HTTP 429). Retry after N seconds." |
| Any other HTTP error | "Synthflow API error 500: the service encountered an error." The status varies, and the reason is a fixed phrase such as "the request was rejected" or "the service is temporarily unavailable". |
| Success response that is not valid JSON, or `success: false` | "Synthflow API error 200: the service returned invalid JSON" or "...: the vendor reported that the operation failed". |
| Timeout or connection failure on a read | "Synthflow request timed out. Retry the read when the connection is available." (or "Synthflow connection failed. ..."). |
| Timeout or connection failure on a write | "Synthflow request timed out. The outcome is unknown. Check whether the operation completed before retrying." (or "Synthflow connection failed. ..."). |
| Invalid identifier or empty update | "Invalid argument 'agent_id': use a non-empty plain identifier (ASCII letters, digits, -, _, ., ~); not . or .." or "Supply at least one update field: name, system_prompt, or voice_id." |
| Invalid arguments | A message such as "Invalid argument 'limit': expected integer between 1 and 200." |
| Anything else | "Error executing tool" followed by the tool name, with no detail. |

Every Synthflow request has a 30-second timeout. On HTTP 429 the server waits for the `Retry-After` interval (whole seconds, 10 when the header is missing or unreadable) and retries, up to 3 times per request and 60 seconds of total waiting; if the next wait would exceed what is left, the tool returns the rate-limit message at once. The server does not retry timeouts, connection failures or 5xx responses.

At startup the server exits with a message on stderr and a non-zero status when `SYNTHFLOW_MCP_TRANSPORT` is neither `stdio` nor `streamable-http`, when `PORT` is not an integer, or when `SYNTHFLOW_MCP_HOST` is anything other than exactly `127.0.0.1`, `localhost` or `::1` and `SYNTHFLOW_MCP_ALLOWED_HOSTS` is not set.

## API endpoint

The server sends every request to Synthflow's US regional API, `https://api.us.synthflow.ai/v2`. The endpoint is fixed in the code.

## Updating agents

`update_agent` requires at least one non-empty `name`, `system_prompt`, or
`voice_id`. It uses Synthflow’s documented partial-update PUT endpoint: omitted
parameters stay unchanged. See [Update an agent](https://docs.synthflow.ai/api-reference/platform-api/agents/update-assistant).

## Testing

The test suite runs offline and needs no Synthflow account: every Synthflow API call is answered by a test double for the `requests` session. It covers list limits and paging, path-identifier and update validation, error classification and the retry budget, credential file handling, the setup and verify commands, the stdio server, and the Streamable HTTP transport including the 2026-07-28 wire format, Host and Origin checks and stateless requests.

```bash
uv sync --locked
uv run --locked pytest -q
```

CI runs the suite on every push and pull request to `main`.

The tools follow Synthflow's published API documentation and have not yet been run against a live Synthflow account.

## License

MIT. See [LICENSE](LICENSE).
