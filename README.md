# synthflow-mcp

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-F59E0B.svg)](https://opensource.org/licenses/MIT)
[![17 tools](https://img.shields.io/badge/tools-17-22C55E.svg)](https://github.com/RosenAdvertising/synthflow-mcp)
[![MCP](https://img.shields.io/badge/MCP-compatible-7C3AED.svg)](https://modelcontextprotocol.io)
[![Synthflow](https://img.shields.io/badge/Synthflow-Voice%20AI-FF6B35.svg)](https://synthflow.ai)

MCP server for [Synthflow Voice AI](https://synthflow.ai). Manage agents, phone numbers, calls, transcripts, knowledge bases, and analytics directly from Claude Desktop or any MCP-compatible client.

## Requirements

- Python 3.10+
- A Synthflow account with an API key (Settings → API)

## Install

```bash
pip install .
synthflow-mcp-setup
synthflow-mcp-verify
```

`synthflow-mcp-setup` prompts for your API key and saves it to your OS keyring
(see [Configuration](#configuration)).

`synthflow-mcp-verify` confirms the key is valid and the server can connect.

## Claude Desktop Config

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "synthflow": {
      "command": "synthflow-mcp"
    }
  }
}
```

Restart Claude Desktop after saving.

## Tools (17)

| Tool                     | Description                         |
| ------------------------ | ----------------------------------- |
| `who_am_i`               | Current account info                |
| `list_agents`            | List all voice agents               |
| `get_agent`              | Get agent by ID                     |
| `create_agent`           | Create a new agent                  |
| `update_agent`           | Update agent name/prompt/voice      |
| `delete_agent`           | Delete an agent                     |
| `list_phone_numbers`     | List provisioned numbers            |
| `get_phone_number`       | Get number by ID                    |
| `provision_phone_number` | Provision a new number              |
| `assign_agent_to_number` | Assign agent to a phone number      |
| `list_calls`             | List calls (optional agent filter)  |
| `get_call`               | Get call by ID                      |
| `get_call_transcript`    | Get full transcript for a call      |
| `initiate_call`          | Trigger an outbound call            |
| `list_knowledge_bases`   | List knowledge bases                |
| `create_knowledge_base`  | Create a knowledge base             |
| `get_analytics`          | Get analytics (optional date range) |

## Configuration

By default your API key (`SYNTHFLOW_API_KEY`) is stored in your operating
system's native secret store via the cross-platform
[`keyring`](https://github.com/jaraco/keyring) library:

| OS      | Backend                                  |
| ------- | ---------------------------------------- |
| macOS   | Keychain                                 |
| Windows | Credential Manager                       |
| Linux   | Secret Service (GNOME Keyring / KWallet) |

The secret is saved under the service name `synthflow-mcp`. Nothing is written
to disk in clear text. To update the key, re-run `synthflow-mcp-setup`.

**File fallback.** On a host with no keyring backend (e.g. a headless Linux box
without Secret Service), or if you set `SYNTHFLOW_MCP_USE_KEYRING=0`, the key
falls back to a `~/.synthflow-mcp/.env` file with `0600` permissions:

```bash
SYNTHFLOW_API_KEY=your_api_key_here
```

**Read order.** Values resolve in the order OS keyring → process environment →
`.env` file. So a rotated key in the keyring always wins, and a value exported in
your shell overrides the file fallback without touching the keyring.

**Pluggable backend.** `keyring` lets you point at any secret store. For example,
install [`keyrings.cryptfile`](https://pypi.org/project/keyrings.cryptfile/) for
an encrypted file backend, or a cloud backend, then select it with the standard
`PYTHON_KEYRING_BACKEND` environment variable or a `keyringrc.cfg`. See the
[keyring configuration docs](https://github.com/jaraco/keyring#configuring).
