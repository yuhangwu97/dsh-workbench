# dsh-workbench

Python SDK for the DSH Workbench AI Task Platform.

```python
from dsh_workbench import DSHClient

client = DSHClient("http://localhost:8766", tenant_id="demo")
task = client.tasks.create(name="Diagnose", pack_id="after-sales", skill_id="equipment-diagnosis")
run = client.tasks.run(task.id)
completed = client.runs.wait(run.id)
```
