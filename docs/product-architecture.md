# DSH Workbench 产品层架构

## 产品定位

DSH Workbench 是面向企业的 AI Task Platform。用户提交的是业务 Task，不是一次性聊天消息；平台负责把输入路由到对应的 Scenario Pack、Skill 和 Workflow，并把执行结果保存成可审计的 Artifact。

```text
Chat / Event / API
        ↓
Task intake
        ↓
Scenario Pack
  ├── Knowledge scope
  ├── Skill selection
  ├── Workflow
  └── Policy / approval
        ↓
DSH runtime
        ↓
Run trace + Artifact
        ↓
Task state / approval / audit
```

## 领域对象

### Task

统一承载业务输入和状态。

```text
id
tenant_id
scenario_pack_id
skill_id / workflow_id
input_snapshot
status: draft | queued | running | waiting_approval | completed | failed | cancelled
output_artifact_ids
created_by
created_at / updated_at
```

### Run

一次实际执行。一个 Task 可以有多次 Run，用于重试、版本对比和审计。

```text
id
task_id
tenant_id / actor_id
runtime: dsh
runtime_version
skill_version
started_at / finished_at
steps[]
usage
error
```

### Artifact

面向用户的业务结果，不等同于 DSH 的日志。

```text
id
task_id
type: report | json | draft | evidence_bundle | patch_plan
schema_version
content_uri
citations[]
created_at
```

### Scenario Pack

业务可安装单元，包含 Skills、Knowledge、Workflows、Policies 和评测案例。

```text
id
name
version
status: draft | enabled | disabled | deprecated
skills[]
knowledge_bases[]
workflows[]
policies[]
evals[]
```

## 所有权边界

| 能力 | 平台产品层 | DSH Runtime |
|---|---:|---:|
| Task 状态 | ✓ |  |
| 租户与用户权限 | ✓ |  |
| 场景包范围 | ✓ |  |
| 知识库访问策略 | ✓ |  |
| 审批与业务动作 | ✓ |  |
| Artifact 生命周期 | ✓ |  |
| 模型调用与复杂推理 |  | ✓ |
| 工具编排与执行轨迹 |  | ✓ |
| 运行时重试 |  | ✓ |

DSH 的输出需要经过平台层的 schema 校验、权限复核和业务动作审批后，才能成为最终 Artifact 或产生外部副作用。

## 部署与认证边界

`Dockerfile` 和 `docker-compose.yml` 提供单容器部署入口，`data` 目录使用持久化卷保存 SQLite 状态。设置 `WORKBENCH_AUTH_TOKEN` 后，除健康和就绪探针外的 API 需要 Bearer Token；`X-Tenant-ID` 与 `X-Actor-ID` 作为当前工作区上下文进入 Task 和 Run。生产环境应由 OIDC/JWT 网关提供身份和租户声明，再映射到这些字段。

## MVP API 边界

```text
GET    /api/v1/scenario-packs
GET    /api/v1/skills
POST   /api/v1/tasks
GET    /api/v1/tasks/:id
POST   /api/v1/tasks/:id/runs
GET    /api/v1/runs/:runId
POST   /api/v1/runs/:runId/callback
GET    /api/v1/tasks/:id/artifacts
GET    /api/v1/audit
GET    /api/v1/health
GET    /api/v1/ready
POST   /api/v1/approvals/:id/approve
POST   /api/v1/approvals/:id/reject
```

前端当前使用本地 fixture；将 `app.js` 中的 `packData` 和 `tasks` 替换为上述 API 数据即可接入真实服务。

## 前端入口与后端接口映射

| 前端入口 | 主要接口 | 结果 |
|---|---|---|
| Chat | `POST /api/v1/chat/messages` | 会话上下文、证据提示、Task 转换入口 |
| 知识库 | `GET /api/v1/knowledge` | 资料源、文档数量、索引状态 |
| 工作流 | `GET /api/v1/workflows` | 流程步骤、发布状态、运行入口 |
| 任务 | `GET/POST /api/v1/tasks` | 统一业务状态和输入快照 |
| 运行记录 | `GET /api/v1/runs`、`GET /api/v1/runs/:id` | Skill / Workflow 的运行历史和单次状态 |
| DSH 回写 | `POST /api/v1/runs/:id/callback` | DSH sidecar 回写 Run 状态和 Artifact |
| 产物 | `GET /api/v1/artifacts` | 结构化结果、证据包和计划文件 |
| 审批 | `POST /api/v1/approvals/:id/approve` | 业务动作的人工确认 |
| 审计 | `GET /api/v1/audit` | 按租户查看 Task、Run、Artifact 和审批事件 |
| 运行探针 | `GET /api/v1/health`、`GET /api/v1/ready` | 容器健康检查和运行时状态 |

## DSH Runtime Boundary

`runtime/dsh_runtime.py` 只接受显式的租户、操作者、`task_id`、`skill_id`、知识范围、允许工具和输出 Schema。当前默认返回 `local-demo` 的 queued envelope；本地 worker 会把 Run 推进到 `running`、`completed` 或 `waiting_approval`，审批通过后恢复执行，并将结果写入产品层 Artifact。设置 `DSH_ENDPOINT` 后，Runtime 会 POST 受限请求到 DSH，DSH 通过 Run callback 回写状态和 Artifact。

业务写入由产品层审批，不能由运行时直接决定。运行时的 trace 可以作为 Run 证据保存，但不能覆盖 Task 状态或 Artifact 内容。
