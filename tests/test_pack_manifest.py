from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def test_after_sales_pack_manifest_declares_executable_resources():
    manifest = yaml.safe_load((ROOT / "packs" / "after-sales" / "pack.yaml").read_text())
    assert manifest["id"] == "after-sales"
    assert manifest["version"]
    assert manifest["skills"]
    assert manifest["workflows"]
    skill_ids = {skill["id"] for skill in manifest["skills"]}
    for workflow in manifest["workflows"]:
        assert workflow["skill_id"] in skill_ids
        assert workflow["steps"]
    assert manifest["policy"]["business_writes"] == "approval-required"
