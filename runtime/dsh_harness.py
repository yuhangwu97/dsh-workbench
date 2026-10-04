"""Native execution adapter for the official DeepSeek Harness Python SDK."""
from __future__ import annotations

import importlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, RLock
from typing import Any

from .dsh_runtime import DshRunRequest


class HarnessUnavailableError(RuntimeError):
    """Raised when the optional DeepSeek Harness SDK cannot be loaded."""


@dataclass(frozen=True)
class HarnessResult:
    status: str
    session_id: str
    final_response: str
    finish_reason: str | None
    events: list[dict[str, Any]] = field(default_factory=list)
    notifications: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


class DshHarnessExecutor:
    """Run a constrained Workbench request through ``DeepSeekHarness``.

    The SDK is imported lazily so the Workbench reference service can still
    start in sidecar mode without installing the native runtime wheel.
    """

    _unsafe_profiles = {"sdk-minimal", "sdk", "web", "desktop"}

    def __init__(
        self,
        *,
        home: str | None = None,
        profile: str | None = None,
        workspace: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
        max_tokens: int | None = None,
        patches: tuple[str, ...] = (),
    ) -> None:
        self.home = str(home or os.getenv("DSH_HARNESS_HOME", "")).strip()
        self.profile = str(profile or os.getenv("DSH_HARNESS_PROFILE", "workbench-readonly")).strip()
        if not self.home:
            raise ValueError("DSH_HARNESS_HOME is required for native Harness mode")
        if not self.profile or self.profile in self._unsafe_profiles:
            raise ValueError("native Harness mode requires a restricted profile")
        self.workspace = str(workspace or os.getenv("DSH_HARNESS_WORKSPACE", os.getcwd())).strip()
        self.provider = provider or os.getenv("DSH_PROVIDER", "").strip() or None
        self.model = model or os.getenv("DSH_MODEL", "").strip() or None
        self.reasoning_effort = reasoning_effort or os.getenv("DSH_REASONING_EFFORT", "").strip() or None
        configured_max_tokens = max_tokens if max_tokens is not None else os.getenv("DSH_MAX_TOKENS", "").strip()
        self.max_tokens = int(configured_max_tokens) if configured_max_tokens else None
        configured_patches = os.getenv("DSH_HARNESS_PATCHES", "").strip()
        self.patches = tuple(patches) or tuple(item for item in configured_patches.split(os.pathsep) if item)
        self._instances: dict[str, Any] = {}
        self._cancelled: set[str] = set()
        self._lock = RLock()

    @property
    def configured(self) -> bool:
        return bool(self.home and self.profile)

    def metadata(self) -> dict[str, Any]:
        return {
            "runtime": "dsh-harness",
            "mode": "native",
            "profile": self.profile,
            "workspace": self.workspace,
            "capabilities": ["reasoning", "tool-orchestration", "structured-output", "sessions", "events"],
            "sdk": "deepseek-harness-sdk",
        }

    def _harness_class(self):
        try:
            module = importlib.import_module("deepseek_harness")
        except (ImportError, ModuleNotFoundError) as exc:
            raise HarnessUnavailableError("install dsh-workbench[harness] (deepseek-harness-sdk) to use native DeepSeek Harness") from exc
        harness_class = getattr(module, "DeepSeekHarness", None)
        if harness_class is None:
            raise HarnessUnavailableError("deepseek_harness.DeepSeekHarness is unavailable")
        return harness_class

    def _prompt(self, request: DshRunRequest) -> str:
        policy = {
            "tenant_id": request.tenant_id,
            "actor_id": request.actor_id,
            "task_id": request.task_id,
            "skill_id": request.skill_id,
            "knowledge_scope": list(request.knowledge_scope),
            "allowed_tools": list(request.allowed_tools),
            "output_schema": request.output_schema,
            "approval_required": request.approval_required,
            "rules": [
                "Only use the declared tools and knowledge scope.",
                "Return a structured result matching output_schema.",
                "Never perform business writes; request Workbench approval instead.",
            ],
        }
        return "Workbench execution policy:\n" + json.dumps(policy, ensure_ascii=False, sort_keys=True) + "\n\nTask input:\n" + json.dumps(request.input, ensure_ascii=False, default=str)

    @staticmethod
    def _json_events(value: Any) -> list[dict[str, Any]]:
        if not value:
            return []
        output: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                output.append(item)
            else:
                try:
                    encoded = json.loads(json.dumps(item, default=lambda obj: getattr(obj, "__dict__", str(obj))))
                except (TypeError, ValueError):
                    encoded = {"value": str(item)}
                output.append(encoded if isinstance(encoded, dict) else {"value": encoded})
        return output

    def _new_harness(self):
        kwargs: dict[str, Any] = {
            "dsh_home": self.home,
            "profile": self.profile,
            "cwd": self.workspace,
        }
        for key, value in (
            ("provider", self.provider),
            ("model", self.model),
            ("reasoning_effort", self.reasoning_effort),
            ("max_tokens", self.max_tokens),
        ):
            if value is not None:
                kwargs[key] = value
        if self.patches:
            kwargs["patches"] = self.patches
        return self._harness_class()(**kwargs)

    def run(self, request: DshRunRequest, *, run_id: str, session_id: str | None = None) -> HarnessResult:
        session = session_id or run_id
        harness = self._new_harness()
        with self._lock:
            self._instances[run_id] = harness
            self._cancelled.discard(run_id)
        try:
            result = harness.run(self._prompt(request), session_id=session)
            with self._lock:
                cancelled = run_id in self._cancelled
            if cancelled:
                return HarnessResult(status="cancelled", session_id=session, final_response="", finish_reason="cancelled", events=self._json_events(getattr(result, "events", [])), notifications=self._json_events(getattr(result, "notifications", [])))
            finish_reason = getattr(result, "finish_reason", None)
            status = "failed" if finish_reason == "error" else "completed"
            return HarnessResult(status=status, session_id=session, final_response=str(getattr(result, "final_response", "") or ""), finish_reason=finish_reason, events=self._json_events(getattr(result, "events", [])), notifications=self._json_events(getattr(result, "notifications", [])))
        except Exception as exc:
            return HarnessResult(status="failed", session_id=session, final_response="", finish_reason="error", error=str(exc)[:500])
        finally:
            with self._lock:
                self._instances.pop(run_id, None)
            try:
                harness.close()
            except Exception:
                pass

    def cancel(self, run_id: str) -> None:
        with self._lock:
            self._cancelled.add(run_id)
            harness = self._instances.get(run_id)
        if harness is not None:
            try:
                harness.close()
            except Exception:
                pass

    def close(self) -> None:
        with self._lock:
            run_ids = list(self._instances)
        for run_id in run_ids:
            self.cancel(run_id)
