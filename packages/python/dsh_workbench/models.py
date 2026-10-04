"""Typed, transport-neutral resource models shared by the SDK."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, TypeVar

from .errors import ModelError


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    WAITING_APPROVAL = "waiting_approval"
    FAILED = "failed"
    REJECTED = "rejected"

    @classmethod
    def parse(cls, value: str) -> "RunStatus":
        try:
            return cls(value)
        except ValueError as exc:
            raise ModelError(f"unknown run status: {value!r}") from exc


TERMINAL_RUN_STATUSES = frozenset({RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.REJECTED})
T = TypeVar("T", bound="Resource")


def _required(data: dict[str, Any], key: str) -> Any:
    value = data.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ModelError(f"missing required field: {key}")
    return value


def _optional_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ModelError(f"invalid datetime: {value!r}") from exc
    raise ModelError(f"invalid datetime value: {value!r}")


@dataclass
class Resource:
    id: str
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    _known_fields: ClassVar[frozenset[str]] = frozenset({"id"})

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result.pop("extra", None)
        result.update(self.extra)
        for key, value in list(result.items()):
            if isinstance(value, Enum):
                result[key] = value.value
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
        return result


@dataclass
class Task(Resource):
    name: str = ""
    pack_id: str = ""
    skill_id: str = ""
    status: str = "queued"
    status_label: str | None = None
    input_snapshot: Any = None
    tenant_id: str | None = None
    created_by: str | None = None
    updated: str | None = None
    copy: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        known = {"id", "name", "pack_id", "skill_id", "status", "status_label", "input_snapshot", "tenant_id", "created_by", "updated", "copy"}
        return cls(
            id=str(_required(data, "id")),
            name=str(_required(data, "name")),
            pack_id=str(data.get("pack_id", "")),
            skill_id=str(data.get("skill_id", "")),
            status=str(data.get("status", "queued")),
            status_label=data.get("status_label"),
            input_snapshot=data.get("input_snapshot"),
            tenant_id=data.get("tenant_id"),
            created_by=data.get("created_by"),
            updated=data.get("updated"),
            copy=data.get("copy"),
            extra={key: value for key, value in data.items() if key not in known},
        )


@dataclass
class Artifact(Resource):
    name: str = ""
    type: str = "file"
    description: str | None = None
    task_id: str | None = None
    run_id: str | None = None
    tenant_id: str | None = None
    uri: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Artifact":
        known = {"id", "name", "type", "description", "task_id", "run_id", "tenant_id", "uri"}
        return cls(
            id=str(data.get("id", data.get("name", "artifact"))),
            name=str(_required(data, "name")),
            type=str(data.get("type", "file")),
            description=data.get("description"),
            task_id=data.get("task_id"),
            run_id=data.get("run_id"),
            tenant_id=data.get("tenant_id"),
            uri=data.get("uri"),
            extra={key: value for key, value in data.items() if key not in known},
        )


@dataclass
class Run(Resource):
    status: RunStatus = RunStatus.QUEUED
    task_id: str | None = None
    workflow_id: str | None = None
    skill_id: str | None = None
    message: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    tenant_id: str | None = None
    actor_id: str | None = None
    runtime: dict[str, Any] = field(default_factory=dict)
    duration: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Run":
        known = {"id", "status", "task_id", "workflow_id", "skill_id", "message", "created_at", "started_at", "finished_at", "tenant_id", "actor_id", "runtime", "duration"}
        return cls(
            id=str(_required(data, "id")),
            status=RunStatus.parse(str(data.get("status", "queued"))),
            task_id=data.get("task_id"),
            workflow_id=data.get("workflow_id"),
            skill_id=data.get("skill_id"),
            message=data.get("message"),
            created_at=_optional_datetime(data.get("created_at")),
            started_at=_optional_datetime(data.get("started_at")),
            finished_at=_optional_datetime(data.get("finished_at")),
            tenant_id=data.get("tenant_id"),
            actor_id=data.get("actor_id"),
            runtime=dict(data.get("runtime") or {}),
            duration=data.get("duration"),
            extra={key: value for key, value in data.items() if key not in known},
        )

    @property
    def terminal(self) -> bool:
        return is_terminal_run_status(self.status)


@dataclass
class ErrorDetail:
    code: str
    message: str
    request_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ErrorDetail":
        return cls(code=str(_required(data, "code")), message=str(_required(data, "message")), request_id=data.get("request_id"), details=dict(data.get("details") or {}))


@dataclass
class ErrorEnvelope:
    error: ErrorDetail

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ErrorEnvelope":
        error = data.get("error")
        if not isinstance(error, dict):
            raise ModelError("response.error must be an object")
        return cls(error=ErrorDetail.from_dict(error))


@dataclass
class Event(Resource):
    type: str = ""
    resource_type: str = ""
    resource_id: str = ""
    tenant_id: str | None = None
    actor_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        known = {"id", "type", "resource_type", "resource_id", "tenant_id", "actor_id", "data", "created_at"}
        return cls(id=str(_required(data, "id")), type=str(_required(data, "type")), resource_type=str(_required(data, "resource_type")), resource_id=str(_required(data, "resource_id")), tenant_id=data.get("tenant_id"), actor_id=data.get("actor_id"), data=dict(data.get("data") or {}), created_at=_optional_datetime(data.get("created_at")), extra={key: value for key, value in data.items() if key not in known})


@dataclass
class Page:
    items: list[Any]
    next_page_token: str | None = None


def is_terminal_run_status(status: RunStatus | str) -> bool:
    return RunStatus.parse(status) in TERMINAL_RUN_STATUSES
