# DSH Workbench 开源框架实现计划

> **面向 AI 代理的工作者：** 以本计划为执行清单，逐项实现并验证。每一项完成后更新复选框并提交小步 commit。

**目标：** 在保持现有 Workbench 可运行的前提下，交付稳定 API 契约、Python/TypeScript SDK、扩展协议、Scenario Pack 示例、测试和发布配置。

**架构：** 根目录的 `server.py` 继续作为无依赖参考服务；`contracts/` 成为跨语言唯一契约；`packages/python` 和 `packages/typescript` 只依赖 HTTP 契约；扩展接口放进 SDK 的 `extensions` 模块。第一阶段不移动已有页面，避免破坏现有 URL 和 Docker 入口。

**技术栈：** Python 3.10+ 标准库、pytest、TypeScript 5、原生 Fetch、Node test runner、OpenAPI 3.1、JSON Schema 2020-12、Docker Compose、GitHub Actions。

---

### 任务 1：公共资源模型和错误契约

**文件：**
- 创建：`packages/python/dsh_workbench/models.py`
- 创建：`packages/python/dsh_workbench/errors.py`
- 创建：`packages/typescript/src/models.ts`
- 创建：`packages/typescript/src/errors.ts`
- 创建：`contracts/schemas/task.json`
- 创建：`contracts/schemas/run.json`
- 创建：`contracts/schemas/event.json`
- 创建：`contracts/schemas/error.json`
- 测试：`tests/test_contracts.py`

- [x] 定义 Task、Run、Artifact、Event、Page、ErrorEnvelope 的跨语言字段和状态枚举。
- [x] Python 使用 `dataclass` 和 `Enum`，提供从 JSON 映射的 `from_dict`，缺失必填字段抛出 `ModelError`。
- [x] TypeScript 使用 `type`/`interface` 和窄化函数，导出 `RunStatus` 和 `isRunTerminal`。
- [x] 用 JSON Schema 校验一份 completed Run、waiting approval Run 和错误响应。
- [x] 运行 `python -m pytest tests/test_contracts.py -q`，预期全部通过。
- [x] 提交 `feat: add cross-language resource contracts`。

### 任务 2：OpenAPI v1 契约

**文件：**
- 创建：`contracts/openapi.yaml`
- 修改：`docs/product-architecture.md`
- 测试：`tests/test_openapi_contract.py`

- [x] 描述 dashboard、packs、tasks、runs、knowledge/search、chat/messages、workflow runs、approvals、artifacts 和 callback 接口。
- [x] 统一声明 `Authorization`、`X-Tenant-ID`、`X-Actor-ID`、`X-Request-ID` 和 `Idempotency-Key`。
- [x] 所有响应引用 `contracts/schemas` 中的模型；写接口声明 201、400、401、403、404、409、422。
- [x] 用 Python 标准库做最小 OpenAPI 结构校验，保证 paths、schemas 和 response 引用存在。
- [x] 运行 `python -m pytest tests/test_openapi_contract.py -q`。
- [x] 提交 `docs: publish versioned openapi contract`。

### 任务 3：参考服务的生产化 API 基础能力

**文件：**
- 修改：`server.py`
- 修改：`runtime/dsh_runtime.py`
- 创建：`tests/test_server_contract.py`
- 创建：`tests/test_server_security.py`

- [x] 增加 `X-Request-ID` 生成/透传和统一错误 envelope，保留现有成功响应兼容性。
- [x] 为创建 Task、运行 Task 和 Workflow Run 增加内存/SQLite 作用域内的 Idempotency-Key 去重记录。
- [x] 增加稳定的分页参数和响应字段，不影响默认无分页调用。
- [x] 为 DSH callback 增加可选 `DSH_CALLBACK_SECRET` 的 HMAC 校验、时间戳和 nonce，开发模式保持兼容。
- [x] 将 Chat 和 Knowledge 的 fixture 行为包装为明确的 provider seam，返回 `source: demo`，避免假装是生产检索。
- [x] 测试租户越权、错误结构、重复创建和 callback 签名。
- [x] 运行 `python -m pytest tests/test_server_contract.py tests/test_server_security.py -q`。
- [x] 提交 `feat: harden reference api contracts`。

### 任务 4：Python SDK

**文件：**
- 创建：`packages/python/pyproject.toml`
- 创建：`packages/python/dsh_workbench/client.py`
- 创建：`packages/python/dsh_workbench/resources.py`
- 创建：`packages/python/dsh_workbench/extensions.py`
- 创建：`packages/python/dsh_workbench/__init__.py`
- 创建：`tests/sdk_python/test_client.py`
- 创建：`tests/sdk_python/test_extensions.py`

