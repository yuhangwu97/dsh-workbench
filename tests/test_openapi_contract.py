from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def test_openapi_declares_public_v1_resources_and_security_headers():
    document = yaml.safe_load((ROOT / "contracts" / "openapi.yaml").read_text())
    assert document["openapi"].startswith("3.")
    paths = document["paths"]
    for path in (
        "/api/v1/tasks",
        "/api/v1/tasks/{task_id}",
        "/api/v1/tasks/{task_id}/runs",
        "/api/v1/runs/{run_id}",
        "/api/v1/runs/{run_id}/callback",
        "/api/v1/knowledge/search",
        "/api/v1/chat/messages",
        "/api/v1/workflows/{workflow_id}/runs",
        "/api/v1/approvals/{task_id}/approve",
        "/api/v1/artifacts",
    ):
        assert path in paths
    assert "bearerAuth" in document["components"]["securitySchemes"]
    assert "Idempotency-Key" in document["components"]["parameters"]
    assert document["components"]["schemas"]["ErrorEnvelope"]["$ref"] == "./schemas/error.json"
