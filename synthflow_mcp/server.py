#!/usr/bin/env python3
"""Synthflow MCP Server — voice agent management, calls, transcripts, phone numbers."""

import json
from mcp.server.fastmcp import FastMCP
from .client import SynthflowClient

mcp = FastMCP(
    "synthflow-mcp",
    instructions="Full access to Synthflow Voice AI: manage agents, phone numbers, calls, transcripts, knowledge bases, and analytics.",
)


# --- Account ---


@mcp.tool()
def who_am_i() -> str:
    """Return Synthflow account analytics and usage summary."""
    return json.dumps(SynthflowClient().who_am_i(), indent=2)


# --- Agents ---


@mcp.tool()
def list_agents(page: int = 1, limit: int = 25) -> str:
    """List all Synthflow voice agents."""
    return json.dumps(SynthflowClient().list_agents(page=page, limit=limit), indent=2)


@mcp.tool()
def get_agent(agent_id: str) -> str:
    """Get details for a specific Synthflow agent by ID."""
    return json.dumps(SynthflowClient().get_agent(agent_id), indent=2)


@mcp.tool()
def create_agent(
    name: str,
    system_prompt: str,
    agent_type: str = "outbound",
    voice_id: str = "",
    language: str = "en-US",
    greeting_message: str = "Hello, how can I help you?",
    llm: str = "gpt-4.1",
) -> str:
    """Create a new Synthflow voice agent. agent_type: outbound | inbound | widget."""
    return json.dumps(
        SynthflowClient().create_agent(
            name,
            system_prompt,
            agent_type=agent_type,
            voice_id=voice_id,
            language=language,
            greeting_message=greeting_message,
            llm=llm,
        ),
        indent=2,
    )


@mcp.tool()
def update_agent(
    agent_id: str, name: str = "", system_prompt: str = "", voice_id: str = ""
) -> str:
    """Update an existing Synthflow agent's name, prompt, or voice."""
    return json.dumps(
        SynthflowClient().update_agent(
            agent_id, name=name, system_prompt=system_prompt, voice_id=voice_id
        ),
        indent=2,
    )


@mcp.tool()
def delete_agent(agent_id: str) -> str:
    """Delete a Synthflow agent by ID."""
    return json.dumps(SynthflowClient().delete_agent(agent_id), indent=2)


# --- Phone Numbers ---


@mcp.tool()
def list_phone_numbers(page: int = 1, limit: int = 25) -> str:
    """List all provisioned Synthflow phone numbers."""
    return json.dumps(
        SynthflowClient().list_phone_numbers(page=page, limit=limit), indent=2
    )


@mcp.tool()
def get_phone_number(number_id: str) -> str:
    """Get details for a specific Synthflow phone number by ID."""
    return json.dumps(SynthflowClient().get_phone_number(number_id), indent=2)


@mcp.tool()
def provision_phone_number(area_code: str = "", country: str = "US") -> str:
    """Create and provision a new phone number in Synthflow."""
    return json.dumps(
        SynthflowClient().provision_phone_number(area_code=area_code, country=country),
        indent=2,
    )


@mcp.tool()
def assign_agent_to_number(number_id: str, agent_id: str) -> str:
    """Update a phone number to assign a specific Synthflow agent to it."""
    return json.dumps(
        SynthflowClient().assign_agent_to_number(number_id, agent_id), indent=2
    )


# --- Calls ---


@mcp.tool()
def list_calls(page: int = 1, limit: int = 25, agent_id: str = "") -> str:
    """List calls, optionally filtered by agent ID."""
    return json.dumps(
        SynthflowClient().list_calls(page=page, limit=limit, agent_id=agent_id),
        indent=2,
    )


@mcp.tool()
def get_call(call_id: str) -> str:
    """Get details for a specific Synthflow call by ID."""
    return json.dumps(SynthflowClient().get_call(call_id), indent=2)


@mcp.tool()
def get_call_transcript(call_id: str) -> str:
    """Get the full transcript for a Synthflow call."""
    return json.dumps(SynthflowClient().get_call_transcript(call_id), indent=2)


@mcp.tool()
def initiate_call(
    agent_id: str, to_number: str, name: str = "", from_number: str = ""
) -> str:
    """Create and initiate an outbound call using a Synthflow agent. name is the recipient's name."""
    return json.dumps(
        SynthflowClient().initiate_call(
            agent_id, to_number, name=name, from_number=from_number
        ),
        indent=2,
    )


# --- Knowledge Bases ---


@mcp.tool()
def list_knowledge_bases(page: int = 1, limit: int = 25) -> str:
    """List all knowledge bases in Synthflow."""
    return json.dumps(
        SynthflowClient().list_knowledge_bases(page=page, limit=limit), indent=2
    )


@mcp.tool()
def create_knowledge_base(name: str, content: str) -> str:
    """Create a new knowledge base in Synthflow."""
    return json.dumps(SynthflowClient().create_knowledge_base(name, content), indent=2)


# --- Analytics ---


@mcp.tool()
def get_analytics(start_date: str = "", end_date: str = "") -> str:
    """Get Synthflow analytics, optionally filtered by date range (YYYY-MM-DD)."""
    return json.dumps(
        SynthflowClient().get_analytics(start_date=start_date, end_date=end_date),
        indent=2,
    )


# ── Resources ─────────────────────────────────────────────────────────────────


@mcp.resource("synthflow://agents", mime_type="application/json")
def agents_resource() -> str:
    """All Synthflow voice agents configured in this account — read-only reference data."""
    return json.dumps(SynthflowClient().list_agents(page=1, limit=100), indent=2)


