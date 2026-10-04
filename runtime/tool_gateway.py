"""Policy-enforced business tools exposed to DSH Harness runs.

The Harness prompt can describe a policy, but it is not an authorization
boundary. Every business tool call must come through this gateway, where the
tenant, run and declared ``allowed_tools`` are checked before dispatch.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any, Callable


class ToolGatewayError(RuntimeError):
    def __init__(self, code: str, message: str, status: int = 400, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}


@dataclass(frozen=True)
class ToolDefinition:
    id: str
    description: str
    kind: str
    requires_approval: bool
    handler: Callable[[dict, dict[str, Any], dict[str, Any]], dict[str, Any]]


def _identifier(value: Any, field: str) -> str:
    result = str(value or "").strip().upper().replace("#", "")
    if not result or len(result) > 120 or not re.fullmatch(r"[A-Z0-9:_-]+", result):
        raise ToolGatewayError("tool.invalid_arguments", f"{field} is required and must be a safe identifier", 422)
    return result


def _ticket_read(_state: dict, arguments: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
    ticket_id = _identifier(arguments.get("ticket_id"), "ticket_id")
    records = {
        "8812": {"ticket_id": "8812", "status": "open", "priority": "high", "customer": "北辰装备", "device_id": "DEV-2987", "symptoms": ["高负载时出现 E-204", "服务每 20 分钟中断"], "last_update": "2026-10-04T08:12:00Z"},
        "TK-20261004-0021": {"ticket_id": "TK-20261004-0021", "status": "investigating", "priority": "urgent", "customer": "华东制造", "device_id": "DEV-3021", "symptoms": ["冷却回路告警", "现场无法恢复"], "last_update": "2026-10-04T09:24:00Z"},
    }
    record = records.get(ticket_id)
    if record is None:
        raise ToolGatewayError("ticket.not_found", "ticket not found", 404, {"ticket_id": ticket_id})
    return dict(record)


def _device_status(_state: dict, arguments: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
    device_id = _identifier(arguments.get("device_id"), "device_id")
    records = {
        "DEV-2987": {"device_id": "DEV-2987", "serial_number": "SN-2987-A", "state": "degraded", "fault_code": "E-204", "temperature_c": 78.4, "pump_power": "unstable", "filter_status": "blocked", "last_seen": "2026-10-04T08:11:42Z"},
        "DEV-3021": {"device_id": "DEV-3021", "serial_number": "SN-3021-B", "state": "offline", "fault_code": "E-204", "temperature_c": 81.1, "pump_power": "unknown", "filter_status": "unknown", "last_seen": "2026-10-04T09:20:13Z"},
    }
    record = records.get(device_id)
    if record is None:
        raise ToolGatewayError("device.not_found", "device not found", 404, {"device_id": device_id})
    return dict(record)


def _maintenance_action(state: dict, arguments: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    ticket_id = _identifier(arguments.get("ticket_id"), "ticket_id")
    device_id = _identifier(arguments.get("device_id"), "device_id")
    action = str(arguments.get("action", "")).strip().lower()
    reason = str(arguments.get("reason", "")).strip()[:500]
    allowed_actions = {"clean_filter", "replace_pump_relay", "dispatch_technician"}
    if action not in allowed_actions:
        raise ToolGatewayError("maintenance.action_invalid", "unsupported maintenance action", 422, {"allowed_actions": sorted(allowed_actions)})
    if not reason:
        raise ToolGatewayError("maintenance.reason_required", "reason is required", 422)
    action_id = f"maint-{uuid.uuid4().hex[:10]}"
    item = {
        "id": action_id,
        "action_id": action_id,
        "tool": "maintenance.action",
        "ticket_id": ticket_id,
        "device_id": device_id,
        "action": action,
        "reason": reason,
        "status": "scheduled",
        "tenant_id": context["tenant_id"],
        "actor_id": context["actor_id"],
        "run_id": context["run_id"],
    }
    state.setdefault("maintenance_actions", []).insert(0, item)
    return {key: value for key, value in item.items() if key not in {"tenant_id", "actor_id"}}


class ToolGateway:
    """Dispatch product tools only after run-scoped authorization checks."""

    def __init__(self) -> None:
        self._definitions = {
            definition.id: definition
            for definition in (
                ToolDefinition("ticket.read", "Read a support ticket and its reported symptoms.", "read", False, _ticket_read),
                ToolDefinition("device.status", "Read the latest device telemetry and fault state.", "read", False, _device_status),
                ToolDefinition("maintenance.action", "Schedule an approved field maintenance action.", "write", True, _maintenance_action),
            )
        }

    def catalog(self) -> list[dict[str, Any]]:
        return [{"id": item.id, "description": item.description, "kind": item.kind, "requires_approval": item.requires_approval} for item in self._definitions.values()]

    def call(self, state: dict, *, tenant_id: str, actor_id: str, run_id: str, tool: str, arguments: dict[str, Any] | None = None, approval_granted: bool = False) -> dict[str, Any]:
        run = next((item for item in state.get("runs", []) if item.get("id") == run_id), None)
        if run is None:
            raise ToolGatewayError("run.not_found", "run not found", 404, {"run_id": run_id})
        if run.get("tenant_id") != tenant_id:
            raise ToolGatewayError("run.forbidden", "run belongs to another tenant", 403)
        if run.get("actor_id") and run.get("actor_id") != actor_id:
            raise ToolGatewayError("tool.actor_mismatch", "run belongs to another actor", 403)
        definition = self._definitions.get(str(tool).strip())
        if definition is None:
            raise ToolGatewayError("tool.not_found", "tool is not registered", 404, {"tool": tool})
        allowed = set(run.get("allowed_tools") or run.get("runtime", {}).get("allowed_tools", []))
        if definition.id not in allowed:
            raise ToolGatewayError("tool.not_allowed", "tool is not declared by this run", 403, {"tool": definition.id, "allowed_tools": sorted(allowed)})
        if run.get("status") not in {"queued", "running", "waiting_approval"}:
            raise ToolGatewayError("run.not_active", "tool calls are only allowed for active runs", 409, {"run_id": run_id, "status": run.get("status")})
        if definition.requires_approval and not approval_granted:
            raise ToolGatewayError("tool.approval_required", "maintenance action requires approval", 409, {"tool": definition.id, "run_id": run_id})
        result = definition.handler(state, dict(arguments or {}), {"tenant_id": tenant_id, "actor_id": actor_id, "run_id": run_id})
        return {"tool": definition.id, "kind": definition.kind, **result}
