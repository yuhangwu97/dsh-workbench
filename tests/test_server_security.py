import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = __import__('pathlib').Path(__file__).parents[1]


def _start(tmp_path, port=8773):
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": str(ROOT),
        "WORKBENCH_STORAGE": "json",
        "WORKBENCH_AUTH_TOKEN": "",
        "DSH_CALLBACK_SECRET": "callback-secret",
        "WORKBENCH_STATE_PATH": str(tmp_path / "state.json"),
    })
    proc = subprocess.Popen([sys.executable, "server.py", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    base = f"http://127.0.0.1:{port}"
    for _ in range(40):
        try:
            urllib.request.urlopen(base + "/api/v1/health", timeout=0.2)
            return proc, base
        except urllib.error.URLError:
            time.sleep(0.05)
    proc.kill()
    raise RuntimeError("server did not start")


def _request(base, body, signature=None):
    raw = json.dumps(body, separators=(",", ":")).encode()
    now = str(int(datetime.now(timezone.utc).timestamp()))
    headers = {"Content-Type": "application/json", "X-DSH-Timestamp": now}
    if signature:
        headers["X-DSH-Signature"] = signature(now, raw)
    request = urllib.request.Request(base + "/api/v1/runs/run-missing/callback", data=raw, method="POST", headers=headers)
    try:
        response = urllib.request.urlopen(request, timeout=3)
        return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_callback_rejects_invalid_signature(tmp_path):
    proc, base = _start(tmp_path)
    try:
        status, body = _request(base, {"status": "completed"}, lambda timestamp, raw: "bad")
        assert status == 401
        assert body["error"]["code"] == "callback.invalid_signature"
    finally:
        proc.terminate()
        proc.wait(timeout=3)


def test_callback_accepts_hmac_signature(tmp_path):
    proc, base = _start(tmp_path, port=8774)
    try:
        def sign(timestamp, raw):
            return hmac.new(b"callback-secret", timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
        status, body = _request(base, {"status": "completed"}, sign)
        assert status == 404
        assert body["error"]["code"] == "run.not_found"
    finally:
        proc.terminate()
        proc.wait(timeout=3)


def test_tenant_scope_hides_tasks_from_other_tenants(tmp_path):
    proc, base = _start(tmp_path, port=8777)
    try:
        body = json.dumps({"name": "Tenant A", "pack_id": "after-sales", "skill_id": "equipment-diagnosis"}).encode()
        create = urllib.request.Request(base + "/api/v1/tasks", data=body, method="POST", headers={"Content-Type": "application/json", "X-Tenant-ID": "tenant-a"})
        with urllib.request.urlopen(create) as response:
            task_id = json.load(response)["id"]
        hidden = urllib.request.Request(base + "/api/v1/tasks", headers={"X-Tenant-ID": "tenant-b"})
        with urllib.request.urlopen(hidden) as response:
            assert all(task["id"] != task_id for task in json.load(response))
    finally:
        proc.terminate()
        proc.wait(timeout=3)
