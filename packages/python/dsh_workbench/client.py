"""HTTP clients for the DSH Workbench public API."""
from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import quote

from .errors import APIError, AuthenticationError, ConflictError, NotFoundError, PermissionError, ServerError, ValidationError
from .models import Artifact, Page, Run, Task, RunStatus, is_terminal_run_status


@dataclass
class HTTPResponse:
    status_code: int
    payload: Any
    headers: Mapping[str, str]


class UrllibTransport:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, body: bytes | None, headers: Mapping[str, str], timeout: float) -> HTTPResponse:
        request = urllib.request.Request(self.base_url + path, data=body, method=method, headers=dict(headers))
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return HTTPResponse(response.status, _decode_json(response.read()), dict(response.headers.items()))
        except urllib.error.HTTPError as exc:
            return HTTPResponse(exc.code, _decode_json(exc.read()), dict(exc.headers.items()))


def _decode_json(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"raw": raw.decode("utf-8", errors="replace")}


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return [item for item in payload["items"] if isinstance(item, dict)]
    return []


_ERROR_TYPES: dict[int, type[APIError]] = {
    401: AuthenticationError,
    403: PermissionError,
    404: NotFoundError,
    409: ConflictError,
    422: ValidationError,
}


class DSHClient:
    """Synchronous SDK client.

    The client is intentionally transport-injectable so integrations can test
    their own code without a live Workbench and can provide a custom retrying
    transport in production.
    """

    def __init__(self, base_url: str, *, api_key: str | None = None, tenant_id: str | None = None, actor_id: str | None = None, timeout: float = 15.0, poll_interval: float = 1.0, transport: Any | None = None, headers: Mapping[str, str] | None = None) -> None:
        if not base_url.strip():
            raise ValueError("base_url is required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.actor_id = actor_id
        self.timeout = timeout
        self.poll_interval = max(0.0, poll_interval)
        self.transport = transport or UrllibTransport(self.base_url)
        self.headers = dict(headers or {})
        self.tasks = TasksResource(self)
        self.runs = RunsResource(self)
        self.chat = ChatResource(self)
        self.knowledge = KnowledgeResource(self)
        self.workflows = WorkflowsResource(self)
        self.approvals = ApprovalsResource(self)
        self.artifacts = ArtifactsResource(self)

    def _request(self, method: str, path: str, payload: Any | None = None, *, idempotency_key: str | None = None) -> Any:
        request_id = self.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:16]}"
        headers = {"Accept": "application/json", "Content-Type": "application/json", "X-Request-ID": request_id, **self.headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.tenant_id:
            headers["X-Tenant-ID"] = self.tenant_id
        if self.actor_id:
            headers["X-Actor-ID"] = self.actor_id
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        body = None if payload is None else json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        response = self.transport.request(method, path, body, headers, self.timeout)
        if response.status_code >= 400:
            self._raise_api_error(response)
        return response.payload

    def _raise_api_error(self, response: HTTPResponse) -> None:
        payload = response.payload if isinstance(response.payload, dict) else {}
        error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
        request_id = error.get("request_id") or response.headers.get("X-Request-ID")
        code = str(error.get("code") or f"http.{response.status_code}")
        message = str(error.get("message") or "request failed")
        details = dict(error.get("details") or {})
        error_type = _ERROR_TYPES.get(response.status_code, ServerError if response.status_code >= 500 else APIError)
        raise error_type(response.status_code, code, message, request_id, details)


class TasksResource:
    def __init__(self, client: DSHClient) -> None:
        self.client = client

    def create(self, *, name: str, pack_id: str, skill_id: str, input: Any = None, idempotency_key: str | None = None) -> Task:
        return Task.from_dict(self.client._request("POST", "/api/v1/tasks", {"name": name, "pack_id": pack_id, "skill_id": skill_id, "input": input}, idempotency_key=idempotency_key))

    def get(self, task_id: str) -> Task:
        payload = self.client._request("GET", f"/api/v1/tasks/{quote(task_id, safe='')}")
        return Task.from_dict(payload["task"] if isinstance(payload, dict) and "task" in payload else payload)

    def list(self, *, page_size: int | None = None, page_token: str | None = None) -> list[Task]:
        return self.list_page(page_size=page_size, page_token=page_token).items

    def list_page(self, *, page_size: int | None = None, page_token: str | None = None) -> Page:
        payload = self.client._request("GET", f"/api/v1/tasks{_query(page_size=page_size, page_token=page_token)}")
        return Page(items=[Task.from_dict(item) for item in _items(payload)], next_page_token=payload.get("next_page_token") if isinstance(payload, dict) else None)

    def run(self, task_id: str, *, input: Any = None, idempotency_key: str | None = None) -> Run:
        return Run.from_dict(self.client._request("POST", f"/api/v1/tasks/{quote(task_id, safe='')}/runs", {"input": input} if input is not None else {}, idempotency_key=idempotency_key))


class RunsResource:
    def __init__(self, client: DSHClient) -> None:
        self.client = client

    def get(self, run_id: str) -> Run:
        return Run.from_dict(self.client._request("GET", f"/api/v1/runs/{quote(run_id, safe='')}"))

    def list(self, *, page_size: int | None = None, page_token: str | None = None) -> list[Run]:
        return self.list_page(page_size=page_size, page_token=page_token).items

    def list_page(self, *, page_size: int | None = None, page_token: str | None = None) -> Page:
        payload = self.client._request("GET", f"/api/v1/runs{_query(page_size=page_size, page_token=page_token)}")
        return Page(items=[Run.from_dict(item) for item in _items(payload)], next_page_token=payload.get("next_page_token") if isinstance(payload, dict) else None)

    def cancel(self, run_id: str) -> Run:
        return Run.from_dict(self.client._request("POST", f"/api/v1/runs/{quote(run_id, safe='')}/cancel", {}))

    def retry(self, run_id: str) -> Run:
        return Run.from_dict(self.client._request("POST", f"/api/v1/runs/{quote(run_id, safe='')}/retry", {}))

    def queue(self) -> dict[str, Any]:
        return self.client._request("GET", "/api/v1/queue")

    def wait(self, run_id: str, *, timeout: float = 300.0, poll_interval: float | None = None) -> Run:
        deadline = time.monotonic() + timeout
        interval = self.client.poll_interval if poll_interval is None else max(0.0, poll_interval)
        while True:
            run = self.get(run_id)
            if is_terminal_run_status(run.status):
                return run
            if time.monotonic() >= deadline:
                raise TimeoutError(f"run {run_id} did not reach a terminal state within {timeout}s")
            if interval:
                time.sleep(interval)


class ChatResource:
    def __init__(self, client: DSHClient) -> None:
        self.client = client

    def send(self, message: str, *, pack_id: str = "after-sales", conversation_id: str | None = None) -> dict[str, Any]:
        return self.client._request("POST", "/api/v1/chat/messages", {"message": message, "pack_id": pack_id, "conversation_id": conversation_id})


class KnowledgeResource:
    def __init__(self, client: DSHClient) -> None:
        self.client = client

    def list_sources(self) -> list[dict[str, Any]]:
        return _items(self.client._request("GET", "/api/v1/knowledge/sources"))

    def ingest(self, *, name: str, content: str, pack_id: str = "after-sales", source_id: str | None = None, document_id: str | None = None, metadata: Mapping[str, Any] | None = None, idempotency_key: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": name, "content": content, "pack_id": pack_id}
        if source_id: payload["source_id"] = source_id
        if document_id: payload["document_id"] = document_id
        if metadata is not None: payload["metadata"] = dict(metadata)
        return self.client._request("POST", "/api/v1/knowledge/ingest", payload, idempotency_key=idempotency_key)

    def citations(self) -> list[dict[str, Any]]:
        return _items(self.client._request("GET", "/api/v1/knowledge/citations"))

    def search(self, query: str, *, pack_id: str = "after-sales", top_k: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": query, "pack_id": pack_id}
        if top_k is not None:
            payload["top_k"] = top_k
        return self.client._request("POST", "/api/v1/knowledge/search", payload)


class WorkflowsResource:
    def __init__(self, client: DSHClient) -> None:
        self.client = client

    def run(self, workflow_id: str, *, input: Any = None, idempotency_key: str | None = None) -> Run:
        return Run.from_dict(self.client._request("POST", f"/api/v1/workflows/{quote(workflow_id, safe='')}/runs", {"input": input} if input is not None else {}, idempotency_key=idempotency_key))


class ApprovalsResource:
    def __init__(self, client: DSHClient) -> None:
        self.client = client

    def approve(self, task_id: str) -> dict[str, Any]:
        return self.client._request("POST", f"/api/v1/approvals/{quote(task_id, safe='')}/approve", {})

    def reject(self, task_id: str) -> dict[str, Any]:
        return self.client._request("POST", f"/api/v1/approvals/{quote(task_id, safe='')}/reject", {})


class ArtifactsResource:
    def __init__(self, client: DSHClient) -> None:
        self.client = client

    def list(self, *, task_id: str | None = None) -> list[Artifact]:
        path = f"/api/v1/tasks/{quote(task_id, safe='')}/artifacts" if task_id else "/api/v1/artifacts"
        return [Artifact.from_dict(item) for item in _items(self.client._request("GET", path))]

    def list_page(self, *, page_size: int | None = None, page_token: str | None = None) -> Page:
        payload = self.client._request("GET", f"/api/v1/artifacts{_query(page_size=page_size, page_token=page_token)}")
        return Page(items=[Artifact.from_dict(item) for item in _items(payload)], next_page_token=payload.get("next_page_token") if isinstance(payload, dict) else None)

    def get(self, artifact_id: str, *, task_id: str | None = None) -> Artifact:
        artifacts = self.list(task_id=task_id)
        for artifact in artifacts:
            if artifact.id == artifact_id or artifact.name == artifact_id:
                return artifact
        raise NotFoundError(404, "artifact.not_found", "artifact not found", None, {"id": artifact_id})


class AsyncDSHClient:
    """Async facade using a worker thread around the dependency-free sync client."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._sync = DSHClient(*args, **kwargs)
        self.tasks = _AsyncTasks(self._sync.tasks)
        self.runs = _AsyncRuns(self._sync.runs)
        self.chat = _AsyncChat(self._sync.chat)
        self.knowledge = _AsyncKnowledge(self._sync.knowledge)
        self.workflows = _AsyncWorkflows(self._sync.workflows)
        self.approvals = _AsyncApprovals(self._sync.approvals)
        self.artifacts = _AsyncArtifacts(self._sync.artifacts)


class _AsyncMethod:
    def __init__(self, method: Callable[..., Any]) -> None:
        self.method = method

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self.method, *args, **kwargs)


class _AsyncTasks:
    def __init__(self, resource: TasksResource) -> None:
        self.resource = resource

    async def create(self, **kwargs: Any) -> Task: return await asyncio.to_thread(self.resource.create, **kwargs)
    async def get(self, task_id: str) -> Task: return await asyncio.to_thread(self.resource.get, task_id)
    async def list(self, **kwargs: Any) -> list[Task]: return await asyncio.to_thread(self.resource.list, **kwargs)
    async def run(self, task_id: str, **kwargs: Any) -> Run: return await asyncio.to_thread(self.resource.run, task_id, **kwargs)


class _AsyncRuns:
    def __init__(self, resource: RunsResource) -> None:
        self.resource = resource

    async def get(self, run_id: str) -> Run: return await asyncio.to_thread(self.resource.get, run_id)
    async def list(self, **kwargs: Any) -> list[Run]: return await asyncio.to_thread(self.resource.list, **kwargs)
    async def cancel(self, run_id: str) -> Run: return await asyncio.to_thread(self.resource.cancel, run_id)
    async def retry(self, run_id: str) -> Run: return await asyncio.to_thread(self.resource.retry, run_id)
    async def queue(self) -> dict[str, Any]: return await asyncio.to_thread(self.resource.queue)
    async def wait(self, run_id: str, **kwargs: Any) -> Run: return await asyncio.to_thread(self.resource.wait, run_id, **kwargs)


class _AsyncApprovals:
    def __init__(self, resource: ApprovalsResource) -> None:
        self.resource = resource

    async def approve(self, task_id: str) -> dict[str, Any]: return await asyncio.to_thread(self.resource.approve, task_id)
    async def reject(self, task_id: str) -> dict[str, Any]: return await asyncio.to_thread(self.resource.reject, task_id)


class _AsyncArtifacts:
    def __init__(self, resource: ArtifactsResource) -> None:
        self.resource = resource

    async def list(self, **kwargs: Any) -> list[Artifact]: return await asyncio.to_thread(self.resource.list, **kwargs)
    async def get(self, artifact_id: str, **kwargs: Any) -> Artifact: return await asyncio.to_thread(self.resource.get, artifact_id, **kwargs)


class _AsyncChat:
    def __init__(self, resource: ChatResource) -> None:
        self.resource = resource

    async def send(self, message: str, **kwargs: Any) -> dict[str, Any]: return await asyncio.to_thread(self.resource.send, message, **kwargs)
    async def __call__(self, message: str, **kwargs: Any) -> dict[str, Any]: return await self.send(message, **kwargs)


class _AsyncKnowledge:
    def __init__(self, resource: KnowledgeResource) -> None:
        self.resource = resource

    async def search(self, query: str, **kwargs: Any) -> dict[str, Any]: return await asyncio.to_thread(self.resource.search, query, **kwargs)


class _AsyncWorkflows:
    def __init__(self, resource: WorkflowsResource) -> None:
        self.resource = resource

    async def run(self, workflow_id: str, **kwargs: Any) -> Run: return await asyncio.to_thread(self.resource.run, workflow_id, **kwargs)


def _query(**values: Any) -> str:
    pairs = [(key, str(value)) for key, value in values.items() if value is not None]
    return "?" + "&".join(f"{quote(key)}={quote(value)}" for key, value in pairs) if pairs else ""
