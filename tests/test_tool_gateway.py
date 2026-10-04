import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

from runtime.tool_gateway import ToolGateway, ToolGatewayError
from server import seed_state

ROOT = os.path.dirname(os.path.dirname(__file__))


def _run():
    return {
        "id": "run-tool-1",
        "task_id": "TK-20261004-0021",
        "tenant_id": "tenant-demo",
        "actor_id": "user-wu-yuhang",
        "status": "running",
        "allowed_tools": ["ticket.read", "device.status", "maintenance.action"],
        "runtime": {"allowed_tools": ["ticket.read", "device.status", "maintenance.action"]},
    }


def test_gateway_enforces_declared_tools_and_returns_after_sales_records():
    state = seed_state()
    state["runs"].append(_run())
    gateway = ToolGateway()

    ticket = gateway.call(state, tenant_id="tenant-demo", actor_id="user-wu-yuhang", run_id="run-tool-1", tool="ticket.read", arguments={"ticket_id": "8812"})
    assert ticket["ticket_id"] == "8812"
    assert ticket["device_id"] == "DEV-2987"

    device = gateway.call(state, tenant_id="tenant-demo", actor_id="user-wu-yuhang", run_id="run-tool-1", tool="device.status", arguments={"device_id": "DEV-2987"})
    assert device["state"] == "degraded"
    assert device["fault_code"] == "E-204"

    state["runs"].append({**_run(), "id": "run-tool-read-only", "allowed_tools": ["ticket.read"], "runtime": {"allowed_tools": ["ticket.read"]}})
    with pytest.raises(ToolGatewayError) as exc_info:
        gateway.call(state, tenant_id="tenant-demo", actor_id="user-wu-yuhang", run_id="run-tool-read-only", tool="device.status", arguments={"device_id": "DEV-2987"})
    assert exc_info.value.code == "tool.not_allowed"
    assert exc_info.value.status == 403


def test_maintenance_action_requires_approval_then_writes_audit_record():
    state = seed_state()
    state["runs"].append(_run())
    gateway = ToolGateway()

    with pytest.raises(ToolGatewayError) as exc_info:
        gateway.call(state, tenant_id="tenant-demo", actor_id="user-wu-yuhang", run_id="run-tool-1", tool="maintenance.action", arguments={"ticket_id": "8812", "device_id": "DEV-2987", "action": "clean_filter", "reason": "E-204"})
    assert exc_info.value.code == "tool.approval_required"

    result = gateway.call(state, tenant_id="tenant-demo", actor_id="user-wu-yuhang", run_id="run-tool-1", tool="maintenance.action", arguments={"ticket_id": "8812", "device_id": "DEV-2987", "action": "clean_filter", "reason": "E-204"}, approval_granted=True)
    assert result["status"] == "scheduled"
    assert result["action"] == "clean_filter"
    assert state["maintenance_actions"][0]["id"] == result["action_id"]


def _port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _request(base, method, path, body=None):
    raw = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(base + path, data=raw, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_http_tool_gateway_flow(tmp_path):
    port = _port()
    env = os.environ.copy()
    env.update({"PYTHONPATH": ROOT, "WORKBENCH_STORAGE": "json", "DSH_RUNTIME_MODE": "demo", "WORKBENCH_STATE_PATH": str(tmp_path / "state.json")})
    process = subprocess.Popen([sys.executable, "server.py", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(50):
            try:
                _request(base, "GET", "/api/v1/health")
                break
            except urllib.error.URLError:
                time.sleep(0.05)
        status, catalog = _request(base, "GET", "/api/v1/tools")
        assert status == 200 and {item["id"] for item in catalog} >= {"ticket.read", "device.status", "maintenance.action"}
        status, task = _request(base, "POST", "/api/v1/tasks", {"name": "工具网关诊断", "pack_id": "after-sales", "skill_id": "equipment-diagnosis"})
        assert status == 201
        status, run = _request(base, "POST", f"/api/v1/tasks/{task['id']}/runs", {})
        assert status == 201
        status, ticket = _request(base, "POST", "/api/v1/tools/call", {"run_id": run["id"], "tool": "ticket.read", "arguments": {"ticket_id": "8812"}})
        assert status == 200 and ticket["result"]["ticket_id"] == "8812"
        status, denied = _request(base, "POST", "/api/v1/tools/call", {"run_id": "run-1000", "tool": "ticket.read", "arguments": {"ticket_id": "8812"}})
        assert status == 403 and denied["error"]["code"] == "tool.not_allowed"
        status, pending = _request(base, "POST", "/api/v1/tools/call", {"run_id": run["id"], "tool": "maintenance.action", "arguments": {"ticket_id": "8812", "device_id": "DEV-2987", "action": "clean_filter", "reason": "E-204"}})
        assert status == 202 and pending["approval"]["status"] == "pending"
        status, approved = _request(base, "POST", f"/api/v1/tool-approvals/{pending['approval']['id']}/approve", {})
        assert status == 200 and approved["result"]["status"] == "scheduled"
    finally:
        process.terminate()
        process.wait(timeout=3)
