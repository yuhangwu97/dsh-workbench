# DSH Workbench

面向企业的开源 AI Task Platform 框架。平台把业务输入统一成 Task，用 Scenario Pack 组织 Skills、Knowledge、Workflows 和审批策略，Workbench 提供官方控制台和参考服务，适合作为 DSH 运行时的产品层。

这是一个可以自托管和二次开发的开源框架。Workbench 是官方控制台和参考服务；`contracts/` 是公共 HTTP/JSON 契约；`packages/python` 和 `packages/typescript` 是给外部应用使用的 SDK。

## 当前 Demo

- **Chat Intake**：接收问题、显示证据并可转为 Task
- **Task Inbox**：查看开放任务、状态、更新时间和场景包归属
- **Scenario Pack Library**：售后诊断、研发助手、运营告警三个业务包
- **Skill Registry**：Skill 的版本、来源、依赖和试运行入口
- **Knowledge Bases**：资料、索引状态和场景包访问范围
- **Workflow Builder**：输入、证据、Skill、审批和 Artifact 的过程编排
- **Artifact Library**：诊断报告、证据包和研发计划的结果目录
- **Task Detail**：Overview、Run trace、Artifacts 三个视图，可直接运行 Task
- **New Task**：选择场景包和 Skill，创建任务并立即加入任务列表
- **本地状态**：当前场景包选择保存在 `localStorage`

## SDK 快速开始

Python：

```bash
python -m pip install dsh-workbench
```

```python
from dsh_workbench import DSHClient

client = DSHClient("http://localhost:8766", tenant_id="tenant-demo")
task = client.tasks.create(name="设备诊断", pack_id="after-sales", skill_id="equipment-diagnosis")
run = client.tasks.run(task.id)
completed = client.runs.wait(run.id)
print(completed.status.value)
```

TypeScript：

```bash
npm install @dsh-workbench/sdk
```

```ts
import { DSHClient } from '@dsh-workbench/sdk';

const client = new DSHClient({ baseUrl: 'http://localhost:8766', tenantId: 'tenant-demo' });
const task = await client.tasks.create({ name: '设备诊断', packId: 'after-sales', skillId: 'equipment-diagnosis' });
const run = await client.tasks.run(task.id);
const completed = await client.runs.wait(run.id);
console.log(completed.status);
```

## 运行

这是一个无构建依赖的前端 Demo，运行 `server.py` 会同时提供静态文件和本地 API：

```bash
python3 server.py --port 8766
```

打开 <http://127.0.0.1:8766/>。服务同时提供 `/api/v1/health`、`/api/v1/dashboard`、Chat 消息、Knowledge、Workflow、Task、Run、Artifact、Approval 和 Audit 接口。运行状态保存在 `data/state.json`。

本地 Run 会经过 `queued → running → completed` 生命周期；需要业务确认的任务会停在 `waiting_approval`，审批通过后恢复执行，拒绝后会标记为 `rejected`。完成后服务会生成结构化 JSON 和证据包 Artifact。默认 runtime 是 `local-demo`；设置 `DSH_ENDPOINT` 后，服务会把受限 Run 请求 POST 到 DSH，并等待 DSH 调用 `POST /api/v1/runs/:id/callback` 回写状态和 Artifact。

每个 Task 和 Run 都携带 `tenant_id`、`created_by` / `actor_id`。本地默认上下文是 `tenant-demo`，API 客户端可通过 `X-Tenant-ID` 和 `X-Actor-ID` 传入工作区上下文；单容器部署使用 SQLite 和 Bearer Token，生产多实例环境建议替换为企业 OIDC/JWT 和托管数据库。

## 容器部署

```bash
cp .env.example .env
# 编辑 .env，至少设置 WORKBENCH_AUTH_TOKEN
docker compose up -d --build
```

Compose 会把 `data` 挂载到持久化卷，默认使用 SQLite 存储，健康检查使用 `/api/v1/health`。认证开启后，除健康检查外的 API 需要 `Authorization: Bearer <WORKBENCH_AUTH_TOKEN>`；前端首次收到 401 会显示工作区 Token 登录框，并在浏览器本地保存 Token。前端仍通过 `X-Tenant-ID` 和 `X-Actor-ID` 传递工作区上下文。正式环境建议把 Bearer 校验替换为企业 OIDC/JWT 网关。

## 产品对象

```text
Task
├── Scenario Pack
│   ├── Skills
│   ├── Knowledge Bases
│   ├── Workflows
│   ├── Policies
│   └── Evaluation Cases
├── Run History
├── Approval
└── Artifact
```

DSH 负责复杂推理和运行时编排；产品层负责 Task 状态、场景范围、权限、审批、审计和 Artifact 生命周期。当前仓库已经包含可持久化的本地 API；生产环境可将 `server.py` 替换为 Go/FastAPI 服务，并把 DSH 作为受限运行时接入。

扩展点见 [docs/extensions.md](docs/extensions.md)。公共 API 变更必须先更新 OpenAPI 和 JSON Schema，再同步两套 SDK。

## 目录

- `index.html`：工作台信息架构和页面骨架
- `styles.css`：浅色企业工具型设计系统、响应式布局和状态样式
- `app.js`：导航、场景包切换、任务创建、Skill 试运行、Task Drawer 交互和 API 数据同步
- `server.py`：无第三方依赖的 API + 静态文件服务器，支持 Bearer 保护和健康检查
- `runtime/dsh_runtime.py`：DSH 受限运行时边界和结构化 Run 请求契约
- `contracts/openapi.yaml`：版本化 HTTP API 契约
- `contracts/schemas/`：Task、Run、Event、Error JSON Schema
- `packages/python/`：Python SDK 和扩展 Protocol
- `packages/typescript/`：TypeScript SDK 和扩展 interface
- `packs/after-sales/`：可复制的 Scenario Pack manifest
- `examples/`：Python/TypeScript 接入示例
- `data/state.json`：本地 JSON 模式的可持久化 Task、Run、Approval、Artifact 状态
- `data/workbench.sqlite3`：Compose SQLite 模式的持久化状态文件
- `Dockerfile` / `docker-compose.yml`：可直接启动的容器部署入口
