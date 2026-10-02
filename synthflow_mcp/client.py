#!/usr/bin/env python3
import logging
import os
import re
import sys
import time
from urllib.parse import quote

import requests
from mcp.server.mcpserver.exceptions import ToolError

from synthflow_mcp import credentials

# Synthflow uses regional endpoints. The global api.synthflow.ai does not route
# to US-provisioned accounts — use the US regional endpoint.
BASE_URL = "https://api.us.synthflow.ai/v2"
REQUEST_TIMEOUT = 30
MAX_RETRY_WAIT = 60
logger = logging.getLogger(__name__)


class UpdateValidationError(ToolError, ValueError):
    """A fixed, safe explanation for an empty update."""


class PathIdentifierError(ToolError, ValueError):
    """A safe, actionable rejection of an invalid path identifier."""


def _path_id(value, parameter: str) -> str:
    """Validate a plain identifier before URL quoting or any HTTP request."""
    expected = (
        "a non-empty plain identifier (ASCII letters, digits, -, _, ., ~); not . or .."
    )
    if (
        isinstance(value, bool)
        or not isinstance(value, (str, int))
        or str(value) in {".", ".."}
        or re.fullmatch(r"[A-Za-z0-9._~-]+", str(value)) is None
    ):
        message = f"Invalid argument '{parameter}': use {expected}."
        raise PathIdentifierError(message)
    return quote(str(value), safe="")


class MissingCredentialsError(RuntimeError):
    pass


class AuthenticationError(RuntimeError):
    pass


class TransportError(RuntimeError):
    def __init__(self, method: str, kind: str):
        self.method = method.upper()
        self.kind = kind
        if self.method in {"GET", "HEAD", "OPTIONS"}:
            action = "Retry the read when the connection is available."
        else:
            action = (
                "The outcome is unknown. Check whether the operation completed "
                "before retrying."
            )
        super().__init__(f"Synthflow {kind}. {action}")


class VendorHTTPError(RuntimeError):
    def __init__(self, status: int, reason: str):
        self.status = status
        self.reason = reason
        super().__init__(f"Synthflow API error {status}: {reason}")


class RateLimitError(RuntimeError):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(
            f"Synthflow rate limit reached (HTTP 429). Retry after {retry_after} seconds."
        )


class NotFoundError(RuntimeError):
    pass


_SAFE_HTTP_REASONS = {
    400: "the request was rejected",
    401: "authentication was rejected",
    403: "access was denied",
    404: "the requested item was not found",
    409: "the request conflicts with current state",
    422: "the request was invalid",
    429: "the service is rate limiting requests",
    500: "the service encountered an error",
    502: "the service is temporarily unavailable",
    503: "the service is temporarily unavailable",
    504: "the service timed out",
}

_SAFE_VENDOR_REASONS = {
    "invalid_request": "invalid request",
    "validation_error": "request validation failed",
    "invalid_parameter": "invalid parameter",
    "service_unavailable": "the service is temporarily unavailable",
}


def _vendor_reason(response):
    fallback = _SAFE_HTTP_REASONS.get(
        response.status_code, "the service rejected the request"
    )
    try:
        payload = response.json()
    except ValueError:
        return fallback
    if isinstance(payload, dict):
        for source in (payload, payload.get("error")):
            if isinstance(source, dict):
                for key in ("code", "error_code", "error", "message", "detail"):
                    value = source.get(key)
                    if isinstance(value, str) and value.lower() in _SAFE_VENDOR_REASONS:
                        return _SAFE_VENDOR_REASONS[value.lower()]
    return fallback


# Resolve credentials through the pluggable store (OS keyring -> .env file).
credentials.load_into_environ(["SYNTHFLOW_API_KEY"])


def _retry_after_seconds(resp, default=10):
    try:
        return max(1, int(resp.headers.get("Retry-After", default)))
    except (TypeError, ValueError):
        return default


