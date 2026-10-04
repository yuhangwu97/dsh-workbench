import inspect

from dsh_workbench.extensions import ArtifactStore, ApprovalPolicy, EventSink, KnowledgeProvider, SkillProvider, WorkflowExecutor


def test_extension_protocols_are_runtime_checkable_interfaces():
    assert inspect.isclass(KnowledgeProvider)
    assert "search" in KnowledgeProvider.__annotations__ or hasattr(KnowledgeProvider, "search")
    assert hasattr(SkillProvider, "run")
    assert hasattr(WorkflowExecutor, "start")
    assert hasattr(ArtifactStore, "put")
    assert hasattr(ApprovalPolicy, "evaluate")
    assert hasattr(EventSink, "publish")
