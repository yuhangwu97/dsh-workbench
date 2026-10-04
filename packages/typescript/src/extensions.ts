import type { Artifact, Run } from './resources.js';

export interface KnowledgeProvider { search(query: string, scope: string[], context: { tenantId: string; actorId: string }): Promise<Array<Record<string, unknown>>>; }
export interface SkillProvider { run(request: { skillId: string; taskId: string; input: unknown; allowedTools: string[]; tenantId: string; actorId: string }): Promise<Run>; }
export interface WorkflowExecutor { start(request: { workflowId: string; taskId?: string; input: unknown; tenantId: string; actorId: string }): Promise<Run>; }
export interface ArtifactStore { put(artifact: Artifact, content: Uint8Array): Promise<Artifact>; get(artifact: Artifact): Promise<Uint8Array>; list(taskId: string | undefined, tenantId: string): Promise<Artifact[]>; }
export interface ApprovalPolicy { evaluate(action: string, context: Record<string, unknown>): Promise<boolean>; }
export interface EventSink { publish(event: Record<string, unknown>): Promise<void>; }
