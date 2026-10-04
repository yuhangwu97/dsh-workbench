#!/usr/bin/env python3
"""Small local API + static server for the DSH Workbench product demo."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import mimetypes
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from runtime.dsh_runtime import DshRuntime

ROOT = Path(__file__).resolve().parent
STATE_PATH = Path(os.getenv("WORKBENCH_STATE_PATH", str(ROOT / "data" / "state.json")))
DB_PATH = ROOT / "data" / "workbench.sqlite3"
STORAGE_MODE = os.getenv("WORKBENCH_STORAGE", "json").strip().lower() or "json"
LOCK = threading.Lock()
DSH_RUNTIME = DshRuntime()
DEMO_TENANT_ID = "tenant-demo"
DEMO_ACTOR_ID = "user-wu-yuhang"
AUTH_TOKEN = os.getenv("WORKBENCH_AUTH_TOKEN", "").strip()
DSH_CALLBACK_SECRET = os.getenv("DSH_CALLBACK_SECRET", "").strip()
CALLBACK_MAX_SKEW = int(os.getenv("DSH_CALLBACK_MAX_SKEW", "300"))

PACKS = [
    {"id": "after-sales", "name": "售后诊断", "color": "green", "status": "enabled", "skills": 8, "workflows": 3, "knowledge_bases": 4, "description": "面向售后团队的设备问题定位、证据收集和维修建议。"},
    {"id": "engineering", "name": "研发助手", "color": "blue", "status": "enabled", "skills": 6, "workflows": 4, "knowledge_bases": 2, "description": "面向研发团队的 Issue 调查、变更分析和测试计划。"},
    {"id": "operations", "name": "运营告警", "color": "orange", "status": "enabled", "skills": 5, "workflows": 2, "knowledge_bases": 3, "description": "面向运营团队的告警聚合、影响分析和升级流程。"},
]
SKILLS = [
    {"id": "equipment-diagnosis", "name": "设备故障诊断", "pack_id": "after-sales", "version": "1.3.0", "trust": "verified", "dependencies": ["kb.search", "ticket.read", "device.status"]},
    {"id": "issue-investigation", "name": "Issue 调查", "pack_id": "engineering", "version": "0.8.2", "trust": "verified", "dependencies": ["repo.read", "issue.read", "search"]},
    {"id": "alert-triage", "name": "告警处置", "pack_id": "operations", "version": "2.1.0", "trust": "org", "dependencies": ["alert.read", "runbook.search"]},
]
SEED_TASKS = [
    {"id": "TK-20261004-0021", "name": "设备 #3021 故障诊断", "pack_id": "after-sales", "skill_id": "equipment-diagnosis", "status": "running", "status_label": "进行中", "updated": "2 分钟前", "copy": "已找到 3 条相关历史案例，建议检查冷却泵电源和过滤器状态。"},
    {"id": "TK-20261004-0018", "name": "RemoteHelpDesk #1842", "pack_id": "engineering", "skill_id": "issue-investigation", "status": "review", "status_label": "待确认", "updated": "12 分钟前", "copy": "已整理代码上下文和复现路径，建议先确认 API 兼容性，再进入修改计划。"},
    {"id": "TK-20261004-0016", "name": "支付服务 P95 延迟", "pack_id": "operations", "skill_id": "alert-triage", "status": "approval", "status_label": "需审批", "updated": "31 分钟前", "copy": "已聚合 4 条重复告警，影响支付 API。建议按照支付服务 Runbook 升级值班负责人。"},
    {"id": "TK-20261003-0091", "name": "Q3 设备巡检报告", "pack_id": "after-sales", "skill_id": "equipment-diagnosis", "status": "completed", "status_label": "已完成", "updated": "昨天", "copy": "巡检报告已生成，包含设备状态摘要和 12 条证据引用。"},
]

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def seed_state() -> dict:
    return {
        "tasks": SEED_TASKS.copy(),
        "runs": [
            {"id": "run-1001", "task_id": "TK-20261004-0021", "skill_id": "equipment-diagnosis", "status": "running", "duration": "18.4s", "message": "3 个引用", "created_at": now_iso()},
            {"id": "run-1000", "task_id": "TK-20261004-0018", "skill_id": "issue-investigation", "status": "running", "duration": "", "message": "6 个工具调用", "created_at": now_iso()},
            {"id": "run-0999", "task_id": "TK-20261004-0016", "skill_id": "alert-triage", "status": "approval", "duration": "", "message": "影响范围分析", "created_at": now_iso()},
        ],
        "approvals": [{"id": "TK-20261004-0016", "task_id": "TK-20261004-0016", "status": "pending", "reason": "升级运营告警"}],
        "audit": [],
        "idempotency": {},
        "artifacts": {
            "TK-20261004-0021": [
                {"name": "DiagnosisReport.json", "type": "json", "description": "结构化诊断结果 · 24 KB"},
                {"name": "evidence-bundle.md", "type": "evidence", "description": "3 条引用 · 8 KB"},
            ]
        },
        "knowledge": [
            {"id": "product-manuals", "name": "产品手册", "pack_id": "after-sales", "documents": 128, "status": "ready", "updated": "今天 09:24"},
            {"id": "historical-tickets", "name": "历史工单", "pack_id": "after-sales", "documents": 3842, "status": "ready", "updated": "昨天 18:42"},
            {"id": "repository-docs", "name": "Repository Docs", "pack_id": "engineering", "documents": 86, "status": "indexing", "updated": "12 分钟前"},
            {"id": "runbooks", "name": "Service Runbooks", "pack_id": "operations", "documents": 42, "status": "ready", "updated": "3 天前"},
        ],
        "workflows": [
            {"id": "diagnose-equipment-v2", "name": "售后诊断 v2", "pack_id": "after-sales", "steps": 5, "status": "published"},
            {"id": "issue-to-patch-plan", "name": "Issue to Patch Plan", "pack_id": "engineering", "steps": 4, "status": "published"},
            {"id": "alert-to-escalation", "name": "Alert to Escalation", "pack_id": "operations", "steps": 4, "status": "published"},
        ],
    }

def read_raw_state() -> dict:
    if STORAGE_MODE == "sqlite":
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DB_PATH, timeout=5) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS workbench_state (id INTEGER PRIMARY KEY CHECK (id = 1), payload TEXT NOT NULL)")
            row = connection.execute("SELECT payload FROM workbench_state WHERE id = 1").fetchone()
        if row:
            try:
                return json.loads(row[0])
            except json.JSONDecodeError:
                return seed_state()
        if STATE_PATH.exists():
            try:
                return json.loads(STATE_PATH.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return seed_state()
        return seed_state()
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not STATE_PATH.exists():
        return seed_state()
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return seed_state()

def load_state() -> dict:
    state = read_raw_state()
    storage_missing = False
    if STORAGE_MODE == "sqlite":
        with sqlite3.connect(DB_PATH, timeout=5) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS workbench_state (id INTEGER PRIMARY KEY CHECK (id = 1), payload TEXT NOT NULL)")
            storage_missing = connection.execute("SELECT 1 FROM workbench_state WHERE id = 1").fetchone() is None
    try:
        seed = seed_state()
        changed = False
        for key in ("knowledge", "workflows"):
            if key not in state:
                state[key] = seed[key]
                changed = True
        if "audit" not in state:
            state["audit"] = seed["audit"]
            changed = True
        if "idempotency" not in state or not isinstance(state["idempotency"], dict):
            state["idempotency"] = {}
            changed = True
        for task in state.get("tasks", []):
            if "input_snapshot" not in task:
                task["input_snapshot"] = task.get("name", "")
                changed = True
            if "tenant_id" not in task:
                task["tenant_id"] = DEMO_TENANT_ID
                changed = True
            if "created_by" not in task:
                task["created_by"] = DEMO_ACTOR_ID
                changed = True
        task_lookup = {task["id"]: task for task in state.get("tasks", [])}
        for run in state.get("runs", []):
            owner = task_lookup.get(run.get("task_id"), {})
            if "tenant_id" not in run:
                run["tenant_id"] = owner.get("tenant_id", DEMO_TENANT_ID)
                changed = True
            if "actor_id" not in run:
                run["actor_id"] = owner.get("created_by", DEMO_ACTOR_ID)
                changed = True
        for task_id, artifacts in state.get("artifacts", {}).items():
            owner = task_lookup.get(task_id, {})
            for artifact in artifacts:
                if "tenant_id" not in artifact:
                    artifact["tenant_id"] = owner.get("tenant_id", DEMO_TENANT_ID)
                    changed = True
        if changed or storage_missing:
            save_state(state)
        return state
    except (TypeError, KeyError):
        state = seed_state()
        save_state(state)
        return state

def save_state(state: dict) -> None:
    payload = json.dumps(state, ensure_ascii=False, indent=2)
    if STORAGE_MODE == "sqlite":
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DB_PATH, timeout=5) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS workbench_state (id INTEGER PRIMARY KEY CHECK (id = 1), payload TEXT NOT NULL)")
            connection.execute("INSERT INTO workbench_state (id, payload) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET payload = excluded.payload", (payload,))
        return
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE_PATH.with_suffix(".tmp")
    temp.write_text(payload, encoding="utf-8")
    temp.replace(STATE_PATH)

def pack_for(pack_id: str) -> dict:
    return next((p for p in PACKS if p["id"] == pack_id), PACKS[0])

def skill_for(skill_id: str) -> dict:
    return next((s for s in SKILLS if s["id"] == skill_id), SKILLS[0])

def request_context(handler: BaseHTTPRequestHandler) -> tuple[str, str]:
    tenant_id = handler.headers.get("X-Tenant-ID", DEMO_TENANT_ID).strip() or DEMO_TENANT_ID
    actor_id = handler.headers.get("X-Actor-ID", DEMO_ACTOR_ID).strip() or DEMO_ACTOR_ID
    return tenant_id[:80], actor_id[:80]

def record_audit(state: dict, *, tenant_id: str, actor_id: str, action: str, resource_type: str, resource_id: str, metadata: dict | None = None) -> None:
    state.setdefault("audit", []).insert(0, {
        "id": f"audit-{uuid.uuid4().hex[:10]}",
        "tenant_id": tenant_id,
        "actor_id": actor_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "metadata": metadata or {},
        "created_at": now_iso(),
    })

def schedule_local_run(run_id: str, *, task_id: str | None = None, workflow_id: str | None = None) -> None:
    """Advance a demo run in the background so the product has a real lifecycle."""
    def worker() -> None:
        with LOCK:
            state = load_state()
            run = next((item for item in state["runs"] if item["id"] == run_id), None)
            if not run:
                return
            run["status"] = "running"
            run["started_at"] = now_iso()
            run["message"] = "运行时正在执行"
            if task_id:
                task = next((item for item in state["tasks"] if item["id"] == task_id), None)
                if task:
                    approval_required = run.get("runtime", {}).get("approval_required")
                    task["status"] = "approval" if approval_required else "running"
                    task["status_label"] = "需审批" if approval_required else "进行中"
                    task["updated"] = "刚刚"
            save_state(state)

        # Keep the demo deterministic while making the state transition observable.
        threading.Event().wait(0.8)

        with LOCK:
            state = load_state()
            run = next((item for item in state["runs"] if item["id"] == run_id), None)
            if not run:
                return
            task = next((item for item in state["tasks"] if item["id"] == task_id), None) if task_id else None
            if task and run.get("runtime", {}).get("approval_required"):
                run["status"] = "waiting_approval"
                run["message"] = "业务动作需要审批"
                run["finished_at"] = now_iso()
                task["status"] = "approval"
                task["status_label"] = "需审批"
            elif task:
                run["status"] = "completed"
                run["duration"] = "0.8s"
                run["message"] = "已生成结构化结果和证据包"
                run["finished_at"] = now_iso()
                task["status"] = "completed"
                task["status_label"] = "已完成"
                task["updated"] = "刚刚"
                task["copy"] = "运行已完成，结果已保存为 Artifact，可继续查看证据和执行轨迹。"
                artifact_base = f"{task_id}-{run_id}"
                state["artifacts"].setdefault(task_id, []).extend([
                    {"name": f"{artifact_base}.json", "type": "json", "description": "结构化运行结果 · 12 KB", "run_id": run_id, "tenant_id": run.get("tenant_id", DEMO_TENANT_ID)},
                    {"name": f"{artifact_base}-evidence.md", "type": "evidence", "description": "知识库引用和执行证据 · 6 KB", "run_id": run_id, "tenant_id": run.get("tenant_id", DEMO_TENANT_ID)},
                ])
            else:
                run["status"] = "completed"
                run["duration"] = "0.8s"
                run["message"] = "Workflow 运行完成"
                run["finished_at"] = now_iso()
            record_audit(state, tenant_id=run.get("tenant_id", DEMO_TENANT_ID), actor_id=run.get("actor_id", DEMO_ACTOR_ID), action=f"run.{run['status']}", resource_type="run", resource_id=run_id, metadata={"task_id": task_id, "workflow_id": workflow_id})
            save_state(state)

    threading.Thread(target=worker, name=f"dsh-run-{run_id}", daemon=True).start()

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}")

    def send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Request-ID", getattr(self, "request_id", ""))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, code: str, message: str, status: int, details: dict | None = None) -> None:
        self.send_json({"error": {"code": code, "message": message, "request_id": getattr(self, "request_id", None), "details": details or {}}}, status)

    def remember_idempotency(self, state: dict, path: str, payload: object, status: int) -> None:
        key = self.headers.get("Idempotency-Key", "").strip()
        if not key:
            return
        tenant_id, _ = request_context(self)
        state.setdefault("idempotency", {})[f"{tenant_id}:POST:{path}:{key[:200]}"] = {"status": status, "payload": payload, "fingerprint": hashlib.sha256(getattr(self, "raw_body", b"")).hexdigest()}

    def replay_idempotency(self, state: dict, path: str) -> bool:
        key = self.headers.get("Idempotency-Key", "").strip()
        if not key:
            return False
        tenant_id, _ = request_context(self)
        saved = state.get("idempotency", {}).get(f"{tenant_id}:POST:{path}:{key[:200]}")
        if not saved:
            return False
        current_fingerprint = hashlib.sha256(getattr(self, "raw_body", b"")).hexdigest()
        if saved.get("fingerprint") and saved["fingerprint"] != current_fingerprint:
            self.send_error_json("idempotency.conflict", "Idempotency-Key was already used with a different request", 409)
            return True
        self.send_json(saved["payload"], int(saved["status"]))
        return True

    def verify_callback_signature(self) -> bool:
        if not DSH_CALLBACK_SECRET:
            return True
        timestamp = self.headers.get("X-DSH-Timestamp", "").strip()
        signature = self.headers.get("X-DSH-Signature", "").strip()
        try:
            timestamp_value = int(timestamp)
        except ValueError:
            return False
        if abs(int(datetime.now(timezone.utc).timestamp()) - timestamp_value) > CALLBACK_MAX_SKEW:
            return False
        expected = hmac.new(DSH_CALLBACK_SECRET.encode("utf-8"), f"{timestamp}.".encode("utf-8") + getattr(self, "raw_body", b""), hashlib.sha256).hexdigest()
        supplied = signature.removeprefix("sha256=")
        return bool(supplied) and hmac.compare_digest(supplied, expected)

    def paginated(self, items: list[dict]) -> list[dict] | dict | None:
        query = parse_qs(urlparse(self.path).query)
        if "page_size" not in query and "page_token" not in query:
            return items
        try:
            page_size = min(max(int(query.get("page_size", ["50"])[0]), 1), 100)
            offset = max(int(query.get("page_token", ["0"])[0] or "0"), 0)
        except ValueError:
            self.send_error_json("pagination.invalid", "page_size and page_token must be numeric", 422)
            return None
        page = items[offset:offset + page_size]
        next_offset = offset + page_size
        return {"items": page, "next_page_token": str(next_offset) if next_offset < len(items) else None}

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1024 * 1024:
            raise ValueError("request body too large")
        raw = self.rfile.read(length) if length else b"{}"
        self.raw_body = raw
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("body must be an object")
        return payload

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Tenant-ID, X-Actor-ID, X-Request-ID, Idempotency-Key, X-DSH-Timestamp, X-DSH-Signature")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        self.request_id = self.headers.get("X-Request-ID", "").strip()[:120] or f"req_{uuid.uuid4().hex[:16]}"
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            if not self.authorized(parsed.path):
                return
            self.api_get(parsed.path)
        else:
            self.static_get(parsed.path)

    def do_POST(self):
        self.request_id = self.headers.get("X-Request-ID", "").strip()[:120] or f"req_{uuid.uuid4().hex[:16]}"
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self.send_error_json("route.not_found", "not found", 404)
            return
        if not self.authorized(parsed.path):
            return
        try:
            self.api_post(parsed.path, self.read_json())
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_error_json("request.invalid", str(exc), 400)
        except Exception as exc:  # keep local demo errors inspectable
            self.send_error_json("internal.error", str(exc), 500)

    def authorized(self, path: str) -> bool:
        if not AUTH_TOKEN or path in {"/api/v1/health", "/api/v1/ready"}:
            return True
        authorization = self.headers.get("Authorization", "")
        supplied = authorization[7:].strip() if authorization.startswith("Bearer ") else ""
        if supplied and hmac.compare_digest(supplied, AUTH_TOKEN):
            return True
        self.send_error_json("auth.required", "authentication required", 401)
        return False

    def static_get(self, path: str):
        requested = (ROOT / path.lstrip("/")).resolve()
        if path in ("", "/"):
            requested = ROOT / "index.html"
        if ROOT not in requested.parents and requested != ROOT:
            self.send_error(403)
            return
        if not requested.exists() or requested.is_dir():
            self.send_error(404)
            return
        body = requested.read_bytes()
        content_type = mimetypes.guess_type(str(requested))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type + ("; charset=utf-8" if content_type.startswith("text/") or content_type == "application/javascript" else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def api_get(self, path: str):
        with LOCK:
            state = load_state()
            tenant_id, _ = request_context(self)
            visible_tasks = [task for task in state["tasks"] if task.get("tenant_id", DEMO_TENANT_ID) == tenant_id]
            visible_task_ids = {task["id"] for task in visible_tasks}
            visible_runs = [run for run in state["runs"] if run.get("task_id") in visible_task_ids or run.get("tenant_id", DEMO_TENANT_ID) == tenant_id]
            if path == "/api/v1/health":
                self.send_json({"status": "ok", "service": "dsh-workbench", "auth": {"mode": "bearer" if AUTH_TOKEN else "demo"}, "runtime": DSH_RUNTIME.metadata()})
            elif path == "/api/v1/ready":
                self.send_json({"status": "ready", "service": "dsh-workbench", "storage": {"type": STORAGE_MODE, "status": "available"}, "runtime": DSH_RUNTIME.metadata()})
            elif path == "/api/v1/runtime":
                self.send_json(DSH_RUNTIME.metadata())
            elif path == "/api/v1/dashboard":
                approvals = [approval for approval in state["approvals"] if approval.get("task_id") in visible_task_ids]
                artifacts = {task_id: items for task_id, items in state["artifacts"].items() if task_id in visible_task_ids}
                self.send_json({"packs": PACKS, "skills": SKILLS, "tasks": visible_tasks, "runs": visible_runs, "approvals": approvals, "knowledge": state["knowledge"], "workflows": state["workflows"], "artifacts": artifacts, "metrics": {"open_tasks": sum(t["status"] != "completed" for t in visible_tasks), "runs_this_week": 148, "completion_rate": 86, "waiting_approval": len([a for a in approvals if a["status"] == "pending"])}, "context": {"tenant_id": tenant_id}})
            elif path == "/api/v1/scenario-packs":
                self.send_json(PACKS)
            elif path == "/api/v1/skills":
                self.send_json(SKILLS)
            elif path == "/api/v1/tasks":
                page = self.paginated(visible_tasks)
                if page is not None:
                    self.send_json(page)
            elif path == "/api/v1/runs":
                page = self.paginated(visible_runs)
                if page is not None:
                    self.send_json(page)
            elif path.startswith("/api/v1/runs/"):
                run_id = path.split("/")[4]
                run = next((item for item in visible_runs if item["id"] == run_id), None)
                if not run:
                    self.send_error_json("run.not_found", "run not found", 404)
                    return
                self.send_json(run)
            elif path == "/api/v1/knowledge":
                self.send_json(state["knowledge"])
            elif path == "/api/v1/workflows":
                self.send_json(state["workflows"])
            elif path == "/api/v1/approvals":
                self.send_json([approval for approval in state["approvals"] if approval.get("task_id") in visible_task_ids])
            elif path == "/api/v1/audit":
                self.send_json([entry for entry in state.get("audit", []) if entry.get("tenant_id", DEMO_TENANT_ID) == tenant_id])
            elif path == "/api/v1/artifacts":
                page = self.paginated([artifact | {"task_id": task_id} for task_id, artifacts in state["artifacts"].items() if task_id in visible_task_ids for artifact in artifacts])
                if page is not None:
                    self.send_json(page)
            elif path.startswith("/api/v1/tasks/") and path.endswith("/artifacts"):
                task_id = path.split("/")[4]
                if task_id not in visible_task_ids:
                    self.send_error_json("task.not_found", "task not found", 404)
                    return
                self.send_json(state["artifacts"].get(task_id, []))
            elif path.startswith("/api/v1/tasks/"):
                task_id = path.split("/")[4]
                task = next((t for t in visible_tasks if t["id"] == task_id), None)
                if not task:
                    self.send_error_json("task.not_found", "task not found", 404)
                    return
                runs = [r for r in state["runs"] if r.get("task_id") == task_id]
                self.send_json({"task": task, "pack": pack_for(task["pack_id"]), "skill": skill_for(task["skill_id"]), "runs": runs, "artifacts": state["artifacts"].get(task_id, [])})
            else:
                self.send_error_json("route.not_found", "not found", 404)

    def api_post(self, path: str, payload: dict):
        with LOCK:
            state = load_state()
            tenant_id, actor_id = request_context(self)
            if self.replay_idempotency(state, path):
                return
            if path == "/api/v1/tasks":
                name = str(payload.get("name", "")).strip() or "未命名任务"
                pack_id = str(payload.get("pack_id", "after-sales"))
                skill_id = str(payload.get("skill_id", "equipment-diagnosis"))
                if pack_id not in {p["id"] for p in PACKS} or skill_id not in {s["id"] for s in SKILLS}:
                    self.send_error_json("task.invalid_reference", "invalid pack or skill", 422)
                    return
                task_id = f"TK-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
                task = {"id": task_id, "name": name, "pack_id": pack_id, "skill_id": skill_id, "input_snapshot": payload.get("input", ""), "tenant_id": tenant_id, "created_by": actor_id, "status": "queued", "status_label": "待运行", "updated": "刚刚", "copy": "任务已创建，等待执行 Skill 和 Workflow。"}
                state["tasks"].insert(0, task)
                record_audit(state, tenant_id=tenant_id, actor_id=actor_id, action="task.created", resource_type="task", resource_id=task_id, metadata={"pack_id": pack_id, "skill_id": skill_id})
                save_state(state)
                self.remember_idempotency(state, path, task, 201)
                save_state(state)
                self.send_json(task, 201)
            elif path == "/api/v1/knowledge/search":
                query = str(payload.get("query", "")).strip()
                pack_id = str(payload.get("pack_id", "after-sales"))
                matches = [
                    {"type": "PDF", "title": "Cooling System Manual", "detail": "第 42 页 · 相关度 94%", "source_id": "product-manuals"},
                    {"type": "TKT", "title": "历史工单 #8812", "detail": "E-204 · 相关度 88%", "source_id": "historical-tickets"},
                ] if pack_id == "after-sales" else [
                    {"type": "DOC", "title": "Repository Docs", "detail": "API compatibility · 相关度 91%", "source_id": "repository-docs"},
                    {"type": "RUN", "title": "Service Runbooks", "detail": "升级路径 · 相关度 84%", "source_id": "runbooks"},
                ]
                self.send_json({"query": query, "pack_id": pack_id, "matches": matches}, 200)
            elif path == "/api/v1/chat/messages":
                message = str(payload.get("message", "")).strip()
                pack = pack_for(str(payload.get("pack_id", "after-sales")))
                self.send_json({"reply": f"已收到你的问题。我会在“{pack['name']}”范围内检索证据，并可以继续创建 Task。", "evidence_count": 2, "pack_id": pack["id"]}, 201)
            elif path.startswith("/api/v1/runs/") and path.endswith("/callback"):
                if not self.verify_callback_signature():
                    self.send_error_json("callback.invalid_signature", "invalid callback signature", 401)
                    return
                run_id = path.split("/")[4]
                run = next((item for item in state["runs"] if item["id"] == run_id), None)
                if not run or run.get("tenant_id", DEMO_TENANT_ID) != tenant_id:
                    self.send_error_json("run.not_found", "run not found", 404)
                    return
                status = str(payload.get("status", "")).strip()
                allowed_statuses = {"queued", "running", "completed", "waiting_approval", "failed", "rejected"}
                if status not in allowed_statuses:
                    self.send_error_json("run.invalid_status", "invalid run status", 422)
                    return
                run["status"] = status
                run["message"] = str(payload.get("message", run.get("message", "")))[:500]
                if status in {"completed", "waiting_approval", "failed", "rejected"}:
                    run["finished_at"] = now_iso()
                task_id = run.get("task_id")
                task = next((item for item in state["tasks"] if item["id"] == task_id), None) if task_id else None
                if task:
                    task_status = {"running": ("running", "进行中"), "waiting_approval": ("approval", "需审批"), "completed": ("completed", "已完成"), "failed": ("failed", "失败"), "rejected": ("cancelled", "已拒绝")}.get(status)
                    if task_status:
                        task["status"], task["status_label"] = task_status
                        task["updated"] = "刚刚"
                    if status == "completed":
                        task["copy"] = "DSH 运行已完成，结果已保存为 Artifact，可继续查看证据和执行轨迹。"
                        artifacts = payload.get("artifacts", [])
                        if isinstance(artifacts, list):
                            for artifact in artifacts[:20]:
                                if isinstance(artifact, dict) and artifact.get("name"):
                                    state["artifacts"].setdefault(task_id, []).append({"name": str(artifact["name"])[:160], "type": str(artifact.get("type", "file"))[:40], "description": str(artifact.get("description", "DSH 输出"))[:300], "run_id": run_id, "tenant_id": tenant_id})
                record_audit(state, tenant_id=tenant_id, actor_id=actor_id, action=f"run.callback_{status}", resource_type="run", resource_id=run_id, metadata={"task_id": task_id})
                save_state(state)
                self.send_json(run)
            elif path.startswith("/api/v1/workflows/") and path.endswith("/runs"):
                workflow_id = path.split("/")[4]
                workflow = next((item for item in state["workflows"] if item["id"] == workflow_id), None)
                if not workflow:
                    self.send_error_json("workflow.not_found", "workflow not found", 404)
                    return
                run = {"id": f"run-{uuid.uuid4().hex[:8]}", "workflow_id": workflow_id, "tenant_id": tenant_id, "actor_id": actor_id, "runtime": DSH_RUNTIME.metadata(), "status": "queued", "message": "Workflow 已加入运行队列", "created_at": now_iso()}
                state["runs"].insert(0, run)
                record_audit(state, tenant_id=tenant_id, actor_id=actor_id, action="workflow.run_queued", resource_type="run", resource_id=run["id"], metadata={"workflow_id": workflow_id})
                self.remember_idempotency(state, path, run, 201)
                save_state(state)
                schedule_local_run(run["id"], workflow_id=workflow_id)
                self.send_json(run, 201)
            elif path == "/api/v1/skill-runs":
                skill_id = str(payload.get("skill_id", "equipment-diagnosis"))
                run = {"id": f"run-{uuid.uuid4().hex[:8]}", "task_id": None, "skill_id": skill_id, "tenant_id": tenant_id, "actor_id": actor_id, "runtime": DSH_RUNTIME.metadata(), "status": "queued", "duration": "", "message": "已加入运行队列", "created_at": now_iso(), "input": payload.get("input", "")}
                state["runs"].insert(0, run)
                record_audit(state, tenant_id=tenant_id, actor_id=actor_id, action="skill.run_queued", resource_type="run", resource_id=run["id"], metadata={"skill_id": skill_id})
                self.remember_idempotency(state, path, run, 201)
                save_state(state)
                schedule_local_run(run["id"])
                self.send_json(run, 201)
            elif path.startswith("/api/v1/tasks/") and path.endswith("/runs"):
                task_id = path.split("/")[4]
                task = next((t for t in state["tasks"] if t["id"] == task_id), None)
                if not task:
                    self.send_error_json("task.not_found", "task not found", 404)
                    return
                if task.get("tenant_id", DEMO_TENANT_ID) != tenant_id:
                    self.send_error_json("task.forbidden", "task belongs to another tenant", 403)
                    return
                approval_required = task.get("status") == "approval"
                run = {"id": f"run-{uuid.uuid4().hex[:8]}", "task_id": task_id, "skill_id": task["skill_id"], "tenant_id": tenant_id, "actor_id": actor_id, "status": "queued", "duration": "", "message": "已加入运行队列", "created_at": now_iso()}
                knowledge_scope = [item["id"] for item in state["knowledge"] if item.get("pack_id") == task["pack_id"]]
                skill = skill_for(task["skill_id"])
                request = DSH_RUNTIME.build_request(
                    tenant_id=tenant_id,
                    actor_id=actor_id,
                    task_id=task_id,
                    skill_id=task["skill_id"],
                    input=payload.get("input", task.get("input_snapshot") or task.get("name", "")),
                    knowledge_scope=knowledge_scope,
                    allowed_tools=skill.get("dependencies", []),
                    output_schema="task.result.v1",
                    approval_required=approval_required,
                )
                run["runtime"] = DSH_RUNTIME.enqueue(request, run_id=run["id"])
                state["runs"].insert(0, run)
                record_audit(state, tenant_id=tenant_id, actor_id=actor_id, action="task.run_queued", resource_type="run", resource_id=run["id"], metadata={"task_id": task_id, "skill_id": task["skill_id"]})
                task["status"] = "approval" if approval_required else "queued"
                task["status_label"] = "需审批" if approval_required else "待运行"
                self.remember_idempotency(state, path, run, 201)
                save_state(state)
                if not DSH_RUNTIME.configured:
                    schedule_local_run(run["id"], task_id=task_id)
                self.send_json(run, 201)
            elif path.startswith("/api/v1/approvals/"):
                task_id = path.split("/")[4]
                decision = "approved" if path.endswith("/approve") else "rejected" if path.endswith("/reject") else None
                if not decision:
                    self.send_error_json("approval.invalid_action", "unknown approval action", 404)
                    return
                target_task = next((task for task in state["tasks"] if task["id"] == task_id), None)
                if not target_task or target_task.get("tenant_id", DEMO_TENANT_ID) != tenant_id:
                    self.send_error_json("task.not_found", "task not found", 404)
                    return
                resumed_runs = []
                for approval in state["approvals"]:
                    if approval["task_id"] == task_id:
                        approval["status"] = decision
                for run in state["runs"]:
                    if run.get("task_id") == task_id and run.get("status") == "waiting_approval":
                        if decision == "approved":
                            run["status"] = "queued"
                            run["message"] = "审批通过，恢复运行"
                            runtime = run.setdefault("runtime", {})
                            runtime["approval_required"] = False
                            resumed_runs.append(run["id"])
                        else:
                            run["status"] = "rejected"
                            run["message"] = "审批被拒绝，运行已停止"
                            run["finished_at"] = now_iso()
                for task in state["tasks"]:
                    if task["id"] == task_id:
                        task["status"] = "queued" if decision == "approved" else "cancelled"
                        task["status_label"] = "已批准" if decision == "approved" else "已拒绝"
                save_state(state)
                for run_id in resumed_runs:
                    schedule_local_run(run_id, task_id=task_id)
                record_audit(state, tenant_id=tenant_id, actor_id=actor_id, action=f"approval.{decision}", resource_type="task", resource_id=task_id, metadata={"resumed_runs": resumed_runs})
                save_state(state)
                self.send_json({"task_id": task_id, "status": decision, "resumed_runs": resumed_runs})
            else:
                self.send_error_json("route.not_found", "not found", 404)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    print(f"DSH Workbench listening on http://{args.host}:{args.port}")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()

if __name__ == "__main__":
    main()
