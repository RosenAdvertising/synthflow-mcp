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
from requests.adapters import BaseAdapter
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError
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
    with pytest.raises(RuntimeError, match="Synthflow authentication failed"):
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


def test_tool_errors_are_actionable_through_in_memory_sdk(monkeypatch, caplog) -> None:
    async def call(name: str, arguments: dict[str, Any] | None = None):
        async with Client(server.mcp, cache=None) as client:
            return await client.call_tool(name, arguments or {})

    monkeypatch.delenv("SYNTHFLOW_API_KEY", raising=False)
    missing = asyncio.run(call("who_am_i"))
    assert missing.is_error is True
    assert _tool_text(missing) == (
        "No Synthflow API key found (SYNTHFLOW_API_KEY). Run "
        "synthflow-mcp-setup, then restart the MCP server."
    )

    monkeypatch.setenv("SYNTHFLOW_API_KEY", "dummy-test-token")
    client = client_module.SynthflowClient()
    monkeypatch.setattr(
        client.session,
        "request",
        lambda *args, **kwargs: httpx.Response(401),
    )
    monkeypatch.setattr(server, "SynthflowClient", lambda: client)
    auth = asyncio.run(call("who_am_i"))
    assert auth.is_error is True
    assert _tool_text(auth) == (
        "Synthflow authentication failed. Check the API key and run "
        "synthflow-mcp-setup to replace it; restart the MCP server after setup."
    )

    forbidden = client_module.requests.Response()
    forbidden.status_code = 403
    monkeypatch.setattr(client.session, "request", lambda *a, **k: forbidden)
    denied = asyncio.run(call("who_am_i"))
    assert denied.is_error is True
    assert _tool_text(denied) == (
        "Synthflow access denied: the connected account lacks permission for "
        "this action (or the authorization expired; re-run "
        "synthflow-mcp-setup if so)."
    )

    cases = [
        (
            429,
            {"Retry-After": "999999999999999999999"},
            "Synthflow rate limit reached (HTTP 429). Retry after 999999999999999999999 seconds.",
        ),
        (
            429,
            {"Retry-After": "https://secret.example/token?name=Private Person"},
            "Synthflow rate limit reached (HTTP 429). Retry after 10 seconds.",
        ),
        (404, {}, "Synthflow item was not found (HTTP 404)."),
        (500, {}, "Synthflow API error 500: the service encountered an error"),
        (418, {}, "Synthflow API error 418: the service rejected the request"),
    ]
    monkeypatch.setattr(client_module.time, "sleep", lambda _seconds: None)
    for status, headers, expected in cases:
        response = client_module.requests.Response()
        response.status_code = status
        response.headers.update(headers)
        response._content = (
            b'{"token":"dummy-test-token","name":"Private Person",'
            b'"email":"person@example.test","url":"https://secret.example/key"}'
        )
        monkeypatch.setattr(client.session, "request", lambda *a, _r=response, **k: _r)
        result = asyncio.run(call("who_am_i"))
        assert result.is_error is True
        assert _tool_text(result) == expected
        for private in (
            "dummy-test-token",
            "Private Person",
            "person@example.test",
            "secret.example",
        ):
            assert private not in _tool_text(result)

    caplog.set_level(logging.WARNING, logger=server.__name__)
    for error_type in (RuntimeError, ValueError, TypeError):
        monkeypatch.setattr(
            server,
            "SynthflowClient",
            lambda error_type=error_type: type(
                "FailingClient",
                (),
                {
                    "who_am_i": lambda self: (_ for _ in ()).throw(
                        error_type("private token https://user:pass@example.test/ Bob")
                    )
                },
            )(),
        )
        unknown = asyncio.run(call("who_am_i"))
        assert unknown.is_error is True
        assert _tool_text(unknown) == "Error executing tool who_am_i"
    assert "private token" not in caplog.text
    assert "example.test" not in caplog.text
    assert "Bob" not in caplog.text

    class ToolErrorClient:
        def who_am_i(self):
            raise ToolError("leaked token and PII")

    monkeypatch.setattr(server, "SynthflowClient", ToolErrorClient)
    anticipated_unknown = asyncio.run(call("who_am_i"))
    assert anticipated_unknown.is_error is True
    assert _tool_text(anticipated_unknown) == "Error executing tool who_am_i"
    assert "leaked token and PII" not in caplog.text


def test_validation_error_through_sdk_uses_field_and_expected_shape(
    monkeypatch,
) -> None:
    called = False

    class StubSynthflowClient:
        def list_agents(self, **kwargs):
            nonlocal called
            called = True
            return {}

    monkeypatch.setattr(server, "SynthflowClient", StubSynthflowClient)
    result = asyncio.run(
        _tool_result("list_agents", {"limit": 999, "agent_id": "private-value"})
    )
    assert result.is_error is True
    assert (
        _tool_text(result)
        == "Invalid argument 'limit': expected integer between 1 and 200."
    )
    assert "999" not in _tool_text(result)
    assert "private-value" not in _tool_text(result)
    assert called is False


