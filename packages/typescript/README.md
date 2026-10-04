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

Run controls are available through `client.runs.cancel(runId)`, `client.runs.retry(runId)`, and `client.runs.queue()`. Scenario Packs and org access are available through `client.scenarioPacks` and `client.organization`. Search responses include `citations` and `citation_id` values for traceable Artifacts.

The TypeScript package calls the Workbench product API. The server can use the official DeepSeek Harness runtime in native mode or an isolated sidecar; configure that on the server with `DSH_RUNTIME_MODE`, not in this client package.
