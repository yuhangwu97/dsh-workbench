# 扩展 DSH Workbench

DSH Workbench 的扩展点只依赖公开资源模型，不需要修改 `server.py`。

## KnowledgeProvider

把 `search` 映射到你的向量库或全文检索服务，返回带来源、片段和相关度的字典列表。实现必须校验 `tenant_id` 和 `scope`，不能跨租户读取。

## SkillProvider

Skill Provider 接收 Skill ID、Task ID、输入和允许的工具白名单，返回结构化 Run。Provider 不应直接写业务数据库；需要业务写入时返回 `waiting_approval`。

## WorkflowExecutor

Workflow Executor 可以使用 DSH、Temporal、LangGraph 或自研执行器。它只负责启动和报告 Run，Task 状态仍由 Workbench 服务统一维护。

## ArtifactStore

ArtifactStore 把结构化结果和证据文件保存到 S3、OSS、MinIO 或本地对象存储。Task/Run 只保存 Artifact 元数据和 URI。

## ApprovalPolicy 与 EventSink

ApprovalPolicy 决定动作是否需要人工确认；EventSink 用于接入 Kafka、Webhook、审计系统或指标管道。

所有 Provider 请求都应携带租户、操作者、request ID 和 allowed tools。生产部署建议把 Provider 放在独立进程，通过网络和权限边界连接 Workbench。

## Knowledge ingestion 与引用

参考服务提供 `POST /api/v1/knowledge/ingest`。它会把文档切成带 `document_id`、`chunk_id` 和 embedding 的片段，并在 `POST /api/v1/knowledge/search` 返回 `citation_id`。默认的 `local-hash-v1` 只用于本地演示；生产环境应通过 Provider 接入实际 embedding 服务，并保留相同的 chunk/citation 字段。

## Run queue

`GET /api/v1/queue` 暴露并发上限和排队数量。`POST /api/v1/runs/{run_id}/cancel` 可以停止排队或运行中的 Run；失败、取消或拒绝的 Run 可以通过 `/retry` 重新入队，默认最多三次尝试。`WORKBENCH_MAX_CONCURRENCY` 控制本地参考执行器的并发上限。

## Identity 与权限

设置 `WORKBENCH_JWT_SECRET` 后，服务会校验 HS256 JWT 的 `iss`、`exp`、`sub`、`org_id`/`tenant_id` 和 `roles`。`WORKBENCH_OIDC_ISSUER` 用于校验 issuer；组织成员接口提供 `owner`、`admin`、`editor`、`operator`、`viewer` 五种角色。真实部署可把同一上下文替换为 OIDC 网关或企业 IdP。

## Scenario Pack 评测

运行 `python3 tools_evaluate_packs.py` 可以检查所有 Pack manifest 是否声明版本、Skills、Knowledge、Workflow 和安全策略。服务端的 `POST /api/v1/scenario-packs/{pack_id}/evaluations` 会把评测结果留在审计和评测记录中。
