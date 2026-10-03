# DSH Workbench 开源框架设计规格

## 目标

把 DSH Workbench 从可演示的 AI Task Platform 升级为可自托管、可被外部应用接入、可通过 SDK 扩展的开源框架。Workbench 继续作为官方控制台和参考服务；公共协议、SDK 与扩展接口独立于控制台实现。

## 产品边界

产品层负责 Task、Scenario Pack、Skill、Knowledge Source、Workflow、Run、Approval、Artifact、Event 和审计语义。DSH 负责受限推理、工具编排和结构化输出。任何推理供应商、向量库、工作流引擎和对象存储都通过协议适配，不进入核心领域模型。

## 仓库结构

```text
apps/workbench          官方控制台和参考 API（当前根目录逐步迁移）
packages/python         dsh-workbench Python SDK
packages/typescript     @dsh-workbench/sdk TypeScript SDK
contracts               OpenAPI 与 JSON Schema
packs                   可复制的 Scenario Pack 示例
examples                Python/TypeScript 接入示例
tests                   协议、SDK、运行时和兼容性测试
docs                    架构、扩展和发布文档
```

第一阶段允许保持现有根目录入口，避免一次迁移破坏当前页面；新包和协议先以独立目录加入，待契约稳定后再移动服务实现。

## 公共资源模型

- **Task**：业务输入的持久化单元，记录场景包、Skill、输入快照、租户和创建者。
- **Run**：Task、Workflow 或 Skill 的一次执行，使用明确状态机：`queued`、`running`、`completed`、`waiting_approval`、`failed`、`rejected`。
- **Skill**：具名、版本化、声明依赖工具的能力。
- **Workflow**：由输入、知识检索、Skill、审批和 Artifact 节点组成的过程定义。
- **Knowledge Source**：可检索资料的元数据和场景访问边界。
- **Approval**：业务写入或高风险动作的人工决策。
- **Artifact**：Run 产出的结构化结果、证据包或文件引用。
- **Event**：Task/Run/Approval/Artifact 的可订阅状态变化。

## HTTP 契约

所有公共接口使用 `/api/v1`，响应带 `X-Request-ID`。写接口接受 `Idempotency-Key`，重复请求返回相同资源。错误统一为：

```json
{
  "error": {
    "code": "task.not_found",
    "message": "task not found",
    "request_id": "req_123",
    "details": {}
  }
}
```

分页使用 `page_size`、`page_token` 和 `next_page_token`。租户和操作者由认证主体解析，开发模式允许 `X-Tenant-ID` 和 `X-Actor-ID`。

## SDK 设计

Python 包名为 `dsh-workbench`，导入名为 `dsh_workbench`；TypeScript 包名为 `@dsh-workbench/sdk`。两者都提供：

```text
client.tasks.create/get/list/run
client.runs.get/list/wait
client.workflows.run
client.knowledge.search
client.artifacts.list/get
client.chat.send
client.approvals.approve/reject
```

SDK 只依赖公共 HTTP/JSON 契约。Python 提供同步 Client 和异步 AsyncClient；TypeScript 使用原生 Fetch，不绑定框架。所有资源使用类型化模型，服务端错误映射为可捕获的 SDK 异常。

## 扩展接口

扩展协议使用 Python Protocol 和 TypeScript interface 定义：

- `KnowledgeProvider.search(query, scope)`
- `SkillProvider.run(request)`
- `WorkflowExecutor.start(request)`
- `ArtifactStore.put/get/list`
- `ApprovalPolicy.evaluate(action, context)`
- `EventSink.publish(event)`

扩展不得直接修改 Task 状态；统一通过服务层返回结构化结果和事件。Provider 请求必须携带 tenant、actor、request_id 和 allowed_tools。

## DSH 运行时边界

DSH 请求必须包含 tenant、actor、task、skill、knowledge scope、allowed tools、output schema 和 approval_required。默认禁止 shell 和不受限文件系统。DSH 通过 callback 返回 Run 状态和 Artifact；生产回调使用 HMAC 签名，拒绝重放请求。

## 交付和兼容性

- OpenAPI 是 HTTP 兼容性的唯一来源。
- JSON Schema 是跨语言资源和事件的唯一来源。
- SDK 遵循 SemVer；v1 之前只保证同一 minor 版本内兼容。
- CI 必须执行 Python 类型/单元测试、TypeScript 类型/单元测试、OpenAPI 校验、参考服务 API 合约测试和 Docker 构建。
- 发布需要构建 Python wheel/sdist、npm tarball，并在 README 提供 5 分钟自托管和首次 SDK 调用。

## 非目标

第一版不内置特定 LLM、向量数据库、Temporal、LangGraph、对象存储或企业身份供应商；不把这些基础设施写死进核心包。