def _tool_text(result: Any) -> str:
    return str(result.content[0].model_dump()["text"])


async def _tool_result(name: str, arguments: dict[str, Any]):
    async with Client(server.mcp, cache=None) as client:
        return await client.call_tool(name, arguments)


@pytest.mark.parametrize(
    ("tool", "arguments", "expected"),
    [
        ("get_agent", {}, "Invalid argument 'agent_id': expected required string."),
        (
            "get_call",
            {"call_id": {"private@example.invalid": "secret"}},
            "Invalid argument 'call_id': expected string.",
        ),
        (
            "list_agents",
            {"page": "private@example.invalid"},
            "Invalid argument 'page': expected integer of at least 1.",
        ),
    ],
)
def test_validation_shapes_come_from_registered_schema(tool, arguments, expected):
    result = asyncio.run(_tool_result(tool, arguments))
    assert result.is_error
    assert _tool_text(result) == expected


def test_recognized_vendor_code_excludes_private_response_data(monkeypatch, caplog):
    monkeypatch.setenv("SYNTHFLOW_API_KEY", "unused")
    instance = client_module.SynthflowClient()
    response = client_module.requests.Response()
    response.status_code = 400
    response._content = b'{"error":{"code":"invalid_request","message":"private@example.invalid token=FAKE"}}'
    monkeypatch.setattr(instance.session, "request", lambda *_args, **_kwargs: response)
    monkeypatch.setattr(server, "SynthflowClient", lambda: instance)
    result = asyncio.run(_tool_result("who_am_i", {}))
    assert result.is_error
    assert _tool_text(result) == "Synthflow API error 400: invalid request"
    assert "private@example.invalid" not in caplog.text
    assert "token=FAKE" not in caplog.text


def test_unexpected_pydantic_error_remains_masked(monkeypatch, caplog):
    from pydantic import ValidationError

    failure = ValidationError.from_exception_data(
        "Vendor",
        [
            {
                "type": "string_type",
                "loc": ("private@example.invalid",),
                "input": "secret",
            }
        ],
    )

    def fail():
        raise failure

    monkeypatch.setattr(server, "SynthflowClient", fail)
    caplog.set_level(logging.WARNING)
    result = asyncio.run(_tool_result("who_am_i", {}))
    assert result.is_error
    assert _tool_text(result) == "Error executing tool who_am_i"
    assert "private@example.invalid" not in caplog.text


@pytest.mark.parametrize(
    ("tool", "arguments", "kind", "expected"),
    [
        (
            "who_am_i",
            {},
            "timeout",
            "Synthflow request timed out. Retry the read when the connection is available.",
        ),
        (
            "who_am_i",
            {},
            "connection",
            "Synthflow connection failed. Retry the read when the connection is available.",
        ),
        (
            "initiate_call",
            {"agent_id": "a", "to_number": "+15555550123"},
            "timeout",
            "Synthflow request timed out. The outcome is unknown. Check whether the operation completed before retrying.",
        ),
        (
            "initiate_call",
            {"agent_id": "a", "to_number": "+15555550123"},
            "connection",
            "Synthflow connection failed. The outcome is unknown. Check whether the operation completed before retrying.",
        ),
    ],
)
def test_transport_failures_are_safe_and_method_aware_through_dispatch(
    monkeypatch, tool, arguments, kind, expected
):
    monkeypatch.setenv("SYNTHFLOW_API_KEY", "fake-secret")
    instance = client_module.SynthflowClient()
    exception = (
        client_module.requests.Timeout("private URL and key")
        if kind == "timeout"
        else client_module.requests.ConnectionError("private URL and key")
    )

    def fail(*_args, **_kwargs):
        raise exception

    monkeypatch.setattr(instance.session, "request", fail)
    monkeypatch.setattr(server, "SynthflowClient", lambda: instance)
    result = asyncio.run(_tool_result(tool, arguments))
    assert result.is_error is True
    assert _tool_text(result) == expected
    assert "private URL" not in _tool_text(result)


def test_request_timeout_and_retry_after_total_budget(monkeypatch):
    monkeypatch.setenv("SYNTHFLOW_API_KEY", "fake-secret")
    client = client_module.SynthflowClient()
    calls: list[dict[str, Any]] = []
    waits: list[int] = []
    responses = []
    for hint in ("40", "30"):
        response = client_module.requests.Response()
        response.status_code = 429
        response.headers["Retry-After"] = hint
        responses.append(response)

    def request(*_args, **kwargs):
        calls.append(kwargs)
        return responses.pop(0)

    monkeypatch.setattr(client.session, "request", request)
    monkeypatch.setattr(client_module.time, "sleep", waits.append)
    monkeypatch.setattr(server, "SynthflowClient", lambda: client)
    result = asyncio.run(_tool_result("who_am_i", {}))
    assert result.is_error is True
    assert _tool_text(result) == (
        "Synthflow rate limit reached (HTTP 429). Retry after 30 seconds."
    )
    assert waits == [40]
    assert len(calls) == 2
    assert all(call["timeout"] == 30 for call in calls)


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("get_agent", "../x", "/assistants/..%2Fx"),
        ("delete_agent", "../x", "/assistants/..%2Fx"),
        ("get_call_transcript", "../x", "/calls/..%2Fx/transcript"),
    ],
)
def test_string_ids_are_quoted_within_their_path_segment(
    monkeypatch, method, path, expected
):
    monkeypatch.setenv("SYNTHFLOW_API_KEY", "fake-secret")
    client = client_module.SynthflowClient()
    seen: list[str] = []

    class CaptureAdapter(BaseAdapter):
        def send(self, request, **kwargs):
            seen.append(request.url)
            response = client_module.requests.Response()
            response.status_code = 200
            response._content = b"{}"
            response.request = request
            return response

        def close(self):
            pass

    client.session.mount("https://", CaptureAdapter())

    getattr(client, method)(path)
    assert seen == [client_module.BASE_URL + expected]


