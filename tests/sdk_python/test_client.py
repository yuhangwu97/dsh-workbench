import json
from dataclasses import dataclass

import pytest

from dsh_workbench import RunStatus
from dsh_workbench.client import AsyncDSHClient, DSHClient
from dsh_workbench.errors import NotFoundError


@dataclass
class Response:
    status_code: int
    payload: object
    headers: dict[str, str]


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, path, body, headers, timeout):
        self.calls.append((method, path, body, headers, timeout))
        return self.responses.pop(0)


def test_client_creates_task_with_workspace_headers():
    transport = FakeTransport([Response(201, {"id": "task-1", "name": "Diagnose", "pack_id": "after-sales", "skill_id": "equipment-diagnosis", "status": "queued"}, {"X-Request-ID": "req-1"})])
    client = DSHClient("https://workbench.test", api_key="token", tenant_id="tenant-a", actor_id="user-a", transport=transport)
    task = client.tasks.create(name="Diagnose", pack_id="after-sales", skill_id="equipment-diagnosis", input={"code": "E-204"}, idempotency_key="create-1")
    assert task.id == "task-1"
    method, path, body, headers, _ = transport.calls[0]
    assert method == "POST"
    assert path == "/api/v1/tasks"
    assert json.loads(body)["input"]["code"] == "E-204"
    assert headers["Authorization"] == "Bearer token"
    assert headers["X-Tenant-ID"] == "tenant-a"
    assert headers["Idempotency-Key"] == "create-1"


def test_client_wait_returns_terminal_run():
    transport = FakeTransport([
        Response(200, {"id": "run-1", "status": "running"}, {}),
        Response(200, {"id": "run-1", "status": "completed", "message": "done"}, {"X-Request-ID": "req-done"}),
    ])
    client = DSHClient("https://workbench.test", transport=transport, poll_interval=0)
    run = client.runs.wait("run-1", timeout=1)
    assert run.status is RunStatus.COMPLETED
    assert len(transport.calls) == 2


def test_client_maps_error_envelope():
    transport = FakeTransport([Response(404, {"error": {"code": "task.not_found", "message": "missing", "request_id": "req-2", "details": {}}}, {})])
    client = DSHClient("https://workbench.test", transport=transport)
    with pytest.raises(NotFoundError) as exc_info:
        client.tasks.get("missing")
    assert exc_info.value.request_id == "req-2"
    assert exc_info.value.status_code == 404


def test_async_client_exposes_same_resource_shape():
    transport = FakeTransport([Response(201, {"reply": "ok", "evidence_count": 2}, {})])
    client = AsyncDSHClient("https://workbench.test", transport=transport)
    import asyncio

    response = asyncio.run(client.chat.send("hello"))
    assert response["evidence_count"] == 2


def test_client_exposes_page_token_for_large_lists():
    transport = FakeTransport([Response(200, {"items": [{"id": "task-1", "name": "A"}], "next_page_token": "1"}, {})])
    client = DSHClient("https://workbench.test", transport=transport)
    page = client.tasks.list_page(page_size=1)
    assert page.next_page_token == "1"
    assert page.items[0].id == "task-1"
