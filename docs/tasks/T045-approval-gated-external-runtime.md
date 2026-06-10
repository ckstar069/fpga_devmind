# T045: Approval-Gated External Provider Runtime Shell

## Goal

在 T042/T043/T044 基础上，建立 "将来可接外部 LLM provider" 的运行时外壳、审批门、请求包结构、UI 预览和审计链路。

本阶段仍然禁止真实外部 API 调用、禁止 API key 存储、禁止网络发送。

## Non-Goals

- 不接入真实外部 LLM provider。
- 不新增 `fetch()` / `axios` / `WebSocket` / `EventSource` 外部调用。
- 不新增 `https://api...` endpoint。
- 不读取、记录、输出 API key。
- 不新增 API key 输入框或 secret 持久化。

## Completed Work

### 1. External Request Package (`src/agent/externalRequestPackage.ts`)

- `ExternalRequestPackage` — 标准化请求包结构：
  - `dry_run: true`
  - `send_allowed: false`
  - `approval_required: true`
  - `approval_state: "not_requested"`
  - `provider_kind: "external_disabled"`
  - `request_id`, `created_at`, `policy_version`
- `request_body_preview` — messages preview (system + user), context item count, token estimate
- `risk_summary` — 显式安全字段：
  - `contains_sensitive_question: boolean`
  - `raw_question_included: false`
  - `api_key_required: false`
  - `network_call_planned: false`
  - `secret_storage_planned: false`
  - `external_call_blocked_by_policy: true`
- `buildExternalRequestPackage(bundle, question, selectedNodeId)`:
  - 复用 `buildDryRunExternalRequestPlan()`
  - `question_preview` 始终来自 redacted preview
  - `JSON.stringify(package)` 不包含 raw sensitive question

### 2. Approval Gate State Machine (`src/agent/approvalGate.ts`)

- `ApprovalState`: `not_requested` | `previewed` | `approved_but_blocked` | `denied`
- `ApprovalDecision` — `send_allowed: false`, `state`, `reason`, `decided_at`
- `createPreviewDecision()` → `previewed`, `send_allowed=false`
- `approveExternalRequest()` → `approved_but_blocked`, `send_allowed=false`
- `denyExternalRequest()` → `denied`, `send_allowed=false`
- **没有任何状态允许真实发送。**

### 3. AgentQA T045 Preview UI (`src/pages/AgentQA.tsx`)

- 新增「T045 请求包预览」按钮
- 展开后显示：
  - Request ID / State / Send Allowed / Provider / Policy version / Tokens / Items
  - Risk Summary（敏感检测、raw question、API key、network、secret storage、policy block）
  - Artifacts used
  - Messages preview（system + user，pre 块）
  - Limitations
  - Approval Decision 状态
  - 操作按钮：
    - 「Simulate Manual Approval」→ 显示 `approved_but_blocked`
    - 「Deny」→ 显示 `denied`
- 红色警告：`Network send remains blocked in T045`

### 4. Policy / Config 保持现有约束

- `policy.ts`: `external_disabled` 仍 `allowed=false`, `network_allowed=false`, `external_calls_allowed=false`, `secret_storage_allowed=false`
- `config.ts`: 仍禁止 `api_key/token/secret/endpoint/base_url/headers`, `allow_network=false`, `allow_external_calls=false`
- `audit.ts`: 仍只存 `question_preview`，不存 raw question，不写磁盘

### 5. 测试

**external-request-package.test.ts (26 tests):**
- schema_version、dry_run=true、send_allowed=false、approval_required=true
- approval_state 初始为 not_requested
- provider_kind=external_disabled
- request_id、created_at、policy_version
- context_bundle、request_plan、request_body_preview
- risk_summary 默认值全部正确
- 敏感/非敏感 question 检测
- user message preview 包含 redacted marker
- `JSON.stringify(package)` 不包含 raw sensitive question（多模式覆盖）
- null bundle、selected_node_id、artifacts_used、limitations

**approval-gate.test.ts (10 tests):**
- preview → previewed, send_allowed=false
- approve → approved_but_blocked, send_allowed=false
- deny → denied, send_allowed=false
- deny 接受自定义 reason
- 所有 decision send_allowed=false
- approve 不改变 package.send_allowed
- 不存在 sent/sending/allowed 状态
- request_id 一致性
- policy_version 存在
- JSON serialization 不含 raw sensitive question

**总计: 193 tests passed** (was 157, +36 new tests)

### 6. 文档

- `docs/implementation-status.md` — 更新 T045 状态
- `docs/tasks/T045-approval-gated-external-runtime.md` — 本文件

## Verification

```bash
cd apps/fpga-devmind-tauri
npm test -- --run   # 193 passed
npm run build       # pass

cd src-tauri
cargo check         # pass
```

```bash
rg -n "api_key|apiKey|secret|token|bearer|password|endpoint|base_url|headers|fetch\(|WebSocket|EventSource|axios|https://" \
  apps/fpga-devmind-tauri/src/agent/
# Expected: no matches (T045 verified)
```

## Constraints Met

- ✅ 外部 provider 仍然 disabled（send_allowed=false, policy_allowed=false）
- ✅ 不保存 API key
- ✅ 不读取环境变量中的 key
- ✅ 不发起网络请求
- ✅ 所有 provider external_calls_made=false
- ✅ Policy 先于执行（T043）
- ✅ 每次 run 生成 audit event（T043）
- ✅ Audit question redaction 防止敏感内容泄漏（T043.1）
- ✅ Context builder 仅从本地 bundle 读取（T044）
- ✅ Request package 使用 redacted preview  only（T045）
- ✅ Approval gate 所有状态 send_allowed=false（T045）
- ✅ 即使 approved 也只能进入 approved_but_blocked（T045）
- ✅ `JSON.stringify(package)` 和 `JSON.stringify(decision)` 不含敏感原文（T045）
- ✅ Dry-run preview 不触发任何外部调用（T044/T045）
