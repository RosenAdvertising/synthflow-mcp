#!/usr/bin/env python3
import os
import sys
import time
import requests
from pathlib import Path

# Synthflow uses regional endpoints. The global api.synthflow.ai does not route
# to US-provisioned accounts — use the US regional endpoint.
BASE_URL = "https://api.us.synthflow.ai/v2"
CONFIG_DIR = Path.home() / ".synthflow-mcp"


def _load_env():
    env_file = CONFIG_DIR / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip())


_load_env()


def _retry_after_seconds(resp, default=10):
    try:
        return int(resp.headers.get("Retry-After", default))
    except (TypeError, ValueError):
        return default


def _json_response(resp):
    try:
        return resp.json()
    except ValueError:
        raise RuntimeError(
            f"Synthflow API returned non-JSON ({resp.status_code}): {resp.text[:200]}"
        )


class SynthflowClient:
    def __init__(self):
        api_key = os.environ.get("SYNTHFLOW_API_KEY", "")
        if not api_key:
            raise RuntimeError("No Synthflow API key found. Run: synthflow-mcp-setup")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _request(self, method, path, params=None, json_body=None, _rate_retries=0):
        url = f"{BASE_URL}/{path.lstrip('/')}"
        resp = self.session.request(method, url, params=params, json=json_body)
        if resp.status_code == 401:
            raise RuntimeError(
                "Synthflow API key invalid or expired. Run: synthflow-mcp-setup"
            )
        if resp.status_code == 429 and _rate_retries < 3:
            wait = _retry_after_seconds(resp)
            print(f"Rate limited. Waiting {wait}s...", file=sys.stderr)
            time.sleep(wait)
            return self._request(
                method,
                path,
                params=params,
                json_body=json_body,
                _rate_retries=_rate_retries + 1,
            )
        if resp.status_code == 204:
            return {"success": True}
        if not resp.ok:
            raise RuntimeError(
                f"Synthflow API error {resp.status_code}: {resp.text[:400]}"
            )
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
        return self.get(f"/assistants/{agent_id}")

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
        # API requires PUT (not PATCH) for agent updates.
        body = {}
        if name:
            body["name"] = name
        if system_prompt:
            body["agent"] = {"prompt": system_prompt}
        if voice_id:
            body.setdefault("agent", {})["voice_id"] = voice_id
        return self._request("PUT", f"/assistants/{agent_id}", json_body=body)

    def delete_agent(self, agent_id):
        return self.delete(f"/assistants/{agent_id}")

    # --- Phone Numbers ---

    def list_phone_numbers(self, page=1, limit=25):
        return self.get("/numbers", params={"page": page, "limit": limit})

    def get_phone_number(self, number_id):
        return self.get(f"/numbers/{number_id}")

    def provision_phone_number(self, area_code="", country="US"):
        body = {"country": country}
        if area_code:
            body["area_code"] = area_code
        return self.post("/numbers", body=body)

    def assign_agent_to_number(self, number_id, agent_id):
        return self.patch(f"/numbers/{number_id}", body={"agent_id": agent_id})

    # --- Calls ---

    def list_calls(self, page=1, limit=25, agent_id=""):
        # API requires model_id (the agent ID) as a mandatory query param.
        params: dict = {"page": page, "limit": limit}
        if agent_id:
            params["model_id"] = agent_id
        return self.get("/calls", params=params)

    def get_call(self, call_id):
        return self.get(f"/calls/{call_id}")

    def get_call_transcript(self, call_id):
        return self.get(f"/calls/{call_id}/transcript")

    def initiate_call(self, agent_id, to_number, name="", from_number=""):
        # API fields: model_id (agent), phone (recipient number), name (recipient name).
        body = {"model_id": agent_id, "phone": to_number, "name": name}
        if from_number:
            body["from_number"] = from_number
        return self.post("/calls", body=body)

    # --- Knowledge Bases ---

    def list_knowledge_bases(self):
        return self.get("/knowledge-bases")

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
