import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from runtime.dsh_runtime import DshRuntime
from runtime.dsh_sidecar import DshSidecarExecutor


class CaptureHandler(BaseHTTPRequestHandler):
    payloads = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        CaptureHandler.payloads.append(json.loads(self.rfile.read(length)))
        body = b'{"accepted":true}'
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


def test_sidecar_executor_sends_harness_contract():
    CaptureHandler.payloads = []
    server = HTTPServer(("127.0.0.1", 0), CaptureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = DshRuntime("http://unused").build_request(
            tenant_id="tenant-a", actor_id="user-a", task_id="task-1", skill_id="skill-1",
            input={"x": 1}, knowledge_scope=["kb-1"], allowed_tools=["kb.search"],
            output_schema="task.result.v1",
        )
        executor = DshSidecarExecutor(f"http://127.0.0.1:{server.server_port}", profile="workbench-readonly", callback_url="http://workbench/callback")
        envelope = executor.dispatch(request, run_id="run-1")
        assert envelope["dispatch"]["status_code"] == 202
        assert CaptureHandler.payloads[0]["session_id"] == "run-1"
        assert CaptureHandler.payloads[0]["callback_url"] == "http://workbench/callback"
        assert CaptureHandler.payloads[0]["allowed_tools"] == ["kb.search"]
    finally:
        server.shutdown()
        server.server_close()
