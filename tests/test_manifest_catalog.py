from pathlib import Path

from server import load_scenario_catalog, load_workflow_catalog


ROOT = Path(__file__).parents[1]


def test_scenario_catalog_is_loaded_from_pack_manifests():
    packs, skills = load_scenario_catalog(ROOT / "packs")
    assert {pack["id"] for pack in packs} == {"after-sales", "engineering", "operations"}
    after_sales = next(pack for pack in packs if pack["id"] == "after-sales")
    assert after_sales["skills"] == 2
    assert after_sales["workflows"] == 1
    diagnosis = next(skill for skill in skills if skill["id"] == "equipment-diagnosis")
    assert diagnosis["name"] == "设备故障诊断"
    assert "ticket.read" in diagnosis["dependencies"]
    assert "maintenance.action" in diagnosis["dependencies"]


def test_workflow_catalog_is_loaded_from_pack_manifests():
    workflows = load_workflow_catalog(ROOT / "packs")
    assert {workflow["id"] for workflow in workflows} == {"diagnose-equipment-v2", "issue-to-patch-plan", "alert-to-escalation"}
    diagnosis = next(workflow for workflow in workflows if workflow["id"] == "diagnose-equipment-v2")
    assert diagnosis["pack_id"] == "after-sales"
    assert diagnosis["steps"] == 5
    assert diagnosis["step_labels"] == ["retrieve-evidence", "read-device", "analyze-fault", "request-approval", "produce-report"]


def test_frontend_does_not_ship_business_catalog_or_task_fixtures():
    app = (ROOT / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "const packData" not in app
    assert "const skillData" not in app
    assert "const skillOptions" not in app
    assert "const tasks =" not in app
    assert "/api/v1/scenario-packs" in app
    assert "/api/v1/skills" in app
    assert 'data-task="diagnosis"' not in html
    assert "设备 #3021 故障诊断" not in html
