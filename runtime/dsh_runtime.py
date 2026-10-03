"""DSH runtime boundary for the DSH Workbench product layer.

The product owns task state, tenant scope, permissions and artifacts. This module
owns only the request/response contract used to hand a constrained run to DSH.
"""
from __future__ import annotations

import os
import json
from urllib.error import URLError
from urllib.request import Request, urlopen
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DshRunRequest:
    tenant_id: str
    actor_id: str
    task_id: str
    skill_id: str
    input: Any
    knowledge_scope: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    output_schema: str
    approval_required: bool = False


class DshRuntime:
    """Safe runtime adapter seam.

    `DSH_ENDPOINT` is intentionally opt-in. Without it, the local product demo
    stays deterministic and exposes a dry-run status instead of pretending that
    a reasoning run happened.
    """

    def __init__(self, endpoint: str | None = None) -> None:
        self.endpoint = endpoint or os.getenv("DSH_ENDPOINT", "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.endpoint)

    def metadata(self) -> dict[str, Any]:
        return {
            "runtime": "dsh",
            "mode": "configured" if self.configured else "local-demo",
            "endpoint": self.endpoint or None,
            "capabilities": ["reasoning", "tool-orchestration", "structured-output"],
            "policy": {
                "tenant_scope": "required",
                "shell": False,
                "filesystem": "restricted",
                "network": "product-approved-egress",
                "business_writes": "approval-required",
            },
        }

    def build_request(self, *, tenant_id: str, actor_id: str, task_id: str, skill_id: str, input: Any, knowledge_scope: list[str], allowed_tools: list[str], output_schema: str, approval_required: bool = False) -> DshRunRequest:
        if not tenant_id or not actor_id or not task_id or not skill_id:
            raise ValueError("tenant_id, actor_id, task_id and skill_id are required")
        if not allowed_tools:
            raise ValueError("a run must declare allowed_tools")
        return DshRunRequest(
            tenant_id=tenant_id,
            actor_id=actor_id,
            task_id=task_id,
            skill_id=skill_id,
            input=input,
            knowledge_scope=tuple(knowledge_scope),
            allowed_tools=tuple(allowed_tools),
            output_schema=output_schema,
            approval_required=approval_required,
        )

    def enqueue(self, request: DshRunRequest, *, run_id: str | None = None) -> dict[str, Any]:
        """Return a product-owned run envelope.

        A production worker can replace this method with a sidecar call. The
        envelope keeps DSH trace data separate from the Task and Artifact truth.
        """
        envelope = {
            "status": "queued",
            "runtime": "dsh",
            "mode": "configured" if self.configured else "local-demo",
            "tenant_id": request.tenant_id,
            "actor_id": request.actor_id,
            "run_id": run_id,
            "task_id": request.task_id,
            "skill_id": request.skill_id,
            "knowledge_scope": list(request.knowledge_scope),
            "allowed_tools": list(request.allowed_tools),
            "output_schema": request.output_schema,
            "approval_required": request.approval_required,
        }
        if self.configured:
            body = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
            http_request = Request(self.endpoint, data=body, method="POST", headers={"Content-Type": "application/json", "X-Tenant-ID": request.tenant_id, "X-Actor-ID": request.actor_id})
            try:
                with urlopen(http_request, timeout=8) as response:
                    envelope["dispatch"] = {"status_code": response.status}
                    response_body = response.read(64 * 1024)
                    if response_body:
                        try:
                            envelope["response"] = json.loads(response_body.decode("utf-8"))
                        except (UnicodeDecodeError, json.JSONDecodeError):
                            envelope["response"] = {"body": response_body[:512].decode("utf-8", errors="replace")}
            except URLError as exc:
                raise RuntimeError(f"DSH dispatch failed: {exc.reason}") from exc
        return envelope
