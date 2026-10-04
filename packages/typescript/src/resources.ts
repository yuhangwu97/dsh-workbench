export type RunStatus = 'queued' | 'running' | 'completed' | 'waiting_approval' | 'failed' | 'rejected';

export interface Task {
  id: string;
  name: string;
  pack_id: string;
  skill_id: string;
  status: string;
  status_label?: string | null;
  input_snapshot?: unknown;
  tenant_id?: string | null;
  created_by?: string | null;
  [key: string]: unknown;
}

export interface Run {
  id: string;
  status: RunStatus;
  task_id?: string | null;
  workflow_id?: string | null;
  skill_id?: string | null;
  message?: string | null;
  runtime?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface Artifact {
  id?: string;
  name: string;
  type: string;
  description?: string | null;
  task_id?: string | null;
  run_id?: string | null;
  uri?: string | null;
  [key: string]: unknown;
}

export interface ChatResponse {
  reply: string;
  evidence_count?: number;
  pack_id?: string;
  [key: string]: unknown;
}

export interface KnowledgeSearchResponse {
  query: string;
  pack_id: string;
  matches: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

export function isTerminalRun(run: Pick<Run, 'status'>): boolean {
  return run.status === 'completed' || run.status === 'failed' || run.status === 'rejected';
}
