import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_tasks_support_page_size_and_page_token(tmp_path):
    env = os.environ.copy()
    env.update({"PYTHONPATH": str(ROOT), "WORKBENCH_STORAGE": "json", "WORKBENCH_STATE_PATH": str(tmp_path / "state.json")})
    process = subprocess.Popen([sys.executable, "server.py", "--host", "127.0.0.1", "--port", "8776"], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    base = "http://127.0.0.1:8776"
    try:
        for _ in range(40):
            try:
                urllib.request.urlopen(base + "/api/v1/health", timeout=0.2)
                break
            except Exception:
                time.sleep(0.05)
        with urllib.request.urlopen(base + "/api/v1/tasks?page_size=2") as response:
            first = json.load(response)
        assert len(first["items"]) == 2
        assert first["next_page_token"]
        with urllib.request.urlopen(base + "/api/v1/tasks?page_size=2&page_token=" + first["next_page_token"]) as response:
            second = json.load(response)
        assert second["items"]
        assert first["items"][0]["id"] != second["items"][0]["id"]
    finally:
        process.terminate()
        process.wait(timeout=3)
