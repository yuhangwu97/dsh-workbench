# dsh-workbench

Python SDK for the DSH Workbench AI Task Platform.

```python
from dsh_workbench import DSHClient

client = DSHClient("http://localhost:8766", tenant_id="demo")
source = client.knowledge.ingest(
    name="Cooling System Manual",
    content="E-204 means a cooling loop interruption. Check the pump relay and filter.",
    pack_id="after-sales",
)
evidence = client.knowledge.search("pump relay", pack_id="after-sales")

task = client.tasks.create(name="Diagnose", pack_id="after-sales", skill_id="equipment-diagnosis")
run = client.tasks.run(task.id)
completed = client.runs.wait(run.id)
```

Run controls are available through `client.runs.cancel(run_id)`, `client.runs.retry(run_id)`, and `client.runs.queue()`. Search responses include `citations` and `citation_id` values that can be attached to an Artifact.
