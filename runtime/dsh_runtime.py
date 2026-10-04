"""Runtime routing between the Workbench product layer and DeepSeek Harness."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


class RuntimeUnavailableError(RuntimeError):
    """Raised when no explicit DSH execution mode is configured."""


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
    tool_gateway_url: str | None = None


class DshRuntime:
    """Route constrained Workbench runs to native DSH or a DSH sidecar.

    ``local-demo`` is deliberately opt-in. With no endpoint or Harness home,
    the runtime reports unavailable instead of pretending a model ran.
    """

    def __init__(self, endpoint: str | None = None, mode: str | None = None) -> None:
        self.endpoint = endpoint or os.getenv("DSH_ENDPOINT", "").strip()
        self.requested_mode = (mode or os.getenv("DSH_RUNTIME_MODE", "auto")).strip().lower() or "auto"
        self._native_executor = None
        self._sidecar_executor = None

    @property
    def mode(self) -> str:
        if self.requested_mode in {"demo", "local-demo"}:
            return "demo"
        if self.requested_mode == "sidecar":
            return "sidecar" if self.endpoint else "unavailable"
        if self.requested_mode == "native":
            return "native" if os.getenv("DSH_HARNESS_HOME", "").strip() else "unavailable"
        if self.requested_mode == "auto":
            if self.endpoint:
                return "sidecar"
            if os.getenv("DSH_HARNESS_HOME", "").strip():
                return "native"
            return "unavailable"
        return "unavailable"

    @property
    def configured(self) -> bool:
        return self.mode in {"native", "sidecar"}

    def metadata(self) -> dict[str, Any]:
        mode = self.mode
        if mode == "native":
            capabilities = ["reasoning", "tool-orchestration", "structured-output", "sessions", "events"]
            runtime = "dsh-harness"
        elif mode == "sidecar":
            capabilities = ["reasoning", "tool-orchestration", "structured-output", "callbacks"]
            runtime = "dsh-harness"
        elif mode == "demo":
            capabilities = ["deterministic-demo"]
            runtime = "dsh"
        else:
            capabilities = []
            runtime = "dsh-harness"
        return {
            "runtime": runtime,
            "mode": mode,
            "endpoint": self.endpoint or None,
            "profile": os.getenv("DSH_HARNESS_PROFILE", "workbench-readonly") if mode == "native" else None,
            "capabilities": capabilities,
            "policy": {
                "tenant_scope": "required",
                "shell": False,
                "filesystem": "restricted",
                "network": "product-approved-egress",
                "business_writes": "approval-required",
            },
            "tool_gateway": {
                "url": os.getenv("DSH_TOOL_GATEWAY_URL", "").strip() or None,
                "path": "/api/v1/tools/call",
                "authorization": "run-scoped allowed_tools plus tenant and actor binding",
            },
        }

    def build_request(self, *, tenant_id: str, actor_id: str, task_id: str, skill_id: str, input: Any, knowledge_scope: list[str], allowed_tools: list[str], output_schema: str, approval_required: bool = False, tool_gateway_url: str | None = None) -> DshRunRequest:
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
            tool_gateway_url=tool_gateway_url or os.getenv("DSH_TOOL_GATEWAY_URL", "").strip() or None,
        )

    def _sidecar(self):
        if self._sidecar_executor is None:
            from .dsh_sidecar import DshSidecarExecutor

            self._sidecar_executor = DshSidecarExecutor(self.endpoint)
        return self._sidecar_executor

    def _dispatch_sidecar(self, request: DshRunRequest, *, run_id: str | None = None) -> dict[str, Any]:
        return self._sidecar().dispatch(request, run_id=run_id or "")

    def enqueue(self, request: DshRunRequest, *, run_id: str | None = None) -> dict[str, Any]:
        mode = self.mode
        if mode == "unavailable":
            raise RuntimeUnavailableError("configure DSH_RUNTIME_MODE=demo, DSH_ENDPOINT, or DSH_HARNESS_HOME")
        if mode == "sidecar":
            return self._dispatch_sidecar(request, run_id=run_id)
        return {
            "status": "queued",
            "runtime": "dsh-harness" if mode == "native" else "dsh",
            "mode": mode,
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

    def dispatch(self, request: DshRunRequest, *, run_id: str) -> Any:
        mode = self.mode
        if mode == "native":
            if self._native_executor is None:
                from .dsh_harness import DshHarnessExecutor

                self._native_executor = DshHarnessExecutor()
            return self._native_executor.run(request, run_id=run_id)
        if mode == "sidecar":
            return self._dispatch_sidecar(request, run_id=run_id)
        if mode == "demo":
            return self.enqueue(request, run_id=run_id)
        raise RuntimeUnavailableError("configure DSH_RUNTIME_MODE=demo, DSH_ENDPOINT, or DSH_HARNESS_HOME")

    def cancel(self, run_id: str) -> None:
        if self.mode == "native" and self._native_executor is not None:
            self._native_executor.cancel(run_id)
        elif self.mode == "sidecar" and self._sidecar_executor is not None:
            self._sidecar_executor.cancel(run_id)

    def close(self) -> None:
        if self._native_executor is not None:
            self._native_executor.close()
