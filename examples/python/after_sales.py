"""Five-minute Python SDK example for the after-sales pack."""
from dsh_workbench import DSHClient

client = DSHClient("http://localhost:8766", tenant_id="tenant-demo", actor_id="example")
task = client.tasks.create(
    name="设备 3021 故障诊断",
    pack_id="after-sales",
    skill_id="equipment-diagnosis",
    input={"device_id": "3021", "fault_code": "E-204"},
)
run = client.tasks.run(task.id)
completed = client.runs.wait(run.id, timeout=60)
print(completed.status.value, client.artifacts.list(task_id=task.id))
