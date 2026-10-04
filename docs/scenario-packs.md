# 三个 Scenario Pack

## 售后诊断

目标：将设备日志、产品手册和历史工单组合成可追溯的诊断任务。

```yaml
name: after-sales-diagnosis
label: 售后诊断
skills:
  - equipment-diagnosis
  - fault-code-analysis
  - repair-recommendation
workflows:
  - diagnose-equipment-v2
knowledge:
  - product-manuals
  - fault-code-library
  - historical-tickets
approval:
  - create-maintenance-ticket
```

默认 Artifact：`DiagnosisReport`。

## 研发助手

目标：把 Issue、代码上下文、影响范围和测试计划组织成工程任务。

```yaml
name: engineering-assistant
label: 研发助手
skills:
  - issue-investigation
  - repository-context
  - change-impact-analysis
  - test-plan
workflows:
  - issue-to-patch-plan
knowledge:
  - repository-docs
  - api-contracts
approval:
  - create-patch
```

默认 Artifact：`InvestigationReport`、`PatchPlan`、`TestPlan`。

## 运营告警

目标：聚合告警、匹配 Runbook、计算影响范围，并在升级前请求确认。

```yaml
name: operations-alerting
label: 运营告警
skills:
  - alert-triage
  - alert-deduplication
  - runbook-match
  - impact-analysis
workflows:
  - alert-to-escalation
knowledge:
  - runbooks
  - service-catalog
  - on-call-policy
approval:
  - escalate-incident
```

默认 Artifact：`IncidentReport`、`EscalationDraft`。

## 统一生命周期

```text
draft → queued → running → waiting_approval → completed
                         ↘ failed
                         ↘ cancelled
```

高风险动作只允许进入 `waiting_approval`，不能因为模型建议就直接执行。

## Registry 与评测

仓库中的 `registry/scenario-packs.json` 是一个可版本化的 Pack 目录，默认收录售后诊断、研发助手和运营告警。服务端通过 `GET /api/v1/registry/scenario-packs` 暴露目录，管理员可以用 `POST` 注册新的 `packs/` manifest。

注册后可以调用 `POST /api/v1/scenario-packs/{pack_id}/evaluations`，或在本地执行：

```bash
python3 tools_evaluate_packs.py
```

评测至少检查 manifest 元数据、Skills、Knowledge Sources、Workflows、租户范围和业务写入审批策略。
