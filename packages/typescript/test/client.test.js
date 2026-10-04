import test from 'node:test';
import assert from 'node:assert/strict';
import { DSHClient, NotFoundError } from '../dist/index.js';

function response(status, body, headers = {}) {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json', ...headers } });
}

test('creates a task with auth and tenant headers', async () => {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, init });
    return response(201, { id: 'task-1', name: 'Diagnose', pack_id: 'after-sales', skill_id: 'equipment-diagnosis', status: 'queued' });
  };
  const client = new DSHClient({ baseUrl: 'https://workbench.test', apiKey: 'token', tenantId: 'tenant-a', actorId: 'user-a', fetchImpl });
  const task = await client.tasks.create({ name: 'Diagnose', packId: 'after-sales', skillId: 'equipment-diagnosis', input: { code: 'E-204' }, idempotencyKey: 'create-1' });
  assert.equal(task.id, 'task-1');
  assert.equal(calls[0].url, 'https://workbench.test/api/v1/tasks');
  assert.equal(calls[0].init.headers.Authorization, 'Bearer token');
  assert.equal(calls[0].init.headers['X-Tenant-ID'], 'tenant-a');
  assert.equal(calls[0].init.headers['Idempotency-Key'], 'create-1');
});

test('waits until a run is terminal', async () => {
  let count = 0;
  const fetchImpl = async () => {
    count += 1;
    return response(200, { id: 'run-1', status: count === 1 ? 'running' : 'completed' });
  };
  const client = new DSHClient({ baseUrl: 'https://workbench.test', pollIntervalMs: 0, fetchImpl });
  const run = await client.runs.wait('run-1', { timeoutMs: 100 });
  assert.equal(run.status, 'completed');
  assert.equal(count, 2);
});

test('maps error envelope to typed error', async () => {
  const client = new DSHClient({
    baseUrl: 'https://workbench.test',
    fetchImpl: async () => response(404, { error: { code: 'task.not_found', message: 'missing', request_id: 'req-2', details: {} } }),
  });
  await assert.rejects(client.tasks.get('missing'), (error) => error instanceof NotFoundError && error.requestId === 'req-2');
});

test('exposes page token for list calls', async () => {
  const client = new DSHClient({
    baseUrl: 'https://workbench.test',
    fetchImpl: async (url) => {
      assert.match(url, /page_size=1/);
      return response(200, { items: [{ id: 'task-1', name: 'A', pack_id: 'after-sales', skill_id: 'equipment-diagnosis', status: 'queued' }], next_page_token: '1' });
    },
  });
  const page = await client.tasks.listPage({ pageSize: 1 });
  assert.equal(page.nextPageToken, '1');
  assert.equal(page.items[0].id, 'task-1');
});
