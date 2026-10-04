# DSH Harness Runtime Integration Design

## Goal

将 DSH Workbench 的执行层改为真正基于 DeepSeek Harness 的运行时，同时保留生产环境可隔离部署的 sidecar 模式。Workbench 继续作为业务控制面；Harness 负责 agent loop、模型调用、工具编排、session 和技术事件。

## Runtime modes

`DSH_RUNTIME_MODE` 控制执行方式：

- `native`：Workbench 进程通过 `deepseek-harness-sdk` 创建 `DeepSeekHarness`，每个 Run 使用明确的 Harness home、profile 和 session id。
- `sidecar`：Workbench 向一个已部署的 DSH Harness gateway 发送相同的受控 Run envelope；gateway 负责创建 Harness session，并通过 callback 回写 Run/Event/Artifact。
- `auto`：有 `DSH_ENDPOINT` 时使用 sidecar；否则尝试 native；两者都不可用时返回 `runtime.unavailable`。`local-demo` 只允许显式设置 `DSH_RUNTIME_MODE=demo`，不再作为默认执行器。

## Ownership boundary

Workbench owns Task, tenant and actor scope, quotas, approvals, business writes, Knowledge citations, Artifact indexing and audit. Harness owns reasoning, model requests, agent loop, plugin tools, session event log and runtime diagnostics. Harness output cannot directly mutate a business resource; all writes go through Workbench approval and idempotency checks.

## Native executor

新增 `runtime/dsh_harness.py`，提供 `DshHarnessExecutor`：

```python
class DshHarnessExecutor(Protocol):
    def start(self, request: DshRunRequest, run_id: str) -> HarnessDispatch:
        ...
    def cancel(self, run_id: str) -> None:
        ...
    def close(self) -> None:
        ...
```

执行器延迟导入 `deepseek_harness.DeepSeekHarness`，未安装时给出结构化 `runtime.unavailable`。配置至少包括：

- `DSH_HARNESS_HOME`：每个部署实例的显式 Harness home；禁止隐式读取 `~/.dsh`。
- `DSH_HARNESS_PROFILE`：Workbench 专用 profile，默认 `workbench-readonly`；启动时拒绝缺失或危险的默认 profile。
- `DSH_HARNESS_WORKSPACE`：隔离工作目录。
- `DSH_PROVIDER`、`DSH_MODEL`、`DSH_REASONING_EFFORT`、`DSH_MAX_TOKENS`。
- `DSH_HARNESS_PATCHES`：有序 profile patch 文件，用于声明只读工具和 Scenario Pack 插件。

每个 Run 生成 `dsh_session_id`，默认与 Workbench `run_id` 一一对应，重试创建新的 session id；用户主动继续对话时显式复用 session id。Prompt 由产品层生成，包含 task input、knowledge scope、citation ids、allowed tools、output schema、approval policy 和禁止直接业务写入的运行规则。

执行结果映射为：

- `run/start` 或 dispatch accepted -> `running`
- `finish_reason=completed` -> `completed`
- `finish_reason=max-tokens` -> `completed`，并记录截断原因
- SDK 协议错误、模型错误、工具错误 -> `failed`
- Workbench cancel token 命中 -> `cancelled`

完成时写入两个产品 Artifact：`harness-result.json` 保存 `final_response`、`finish_reason`、`session_id` 和 usage；`harness-events.jsonl` 保存经脱敏的 Harness 事件。原始 session 日志仍由 Harness home 管理，不作为业务事实源。

## Sidecar executor

sidecar 复用相同的 `DshRunRequest` 和 `HarnessDispatch`，POST 到 `DSH_ENDPOINT`。请求必须带 tenant、actor、run、session、knowledge scope、allowed tools、output schema、profile 和 callback URL。sidecar 只允许回写签名 callback；Workbench 校验 tenant、run 状态、nonce、时间戳和 Artifact 数量上限。

sidecar gateway 的实现契约固定为：接收受控 envelope，使用官方 `DeepSeekHarness` 创建 session，按事件发送 `running`/`completed`/`failed` callback，并在关闭或超时时回收 Harness 进程。这样 native 和 sidecar 使用同一份产品协议。

## Cancellation, retry and quota

Run 创建后先写入 `queued`，再由受控 worker 获取执行额度。每个 Run 有 `attempt`、`max_attempts`、`cancel_requested` 和 `dsh_session_id`。取消先更新产品状态，再通知执行器；native 模式通过关闭该 Run 的 Harness 实例释放进程，sidecar 模式发送 cancel 请求。重试永远创建新的 session，保留旧 session id 和失败原因，避免复用污染上下文。

## Security defaults

禁止使用官方 `sdk-minimal` 的默认 shell/filesystem 能力作为 SaaS profile。Workbench profile 必须显式声明只读工具、隔离 cwd、允许的 egress 和 Scenario Pack plugin；业务工具只能通过带 tenant/object 复核的 MCP/provider 暴露。Harness 不接收全局 token，也不能直接写入 Workbench 数据库。

## Tests and acceptance

新增运行时契约测试：

1. native executor 使用 fake `deepseek_harness` 模块验证构造参数、session id、prompt policy 和结果映射。
2. native executor 在缺少 SDK、缺失 home、危险 profile 时返回结构化错误。
3. callback 流程验证 HMAC、nonce、tenant scope、事件和 Artifact 限制。
4. cancel/retry 验证状态机、session 生命周期和 attempt 递增。
5. sidecar contract fixture 验证 native/sidecar envelope 字段一致。
6. 在安装官方 SDK 的独立环境中执行一个真实 Harness smoke test；未提供 API key 时只运行初始化探针，不声称模型调用成功。

验收标准：参考服务的 `/api/v1/ready` 明确报告 `native`、`sidecar` 或 `unavailable`；没有 Harness SDK 或 endpoint 时不会把 `local-demo` 当成真实运行；配置 native 后 Task -> Run -> Harness result -> Artifact 链路可追踪；生产 profile 默认拒绝 shell、任意文件系统和直接业务写入。
