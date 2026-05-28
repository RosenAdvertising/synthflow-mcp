#!/usr/bin/env python3
"""
Phase 0 data seed for the Synthflow developer account.

Creates 3 law-firm-representative voice agents tagged [SEED].
These give smoke and write tiers a populated account to work against.

Prerequisites:
  1. Add Synthflow API key to ~/.synthflow-mcp/.env:
       echo "SYNTHFLOW_API_KEY=$(op read 'op://Cowork/synthflow-dev-account/credential')" \
           >> ~/.synthflow-mcp/.env

  2. Run the seed:
       python tests/seed_data.py

Usage:
    python tests/seed_data.py            # create seed agents
    python tests/seed_data.py --reset    # wipe existing seed agents, then re-create
    python tests/seed_data.py --wipe     # wipe only (no re-create)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from synthflow_mcp.client import SynthflowClient

SEED_TAG = "[SEED]"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _extract_id(resp: dict, label: str) -> str | None:
    """Extract model_id from a Synthflow create response; print status."""
    model_id = (
        resp.get("response", {}).get("model_id")
        if isinstance(resp.get("response"), dict)
        else None
    )
    if not model_id:
        err = resp.get("message") or resp.get("error") or str(resp)[:200]
        print(f"  ✗  {label} — {err}", file=sys.stderr)
        return None
    print(f"  ✓  {label}  (id={model_id})")
    return model_id


def _list_all_agents(client: SynthflowClient) -> list[dict]:
    """Page through /assistants and return every agent."""
    agents: list[dict] = []
    page = 1
    while True:
        resp = client.list_agents(page=page, limit=100)
        batch = resp.get("response") or []
        if not isinstance(batch, list):
            batch = []
        agents.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return agents


# ── Seed ──────────────────────────────────────────────────────────────────────


def seed(client: SynthflowClient) -> list[str]:
    """Create 3 law-firm voice agents tagged [SEED]. Returns list of created IDs."""
    created: list[str] = []
    print("\n── Agents ─────────────────────────────────────────")

    agents_to_create = [
        dict(
            name=f"{SEED_TAG} Intake Specialist — Rivera & Associates",
            system_prompt=(
                "You are an intake specialist for Rivera & Associates, a personal injury law firm. "
                "Gather the caller's name, phone number, and a brief description of their accident. "
                "Be empathetic, professional, and collect enough information for a callback. "
                "Never provide legal advice — always route to an attorney for substantive questions."
            ),
            agent_type="inbound",
            greeting_message=(
                "Thank you for calling Rivera and Associates. My name is Alex. "
                "How can I help you today?"
            ),
            language="en-US",
            llm="gpt-4.1",
        ),
        dict(
            name=f"{SEED_TAG} Outbound Callback — Hartley Family Law",
            system_prompt=(
                "You are a callback agent for Hartley Family Law. "
                "You are following up on a web inquiry about divorce or custody services. "
                "Confirm the caller's availability, answer basic questions about the firm's process, "
                "and schedule a free 30-minute consultation if the caller is interested."
            ),
            agent_type="outbound",
            greeting_message=(
                "Hello, this is Jordan calling from Hartley Family Law. "
                "You recently reached out to us about our services. Is this a good time to talk?"
            ),
            language="en-US",
            llm="gpt-4.1",
        ),
        dict(
            name=f"{SEED_TAG} After-Hours Voicemail — Webb Criminal Defense",
            system_prompt=(
                "You are an after-hours answering agent for Webb Criminal Defense. "
                "The office is currently closed. Collect the caller's name, phone number, "
                "and a brief description of their situation. Assure them that an attorney "
                "will return their call within 24 hours. For emergencies, advise them to "
                "call the 24-hour emergency line at 555-0100."
            ),
            agent_type="inbound",
            greeting_message=(
                "You have reached Webb Criminal Defense after-hours line. "
                "I can take your message and ensure an attorney returns your call. "
                "What is your name?"
            ),
            language="en-US",
            llm="gpt-4.1",
        ),
    ]

    for cfg in agents_to_create:
        try:
            resp = client.create_agent(**cfg)
            agent_id = _extract_id(resp, cfg["name"])
            if agent_id:
                created.append(agent_id)
        except Exception as exc:
            print(f"  ✗  {cfg['name']} — {exc}", file=sys.stderr)

    return created


# ── Wipe ──────────────────────────────────────────────────────────────────────


def wipe(client: SynthflowClient) -> None:
    """Delete all agents whose name contains [SEED]."""
    print(f"\nWiping '{SEED_TAG}' seed agents...")
    agents = _list_all_agents(client)
    deleted = 0
    for agent in agents:
        name = agent.get("name") or ""
        agent_id = agent.get("model_id") or agent.get("id") or ""
        if SEED_TAG in name and agent_id:
            try:
                client.delete_agent(agent_id)
                print(f"  deleted agent {agent_id} ({name})")
                deleted += 1
            except Exception as exc:
                print(
                    f"  ✗  failed to delete {agent_id} ({name}): {exc}", file=sys.stderr
                )
    if deleted == 0:
        print("  (no seed agents found)")
    print("Wipe complete.\n")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the Synthflow developer account with representative voice agents."
    )
    parser.add_argument(
        "--reset", action="store_true", help="Wipe seed agents then re-create"
    )
    parser.add_argument(
        "--wipe", action="store_true", help="Wipe seed agents only (no re-create)"
    )
    args = parser.parse_args()

    try:
        client = SynthflowClient()
    except RuntimeError as exc:
        print(f"Auth error: {exc}", file=sys.stderr)
        sys.exit(1)

    # Identity check — confirm which account we're seeding before touching anything.
    try:
        acct = client.who_am_i()
        # who_am_i returns analytics; print something meaningful
        calls = acct.get("response", {})
        total = calls.get("total_calls") if isinstance(calls, dict) else "?"
        print(f"Authenticated — Synthflow account (total_calls={total})")
    except Exception as exc:
        print(f"Auth check failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.wipe or args.reset:
        wipe(client)
    if not args.wipe:
        created = seed(client)
        print(f"\nSeed complete — {len(created)} agent(s) created.")
        print("\nNext step:")
        print(
            "  SEED_CONFIRMED=1 mcp-test-kit run --tier smoke --config tests/config.py"
        )


if __name__ == "__main__":
    main()
