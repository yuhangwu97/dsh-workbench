import { errorForStatus, ErrorEnvelope } from './errors.js';
import { Artifact, ChatResponse, isTerminalRun, KnowledgeSearchResponse, KnowledgeSource, Page, Run, Task } from './resources.js';

export interface DSHClientOptions {
  baseUrl: string;
  apiKey?: string;
  tenantId?: string;
  actorId?: string;
  requestId?: string;
  timeoutMs?: number;
  pollIntervalMs?: number;
  fetchImpl?: typeof fetch;
  headers?: Record<string, string>;
}

export interface CreateTaskInput {
  name: string;
  packId: string;
  skillId: string;
  input?: unknown;
  idempotencyKey?: string;
}

export class DSHClient {
  readonly tasks: TasksResource;
  readonly runs: RunsResource;
  readonly chat: ChatResource;
  readonly knowledge: KnowledgeResource;
  readonly workflows: WorkflowsResource;
  readonly approvals: ApprovalsResource;
  readonly artifacts: ArtifactsResource;
  private readonly baseUrl: string;
  private readonly options: DSHClientOptions;
  private readonly fetchImpl: typeof fetch;

  constructor(options: DSHClientOptions) {
    if (!options.baseUrl.trim()) throw new Error('baseUrl is required');
    this.baseUrl = options.baseUrl.replace(/\/$/, '');
    this.options = options;
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.tasks = new TasksResource(this);
    this.runs = new RunsResource(this);
    this.chat = new ChatResource(this);
    this.knowledge = new KnowledgeResource(this);
    this.workflows = new WorkflowsResource(this);
    this.approvals = new ApprovalsResource(this);
    this.artifacts = new ArtifactsResource(this);
  }

