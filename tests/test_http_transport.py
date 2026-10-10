"""In-process Streamable HTTP checks for MCP spec 2026-07-28."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from mcp import Client

from synthflow_mcp import server

PROTOCOL_VERSION = "2026-07-28"
PROTOCOL_VERSION_META_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_META_KEY = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_META_KEY = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_META_KEY = "io.modelcontextprotocol/serverInfo"
LOOPBACK_BASE = "http://127.0.0.1:8080"


def _bind_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNTHFLOW_MCP_HOST", "127.0.0.1")
    monkeypatch.delenv("SYNTHFLOW_MCP_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("SYNTHFLOW_MCP_ALLOWED_ORIGINS", raising=False)


def _modern_body(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    request_id: int = 1,
) -> dict[str, Any]:
    request_params = dict(params or {})
    request_params["_meta"] = {
        PROTOCOL_VERSION_META_KEY: PROTOCOL_VERSION,
        CLIENT_CAPABILITIES_META_KEY: {},
        CLIENT_INFO_META_KEY: {"name": "synthflow-http-test", "version": "0"},
    }
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": request_params,
    }


def _modern_headers(
    method: str, params: dict[str, Any] | None = None
) -> dict[str, str]:
    headers = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
        "mcp-protocol-version": PROTOCOL_VERSION,
        "mcp-method": method,
    }
    if method == "tools/call":
        headers["mcp-name"] = str((params or {})["name"])
    return headers


def _jsonrpc(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        payloads = [
            json.loads(line.removeprefix("data:").strip())
            for line in response.text.splitlines()
            if line.startswith("data:")
        ]
        assert payloads, response.text
        body = payloads[-1]
    else:
        body = response.json()
    assert body["jsonrpc"] == "2.0"
    return body


def _wire_tool(tool: Any) -> dict[str, Any]:
    if hasattr(tool, "model_dump"):
        dumped = tool.model_dump(by_alias=True, mode="json", exclude_none=True)
    else:
        dumped = tool
    return {"name": dumped["name"], "inputSchema": dumped["inputSchema"]}


async def _post(
    app: Any,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    request_id: int = 1,
    header_overrides: dict[str, str] | None = None,
    base_url: str = LOOPBACK_BASE,
) -> httpx.Response:
    headers = _modern_headers(method, params)
    if header_overrides:
        headers.update(header_overrides)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url=base_url, timeout=10.0
        ) as client:
            return await client.post(
                "/mcp",
                headers=headers,
                json=_modern_body(method, params, request_id=request_id),
            )


async def _stdio_tools() -> list[dict[str, Any]]:
    async with Client(server.mcp, cache=None) as client:
        listed = await client.list_tools()
    return [_wire_tool(tool) for tool in listed.tools]


def test_http_tools_list_matches_stdio_server(monkeypatch: pytest.MonkeyPatch) -> None:
    _bind_loopback(monkeypatch)
    app = server.create_serve_app()
    response = asyncio.run(_post(app, "tools/list"))
    result = _jsonrpc(response)["result"]
    http_tools = [_wire_tool(tool) for tool in result["tools"]]
    stdio_tools = asyncio.run(_stdio_tools())
    assert http_tools == stdio_tools
    assert [tool["name"] for tool in http_tools]


def test_read_tool_runs_over_http_against_vendor_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {"account": "synthflow-http-test", "calls": 3}

    class StubSynthflowClient:
        def who_am_i(self) -> dict[str, Any]:
            return payload

    _bind_loopback(monkeypatch)
    monkeypatch.setattr(server, "SynthflowClient", StubSynthflowClient)
    expected = json.dumps(payload, indent=2)

    async def stdio_text() -> str:
        async with Client(server.mcp, cache=None) as client:
            result = await client.call_tool("who_am_i", {})
        return str(result.content[0].text)

    app = server.create_serve_app()
    response = asyncio.run(
        _post(app, "tools/call", {"name": "who_am_i", "arguments": {}})
    )
    result = _jsonrpc(response)["result"]
    assert result.get("isError") is not True
    assert result["content"][0]["text"] == expected
    assert asyncio.run(stdio_text()) == expected


def test_http_responses_carry_no_session_and_requests_share_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_loopback(monkeypatch)
    app = server.create_serve_app()

    async def two_posts() -> tuple[httpx.Response, httpx.Response]:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url=LOOPBACK_BASE, timeout=10.0
            ) as client:
                first = await client.post(
                    "/mcp",
                    headers=_modern_headers("tools/list"),
                    json=_modern_body("tools/list", request_id=1),
                )
                second = await client.post(
                    "/mcp",
                    headers={
                        **_modern_headers("tools/list"),
                        "mcp-session-id": "not-a-session",
                    },
                    json=_modern_body("tools/list", request_id=2),
                )
                return first, second

    first, second = asyncio.run(two_posts())
    for response in (first, second):
        assert response.status_code == 200, response.text
        assert "mcp-session-id" not in response.headers
    assert _jsonrpc(first)["result"]["tools"] == _jsonrpc(second)["result"]["tools"]
    assert _jsonrpc(first)["id"] == 1
    assert _jsonrpc(second)["id"] == 2


def test_bogus_transport_exits_and_default_stays_stdio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SYNTHFLOW_MCP_TRANSPORT", "bogus")
    with pytest.raises(SystemExit) as caught:
        server.main()
    message = str(caught.value)
    assert "SYNTHFLOW_MCP_TRANSPORT" in message
    assert "stdio" in message
    assert server.STREAMABLE_HTTP_TRANSPORT in message

    monkeypatch.delenv("SYNTHFLOW_MCP_TRANSPORT", raising=False)
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def record_run(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(server.mcp, "run", record_run)
    assert server._requested_transport() == "stdio"
    server.main()
    assert calls == [((), {})]


def test_allowed_hosts_refuse_other_host_and_bad_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SYNTHFLOW_MCP_HOST", "10.1.2.3")
    monkeypatch.setenv("SYNTHFLOW_MCP_ALLOWED_HOSTS", "mcp.example.test:*")
    monkeypatch.setenv("SYNTHFLOW_MCP_ALLOWED_ORIGINS", "https://app.example.test")
    app = server.create_serve_app()

    async def both() -> tuple[httpx.Response, httpx.Response]:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://mcp.example.test",
                timeout=10.0,
            ) as client:

                async def post(host: str, origin: str | None) -> httpx.Response:
                    headers = _modern_headers("tools/list")
                    headers["host"] = host
                    if origin is not None:
                        headers["origin"] = origin
                    return await client.post(
                        "/mcp",
                        headers=headers,
                        json=_modern_body("tools/list"),
                    )

                other_host = await post("evil.example:443", None)
                bad_origin = await post("mcp.example.test:443", "https://evil.example")
                return other_host, bad_origin

    other_host, bad_origin = asyncio.run(both())
    assert other_host.status_code == 421
    assert bad_origin.status_code == 403


def test_non_loopback_host_without_allowed_hosts_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SYNTHFLOW_MCP_HOST", "10.1.2.3")
    monkeypatch.delenv("SYNTHFLOW_MCP_ALLOWED_HOSTS", raising=False)
    with pytest.raises(SystemExit) as caught:
        server.create_serve_app()
    assert "SYNTHFLOW_MCP_ALLOWED_HOSTS" in str(caught.value)


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_sdk_protected_loopback_needs_no_allowed_hosts(
    monkeypatch: pytest.MonkeyPatch, host: str
) -> None:
    monkeypatch.setenv("SYNTHFLOW_MCP_HOST", host)
    monkeypatch.delenv("SYNTHFLOW_MCP_ALLOWED_HOSTS", raising=False)
    assert server.create_serve_app() is not None


@pytest.mark.parametrize("host", ["LOCALHOST", "127.0.0.2", "[::1]"])
def test_unprotected_loopback_spellings_without_allowed_hosts_exit(
    monkeypatch: pytest.MonkeyPatch, host: str
) -> None:
    monkeypatch.setenv("SYNTHFLOW_MCP_HOST", host)
    monkeypatch.delenv("SYNTHFLOW_MCP_ALLOWED_HOSTS", raising=False)
    with pytest.raises(SystemExit) as caught:
        server.create_serve_app()
    assert "SYNTHFLOW_MCP_ALLOWED_HOSTS" in str(caught.value)


@pytest.mark.parametrize("host", ["LOCALHOST", "127.0.0.2", "[::1]"])
def test_unprotected_loopback_spellings_validate_host_and_origin(
    monkeypatch: pytest.MonkeyPatch, host: str
) -> None:
    monkeypatch.setenv("SYNTHFLOW_MCP_HOST", host)
    monkeypatch.setenv("SYNTHFLOW_MCP_ALLOWED_HOSTS", "mcp.example.test:*")
    monkeypatch.setenv("SYNTHFLOW_MCP_ALLOWED_ORIGINS", "https://app.example.test")
    app = server.create_serve_app()

    async def both() -> tuple[httpx.Response, httpx.Response]:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://mcp.example.test",
                timeout=10.0,
            ) as client:

                async def post(request_host: str, origin: str | None) -> httpx.Response:
                    headers = _modern_headers("tools/list")
                    headers["host"] = request_host
                    if origin is not None:
                        headers["origin"] = origin
                    return await client.post(
                        "/mcp",
                        headers=headers,
                        json=_modern_body("tools/list"),
                    )

                other_host = await post("evil.example:443", None)
                bad_origin = await post("mcp.example.test:443", "https://evil.example")
                return other_host, bad_origin

    other_host, bad_origin = asyncio.run(both())
    assert other_host.status_code == 421
    assert bad_origin.status_code == 403


def test_get_and_delete_are_rejected_and_discover_names_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_loopback(monkeypatch)
    app = server.create_serve_app()

    async def probe() -> tuple[httpx.Response, httpx.Response, httpx.Response]:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url=LOOPBACK_BASE, timeout=10.0
            ) as client:
                modern = {"mcp-protocol-version": PROTOCOL_VERSION}
                get_response = await client.get("/mcp", headers=modern)
                delete_response = await client.delete("/mcp", headers=modern)
                discover = await client.post(
                    "/mcp",
                    headers=_modern_headers("server/discover"),
                    json=_modern_body("server/discover"),
                )
                return get_response, delete_response, discover

    get_response, delete_response, discover = asyncio.run(probe())
    assert get_response.status_code == 405
    assert delete_response.status_code == 405
    result = _jsonrpc(discover)["result"]
    assert PROTOCOL_VERSION in result["supportedVersions"]
    version = result["_meta"][SERVER_INFO_META_KEY]["version"]
    assert isinstance(version, str) and version.strip()


def test_stateless_lifespan_runs_once_per_app_not_per_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_loopback(monkeypatch)
    enters: list[str] = []

    @asynccontextmanager
    async def counting_lifespan(_mcp_server: Any):
        enters.append("enter")
        yield {"enters": len(enters)}

    monkeypatch.setattr(server.mcp._lowlevel_server, "lifespan", counting_lifespan)
    app = server.create_serve_app()

    async def two_lists() -> None:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url=LOOPBACK_BASE, timeout=10.0
            ) as client:
                for request_id in (1, 2):
                    response = await client.post(
                        "/mcp",
                        headers=_modern_headers("tools/list"),
                        json=_modern_body("tools/list", request_id=request_id),
                    )
                    assert response.status_code == 200, response.text
            assert enters == ["enter"]

    asyncio.run(two_lists())
    assert enters == ["enter"]


def test_non_integer_port_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "not-a-port")
    with pytest.raises(SystemExit) as caught:
        server._port()
    assert "PORT" in str(caught.value)


def test_empty_transport_selects_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNTHFLOW_MCP_TRANSPORT", "")
    assert server._requested_transport() == "stdio"
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    monkeypatch.setattr(server.mcp, "run", lambda *a, **k: calls.append((a, k)))
    server.main()
    assert calls == [((), {})]


def test_whitespace_transport_selects_stdio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SYNTHFLOW_MCP_TRANSPORT", "   ")
    assert server._requested_transport() == "stdio"


def test_empty_host_yields_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNTHFLOW_MCP_HOST", "")
    assert server._host() == "127.0.0.1"
    monkeypatch.delenv("SYNTHFLOW_MCP_ALLOWED_HOSTS", raising=False)
    assert server.create_serve_app() is not None


def test_whitespace_host_yields_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNTHFLOW_MCP_HOST", "   ")
    assert server._host() == "127.0.0.1"


def test_uppercase_localhost_is_non_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SYNTHFLOW_MCP_HOST", "LOCALHOST")
    assert server._host() == "LOCALHOST"
    monkeypatch.delenv("SYNTHFLOW_MCP_ALLOWED_HOSTS", raising=False)
    with pytest.raises(SystemExit) as caught:
        server.create_serve_app()
    assert "SYNTHFLOW_MCP_ALLOWED_HOSTS" in str(caught.value)


def test_server_import_without_installed_distribution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib
    import importlib.metadata

    def _missing(_name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(_name)

    monkeypatch.setattr(importlib.metadata, "version", _missing)
    reloaded = importlib.reload(server)
    assert reloaded.mcp is not None
