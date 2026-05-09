# synthflow-mcp

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

`synthflow-mcp-setup` prompts for your API key and saves it to `~/.synthflow-mcp/.env` (mode 600).

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

| Tool | Description |
|---|---|
| `who_am_i` | Current account info |
| `list_agents` | List all voice agents |
| `get_agent` | Get agent by ID |
| `create_agent` | Create a new agent |
| `update_agent` | Update agent name/prompt/voice |
| `delete_agent` | Delete an agent |
| `list_phone_numbers` | List provisioned numbers |
| `get_phone_number` | Get number by ID |
| `provision_phone_number` | Provision a new number |
| `assign_agent_to_number` | Assign agent to a phone number |
| `list_calls` | List calls (optional agent filter) |
| `get_call` | Get call by ID |
| `get_call_transcript` | Get full transcript for a call |
| `initiate_call` | Trigger an outbound call |
| `list_knowledge_bases` | List knowledge bases |
| `create_knowledge_base` | Create a knowledge base |
| `get_analytics` | Get analytics (optional date range) |

## Configuration

API key is stored at `~/.synthflow-mcp/.env`:

```
SYNTHFLOW_API_KEY=your_api_key_here
```

The server loads this file automatically on startup. To update the key, re-run `synthflow-mcp-setup` or edit the file directly.
