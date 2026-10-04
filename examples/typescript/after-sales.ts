import { DSHClient } from '@dsh-workbench/sdk';

const client = new DSHClient({ baseUrl: 'http://localhost:8766', tenantId: 'tenant-demo', actorId: 'example' });
const task = await client.tasks.create({
  name: '设备 3021 故障诊断',
  packId: 'after-sales',
  skillId: 'equipment-diagnosis',
  input: { device_id: '3021', fault_code: 'E-204' },
});
const run = await client.tasks.run(task.id);
const completed = await client.runs.wait(run.id, { timeoutMs: 60_000 });
console.log(completed.status, await client.artifacts.list(task.id));
