import json
from pathlib import Path

import pytest

from dsh_workbench.models import Artifact, ErrorEnvelope, Run, RunStatus, Task, is_terminal_run_status
from dsh_workbench.errors import ModelError

ROOT = Path(__file__).parents[1]


def test_run_model_round_trips_completed_run():
    payload = {
        "id": "run-1",
        "task_id": "task-1",
        "status": "completed",
        "message": "done",
        "created_at": "2026-10-04T00:00:00Z",
        "finished_at": "2026-10-04T00:00:01Z",
    }
    run = Run.from_dict(payload)
    assert run.status is RunStatus.COMPLETED
    assert run.to_dict()["id"] == "run-1"
    assert is_terminal_run_status(run.status)


def test_task_model_requires_id_and_name():
    with pytest.raises(ModelError):
        Task.from_dict({"name": "missing id"})


def test_artifact_and_error_models_preserve_details():
    artifact = Artifact.from_dict({"name": "report.json", "type": "json", "task_id": "task-1"})
    error = ErrorEnvelope.from_dict({"error": {"code": "task.not_found", "message": "missing", "request_id": "req-1", "details": {"id": "task-1"}}})
    assert artifact.name == "report.json"
    assert error.error.code == "task.not_found"
    assert error.error.details["id"] == "task-1"


def test_json_schemas_have_required_contract_sections():
    for name in ("task", "run", "event", "error"):
        schema = json.loads((ROOT / "contracts" / "schemas" / f"{name}.json").read_text())
        assert schema["$schema"]
        assert schema["type"] == "object"
        assert schema["required"]
