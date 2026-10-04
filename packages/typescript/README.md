# @dsh-workbench/sdk

TypeScript SDK for the DSH Workbench AI Task Platform.

```ts
import { DSHClient } from '@dsh-workbench/sdk';

const client = new DSHClient({ baseUrl: 'http://localhost:8766', tenantId: 'demo' });
const task = await client.tasks.create({ name: 'Diagnose', packId: 'after-sales', skillId: 'equipment-diagnosis' });
const run = await client.tasks.run(task.id);
const completed = await client.runs.wait(run.id);
```
