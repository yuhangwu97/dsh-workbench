import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from runtime.dsh_runtime import DshRuntime


class CaptureHandler(BaseHTTPRequestHandler):
    payload = None
    headers = None

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        CaptureHandler.payload = json.loads(self.rfile.read(length))
        CaptureHandler.headers = dict(self.headers)
        body = b'{"accepted":true}'
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


def test_runtime_builds_scoped_request_and_dispatches_to_dsh():
    server = HTTPServer(("127.0.0.1", 0), CaptureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        runtime = DshRuntime(f"http://127.0.0.1:{server.server_port}")
        request = runtime.build_request(tenant_id="tenant-a", actor_id="user-a", task_id="task-1", skill_id="skill-1", input={"x": 1}, knowledge_scope=["kb-1"], allowed_tools=["kb.search"], output_schema="task.result.v1", approval_required=True)
        envelope = runtime.enqueue(request, run_id="run-1")
        assert envelope["dispatch"]["status_code"] == 202
        assert CaptureHandler.payload["tenant_id"] == "tenant-a"
        assert CaptureHandler.payload["allowed_tools"] == ["kb.search"]
        assert (CaptureHandler.headers.get("X-Tenant-ID") or CaptureHandler.headers.get("X-Tenant-Id")) == "tenant-a"
    finally:
        server.shutdown()
        server.server_close()
