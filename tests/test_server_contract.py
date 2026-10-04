import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parents[1]


def _start_server(tmp_path, port=8771):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["WORKBENCH_STORAGE"] = "json"
    env["WORKBENCH_AUTH_TOKEN"] = ""
    env["DSH_CALLBACK_SECRET"] = ""
    env["WORKBENCH_STATE_PATH"] = str(tmp_path / "state.json")
    process = subprocess.Popen([sys.executable, "server.py", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for _ in range(40):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/health", timeout=0.2)
            return process, f"http://127.0.0.1:{port}"
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.05)
    process.kill()
    raise RuntimeError("server did not start")


def _request(base, method, path, payload=None, headers=None):
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(base + path, data=body, method=method, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        response = urllib.request.urlopen(request, timeout=3)
        return response.status, response.headers, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, json.loads(exc.read())


def test_api_errors_have_stable_envelope_and_request_id(tmp_path):
    process, base = _start_server(tmp_path)
    try:
        status, headers, body = _request(base, "GET", "/api/v1/tasks/missing")
        assert status == 404
        assert headers["X-Request-ID"]
        assert body["error"]["code"] == "task.not_found"
        assert body["error"]["request_id"] == headers["X-Request-ID"]
    finally:
        process.terminate()
        process.wait(timeout=3)


def test_idempotency_key_replays_same_task(tmp_path):
    process, base = _start_server(tmp_path, port=8772)
    try:
        headers = {"Idempotency-Key": "create-task-1"}
        first = _request(base, "POST", "/api/v1/tasks", {"name": "Idempotent", "pack_id": "after-sales", "skill_id": "equipment-diagnosis"}, headers)
        second = _request(base, "POST", "/api/v1/tasks", {"name": "Idempotent", "pack_id": "after-sales", "skill_id": "equipment-diagnosis"}, headers)
        assert first[0] == second[0] == 201
        assert first[2]["id"] == second[2]["id"]
        conflict = _request(base, "POST", "/api/v1/tasks", {"name": "Different", "pack_id": "after-sales", "skill_id": "equipment-diagnosis"}, headers)
        assert conflict[0] == 409
        assert conflict[2]["error"]["code"] == "idempotency.conflict"
    finally:
        process.terminate()
        process.wait(timeout=3)