@mcp.resource("synthflow://phone_numbers", mime_type="application/json")
def phone_numbers_resource() -> str:
    """All provisioned Synthflow phone numbers — read-only reference data."""
    return json.dumps(SynthflowClient().list_phone_numbers(page=1, limit=100), indent=2)


@mcp.resource("synthflow://security-notes", mime_type="text/markdown")
def security_notes_resource() -> str:
    """Security posture and injection-risk guidance for the Synthflow MCP server."""
    return """# Synthflow MCP — Security Notes

## Agent prompt injection surface

The `system_prompt` field passed to `create_agent` and `update_agent` is transmitted
verbatim to Synthflow and becomes the live instruction set for a voice agent that speaks
directly to real callers (law-firm intake, after-hours answering). Any third-party content
placed into agent instructions — e.g. content drawn from a web search, an external
knowledge base, or caller-supplied text — is an **injection surface**.

Mitigations:
- Treat all caller-supplied content as untrusted input; never echo it back into a
  `system_prompt` or knowledge-base entry without sanitisation.
- Review `create_agent` / `update_agent` calls before executing them; prompt changes
  to production agents should be treated as code deploys.
- Restrict who or what can call `create_agent` / `update_agent` in your MCP client
  configuration.

## PII and call recordings

Legal intake calls may carry protected personal information (names, case details,
medical/financial data). Call transcripts retrieved via `get_call_transcript` should be:
- Stored only in systems that meet the firm's data-retention policy.
- Not logged to general-purpose observability pipelines without redaction.
- Treated as attorney-client privileged where applicable.

## API key scope

`SYNTHFLOW_API_KEY` grants full account access (agents, calls, knowledge bases,
phone numbers). Store it in the OS keyring or a secrets manager — never in source
code, `.env` files committed to version control, or plain-text logs.

## Rate limiting

Synthflow enforces per-account rate limits. The client retries up to 3 times on 429s.
Automated pipelines that enumerate calls or transcripts should add explicit pacing to
avoid exhausting the retry budget for interactive sessions.
"""


# ── Prompts ───────────────────────────────────────────────────────────────────


@mcp.prompt()
def setup_offhours_intake_agent() -> str:
    """Step-by-step guide to configure a Synthflow inbound agent for law-firm off-hours intake."""
    return """You are configuring a Synthflow voice agent for after-hours legal intake.
Follow these steps using the synthflow-mcp tools:

1. **Inventory existing agents** — call list_agents and note any existing intake agents
   to avoid duplicates and to reuse voice IDs or greeting patterns.

2. **Check provisioned numbers** — call list_phone_numbers to see which numbers are
   available and whether any are already assigned to an intake agent.

3. **Create or update the intake knowledge base** — call create_knowledge_base with
   the firm's practice areas, intake questions (name, case type, urgency), and escalation
   instructions (e.g. "If caller mentions injury or accident, flag as urgent").

4. **Create the agent** — call create_agent with:
   - agent_type: "inbound"
   - system_prompt: Include the firm name, the intake questions to ask, instructions to
     collect caller name + phone + brief case description, and a closing statement that
     the attorney will call back within one business day.
   - greeting_message: "Thank you for calling [Firm Name]. Our office is currently closed.
     I can take a message and have an attorney contact you. May I have your name?"
   - language: match the firm's primary client base (e.g. "en-US" or "es-US")

5. **Assign the agent to the intake number** — call assign_agent_to_number with the
   chosen number_id and the new agent's ID.

6. **Verify** — call get_agent and get_phone_number to confirm the assignment is live.

Security reminder: the system_prompt reaches live callers — do not include internal
escalation paths, pricing, or confidential firm procedures in the prompt text."""


@mcp.prompt()
def triage_recent_calls(agent_id: str) -> str:
    """Review and triage recent calls for a Synthflow intake agent."""
    return f"""Triage recent calls for Synthflow agent {agent_id}.

1. Call list_calls with agent_id="{agent_id}" and limit=50 to fetch recent calls.
2. For each call, call get_call to retrieve duration, status, and caller metadata.
3. For calls longer than 60 seconds, call get_call_transcript to read the conversation.
4. Classify each call:
   - HOT LEAD: caller described a legal matter and left contact details
   - CALLBACK NEEDED: caller was cut off, unclear outcome, or expressed urgency
   - INFO ONLY: caller asked a general question, no intake needed
   - WRONG NUMBER / SPAM: irrelevant call
5. Produce a triage list ordered by priority (HOT LEAD first), with one line per call:
   call_id | duration | classification | key detail (e.g. case type or caller name if given)
6. Flag any call where PII (full name + phone number) was captured — those transcripts
   should be handled according to the firm's data-retention policy."""


@mcp.prompt()
def review_agent_performance() -> str:
    """Analyse Synthflow analytics to assess agent effectiveness and call quality."""
    return """Review Synthflow agent performance using analytics and call data.

1. Call get_analytics (no date filter) to get the baseline account-level summary.
2. Call list_agents to enumerate all active agents.
3. For each agent:
   a. Call list_calls with agent_id and limit=100 to count recent call volume.
   b. Sample 5–10 transcripts via get_call_transcript to assess call quality:
      - Did the agent collect required intake fields (name, phone, case type)?
      - Were there long silences, repeated misunderstandings, or early hang-ups?
      - Did the agent follow its system_prompt greeting and closing exactly?
4. Flag agents that show:
   - High short-call rate (< 30s) — likely caller hang-ups
   - Missing intake fields in transcripts — prompt may need tightening
   - Repeated misunderstanding loops — knowledge base may be incomplete
5. Recommend: keep as-is / update prompt / update knowledge base / replace agent.
   For any recommended prompt change, draft the revised system_prompt text."""


def main():
    mcp.run()


if __name__ == "__main__":
    main()
