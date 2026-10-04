#!/usr/bin/env python3
"""Run lightweight, deterministic Scenario Pack checks.

Usage: python3 tools_evaluate_packs.py [packs/after-sales/pack.yaml]
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # keep the command useful in the dependency-free repo
    yaml = None


def simple_yaml(path: Path) -> dict:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith(" ") and ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    return values


def evaluate(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if yaml else simple_yaml(path)
    checks = []
    for key in ("api_version", "id", "name", "version", "skills", "knowledge_sources", "workflows", "policy"):
        checks.append({"id": f"manifest.{key}", "passed": key in data and bool(data[key]), "message": f"{key} is declared"})
    policy = data.get("policy", {}) if isinstance(data, dict) else {}
    checks.extend([
        {"id": "policy.tenant_scope", "passed": policy.get("tenant_scope") == "required", "message": "tenant scope is required"},
        {"id": "policy.business_writes", "passed": policy.get("business_writes") == "approval-required", "message": "business writes require approval"},
    ])
    passed = sum(1 for check in checks if check["passed"])
    return {"pack_id": data.get("id", path.stem), "pack_version": data.get("version", "unknown"), "passed": passed, "total": len(checks), "score": round(passed / max(len(checks), 1), 4), "checks": checks}


def main() -> int:
    paths = [Path(item) for item in sys.argv[1:]] or sorted(Path("packs").glob("*/pack.yaml"))
    results = [evaluate(path) for path in paths]
    print(__import__("json").dumps({"results": results, "passed": all(item["score"] == 1 for item in results)}, ensure_ascii=False, indent=2))
    return 0 if all(item["score"] == 1 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
