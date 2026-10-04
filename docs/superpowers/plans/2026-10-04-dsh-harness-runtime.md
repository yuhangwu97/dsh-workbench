# DSH Harness Runtime 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [x]`）语法来跟踪进度。

**目标：** 将 Workbench 执行层改为真正调用 DeepSeek Harness Python SDK，同时保留可隔离部署的 sidecar 模式，并让 Run、Event、Artifact、取消和重试都由统一运行时契约驱动。

**架构：** `DshRuntime` 变为路由器，`DshHarnessExecutor` 负责原生 `DeepSeekHarness` 进程，`DshSidecarExecutor` 负责受控 HTTP sidecar。服务层继续拥有业务状态、权限、审批和审计；Harness 只拥有推理、工具和技术事件。没有 SDK 或 endpoint 时，默认报告 `unavailable`，仅显式 `DSH_RUNTIME_MODE=demo` 才启用演示 worker。

**技术栈：** Python 3.10+ 标准库、官方 `deepseek-harness-sdk` 可选依赖、pytest、HTTP JSON callback、HMAC、SQLite/JSON 参考存储。

---

### 任务 1：原生 Harness 执行器契约

**文件：**
- 创建：`runtime/dsh_harness.py`
- 创建：`tests/test_dsh_harness.py`
- 修改：`runtime/__init__.py`
- 修改：`packages/python/pyproject.toml`

- [x] **步骤 1：编写失败测试**

```python
def test_native_executor_builds_session_prompt_and_maps_result(monkeypatch, tmp_path):
    calls = {}
    class Result:
        final_response = "diagnosis"
        finish_reason = "completed"
        events = [{"type": "turn/end"}]
        notifications = []
    class FakeHarness:
        def __init__(self, **kwargs):
            calls["kwargs"] = kwargs
        def run(self, prompt, *, session_id):
            calls["prompt"] = prompt
            calls["session_id"] = session_id
            return Result()
        def close(self):
            calls["closed"] = True
    monkeypatch.setitem(sys.modules, "deepseek_harness", SimpleNamespace(DeepSeekHarness=FakeHarness))
    executor = DshHarnessExecutor(home=str(tmp_path), profile="workbench-readonly")
    result = executor.run(request, run_id="run-1")
    assert result.status == "completed"
    assert result.session_id == "run-1"
    assert "allowed_tools" in calls["prompt"]
```

- [x] **步骤 2：运行测试确认失败**

运行：`python3 -m pytest tests/test_dsh_harness.py::test_native_executor_builds_session_prompt_and_maps_result -q`
预期：FAIL，报错 `ModuleNotFoundError` 或 `DshHarnessExecutor` 未定义。

- [x] **步骤 3：实现最少执行器**

`runtime/dsh_harness.py` 定义 `HarnessResult`、`DshHarnessConfig` 和 `DshHarnessExecutor`；延迟导入 `DeepSeekHarness`，传入 `dsh_home`、`profile`、`cwd`、`provider`、`model`、`reasoning_effort` 和 `max_tokens`，将 `DshRunRequest` 序列化成明确的 policy prompt，并把 `final_response`、`finish_reason`、events、notifications 映射成结果。

- [x] **步骤 4：运行测试确认通过**

运行：`python3 -m pytest tests/test_dsh_harness.py -q`
预期：所有 native executor 测试通过，缺失 SDK、缺失 home 和危险 profile 测试也通过。

- [x] **步骤 5：加入可选依赖并提交**

在 `pyproject.toml` 增加 `harness` extra：`deepseek-harness-sdk>=0.1.0`，不把 SDK 强制装进参考服务。提交：`feat: add native dsh harness executor`。

### 任务 2：统一运行时路由和配置

**文件：**
- 修改：`runtime/dsh_runtime.py`
- 修改：`runtime/__init__.py`
- 创建：`tests/test_runtime_modes.py`
- 修改：`.env.example`
- 修改：`docker-compose.yml`

- [x] **步骤 1：编写失败测试**

覆盖 `DSH_RUNTIME_MODE=native|sidecar|auto|demo`：native 选择 `DshHarnessExecutor`，sidecar 选择 HTTP executor，auto 按 endpoint/native 能力选择，未配置时返回 `mode=unavailable`；demo 只在显式设置时可用。

- [x] **步骤 2：运行测试确认失败**

运行：`python3 -m pytest tests/test_runtime_modes.py -q`
预期：FAIL，当前 `DshRuntime` 仍只有 configured/local-demo 两种模式。

- [x] **步骤 3：实现运行时路由**

保留 `DshRunRequest` 和现有远程 envelope 字段，新增 `mode`、`executor`、`session_id`、`capabilities`；`DshRuntime.dispatch()` 委托 native/sidecar executor，`enqueue()` 只负责产生 queued metadata 和调度入口。将 demo worker 改为显式模式。

- [x] **步骤 4：运行测试确认通过**

运行：`python3 -m pytest tests/test_runtime_modes.py tests/test_runtime.py -q`
预期：全部通过，旧 sidecar HTTP 请求字段保持兼容。

- [x] **步骤 5：更新环境和提交**

补充 `DSH_RUNTIME_MODE`、`DSH_HARNESS_HOME`、`DSH_HARNESS_PROFILE`、`DSH_HARNESS_WORKSPACE`、`DSH_PROVIDER`、`DSH_MODEL`、`DSH_REASONING_EFFORT`、`DSH_MAX_TOKENS` 和 `DSH_HARNESS_PATCHES`。提交：`feat: route workbench runs through dsh modes`。

