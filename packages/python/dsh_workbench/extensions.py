"""Provider protocols for replacing infrastructure without forking the domain layer."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .models import Artifact, Event, Run


@runtime_checkable
class KnowledgeProvider(Protocol):
    def search(self, query: str, *, scope: list[str], tenant_id: str, actor_id: str, top_k: int = 10) -> list[dict[str, Any]]: ...


@runtime_checkable
class SkillProvider(Protocol):
    def run(self, *, skill_id: str, task_id: str, input: Any, allowed_tools: list[str], tenant_id: str, actor_id: str) -> Run: ...


@runtime_checkable
class WorkflowExecutor(Protocol):
    def start(self, *, workflow_id: str, task_id: str | None, input: Any, tenant_id: str, actor_id: str) -> Run: ...


@runtime_checkable
class ArtifactStore(Protocol):
    def put(self, artifact: Artifact, content: bytes) -> Artifact: ...
    def get(self, artifact: Artifact) -> bytes: ...
    def list(self, *, task_id: str | None, tenant_id: str) -> list[Artifact]: ...


@runtime_checkable
class ApprovalPolicy(Protocol):
    def evaluate(self, *, action: str, context: dict[str, Any], tenant_id: str, actor_id: str) -> bool: ...


@runtime_checkable
class EventSink(Protocol):
    def publish(self, event: Event) -> None: ...
