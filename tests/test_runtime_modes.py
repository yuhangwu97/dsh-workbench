import pytest

from runtime.dsh_runtime import DshRuntime, RuntimeUnavailableError


def test_demo_mode_is_explicit(monkeypatch):
    monkeypatch.setenv("DSH_RUNTIME_MODE", "demo")
    monkeypatch.delenv("DSH_ENDPOINT", raising=False)
    monkeypatch.delenv("DSH_HARNESS_HOME", raising=False)

    runtime = DshRuntime()

    assert runtime.metadata()["mode"] == "demo"
    assert runtime.metadata()["runtime"] == "dsh"
    assert runtime.configured is False


def test_sidecar_mode_uses_endpoint(monkeypatch):
    monkeypatch.setenv("DSH_RUNTIME_MODE", "sidecar")
    runtime = DshRuntime("http://127.0.0.1:9999")

    assert runtime.metadata()["mode"] == "sidecar"
    assert runtime.configured is True


def test_auto_mode_prefers_sidecar_then_native(monkeypatch, tmp_path):
    monkeypatch.setenv("DSH_RUNTIME_MODE", "auto")
    monkeypatch.setenv("DSH_ENDPOINT", "http://127.0.0.1:9999")
    assert DshRuntime().metadata()["mode"] == "sidecar"

    monkeypatch.delenv("DSH_ENDPOINT")
    monkeypatch.setenv("DSH_HARNESS_HOME", str(tmp_path))
    native = DshRuntime()
    assert native.metadata()["mode"] == "native"
    assert native.configured is True


def test_auto_mode_reports_unavailable_without_runtime(monkeypatch):
    monkeypatch.setenv("DSH_RUNTIME_MODE", "auto")
    monkeypatch.delenv("DSH_ENDPOINT", raising=False)
    monkeypatch.delenv("DSH_HARNESS_HOME", raising=False)

    runtime = DshRuntime()

    assert runtime.metadata()["mode"] == "unavailable"
    assert runtime.configured is False
    with pytest.raises(RuntimeUnavailableError, match="DSH_RUNTIME_MODE"):
        runtime.enqueue(runtime.build_request(tenant_id="t", actor_id="a", task_id="x", skill_id="s", input="hi", knowledge_scope=["kb"], allowed_tools=["kb.search"], output_schema="task.result.v1"))


def test_runtime_binds_tool_gateway_to_run_request(monkeypatch):
    monkeypatch.setenv("DSH_TOOL_GATEWAY_URL", "http://workbench.test")
    request = DshRuntime(mode="demo").build_request(tenant_id="t", actor_id="a", task_id="x", skill_id="s", input="hi", knowledge_scope=[], allowed_tools=["ticket.read"], output_schema="task.result.v1")
    assert request.tool_gateway_url == "http://workbench.test"
    assert DshRuntime(mode="demo").metadata()["tool_gateway"]["url"] == "http://workbench.test"
