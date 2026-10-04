"""HTTP gateway adapter for an isolated DeepSeek Harness sidecar."""
from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from .dsh_runtime import DshRunRequest


class DshSidecarExecutor:
    def __init__(self, endpoint: str, *, profile: str | None = None, callback_url: str | None = None, timeout: float = 8.0) -> None:
        self.endpoint = endpoint.strip()
        if not self.endpoint:
            raise ValueError("DSH_ENDPOINT is required for sidecar mode")
        self.profile = profile or os.getenv("DSH_HARNESS_PROFILE", "workbench-readonly")
        if self.profile in {"sdk-minimal", "sdk", "web", "desktop"}:
            raise ValueError("sidecar mode requires a restricted Harness profile")
        self.callback_url = callback_url if callback_url is not None else os.getenv("DSH_CALLBACK_URL", "").strip()
        self.timeout = timeout

    def _post(self, payload: dict[str, Any], *, path: str = "") -> dict[str, Any]:
        url = self.endpoint.rstrip("/") + path
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(url, data=body, method="POST", headers={"Content-Type": "application/json", "X-Tenant-ID": str(payload.get("tenant_id", "")), "X-Actor-ID": str(payload.get("actor_id", ""))})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result: dict[str, Any] = {"dispatch": {"status_code": response.status}}
                response_body = response.read(64 * 1024)
                if response_body:
                    try:
                        decoded = json.loads(response_body.decode("utf-8"))
                        result["response"] = decoded if isinstance(decoded, dict) else {"value": decoded}
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        result["response"] = {"body": response_body[:512].decode("utf-8", errors="replace")}
                return result
        except URLError as exc:
            raise RuntimeError(f"DSH sidecar dispatch failed: {exc.reason}") from exc

    def envelope(self, request: DshRunRequest, *, run_id: str) -> dict[str, Any]:
        return {
            "status": "queued",
            "runtime": "dsh-harness",
            "mode": "sidecar",
            "tenant_id": request.tenant_id,
            "actor_id": request.actor_id,
            "run_id": run_id,
            "session_id": run_id,
            "task_id": request.task_id,
            "skill_id": request.skill_id,
            "input": request.input,
            "knowledge_scope": list(request.knowledge_scope),
            "allowed_tools": list(request.allowed_tools),
            "output_schema": request.output_schema,
            "approval_required": request.approval_required,
            "tool_gateway_url": request.tool_gateway_url,
            "profile": self.profile,
            "callback_url": self.callback_url,
        }

    def dispatch(self, request: DshRunRequest, *, run_id: str) -> dict[str, Any]:
        envelope = self.envelope(request, run_id=run_id)
        return envelope | self._post(envelope)

    def cancel(self, run_id: str, *, tenant_id: str = "", actor_id: str = "") -> dict[str, Any]:
        return self._post({"run_id": run_id, "tenant_id": tenant_id, "actor_id": actor_id, "status": "cancelled"}, path=f"/{run_id}/cancel")
