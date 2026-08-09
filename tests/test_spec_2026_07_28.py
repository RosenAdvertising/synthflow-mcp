"""Offline conformance regressions for the MCP 2026-07-28 migration."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
from mcp import Client
from mcp.types import LATEST_PROTOCOL_VERSION
from mcp_types.version import MODERN_PROTOCOL_VERSIONS

from synthflow_mcp import client as client_module
from synthflow_mcp import server
from synthflow_mcp.setup import verify


PROTOCOL_VERSION = "2026-07-28"
LEGACY_PROTOCOL_VERSION = "2025-11-25"
PROTOCOL_VERSION_META_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_META_KEY = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_META_KEY = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_META_KEY = "io.modelcontextprotocol/serverInfo"
REPO_ROOT = Path(__file__).resolve().parents[1]
LIST_TOOL_NAMES = (
    "list_agents",
    "list_phone_numbers",
    "list_calls",
    "list_knowledge_bases",
)
EXPECTED_TOOL_NAMES = [
    "who_am_i",
    "list_agents",
    "get_agent",
    "create_agent",
    "update_agent",
    "delete_agent",
    "list_phone_numbers",
    "get_phone_number",
    "provision_phone_number",
    "assign_agent_to_number",
    "list_calls",
    "get_call",
    "get_call_transcript",
    "initiate_call",
    "list_knowledge_bases",
    "create_knowledge_base",
    "get_analytics",
]


def _modern_request(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    protocol_version: str = PROTOCOL_VERSION,
    request_id: int = 1,
) -> tuple[dict[str, str], dict[str, Any]]:
    request_params = dict(params or {})
    request_params["_meta"] = {
        PROTOCOL_VERSION_META_KEY: protocol_version,
        CLIENT_CAPABILITIES_META_KEY: {},
        CLIENT_INFO_META_KEY: {"name": "synthflow-spec-test", "version": "0"},
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "mcp-protocol-version": protocol_version,
        "mcp-method": method,
    }
    if method == "tools/call":
        headers["mcp-name"] = str(request_params["name"])
    elif method == "prompts/get":
        headers["mcp-name"] = str(request_params["name"])
    elif method == "resources/read":
        headers["mcp-name"] = str(request_params["uri"])
    return headers, {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": request_params,
    }


async def _post_modern(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    protocol_version: str = PROTOCOL_VERSION,
    header_overrides: dict[str, str] | None = None,
    drop_headers: tuple[str, ...] = (),
) -> httpx.Response:
    app = server.mcp.streamable_http_app(
        host="0.0.0.0",
        stateless_http=True,
        json_response=True,
    )
    headers, body = _modern_request(
        method,
        params,
        protocol_version=protocol_version,
    )
    if header_overrides:
        headers.update(header_overrides)
    for header in drop_headers:
        headers.pop(header, None)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://spec-test",
        ) as client:
            return await client.post("/mcp", headers=headers, json=body)


def _result(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["jsonrpc"] == "2.0"
    return payload["result"]


def test_spec_guard_pins_the_2026_revision() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tests" / "spec_check.py"), "--mcp-only"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Spec check: PASS" in result.stdout
    assert LATEST_PROTOCOL_VERSION == PROTOCOL_VERSION
    assert MODERN_PROTOCOL_VERSIONS == (PROTOCOL_VERSION,)


def test_modern_discovery_is_sessionless_and_declares_existing_capabilities() -> None:
    response = asyncio.run(_post_modern("server/discover"))
    result = _result(response)

    assert "mcp-session-id" not in response.headers
    assert result["supportedVersions"] == [PROTOCOL_VERSION]
    assert result["resultType"] == "complete"
    assert result["ttlMs"] == 0
    assert result["cacheScope"] == "private"
    assert result["capabilities"] == {
        "prompts": {"listChanged": True},
        "resources": {"listChanged": True, "subscribe": True},
        "tools": {"listChanged": True},
    }
    assert "extensions" not in result["capabilities"]
    assert result["_meta"][SERVER_INFO_META_KEY]["name"] == "synthflow-mcp"


def test_client_defaults_modern_and_keeps_legacy_negotiation() -> None:
    async def negotiate() -> tuple[str, str]:
        async with Client(server.mcp, cache=None) as modern:
            modern_version = modern.protocol_version
        async with Client(server.mcp, mode="legacy", cache=None) as legacy:
            legacy_version = legacy.protocol_version
        return modern_version, legacy_version

    modern_version, legacy_version = asyncio.run(negotiate())
    assert modern_version == PROTOCOL_VERSION
    assert legacy_version == LEGACY_PROTOCOL_VERSION


def test_cacheable_results_are_complete_private_and_deterministic() -> None:
    async def list_results() -> list[dict[str, Any]]:
        methods = (
            "tools/list",
            "tools/list",
            "prompts/list",
            "resources/list",
            "resources/templates/list",
        )
        return [_result(await _post_modern(method)) for method in methods]

    first_tools, second_tools, prompts, resources, templates = asyncio.run(
        list_results()
    )
    for result in (first_tools, second_tools, prompts, resources, templates):
        assert result["resultType"] == "complete"
        assert result["ttlMs"] == 0
        assert result["cacheScope"] == "private"

    first_names = [tool["name"] for tool in first_tools["tools"]]
    second_names = [tool["name"] for tool in second_tools["tools"]]
    assert first_names == EXPECTED_TOOL_NAMES
    assert second_names == EXPECTED_TOOL_NAMES
    assert all(tool["inputSchema"]["type"] == "object" for tool in first_tools["tools"])
    assert [item["name"] for item in prompts["prompts"]] == [
        "setup_offhours_intake_agent",
        "triage_recent_calls",
        "review_agent_performance",
    ]
    assert [item["uri"] for item in resources["resources"]] == [
        "synthflow://agents",
        "synthflow://phone_numbers",
        "synthflow://security-notes",
    ]
    assert templates["resourceTemplates"] == []


def test_list_tool_limits_are_schema_enforced_total_caps(monkeypatch) -> None:
    listed_tools = _result(asyncio.run(_post_modern("tools/list")))["tools"]
    schemas = {tool["name"]: tool["inputSchema"] for tool in listed_tools}
    for name in LIST_TOOL_NAMES:
        limit_schema = schemas[name]["properties"]["limit"]
        assert limit_schema["minimum"] == 1
        assert limit_schema["maximum"] == 200
        assert schemas[name]["properties"]["page"]["minimum"] == 1

    calls: list[tuple[int, int, str]] = []

    class StubSynthflowClient:
        def list_calls(self, page: int, limit: int, agent_id: str) -> dict[str, Any]:
            calls.append((page, limit, agent_id))
            return {"calls": [{"id": number} for number in range(limit)]}

    monkeypatch.setattr(server, "SynthflowClient", StubSynthflowClient)
    response = asyncio.run(
        _post_modern(
            "tools/call",
            {
                "name": "list_calls",
                "arguments": {"page": 2, "limit": 3, "agent_id": "agent-test"},
            },
        )
    )
    result = _result(response)
    assert result["resultType"] == "complete"
    assert result.get("isError", False) is False
    assert calls == [(2, 3, "agent-test")]
    assert len(json.loads(result["content"][0]["text"])["calls"]) == 3

    invalid = asyncio.run(
        _post_modern(
            "tools/call",
            {"name": "list_calls", "arguments": {"limit": 201}},
        )
    )
    invalid_result = _result(invalid)
    assert invalid_result["resultType"] == "complete"
    assert invalid_result["isError"] is True
    assert calls == [(2, 3, "agent-test")]


@pytest.mark.parametrize(
    ("method_name", "path", "extra_args", "extra_params"),
    [
        ("list_agents", "/assistants", {}, {}),
        ("list_phone_numbers", "/numbers", {}, {}),
        (
            "list_calls",
            "/calls",
            {"agent_id": "agent-test"},
            {"model_id": "agent-test"},
        ),
        ("list_knowledge_bases", "/knowledge-bases", {}, {}),
    ],
)
def test_each_vendor_list_method_makes_one_bounded_request(
    monkeypatch,
    method_name: str,
    path: str,
    extra_args: dict[str, str],
    extra_params: dict[str, str],
) -> None:
    monkeypatch.setenv("SYNTHFLOW_API_KEY", "unit-test-secret")
    client = client_module.SynthflowClient()
    requests: list[tuple[str, dict[str, Any]]] = []

    def fake_get(request_path: str, params: dict[str, Any]) -> dict[str, Any]:
        requests.append((request_path, params))
        return {"items": [{"id": number} for number in range(params["limit"])]}

    monkeypatch.setattr(client, "get", fake_get)
    result = getattr(client, method_name)(page=2, limit=7, **extra_args)

    assert requests == [(path, {"page": 2, "limit": 7, **extra_params})]
    assert len(result["items"]) == 7


def test_resource_and_prompt_results_have_modern_shape_and_not_found_code() -> None:
    resource = asyncio.run(
        _post_modern("resources/read", {"uri": "synthflow://security-notes"})
    )
    resource_result = _result(resource)
    assert resource_result["resultType"] == "complete"
    assert resource_result["ttlMs"] == 0
    assert resource_result["cacheScope"] == "private"
    assert "Security Notes" in resource_result["contents"][0]["text"]

    prompt = asyncio.run(
        _post_modern("prompts/get", {"name": "review_agent_performance"})
    )
    assert _result(prompt)["resultType"] == "complete"

    missing = asyncio.run(
        _post_modern("resources/read", {"uri": "synthflow://does-not-exist"})
    )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == -32602


def test_modern_http_sends_protocol_and_requires_method_and_name_headers() -> None:
    headers, _ = _modern_request(
        "tools/call",
        {"name": "list_agents", "arguments": {}},
    )
    assert headers["mcp-protocol-version"] == PROTOCOL_VERSION
    assert headers["mcp-method"] == "tools/call"
    assert headers["mcp-name"] == "list_agents"

    protocol_mismatch = asyncio.run(
        _post_modern(
            "tools/list",
            header_overrides={"mcp-protocol-version": "2099-01-01"},
        )
    )
    assert protocol_mismatch.status_code == 400
    assert protocol_mismatch.json()["error"]["code"] == -32020

    missing_method = asyncio.run(
        _post_modern("tools/list", drop_headers=("mcp-method",))
    )
    assert missing_method.status_code == 400
    assert missing_method.json()["error"]["code"] == -32020

    missing_name = asyncio.run(
        _post_modern(
            "tools/call",
            {"name": "list_agents", "arguments": {}},
            drop_headers=("mcp-name",),
        )
    )
    assert missing_name.status_code == 400
    assert missing_name.json()["error"]["code"] == -32020

    mismatch = asyncio.run(
        _post_modern(
            "tools/list",
            header_overrides={"mcp-method": "resources/list"},
        )
    )
    assert mismatch.status_code == 400
    assert mismatch.json()["error"]["code"] == -32020


def test_modern_http_uses_new_version_and_method_error_codes() -> None:
    unsupported = asyncio.run(_post_modern("tools/list", protocol_version="2099-01-01"))
    assert unsupported.status_code == 400
    assert unsupported.json()["error"] == {
        "code": -32022,
        "message": "Unsupported protocol version",
        "data": {
            "supported": [PROTOCOL_VERSION],
            "requested": "2099-01-01",
        },
    }

    unknown = asyncio.run(_post_modern("example/unknown"))
    assert unknown.status_code == 404
    assert unknown.json()["error"] == {
        "code": -32601,
        "message": "Method not found",
        "data": "example/unknown",
    }


def test_rejection_paths_log_only_pii_free_reasons(monkeypatch, caplog) -> None:
    caplog.set_level(logging.WARNING, logger=client_module.__name__)
    monkeypatch.delenv("SYNTHFLOW_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="No Synthflow API key"):
        client_module.SynthflowClient()
    assert any(
        getattr(record, "event", "") == "synthflow_credentials_missing"
        for record in caplog.records
    )

    caplog.clear()
    monkeypatch.setenv("SYNTHFLOW_API_KEY", "unit-test-secret")
    client = client_module.SynthflowClient()
    response = httpx.Response(
        401,
        text='{"email":"person@example.test","name":"Private Person"}',
    )
    monkeypatch.setattr(client.session, "request", lambda *args, **kwargs: response)
    with pytest.raises(RuntimeError, match="invalid or expired"):
        client.get("/assistants")

    assert any(
        getattr(record, "reason", "") == "unauthorized" for record in caplog.records
    )
    rendered_logs = caplog.text
    assert "unit-test-secret" not in rendered_logs
    assert "person@example.test" not in rendered_logs
    assert "Private Person" not in rendered_logs


def test_vendor_errors_and_verification_output_do_not_echo_pii(
    monkeypatch, caplog, capsys
) -> None:
    caplog.set_level(logging.WARNING)
    monkeypatch.setenv("SYNTHFLOW_API_KEY", "unit-test-secret")
    client = client_module.SynthflowClient()
    response = client_module.requests.Response()
    response.status_code = 500
    response._content = b'{"email":"person@example.test","name":"Private Person"}'
    monkeypatch.setattr(client.session, "request", lambda *args, **kwargs: response)

    with pytest.raises(RuntimeError, match="Synthflow API error 500") as caught:
        client.get("/assistants")
    assert "person@example.test" not in str(caught.value)
    assert "Private Person" not in str(caught.value)

    class StubSynthflowClient:
        def who_am_i(self) -> dict[str, str]:
            return {"email": "person@example.test", "name": "Private Person"}

    monkeypatch.setattr(client_module, "SynthflowClient", StubSynthflowClient)
    verify.main()
    output = capsys.readouterr().out
    assert "Account identity verified." in output
    assert "person@example.test" not in output
    assert "Private Person" not in output
    assert "unit-test-secret" not in caplog.text
    assert "person@example.test" not in caplog.text
    assert "Private Person" not in caplog.text
