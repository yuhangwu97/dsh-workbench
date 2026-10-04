import sys
from types import SimpleNamespace

from runtime.dsh_harness import DshHarnessExecutor
from runtime.dsh_runtime import DshRuntime


def test_fake_harness_smoke_covers_task_run_result_contract(monkeypatch, tmp_path):
    class Result:
        final_response = '{"answer":"ok"}'
        finish_reason = "completed"
        events = [{"type": "turn/end", "data": {"reason": {"kind": "completed"}}}]
        notifications = []

    class FakeHarness:
        def __init__(self, **_kwargs):
            pass

        def run(self, _prompt, *, session_id):
            assert session_id == "run-smoke"
            return Result()

        def close(self):
            pass

    monkeypatch.setitem(sys.modules, "deepseek_harness", SimpleNamespace(DeepSeekHarness=FakeHarness))
    runtime = DshRuntime(mode="native")
    monkeypatch.setenv("DSH_HARNESS_HOME", str(tmp_path))
    request = runtime.build_request(
        tenant_id="tenant-a", actor_id="user-a", task_id="task-1", skill_id="skill-1",
        input={"query": "hello"}, knowledge_scope=["kb-1"], allowed_tools=["kb.search"], output_schema="task.result.v1",
    )
    result = runtime.dispatch(request, run_id="run-smoke")
    assert result.status == "completed"
    assert result.session_id == "run-smoke"
    assert result.final_response == '{"answer":"ok"}'
