# @dsh-workbench/sdk

TypeScript SDK for the DSH Workbench AI Task Platform.

```ts
import { DSHClient } from '@dsh-workbench/sdk';

const client = new DSHClient({ baseUrl: 'http://localhost:8766', tenantId: 'demo' });
await client.knowledge.ingest({
  name: 'Cooling System Manual',
  content: 'E-204 means a cooling loop interruption. Check the pump relay and filter.',
  packId: 'after-sales',
});
const evidence = await client.knowledge.search('pump relay', 'after-sales');

const task = await client.tasks.create({ name: 'Diagnose', packId: 'after-sales', skillId: 'equipment-diagnosis' });
const run = await client.tasks.run(task.id);
const completed = await client.wait(run.id);
```

Run controls are available through `client.runs.cancel(runId)`, `client.runs.retry(runId)`, and `client.runs.queue()`. Search responses include `citations` and `citation_id` values for traceable Artifacts.
