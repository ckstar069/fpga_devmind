# T043: Provider Safety Gate + Config Policy + Audit Log

## Goal

在 T042 provider boundary 之上建立安全门禁，确保外部 LLM provider 在被充分评估前无法启用。

## Completed Work

### 1. Provider Policy (`src/agent/policy.ts`)

- `evaluateProviderPolicy(input)` — 运行前策略评估
- `ProviderPolicyResult` — 包含 allowed / reason / network_allowed / external_calls_allowed / secret_storage_allowed
- deterministic: allowed=true
- offline_mock: allowed=true
- external_disabled: allowed=false
- unknown: allowed=false
- 所有 provider: network_allowed=false, secret_storage_allowed=false

### 2. Provider Config (`src/agent/config.ts`)

- `ProviderConfig` — 仅允许非敏感字段
- `DEFAULT_PROVIDER_CONFIGS` — 内存静态配置，无持久化
- `validateProviderConfig(config)` — 拒绝 api_key / token / secret / endpoint / base_url / headers
- `containsSecretKeys(obj)` — 递归检测嵌套 secret
- 禁止 allow_network=true 和 allow_external_calls=true

### 3. Provider Audit (`src/agent/audit.ts`)

- `ProviderRunAuditEvent` — 每次 run 的审计事件
- `buildProviderRunAuditEvent(runResult, policyResult, question)` — 构建审计事件
- `buildQuestionPreview(question)` — 最多 80 字符预览
- 内存审计日志：`appendAuditEvent` / `getAuditEvents` / `getRecentAuditEvents` / `getAuditStats` / `clearAuditLog`
- 不记录 API key，不写入磁盘

### 4. runAgent 集成 (`src/agent/index.ts`)

- `runAgent()` 在分发 provider 前先调用 `evaluateProviderPolicy()`
- Policy denied → 路由到 externalDisabledProvider
- 每次 run 后构建并记录 audit event
- Unknown provider 被 policy 拒绝，不会执行任何 provider 代码

### 5. providers.ts 类型扩展

- `AgentRunResult` 新增 `policy_result: AgentRunPolicyResult` 和 `audit_event: AgentRunAuditEvent`
- 三个 provider 在返回时填充 policy_result 和 audit_event

### 6. AgentQA 展示 (`src/pages/AgentQA.tsx`)

- Provider 选择区域展示 policy 状态（允许/拒绝、联网、外部调用、secret 存储）
- 回答卡片展示 policy decision badge 和 audit event 摘要（event_id、question_preview、policy_reason）
- Trace 面板展示 policy version

### 7. 测试 (`src/__tests__/`)

- `provider-policy.test.ts` — 9 tests：allowed/denied、network=false、secret_storage=false、isExternalCallsAllowed、isProviderAllowed
- `provider-config.test.ts` — 17 tests：无 secret 字段、reject api_key/token/endpoint/headers/base_url/secret、reject enabled external_disabled、reject allow_network/allow_external_calls、containsSecretKeys
- `provider-audit.test.ts` — 10 tests：event_id、question_preview 截断、denied provider audit、无 api key 字样、内存日志累积、recent events、stats、clear
- `providers.test.ts` — 15 tests：全部通过（含 unknown provider policy denied 断言更新）

**总计: 104 tests passed**

### 8. 文档

- `docs/provider-safety-policy.md` — 安全策略文档
- `docs/implementation-status.md` — 更新 T043 状态
- `docs/tasks/T043-provider-safety-gate.md` — 本文件

## Verification

```bash
cd apps/fpga-devmind-tauri
npm test -- --run   # 104 passed
npm run build       # pass

cd src-tauri
cargo check         # pass
```

```bash
rg -n "api_key|apiKey|secret|token|bearer|password|endpoint|base_url|headers|fetch\(|WebSocket|EventSource|axios|https://" \
  apps/fpga-devmind-tauri/src/agent/
# Expected: no matches
```

## Constraints Met

- ✅ 外部 provider 仍然 disabled
- ✅ 不保存 API key
- ✅ 不读取环境变量中的 key
- ✅ 不发起网络请求
- ✅ 所有 provider external_calls_made=false
- ✅ Policy 先于执行
- ✅ 每次 run 生成 audit event
