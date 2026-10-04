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
