from runtime.dsh_harness import HarnessResult
from server import apply_harness_result, seed_state


def test_harness_result_updates_run_task_events_and_artifacts():
    state = seed_state()
    task = state["tasks"][0].copy()
    run = {
        "id": "run-native-1",
        "task_id": task["id"],
        "tenant_id": "tenant-demo",
        "actor_id": "user-wu-yuhang",
        "status": "running",
        "attempt": 1,
        "max_attempts": 3,
        "runtime": {"mode": "native"},
    }
    result = HarnessResult(
        status="completed",
        session_id="session-native-1",
        final_response='{"root_cause":"filter"}',
        finish_reason="completed",
        events=[{"type": "turn/end", "seq": 2, "data": {"reason": {"kind": "completed"}}}],
    )

    apply_harness_result(state, run, task, result)

    assert run["status"] == "completed"
    assert run["dsh_session_id"] == "session-native-1"
    assert run["runtime"]["finish_reason"] == "completed"
    assert task["status"] == "completed"
    assert any(item["name"] == "harness-result.json" for item in state["artifacts"][task["id"]])
    assert any(item["name"] == "harness-events.jsonl" for item in state["artifacts"][task["id"]])
    assert state["events"][0]["type"] == "turn/end"


def test_harness_failure_marks_task_failed():
    state = seed_state()
    task = state["tasks"][0].copy()
    run = {"id": "run-native-2", "task_id": task["id"], "tenant_id": "tenant-demo", "actor_id": "user-wu-yuhang", "status": "running", "runtime": {"mode": "native"}}
    result = HarnessResult(status="failed", session_id="session-native-2", final_response="", finish_reason="error", error="model unavailable")

    apply_harness_result(state, run, task, result)

    assert run["status"] == "failed"
    assert run["message"] == "model unavailable"
    assert task["status"] == "failed"