def test_setup_and_verify_fail_cleanly_without_credentials_or_with_bad_key(
    monkeypatch, capsys
):
    monkeypatch.delenv("SYNTHFLOW_API_KEY", raising=False)
    with pytest.raises(SystemExit) as missing_exit:
        verify.main()
    assert missing_exit.value.code == 1
    verify_output = capsys.readouterr().out
    assert verify_output == (
        "Error: unable to verify the Synthflow connection.\n"
        "Run synthflow-mcp-setup to configure your API key.\n"
    )

    monkeypatch.setattr(
        "synthflow_mcp.setup.setup.getpass",
        lambda _prompt: (_ for _ in ()).throw(EOFError),
    )
    from synthflow_mcp.setup import setup

    with pytest.raises(SystemExit) as eof_exit:
        setup.main()
    assert eof_exit.value.code == 1
    setup_output = capsys.readouterr().out
    assert "no API key was provided" in setup_output
    assert "Traceback" not in setup_output

    monkeypatch.setattr("synthflow_mcp.setup.setup.getpass", lambda _prompt: "  ")
    with pytest.raises(SystemExit) as blank_exit:
        setup.main()
    assert blank_exit.value.code == 1
    blank_output = capsys.readouterr().out
    assert blank_output == (
        "Synthflow MCP Setup\n"
        "Get your API key at: https://app.synthflow.ai → Settings → API\n"
        "\n"
        "Error: API key cannot be empty.\n"
    )

    class BadKeyClient:
        def __init__(self):
            pass

        def who_am_i(self):
            raise client_module.AuthenticationError("private response detail")

    monkeypatch.setattr(verify, "logger", logging.getLogger("test.verify"))
    monkeypatch.setattr(client_module, "SynthflowClient", BadKeyClient)
    with pytest.raises(SystemExit) as bad_exit:
        verify.main()
    assert bad_exit.value.code == 1
    bad_output = capsys.readouterr().out
    assert "unable to verify" in bad_output
    assert "Run synthflow-mcp-setup" in bad_output
    assert "private response detail" not in bad_output


def test_large_retry_hint_is_not_shortened_or_slept(monkeypatch):
    monkeypatch.setenv("SYNTHFLOW_API_KEY", "fake-key")
    client = client_module.SynthflowClient()
    response = client_module.requests.Response()
    response.status_code = 429
    response.headers["Retry-After"] = "120"
    monkeypatch.setattr(client.session, "request", lambda *a, **kw: response)
    waits = []
    monkeypatch.setattr(client_module.time, "sleep", waits.append)
    monkeypatch.setattr(server, "SynthflowClient", lambda: client)
    result = asyncio.run(_tool_result("who_am_i", {}))
    assert result.is_error is True
    assert (
        _tool_text(result)
        == "Synthflow rate limit reached (HTTP 429). Retry after 120 seconds."
    )
    assert waits == []


def test_unsuccessful_200_cannot_be_a_successful_tool_result(monkeypatch):
    monkeypatch.setenv("SYNTHFLOW_API_KEY", "fake-key")
    client = client_module.SynthflowClient()
    response = client_module.requests.Response()
    response.status_code = 200
    response._content = b'{"success":false,"error":"PRIVATE_SENTINEL"}'
    monkeypatch.setattr(client.session, "request", lambda *a, **kw: response)
    monkeypatch.setattr(server, "SynthflowClient", lambda: client)
    result = asyncio.run(
        _tool_result("initiate_call", {"agent_id": "fake", "to_number": "+15555550123"})
    )
    assert result.is_error is True
    assert (
        _tool_text(result)
        == "Synthflow API error 200: the vendor reported that the operation failed"
    )


@pytest.mark.parametrize(
    "resource", [server.agents_resource, server.phone_numbers_resource]
)
def test_unexpected_resource_failure_is_masked(monkeypatch, resource):
    from mcp.server.mcpserver.exceptions import ResourceError

    def fail():
        raise RuntimeError("PRIVATE_SENTINEL")

    monkeypatch.setattr(server, "SynthflowClient", fail)
    with pytest.raises(ResourceError) as caught:
        resource()
    assert (
        str(caught.value)
        == "Unable to read this Synthflow resource. Try again or check the connection."
    )