- [x] 实现 `DSHClient` 和 `AsyncDSHClient`，支持 base_url、api_key、tenant_id、actor_id、timeout、request_id 和自定义 headers。
- [x] 实现 `tasks.create/get/list/run`、`runs.get/list/wait`、`chat.send`、`knowledge.search`、`workflows.run`、`approvals.approve/reject`、`artifacts.list/get`。
- [x] 将 401/403/404/409/422/5xx 映射到明确的异常类并携带 request_id、status_code、details。
- [x] `runs.wait` 使用轮询间隔、超时和 terminal status，不无限重试；支持 callback 后读取 Artifact。
- [x] 提供 Protocol：`KnowledgeProvider`、`SkillProvider`、`WorkflowExecutor`、`ArtifactStore`、`ApprovalPolicy`、`EventSink`。
- [x] 用本地 fixture HTTP handler 测试 headers、序列化、错误映射和 wait 行为。
- [x] 运行 `python -m pytest tests/sdk_python -q`，并构建 wheel/sdist。
- [x] 提交 `feat: add python sdk`。

### 任务 5：TypeScript SDK

**文件：**
- 创建：`packages/typescript/package.json`
- 创建：`packages/typescript/tsconfig.json`
- 创建：`packages/typescript/src/client.ts`
- 创建：`packages/typescript/src/resources.ts`
- 创建：`packages/typescript/src/extensions.ts`
- 创建：`packages/typescript/src/index.ts`
- 创建：`packages/typescript/test/client.test.ts`

- [x] 实现基于原生 Fetch 的 `DSHClient`，支持同 Python SDK 的资源方法和请求 headers。
- [x] 导出资源类型、状态类型、错误类和扩展 interface。
- [x] 统一处理非 2xx 响应，保留 request_id 和 details。
- [x] `runs.wait` 支持 AbortSignal 和超时。
- [x] 使用 Node test runner 测试请求路径、body、headers、错误和轮询。
- [x] 运行 `npm install`、`npm run typecheck`、`npm test`、`npm pack --dry-run`。
- [x] 提交 `feat: add typescript sdk`。

### 任务 6：Scenario Pack manifest 和扩展示例

**文件：**
- 创建：`packs/after-sales/pack.yaml`
- 创建：`packs/after-sales/README.md`
- 创建：`examples/python/after_sales.py`
- 创建：`examples/typescript/after-sales.ts`
- 创建：`docs/extensions.md`
- 测试：`tests/test_pack_manifest.py`

- [x] 定义 pack id、版本、Skills、Knowledge Sources、Workflows、权限和 approval policy。
- [x] 示例展示：创建 Task、运行、等待、读取 Artifact。
- [x] 文档展示如何实现自定义 KnowledgeProvider 和 ArtifactStore，而不修改 SDK。
- [x] 用最小 YAML parser 检查 manifest 的必填字段、唯一 id 和声明的 Skill/Workflow 引用。
- [x] 运行 `python -m pytest tests/test_pack_manifest.py -q`。
- [x] 提交 `feat: add scenario pack extension examples`。

### 任务 7：发布、CI 和开发者体验

**文件：**
- 创建：`.github/workflows/ci.yml`
- 创建：`packages/python/README.md`
- 创建：`packages/typescript/README.md`
- 修改：`README.md`
- 修改：`docker-compose.yml`
- 创建：`LICENSE`
- 创建：`CHANGELOG.md`

- [x] CI 执行 Python compile/pytest、Python build、TypeScript typecheck/test/pack、OpenAPI 校验、Docker build。
- [x] Python 包配置 PyPI wheel/sdist 元数据；TypeScript 包配置 npm exports、types 和 files。
- [x] 根 README 加入 5 分钟自托管、Python/TypeScript 首次调用、扩展入口、架构边界和安全说明。
- [x] Docker 健康检查和现有 `python3 server.py --port 8766` 入口继续可用。
- [x] 本地执行全部检查并记录结果。
- [x] 提交 `chore: prepare framework release`。

### 任务 8：最终验收和推送

**文件：**
- 修改：`docs/superpowers/specs/2026-10-04-open-source-framework-design.md`（如发现规格缺口）
- 修改：`docs/superpowers/plans/2026-10-04-open-source-framework.md`（更新复选框）

- [ ] 启动参考服务，运行 SDK 到 API 的端到端链路：create Task → run → wait → list Artifact。
- [ ] 运行跨租户拒绝、HMAC callback、幂等创建、Docker health/ready 验证。
- [ ] 检查 `git diff --check`、仓库状态和构建产物。
- [ ] 将最终提交推送到 `https://github.com/yuhangwu97/dsh-workbench.git` 的 `main`。
- [ ] 在 README 和最终回复中明确当前参考服务能力与生产替换边界。
