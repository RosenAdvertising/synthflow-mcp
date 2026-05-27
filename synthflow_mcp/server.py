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
    """Return current Synthflow account info."""
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
    name: str, system_prompt: str, voice_id: str = "", language: str = "en-US"
) -> str:
    """Create a new Synthflow voice agent."""
    return json.dumps(
        SynthflowClient().create_agent(
            name, system_prompt, voice_id=voice_id, language=language
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
    """Provision a new phone number in Synthflow."""
    return json.dumps(
        SynthflowClient().provision_phone_number(area_code=area_code, country=country),
        indent=2,
    )


@mcp.tool()
def assign_agent_to_number(number_id: str, agent_id: str) -> str:
    """Assign a Synthflow agent to a phone number."""
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
def initiate_call(agent_id: str, to_number: str, from_number: str = "") -> str:
    """Initiate an outbound call using a Synthflow agent."""
    return json.dumps(
        SynthflowClient().initiate_call(agent_id, to_number, from_number=from_number),
        indent=2,
    )


# --- Knowledge Bases ---


@mcp.tool()
def list_knowledge_bases() -> str:
    """List all knowledge bases in Synthflow."""
    return json.dumps(SynthflowClient().list_knowledge_bases(), indent=2)


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


def main():
    mcp.run()


if __name__ == "__main__":
    main()