  async request<T>(method: string, path: string, body?: unknown, idempotencyKey?: string): Promise<T> {
    const headers: Record<string, string> = { Accept: 'application/json', 'Content-Type': 'application/json', 'X-Request-ID': this.options.requestId ?? `req_${crypto.randomUUID().replaceAll('-', '').slice(0, 16)}`, ...this.options.headers };
    if (this.options.apiKey) headers.Authorization = `Bearer ${this.options.apiKey}`;
    if (this.options.tenantId) headers['X-Tenant-ID'] = this.options.tenantId;
    if (this.options.actorId) headers['X-Actor-ID'] = this.options.actorId;
    if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.options.timeoutMs ?? 15000);
    try {
      const response = await this.fetchImpl(`${this.baseUrl}${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal });
      const payload = await response.json() as T | ErrorEnvelope;
      if (!response.ok) {
        const envelope = payload as ErrorEnvelope;
        const error = envelope.error;
        throw errorForStatus(response.status, error?.code ?? `http.${response.status}`, error?.message ?? 'request failed', error?.request_id ?? response.headers.get('X-Request-ID') ?? undefined, error?.details ?? {});
      }
      return payload as T;
    } finally {
      clearTimeout(timeout);
    }
  }

  async wait(runId: string, options: { timeoutMs?: number; pollIntervalMs?: number } = {}): Promise<Run> {
    const deadline = Date.now() + (options.timeoutMs ?? 300000);
    while (true) {
      const run = await this.runs.get(runId);
      if (isTerminalRun(run)) return run;
      if (Date.now() >= deadline) throw new Error(`run ${runId} did not reach a terminal state`);
      const interval = options.pollIntervalMs ?? this.options.pollIntervalMs ?? 1000;
      if (interval > 0) await new Promise(resolve => setTimeout(resolve, interval));
    }
  }
}

class TasksResource {
  constructor(private readonly client: DSHClient) {}
  create(input: CreateTaskInput): Promise<Task> { return this.client.request<Task>('POST', '/api/v1/tasks', { name: input.name, pack_id: input.packId, skill_id: input.skillId, input: input.input }, input.idempotencyKey); }
  async get(taskId: string): Promise<Task> { const payload = await this.client.request<Task | {task: Task}>('GET', `/api/v1/tasks/${encodeURIComponent(taskId)}`); const detail = payload as Task | { task: Task }; return typeof detail === 'object' && detail !== null && 'task' in detail ? (detail as { task: Task }).task : detail as Task; }
  async list(options: { pageSize?: number; pageToken?: string } = {}): Promise<Task[]> { return (await this.listPage(options)).items; }
  async listPage(options: { pageSize?: number; pageToken?: string } = {}): Promise<Page<Task>> { const query = new URLSearchParams(); if (options.pageSize !== undefined) query.set('page_size', String(options.pageSize)); if (options.pageToken) query.set('page_token', options.pageToken); const payload = await this.client.request<Task[] | { items: Task[]; next_page_token?: string | null }>('GET', `/api/v1/tasks${query.toString() ? `?${query}` : ''}`); return Array.isArray(payload) ? { items: payload, nextPageToken: null } : { items: payload.items, nextPageToken: payload.next_page_token ?? null }; }
  run(taskId: string, input?: unknown, idempotencyKey?: string): Promise<Run> { return this.client.request<Run>('POST', `/api/v1/tasks/${encodeURIComponent(taskId)}/runs`, input === undefined ? {} : { input }, idempotencyKey); }
}

class RunsResource {
  constructor(private readonly client: DSHClient) {}
  get(runId: string): Promise<Run> { return this.client.request<Run>('GET', `/api/v1/runs/${encodeURIComponent(runId)}`); }
  async list(options: { pageSize?: number; pageToken?: string } = {}): Promise<Run[]> { return (await this.listPage(options)).items; }
  async listPage(options: { pageSize?: number; pageToken?: string } = {}): Promise<Page<Run>> { const query = new URLSearchParams(); if (options.pageSize !== undefined) query.set('page_size', String(options.pageSize)); if (options.pageToken) query.set('page_token', options.pageToken); const payload = await this.client.request<Run[] | { items: Run[]; next_page_token?: string | null }>('GET', `/api/v1/runs${query.toString() ? `?${query}` : ''}`); return Array.isArray(payload) ? { items: payload, nextPageToken: null } : { items: payload.items, nextPageToken: payload.next_page_token ?? null }; }
  cancel(runId: string): Promise<Run> { return this.client.request<Run>('POST', `/api/v1/runs/${encodeURIComponent(runId)}/cancel`, {}); }
  retry(runId: string): Promise<Run> { return this.client.request<Run>('POST', `/api/v1/runs/${encodeURIComponent(runId)}/retry`, {}); }
  queue(): Promise<Record<string, unknown>> { return this.client.request<Record<string, unknown>>('GET', '/api/v1/queue'); }
  wait(runId: string, options?: { timeoutMs?: number; pollIntervalMs?: number }): Promise<Run> { return this.client.wait(runId, options); }
}

class ChatResource {
  constructor(private readonly client: DSHClient) {}
  send(message: string, packId = 'after-sales', conversationId?: string): Promise<ChatResponse> { return this.client.request<ChatResponse>('POST', '/api/v1/chat/messages', { message, pack_id: packId, conversation_id: conversationId }); }
}

class KnowledgeResource {
  constructor(private readonly client: DSHClient) {}
  listSources(): Promise<KnowledgeSource[]> { return this.client.request<KnowledgeSource[]>('GET', '/api/v1/knowledge/sources'); }
  ingest(input: { name: string; content: string; packId?: string; sourceId?: string; documentId?: string; metadata?: Record<string, unknown>; idempotencyKey?: string }): Promise<Record<string, unknown>> { return this.client.request('POST', '/api/v1/knowledge/ingest', { name: input.name, content: input.content, pack_id: input.packId ?? 'after-sales', ...(input.sourceId ? { source_id: input.sourceId } : {}), ...(input.documentId ? { document_id: input.documentId } : {}), ...(input.metadata ? { metadata: input.metadata } : {}) }, input.idempotencyKey); }
  citations(): Promise<Array<Record<string, unknown>>> { return this.client.request('GET', '/api/v1/knowledge/citations'); }
  search(query: string, packId = 'after-sales', topK?: number): Promise<KnowledgeSearchResponse> { return this.client.request<KnowledgeSearchResponse>('POST', '/api/v1/knowledge/search', { query, pack_id: packId, ...(topK === undefined ? {} : { top_k: topK }) }); }
}

class WorkflowsResource {
  constructor(private readonly client: DSHClient) {}
  run(workflowId: string, input?: unknown, idempotencyKey?: string): Promise<Run> { return this.client.request<Run>('POST', `/api/v1/workflows/${encodeURIComponent(workflowId)}/runs`, input === undefined ? {} : { input }, idempotencyKey); }
}

class ApprovalsResource {
  constructor(private readonly client: DSHClient) {}
  approve(taskId: string): Promise<Record<string, unknown>> { return this.client.request('POST', `/api/v1/approvals/${encodeURIComponent(taskId)}/approve`, {}); }
  reject(taskId: string): Promise<Record<string, unknown>> { return this.client.request('POST', `/api/v1/approvals/${encodeURIComponent(taskId)}/reject`, {}); }
}

class ArtifactsResource {
  constructor(private readonly client: DSHClient) {}
  list(taskId?: string): Promise<Artifact[]> { return this.client.request<Artifact[]>('GET', taskId ? `/api/v1/tasks/${encodeURIComponent(taskId)}/artifacts` : '/api/v1/artifacts'); }
  async listPage(options: { pageSize?: number; pageToken?: string } = {}): Promise<Page<Artifact>> { const query = new URLSearchParams(); if (options.pageSize !== undefined) query.set('page_size', String(options.pageSize)); if (options.pageToken) query.set('page_token', options.pageToken); const payload = await this.client.request<Artifact[] | { items: Artifact[]; next_page_token?: string | null }>('GET', `/api/v1/artifacts${query.toString() ? `?${query}` : ''}`); return Array.isArray(payload) ? { items: payload, nextPageToken: null } : { items: payload.items, nextPageToken: payload.next_page_token ?? null }; }
  async get(artifactId: string, taskId?: string): Promise<Artifact> { const artifacts = await this.list(taskId); const artifact = artifacts.find(item => item.id === artifactId || item.name === artifactId); if (!artifact) throw errorForStatus(404, 'artifact.not_found', 'artifact not found'); return artifact; }
}