def _json_response(resp):
    try:
        payload = resp.json()
    except ValueError:
        logger.error(
            "Synthflow response rejected",
            extra={
                "event": "synthflow_response_rejected",
                "reason": "non_json",
                "status_code": resp.status_code,
            },
        )
        raise VendorHTTPError(
            resp.status_code, "the service returned invalid JSON"
        ) from None

    if isinstance(payload, dict) and payload.get("success") is False:
        raise VendorHTTPError(
            resp.status_code, "the vendor reported that the operation failed"
        )
    return payload


class SynthflowClient:
    def __init__(self):
        api_key = os.environ.get("SYNTHFLOW_API_KEY", "")
        if not api_key:
            logger.warning(
                "Synthflow credential rejected",
                extra={"event": "synthflow_credentials_missing"},
            )
            raise MissingCredentialsError(
                "No Synthflow API key found (SYNTHFLOW_API_KEY). Run "
                "synthflow-mcp-setup, then restart the MCP server."
            )
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _request(
        self,
        method,
        path,
        params=None,
        json_body=None,
        _rate_retries=0,
        _rate_waited=0,
    ):
        url = f"{BASE_URL}/{path.lstrip('/')}"
        try:
            resp = self.session.request(
                method, url, params=params, json=json_body, timeout=REQUEST_TIMEOUT
            )
        except requests.Timeout:
            logger.warning(
                "Synthflow request failed",
                extra={
                    "event": "synthflow_transport_error",
                    "reason": "timeout",
                    "method": method.upper(),
                },
            )
            raise TransportError(method, "request timed out") from None
        except requests.ConnectionError:
            logger.warning(
                "Synthflow request failed",
                extra={
                    "event": "synthflow_transport_error",
                    "reason": "connection",
                    "method": method.upper(),
                },
            )
            raise TransportError(method, "connection failed") from None
        except requests.RequestException:
            logger.warning(
                "Synthflow request failed",
                extra={
                    "event": "synthflow_transport_error",
                    "reason": "request_failed",
                    "method": method.upper(),
                },
            )
            raise TransportError(method, "request failed") from None
        if resp.status_code == 401:
            logger.warning(
                "Synthflow request rejected",
                extra={
                    "event": "synthflow_request_rejected",
                    "reason": "unauthorized",
                    "status_code": 401,
                },
            )
            raise AuthenticationError(
                "Synthflow authentication failed. Check the API key and run "
                "synthflow-mcp-setup to replace it; restart the MCP server after setup."
            )
        if resp.status_code == 403:
            raise AuthenticationError(
                "Synthflow access denied: the connected account lacks permission for "
                "this action (or the authorization expired; re-run "
                "synthflow-mcp-setup if so)."
            )
        if resp.status_code == 429 and _rate_retries < 3:
            retry_hint = _retry_after_seconds(resp, default=10)
            if _rate_waited + retry_hint > MAX_RETRY_WAIT:
                raise RateLimitError(retry_hint)
            wait = min(retry_hint, MAX_RETRY_WAIT)
            logger.warning(
                "Synthflow request deferred",
                extra={
                    "event": "synthflow_request_rate_limited",
                    "retry_after_seconds": wait,
                    "retry_number": _rate_retries + 1,
                    "status_code": 429,
                },
            )
            print(f"Rate limited. Waiting {wait}s...", file=sys.stderr)
            time.sleep(wait)
            return self._request(
                method,
                path,
                params=params,
                json_body=json_body,
                _rate_retries=_rate_retries + 1,
                _rate_waited=_rate_waited + wait,
            )
        if resp.status_code == 429:
            raise RateLimitError(_retry_after_seconds(resp, default=10))
        if resp.status_code == 204:
            return {"success": True}
        if not resp.ok:
            logger.error(
                "Synthflow request rejected",
                extra={
                    "event": "synthflow_request_rejected",
                    "reason": "vendor_api_error",
                    "status_code": resp.status_code,
                },
            )
            if resp.status_code == 404:
                raise NotFoundError("Synthflow item was not found (HTTP 404).")
            reason = _vendor_reason(resp)
            raise VendorHTTPError(resp.status_code, reason)
        return _json_response(resp)

    def get(self, path, params=None):
        return self._request("GET", path, params=params)

    def post(self, path, body=None):
        return self._request("POST", path, json_body=body)

    def patch(self, path, body=None):
        return self._request("PATCH", path, json_body=body)

    def delete(self, path):
        return self._request("DELETE", path)

    # --- Account ---

    def who_am_i(self):
        # /account does not exist in the Synthflow v2 API. Return analytics as the
        # closest account-level signal available without extra params.
        return self.get("/analytics")

    # --- Agents ---

    def list_agents(self, page=1, limit=25):
        return self.get("/assistants", params={"page": page, "limit": limit})

    def get_agent(self, agent_id):
        return self.get(f"/assistants/{_path_id(agent_id, 'agent_id')}")

    def create_agent(
        self,
        name,
        system_prompt,
        agent_type="outbound",
        voice_id="",
        language="en-US",
        greeting_message="Hello, how can I help you?",
        llm="gpt-4.1",
    ):
        agent_cfg = {
            "prompt": system_prompt,
            "greeting_message": greeting_message,
            "llm": llm,
            "language": language,
        }
        if voice_id:
            agent_cfg["voice_id"] = voice_id
        return self.post(
            "/assistants", body={"type": agent_type, "name": name, "agent": agent_cfg}
        )

    def update_agent(self, agent_id, name="", system_prompt="", voice_id=""):
        path = f"/assistants/{_path_id(agent_id, 'agent_id')}"
        validate_agent_update(name, system_prompt, voice_id)
        # Documented partial PUT: omitted parameters are unchanged.
        # https://docs.synthflow.ai/api-reference/platform-api/agents/update-assistant
        body = {}
        if name:
            body["name"] = name
        if system_prompt:
            body["agent"] = {"prompt": system_prompt}
        if voice_id:
            body.setdefault("agent", {})["voice_id"] = voice_id
        return self._request("PUT", path, json_body=body)

    def delete_agent(self, agent_id):
        return self.delete(f"/assistants/{_path_id(agent_id, 'agent_id')}")

    # --- Phone Numbers ---

    def list_phone_numbers(self, page=1, limit=25):
        return self.get("/numbers", params={"page": page, "limit": limit})

    def get_phone_number(self, number_id):
        return self.get(f"/numbers/{_path_id(number_id, 'number_id')}")

    def provision_phone_number(self, area_code="", country="US"):
        body = {"country": country}
        if area_code:
            body["area_code"] = area_code
        return self.post("/numbers", body=body)

    def assign_agent_to_number(self, number_id, agent_id):
        return self.patch(
            f"/numbers/{_path_id(number_id, 'number_id')}", body={"agent_id": agent_id}
        )

    # --- Calls ---

    def list_calls(self, page=1, limit=25, agent_id=""):
        # API requires model_id (the agent ID) as a mandatory query param.
        params: dict = {"page": page, "limit": limit}
        if agent_id:
            params["model_id"] = agent_id
        return self.get("/calls", params=params)

    def get_call(self, call_id):
        return self.get(f"/calls/{_path_id(call_id, 'call_id')}")

    def get_call_transcript(self, call_id):
        return self.get(f"/calls/{_path_id(call_id, 'call_id')}/transcript")

    def initiate_call(self, agent_id, to_number, name="", from_number=""):
        # API fields: model_id (agent), phone (recipient number), name (recipient name).
        body = {"model_id": agent_id, "phone": to_number, "name": name}
        if from_number:
            body["from_number"] = from_number
        return self.post("/calls", body=body)

    # --- Knowledge Bases ---

    def list_knowledge_bases(self, page=1, limit=25):
        return self.get("/knowledge-bases", params={"page": page, "limit": limit})

    def create_knowledge_base(self, name, content):
        return self.post("/knowledge-bases", body={"name": name, "content": content})

    # --- Analytics ---

    def get_analytics(self, start_date="", end_date=""):
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return self.get("/analytics", params=params if params else None)


def validate_agent_update(name, system_prompt, voice_id):
    if not any(value.strip() for value in (name, system_prompt, voice_id)):
        raise UpdateValidationError(
            "Supply at least one update field: name, system_prompt, or voice_id."
        )
