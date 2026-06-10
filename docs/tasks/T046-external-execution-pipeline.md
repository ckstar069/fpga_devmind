# T046: External Provider Execution Pipeline with Blocked/Mock Transport

## Goal

在 T045 approval-gated request package 基础上，建立 "外部 provider 执行管线" 的完整工程骨架：

- Provider registry（所有 provider 均为 blocked/mock/future）
- Egress guard（最终网络发送门禁）
- Transport abstraction（blocked + mock）
- Execution pipeline（端到端管线）
- AgentQA UI 执行预览

本阶段仍然禁止真实外部 API 调用、禁止 API key 存储、禁止网络发送。

## Non-Goals

- 不接入真实外部 LLM provider。
- 不新增 `fetch()` / `axios` / `WebSocket` / `EventSource` 外部调用。
- 不新增 `https://api...` endpoint。
- 不读取、记录、输出 API key。
- 不新增 API key 输入框或 secret 持久化。
- 不实现真实 OpenAI/Anthropic/DeepSeek/Kimi/Gemini/GLM adapter。

## Completed Work

### 1. Provider Registry (`src/agent/externalProviderRegistry.ts`)

- `ExternalProviderId`: 7 个 provider ID
  - `external_disabled` (blocked)
  - `mock_external_llm` (mock_only)
  - `future_openai`, `future_anthropic`, `future_deepseek`, `future_gemini`, `future_glm` (future)
- `ExternalProviderDescriptor`: `send_allowed=false`, `network_allowed=false`, `secret_storage_allowed=false`
- `getExternalProviderDescriptors()`: 返回所有 descriptor
- `getExternalProviderDescriptor(id)`: 按 ID 查询
- `isExternalProviderSendAllowed()`: 永远返回 false
- `getSelectableExternalProviderIds()`: UI 可选列表（mock + future placeholders）

### 2. Egress Guard (`src/agent/egressGuard.ts`)

- `EgressGuardDecision`: `allowed=false`, `network_allowed=false`, `external_calls_allowed=false`
- `evaluateEgressGuard(input)`: 最终网络发送门禁
  - `approved_but_blocked` → "approved by user but blocked before network in T046"
  - `future provider` → "future provider placeholder only"
  - 任何状态 → blocked
  - 即使 `send_allowed=true` 伪造输入也 blocked

### 3. Transport Abstraction (`src/agent/externalTransport.ts`)

- `ExternalTransportKind`: `"blocked" | "mock"`
- `ExternalTransportRequest`: request_id, provider_id, request_package, approval_decision
- `ExternalTransportResponse`: sent=false, blocked=true, mock_response, answer_preview, egress_guard
- `executeBlockedTransport()`: 永远 blocked，无 mock answer
- `executeMockTransport()`: 生成 deterministic mock answer，但仍 blocked
- 两者都调用 `evaluateEgressGuard()`

### 4. Execution Pipeline (`src/agent/externalExecution.ts`)

- `ExternalExecutionResult`: 完整执行结果（send_allowed=false, sent=false, blocked=true）
- `executeExternalProviderPipeline(input)`: 端到端管线
  1. `buildExternalRequestPackage()`
  2. 根据 `approval_action` 调用 approval gate
  3. 调用 transport（blocked 或 mock）
  4. 返回 `ExternalExecutionResult`
- `approval_action`: `"preview_only" | "simulate_approve" | "deny"`
- 所有路径：send_allowed=false, sent=false, blocked=true

### 5. AgentQA T046 Execution Panel (`src/pages/AgentQA.tsx`)

- 新增「T046 执行管线」按钮
- 展开后显示：
  - Provider registry 选择器（mock_external_llm, future_openai, future_anthropic, future_deepseek）
  - Transport kind 选择器（blocked / mock）
  - Execution result（sent, blocked, mock_response, send_allowed, approval_state）
  - Egress guard reason
  - Mock answer preview（mock transport 时）
  - Artifacts / evidence / limitations
- 操作按钮：Preview only, Simulate approval + transport, Deny
- 安全提示：
  - `⚠️ No real network call is available in T046`
  - `Mock transport is deterministic and offline only`

### 6. 测试

**external-provider-registry.test.ts (13 tests):**
- registry version 正确
- 包含所有 7 个 provider
- 所有 provider `send_allowed=false`
- 所有 provider `network_allowed=false`
- 所有 provider `secret_storage_allowed=false`
- mock_external_llm status=mock_only
- future providers status=future
- 不包含真实 endpoint/api URL
- 不包含 secret 值

**egress-guard.test.ts (10 tests):**
- 永远 `allowed=false`
- `approved_but_blocked` 仍 blocked
- `previewed` 仍 blocked
- `denied` 仍 blocked
- `future provider` 仍 blocked
- 伪造 `send_allowed=true` 仍 blocked
- decision 包含 request_id/provider_id/checked_at
- JSON serialization 不含敏感内容

**external-execution.test.ts (19 tests):**
- preview_only → blocked=true, sent=false
- simulate_approve + blocked → approved_but_blocked, sent=false
- simulate_approve + mock → mock_response=true, sent=false
- deny → denied, sent=false
- 所有路径 send_allowed=false
- 所有路径 egress_guard.allowed=false
- JSON 不包含 raw sensitive question
- JSON 不包含 secret 值
- null bundle 可执行，limitations 包含 "No bundle loaded"
- artifacts_used / evidence_ids 从 request package 传递
- 不存在 sent=true 的路径
- 不存在 blocked=false 的路径
- future provider 可执行但 blocked
- transport response 包含在 result 中
- limitations 包含 T046 和 no network 说明

**总计: 235 TypeScript tests passed** (was 193, +42 new tests)

### 7. 文档

- `docs/implementation-status.md` — 更新 T046 状态
- `docs/tasks/T046-external-execution-pipeline.md` — 本文件

## Verification

```bash
cd apps/fpga-devmind-tauri
npm test -- --run   # 235 passed
npm run build       # pass

cd src-tauri
cargo check         # pass
```

```bash
pytest -q           # 786 passed, 5 skipped
```

```bash
# T046 文件外部调用扫描
rg -n "fetch\(|WebSocket|EventSource|axios|https://" \
  apps/fpga-devmind-tauri/src/agent/externalProviderRegistry.ts \
  apps/fpga-devmind-tauri/src/agent/egressGuard.ts \
  apps/fpga-devmind-tauri/src/agent/externalTransport.ts \
  apps/fpga-devmind-tauri/src/agent/externalExecution.ts \
  apps/fpga-devmind-tauri/src/pages/AgentQA.tsx
# Expected: no matches (only test assertions contain "https://" as negative checks)
```

## Constraints Met

- ✅ 外部 provider 仍然 disabled（所有 send_allowed=false）
- ✅ 不保存 API key
- ✅ 不读取环境变量中的 key
- ✅ 不发起网络请求
- ✅ 所有 transport sent=false, blocked=true
- ✅ Egress guard 永远 allowed=false
- ✅ 即使 approved 也只能进入 approved_but_blocked
- ✅ `JSON.stringify(result)` 不含敏感原文
- ✅ 真实 provider adapter 仍是未来任务，不属于 T046
- ✅ No new fetch/axios/WebSocket/EventSource calls in T046 files