### 任务 3：服务端 Run、Event 和 Artifact 映射

**文件：**
- 修改：`server.py`
- 创建：`tests/test_harness_server_flow.py`
- 修改：`contracts/schemas/run.json`
- 修改：`contracts/schemas/event.json`

- [x] **步骤 1：编写失败测试**

启动参考服务并注入 fake native executor，验证 Task Run 会记录 `dsh_session_id`，先变成 `running`，完成后写入 `harness-result.json` 和 `harness-events.jsonl`，并且 Harness 异常变成 `failed`。

- [x] **步骤 2：运行测试确认失败**

运行：`python3 -m pytest tests/test_harness_server_flow.py -q`
预期：FAIL，当前服务只在 remote callback 或 local demo worker 下更新 Run，没有 native result/artifact 映射。

- [x] **步骤 3：实现后台 dispatch 和状态映射**

新增受控 Harness worker：在 Run 入库后占用 `RUN_SEMAPHORE`，更新 `running`，调用 `DSH_RUNTIME.dispatch()`，再通过统一内部 callback 更新状态与 Artifact；把 `dsh_session_id`、`finish_reason`、`runtime_mode` 和 attempt 写进 Run。回调和 native 结果都经过同一条校验函数。

- [x] **步骤 4：实现取消和重试语义**

取消先写 `cancel_requested` 和 `cancelled`，再调用 executor.cancel；重试递增 attempt、清理旧 session 绑定并创建新的 `dsh_session_id`。旧 Run 事件和失败原因保留。

- [x] **步骤 5：运行测试确认通过并提交**

运行：`python3 -m pytest tests/test_harness_server_flow.py tests/test_server_contract.py tests/test_server_security.py -q`
预期：服务端状态、Artifact、取消和重试测试全部通过。提交：`feat: map dsh harness runs into workbench state`。

### 任务 4：Sidecar 契约和 Harness 安全边界

**文件：**
- 创建：`runtime/dsh_sidecar.py`
- 创建：`tests/test_dsh_sidecar.py`
- 修改：`contracts/openapi.yaml`
- 修改：`docs/product-architecture.md`
- 修改：`docs/releasing.md`

- [x] **步骤 1：编写失败测试**

验证 sidecar envelope 包含 tenant、actor、run、session、scope、allowed_tools、profile、callback；验证 HMAC callback、nonce、时间戳、tenant scope 和 Artifact 数量限制。

- [x] **步骤 2：运行测试确认失败**

运行：`python3 -m pytest tests/test_dsh_sidecar.py -q`
预期：FAIL，当前没有独立 sidecar executor 和版本化 envelope schema。

- [x] **步骤 3：实现 sidecar executor**

`DshSidecarExecutor` 复用 `DshRunRequest`，发送 JSON envelope 和 callback metadata，解析 accepted response；提供 `cancel()` 请求。sidecar 不接受任意 callback URL，callback 必须来自 Workbench 配置。

- [x] **步骤 4：补充安全文档和 OpenAPI**

写清 `workbench-readonly` profile 要求、禁止 `sdk-minimal` 直接作为 SaaS profile、隔离 `DSH_HOME`/cwd、只读 MCP/provider 和业务写入审批边界；新增 sidecar dispatch/cancel schema。

- [x] **步骤 5：运行测试并提交**

运行：`python3 -m pytest tests/test_dsh_sidecar.py tests/test_openapi_contract.py -q`
预期：全部通过。提交：`feat: add dsh harness sidecar contract`。

### 任务 5：SDK、文档、CI 和验收

**文件：**
- 修改：`README.md`
- 修改：`packages/python/README.md`
- 修改：`packages/typescript/README.md`
- 修改：`.github/workflows/ci.yml`
- 创建：`tests/test_harness_smoke.py`
- 修改：`CHANGELOG.md`

- [x] **步骤 1：编写 smoke test**

fake SDK smoke test 验证 `Task -> Run -> session -> result -> Artifact`；如果安装了官方 SDK，提供显式 `DSH_HARNESS_SMOKE=1` 的真实初始化探针，缺 API key 时报告 `skipped` 而不是伪造通过。

- [x] **步骤 2：实现文档和安装入口**

README 增加 `pip install 'dsh-workbench[harness]'`、DSH_HOME/profile 配置、native/sidecar 选择和安全提示；SDK 文档说明 Workbench SDK 调用的是产品 API，Harness SDK 是服务端运行时依赖。

- [x] **步骤 3：更新 CI**

CI 默认跑 fake Harness 契约测试；单独 job 只在 secret 存在时运行真实 Harness smoke test，并输出 runtime metadata，不打印 API key 或 session 内容。

- [x] **步骤 4：运行全套验证**

运行：

```bash
python3 -m pytest -q
python3 -m compileall runtime server.py
python3 -m pytest tests/test_harness_smoke.py -q
npm --prefix packages/typescript run typecheck
npm --prefix packages/typescript test
npm --prefix packages/typescript pack --dry-run
python3 -m build packages/python
python3 tools_evaluate_packs.py

git diff --check
git status --short
```

预期：Python/TypeScript 检查、SDK 构建、pack 评测和 diff 检查均退出码 0；没有 Harness secret 时真实 smoke test 明确为 skipped。

- [ ] **步骤 5：提交并推送**

提交：`feat: make dsh harness the workbench runtime`；确认 `git log -1`、`git status --short` 和远程分支后推送 `main`。
