import sys
from types import SimpleNamespace

import pytest

from runtime.dsh_harness import DshHarnessExecutor, HarnessUnavailableError
from runtime.dsh_runtime import DshRuntime


def make_request():
    return DshRuntime("http://unused").build_request(
        tenant_id="tenant-a",
        actor_id="user-a",
        task_id="task-1",
        skill_id="equipment-diagnosis",
        input={"fault_code": "E-204"},
        knowledge_scope=["product-manuals"],
        allowed_tools=["kb.search", "device.status"],
        output_schema="task.result.v1",
        approval_required=False,
    )


def test_native_executor_builds_scoped_prompt_and_maps_result(monkeypatch, tmp_path):
    calls = {}

    class Result:
        final_response = "diagnosis"
        finish_reason = "completed"
        events = [{"type": "turn/end", "data": {"reason": {"kind": "completed"}}}]
        notifications = []

    class FakeHarness:
        def __init__(self, **kwargs):
            calls["kwargs"] = kwargs

        def run(self, prompt, *, session_id):
            calls["prompt"] = prompt
            calls["session_id"] = session_id
            return Result()

        def close(self):
            calls["closed"] = True

    monkeypatch.setitem(sys.modules, "deepseek_harness", SimpleNamespace(DeepSeekHarness=FakeHarness))
    executor = DshHarnessExecutor(home=str(tmp_path), profile="workbench-readonly")

    result = executor.run(make_request(), run_id="run-1")

    assert result.status == "completed"
    assert result.session_id == "run-1"
    assert result.final_response == "diagnosis"
    assert '"allowed_tools": ["kb.search", "device.status"]' in calls["prompt"]
    assert '"tenant_id": "tenant-a"' in calls["prompt"]
    assert calls["session_id"] == "run-1"
    assert calls["kwargs"]["dsh_home"] == str(tmp_path)
    assert calls["kwargs"]["profile"] == "workbench-readonly"
    executor.close()
    assert calls["closed"] is True


def test_native_executor_rejects_unsafe_profile(tmp_path):
    with pytest.raises(ValueError, match="restricted profile"):
        DshHarnessExecutor(home=str(tmp_path), profile="sdk-minimal")


def test_native_executor_reports_missing_sdk(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "deepseek_harness", None)
    executor = DshHarnessExecutor(home=str(tmp_path), profile="workbench-readonly")

    with pytest.raises(HarnessUnavailableError, match="deepseek-harness-sdk"):
        executor.run(make_request(), run_id="run-1")
