# T044: LLM Context Builder + Dry-run External Request Plan

## Goal

建立一个离线的上下文组装层，回答："如果未来允许接入外部 provider，它会收到什么有界上下文？"

该层必须：
- 仅从本地 bundle artifacts 构建 Source Evidence Pack
- 组装 LLM Context Bundle（ capped items ≤20，truncated previews ≤500 chars，rough token estimates）
- 生成 Dry-run External Request Plan —— 被策略明确阻止（external_disabled）
- 在 AgentQA 中展示上下文预览，不发送任何网络请求
- 维持所有 T043 安全保证（无 API key、无网络、无 secret）

## Completed Work

### 1. Source Evidence Pack (`src/agent/sourcePack.ts`)

- `SourceEvidenceItem` — kind: concept | edge | node | limitation
- `SourceEvidencePack` — 包含 matched_concepts、matched_edges、items、evidence_ids、source_files、artifacts_used、limitations
- `buildSourceEvidencePack(bundle, question, selectedNodeId)`:
  1. 优先匹配 `agent_navigation_index.concept_routes`（关键词或 selectedNodeId）
  2. 匹配 `edge_routes`（selectedNodeId 关联）
  3. `semantic_pipeline_view.cross_stage_edges`（selectedNodeId 关联）
  4. Graph node fallback（关键词匹配）
- `buildQuestionPreview()` 自动脱敏（T043.1）

### 2. LLM Context Builder (`src/agent/contextBuilder.ts`)

- `LlmContextItem` — kind: semantic_summary | pipeline_edge | concept_route | quality_status | limitation | node_fallback | discovery_eval
- `LlmContextBundle` — 包含 context_items、artifacts_used、evidence_ids、source_files、limitations、token_estimate_rough
- `buildLlmContext(bundle, question, selectedNodeId)`:
  1. Semantic summary（project purpose + core concepts + pipeline stages）
  2. Source evidence pack items（最多 12 条）
  3. Pipeline view edges（最多 5 条）+ pipeline summary
  4. Navigation index quality status
  5. Discovery eval result（如有）
  6. Cap items to `MAX_CONTEXT_ITEMS = 20`
- Token estimate: `Math.ceil(totalTextLength / 4)`
- Content preview truncation: `MAX_CONTENT_PREVIEW = 500`

### 3. Dry-run Request Plan (`src/agent/requestPlan.ts`)

- `ExternalRequestPlan` — 显式字段：
  - `dry_run: true`
  - `policy_allowed: false`
  - `blocked_reason: "外部 provider 被 T043 安全策略禁用..."`
  - `provider_kind: "external_disabled"`
  - `hypothetical_request_preview` — model_name、purpose、message_count_estimate、total_tokens_estimate、system_prompt_preview、user_prompt_preview、context_items_summary
- `buildDryRunExternalRequestPlan(bundle, question, selectedNodeId)`:
  - 调用 `evaluateProviderPolicy({ provider_kind: "external_disabled", question })`
  - 调用 `buildLlmContext(bundle, question, selectedNodeId)`
  - 构建 hypothetical system/user prompt 预览
  - **不包含 api_key / endpoint / headers / base_url 字段**

### 4. AgentQA Dry-run Preview UI (`src/pages/AgentQA.tsx`)

- 每个回答卡片增加「上下文预览 (Dry-run)」按钮
- 展开后展示：
  - 策略阻止原因（红色警告）
  - 预估 Token 数
  - 使用 Artifacts 列表
  - 上下文项摘要（kind + title + chars）
  - System Prompt 预览（pre 块）
  - User Prompt 预览（pre 块）
  - 局限说明

### 5. 测试 (`src/__tests__/context-builder.test.ts` + `src/__tests__/request-plan.test.ts`)

**context-builder.test.ts (17 tests):**
- null bundle → 空 pack / 空 context
- 关键词匹配 concept routes
- selectedNodeId 匹配
- artifacts_used / evidence_ids / source_files 存在
- 敏感内容 question_preview 脱敏
- 包含 semantic summary、pipeline edges、quality status
- items 上限 20、preview 上限 500、token estimate ≥0

**request-plan.test.ts (18 tests):**
- schema_version 匹配常量
- dry_run=true、policy_allowed=false
- provider_kind=external_disabled
- blocked_reason 包含"禁用"
- context_bundle 有 items
- hypothetical_request_preview 各字段存在
- context_items_summary 数量匹配
- token_estimate 匹配
- 敏感内容 question_preview 脱敏
- null bundle 可工作
- selected_node_id 保留
- limitations 包含 dry-run 和策略说明
- **无 api_key/endpoint/headers/base_url 字段**

**总计: 150 tests passed** (was 115, +35 new tests)

### 6. 文档

- `docs/implementation-status.md` — 更新 T044 状态
- `docs/tasks/T044-llm-context-builder-dry-run.md` — 本文件

## Verification

```bash
cd apps/fpga-devmind-tauri
npm test -- --run   # 150 passed
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

- ✅ 外部 provider 仍然 disabled（policy_allowed=false, dry_run=true）
- ✅ 不保存 API key
- ✅ 不读取环境变量中的 key
- ✅ 不发起网络请求
- ✅ 所有 provider external_calls_made=false
- ✅ Policy 先于执行（T043）
- ✅ 每次 run 生成 audit event（T043）
- ✅ Audit question redaction 防止敏感内容泄漏（T043.1）
- ✅ Context builder 仅从本地 bundle 读取，不访问文件系统
- ✅ Context items capped ≤20，previews truncated ≤500 chars
- ✅ Token estimate rough（char count / 4），仅供开发者参考
- ✅ Dry-run preview 不触发任何外部调用
