from pathlib import Path

from mcp_test_kit.config import (
    ResilienceConfig,
    SpecCheckConfig,
    SmokeConfig,
    ToolkitConfig,
    WriteConfig,
    WriteStep,
)
from synthflow_mcp.server import mcp

_TESTS_DIR = Path(__file__).parent

TOOLKIT = ToolkitConfig(
    mcp_server=mcp,
    spec_check=SpecCheckConfig(
        endpoints_path=_TESTS_DIR.parent / "endpoints.yaml",
        openapi_path=_TESTS_DIR.parent
        / "endpoints.yaml",  # dummy — contract tier skipped
    ),
    source_path=_TESTS_DIR.parent / "synthflow_mcp",
    module_path="synthflow_mcp",
    server_path=_TESTS_DIR.parent / "synthflow_mcp" / "server.py",
    resilience=ResilienceConfig(tools_to_timeout_test=["who_am_i"]),
    skip_tiers={
        "contract": "no published OpenAPI spec for Synthflow API",
    },
    smoke=SmokeConfig(
        server=mcp,
        # Zero-arg read probes against live API (US regional endpoint).
        # list_calls excluded — requires model_id param (not zero-arg).
        read_tools=["who_am_i", "list_agents", "list_phone_numbers"],
    ),
    write=WriteConfig(
        server=mcp,
        # who_am_i returns account analytics — sufficient identity signal.
        identity_tool="who_am_i",
        steps=[
            # Agent CRUD — fully reversible, no lingering state.
            WriteStep(
                tool="create_agent",
                args={
                    "name": "mcp_test_kit_probe",
                    "system_prompt": "[mcp-test-kit write test — delete immediately]",
                    "agent_type": "outbound",
                    "greeting_message": "Hello",
                    "llm": "gpt-4.1",
                    "language": "en-US",
                },
                state_key="agent_id",
                # Synthflow returns {"status":"ok","response":{"model_id":"..."}}
                extract=lambda r: r.get("response", {}).get("model_id"),
            ),
            WriteStep(
                tool="delete_agent",
                args=lambda s: {"agent_id": s["agent_id"]},
                skip_if_missing="agent_id",
                cleanup=True,
            ),
        ],
    ),
)
