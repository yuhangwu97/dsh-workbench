import base64
import hashlib
import hmac
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from runtime.knowledge import KnowledgeIndex, split_text
from runtime.security import verify_hs256
from tools_evaluate_packs import evaluate

ROOT = Path(__file__).parents[1]


def _port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _request(base, method, path, body=None, headers=None):
    raw = None if body is None else json.dumps(body, ensure_ascii=False).encode()
    request = urllib.request.Request(base + path, data=raw, method=method, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_knowledge_index_returns_stable_chunks_and_ranked_hits():
    assert split_text("one\ntwo\nthree", chunk_size=120) == [{"index": 0, "text": "one\ntwo\nthree", "start": 0, "end": 13}]
    index = KnowledgeIndex()
    source = {"id": "source-1", "source_id": "manuals", "pack_id": "after-sales"}
    chunks = index.ingest(source, "E-204 cooling pump relay inspection")
    hits = index.search(chunks, "cooling pump")
    assert chunks[0]["source_id"] == "manuals"
    assert hits[0]["id"] == chunks[0]["id"]
    assert hits[0]["score"] > 0


def test_pack_evaluator_requires_safety_policy():
    result = evaluate(ROOT / "packs/after-sales/pack.yaml")
    assert result["score"] == 1
    assert result["total"] >= 8


def test_hs256_claims_are_verified():
    def enc(value):
        return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).rstrip(b"=").decode()
    header, claims = enc({"alg": "HS256"}), enc({"sub": "user-1", "roles": ["editor"]})
    signature = base64.urlsafe_b64encode(hmac.new(b"secret", f"{header}.{claims}".encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    assert verify_hs256(f"{header}.{claims}.{signature}", "secret")["sub"] == "user-1"
    assert verify_hs256(f"{header}.{claims}.bad", "secret") is None


def test_http_ingestion_citations_and_run_controls(tmp_path):
    port = _port()
    env = os.environ.copy()
    env.update({"PYTHONPATH": str(ROOT), "WORKBENCH_STORAGE": "json", "DSH_RUNTIME_MODE": "demo", "WORKBENCH_STATE_PATH": str(tmp_path / "state.json")})
    process = subprocess.Popen([sys.executable, "server.py", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(50):
            try:
                _request(base, "GET", "/api/v1/health")
                break
            except urllib.error.URLError:
                time.sleep(0.05)
        status, ingested = _request(base, "POST", "/api/v1/knowledge/ingest", {"source_id": "manuals", "name": "Manual", "pack_id": "after-sales", "content": "E-777 pump relay inspection"})
        assert status == 201 and ingested["chunks"] == 1
        status, search = _request(base, "POST", "/api/v1/knowledge/search", {"query": "pump relay", "pack_id": "after-sales"})
        assert status == 200 and search["citations"] and search["matches"][0]["citation_id"]
        status, run = _request(base, "POST", "/api/v1/workflows/diagnose-equipment-v2/runs", {})
        assert status == 201
        status, cancelled = _request(base, "POST", f"/api/v1/runs/{run['id']}/cancel", {})
        assert status == 200 and cancelled["status"] == "cancelled"
        status, retried = _request(base, "POST", f"/api/v1/runs/{run['id']}/retry", {})
        assert status == 200 and retried["attempt"] == 2
    finally:
        process.terminate()
        process.wait(timeout=3)
