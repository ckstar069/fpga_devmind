# T047: Ephemeral Real Provider Adapter + Manual Send Gate

**Goal:** Add the first real external LLM provider capability with strict security: API keys are memory-only, never persisted; frontend does not call external APIs directly; all real network requests go through Tauri Rust backend commands; explicit manual user consent is required for every send.

**Architecture:** Three-layer defense: (1) TypeScript frontend manages UI state and ephemeral session metadata (fingerprint only), (2) `evaluateRealSendGate()` enforces 5 conditions before allowing any send, (3) Rust backend `invoke_openai_compatible_ephemeral` handles actual HTTP via `reqwest`, receives the raw key as a function parameter that never escapes in return values or logs.

**Security Model:**
- `EphemeralProviderSessionState`: `storage: "memory_only"`, `key_fingerprint` (irreversible first4...last4), `endpoint_origin_preview` (scheme+host only)
- `RealProviderInvocationRequest` (TS contract): NO `api_key` field
- `RealProviderInvocationResult`: `raw_response_stored: false`, `audit_redacted: true`
- `RealProviderAuditSummary`: in-memory log only, `raw_key_stored: false`, `raw_prompt_stored: false`, `raw_response_stored: false`
- `evaluateEgressGuard()` (T046): UNCHANGED — always returns `allowed: false`
- `evaluateRealSendGate()` (T047): SEPARATE function — returns `allowed: true` ONLY when all 5 conditions met

---

## Files Created

| File | Description |
|------|-------------|
| `apps/fpga-devmind-tauri/src/agent/ephemeralProviderSession.ts` | `EphemeralProviderSessionState`, `createEphemeralProviderSession()`, `buildKeyFingerprint()`, `buildEndpointOriginPreview()`, `clearEphemeralProviderSession()`, `touchEphemeralProviderSession()` |
| `apps/fpga-devmind-tauri/src/agent/realProviderContract.ts` | `RealProviderInvocationRequest`, `RealProviderInvocationResult`, `buildRealProviderInvocationRequest()`, `buildBlockedRealProviderResult()`, `buildNotConfiguredResult()` |
| `apps/fpga-devmind-tauri/src/agent/realProviderAudit.ts` | `RealProviderAuditSummary`, in-memory audit log (`_realProviderAuditLog`), `buildRealProviderAuditSummary()`, `appendRealProviderAudit()`, `getRealProviderAudits()`, `clearRealProviderAudits()` |
| `apps/fpga-devmind-tauri/src-tauri/src/provider_runtime.rs` | `OpenAiChatRequest` / `OpenAiChatResponse` structs, `validate_endpoint_url()`, `redact_error()`, `truncate_preview()`, `invoke_openai_compatible_ephemeral` Tauri command |
| `apps/fpga-devmind-tauri/src/__tests__/ephemeral-provider-session.test.ts` | 14 tests |
| `apps/fpga-devmind-tauri/src/__tests__/real-provider-contract.test.ts` | 11 tests |
| `apps/fpga-devmind-tauri/src/__tests__/real-provider-audit.test.ts` | 12 tests |

## Files Modified

| File | Changes |
|------|---------|
| `apps/fpga-devmind-tauri/src/agent/egressGuard.ts` | Added `RealSendGateInput`, `RealSendGateDecision`, `evaluateRealSendGate()` after existing `evaluateEgressGuard()` |
| `apps/fpga-devmind-tauri/src/agent/index.ts` | Added exports for T047 modules |
| `apps/fpga-devmind-tauri/src-tauri/src/lib.rs` | Added `mod provider_runtime;`, registered `provider_runtime::invoke_openai_compatible_ephemeral` in invoke_handler |
| `apps/fpga-devmind-tauri/src-tauri/Cargo.toml` | Added `reqwest = { version = "0.12", features = ["json"] }` and `chrono = { version = "0.4", features = ["serde"] }` |
| `apps/fpga-devmind-tauri/src/pages/AgentQA.tsx` | Added T047 panel: session config (endpoint, model, API key password input), fingerprint display, send gate status, explicit confirmation dialog, real send button, result display, safety banner |

## Ephemeral Session

```typescript
export interface EphemeralProviderSessionState {
  schema_version: "ephemeral-provider-session-0.1";
  configured: boolean;
  provider_id: "openai_compatible_ephemeral";
  model_name: string;
  key_present: boolean;
  key_fingerprint: string | null;     // "sk-a...wxyz" (first 4 + ... + last 4)
  endpoint_origin_preview: string;    // "https://api.openai.com"
  storage: "memory_only";
  created_at: string | null;
  last_used_at: string | null;
}
```

- `createEphemeralProviderSession({ api_key, endpoint_url, model_name })` computes fingerprint and origin preview; does NOT store raw key
- `JSON.stringify(session)` never contains raw key (verified by test)
- Session lives in React `useState` only — no localStorage, no disk write

## Real Send Gate

```typescript
export interface RealSendGateDecision {
  schema_version: "real-send-gate-0.1";
  allowed: boolean;
  reason: string;
  conditions_met: {
    session_configured: boolean;
    key_present: boolean;
    endpoint_https: boolean;
    approval_adequate: boolean;
    user_explicit_consent: boolean;
  };
}
```

`evaluateRealSendGate()` returns `allowed: true` ONLY when ALL 5 are true:
1. Session is configured
2. API key is present (in the separate memory-only state, not in the session object)
3. Endpoint URL uses `https://`
4. Approval state is `approved_but_blocked` or better
5. `send_allowed_by_user === true`

## Rust Backend Command

```rust
#[tauri::command]
pub async fn invoke_openai_compatible_ephemeral(
    endpoint_url: String,
    model_name: String,
    api_key: String,          // Received as parameter, NEVER returned
    system_prompt: String,
    user_prompt: String,
    request_id: String,
) -> Result<RealProviderInvocationResult, String>
```

- 60-second timeout via `tokio::time::timeout`
- `validate_endpoint_url()`: blocks `http://`, `file://`, `ftp://`, `localhost`, `127.0.0.1`, `::1`
- `redact_error()`: replaces key patterns with `***REDACTED***`
- `truncate_preview()`: max 4000 characters for response preview
- Returns `RealProviderInvocationResult` with `answer_text_preview` only — full response is NOT stored

## AgentQA UI Panel

The T047 panel in AgentQA includes:
- **Safety banner**: "⚠️ 真实网络请求 — 仅用于明确了解风险的用户"
- **Session config**: Endpoint URL input, Model name input, API key password input
- **Session status**: Provider, Model, Endpoint preview, Key fingerprint, Storage: memory_only
- **Real Send Gate**: Allowed/No + 5 condition checklist (✓/✗)
- **Confirmation dialog**: Explicit checkbox "我了解这将使用我的临时 API key 发起真实外部网络请求"
- **Result display**: Sent/Blocked, Status, Answer preview (truncated), Error preview (redacted)
- **Safety notes**: "API key 仅在内存中存在" / "Raw key 永远不会写入项目文件或审计日志"

## Verification

```bash
# TypeScript tests
cd apps/fpga-devmind-tauri
npm test -- --run
# → 272 tests passed (17 test files)

# Rust build + test
cd apps/fpga-devmind-tauri/src-tauri
cargo check   # → clean
cargo test    # → 12 passed

# Security scan
rg -i "sk-[a-z0-9]{20,}" --type ts --type tsx --type js --type py --type rs
# → no results (no hardcoded keys)

# Production build
cd apps/fpga-devmind-tauri
npm run build
# → success (tsc + vite build clean)
```

## T047.1 Security Hardening (PR #4 patch)

### Rust Backend
- **`build_provider_error_preview()`**: Non-2xx responses no longer return raw provider body. Error preview is redacted then truncated to 500 chars max.
- **Enhanced `redact_error()`**: Covers sk-/sk_live_/sk_test_/ghp_/github_pat_/xoxb-/Bearer/Authorization/api_key=/apiKey=/token=/password=/JWT eyJ... patterns. Falls back to blanket redaction if any suspicious pattern remains.
- **Char-safe `truncate_chars()`**: Uses Unicode char iteration instead of byte slicing — safe for Chinese text and emoji. Max 4000 chars for answer preview, 1000 chars for error preview.
- **Backend pre-flight gate `validate_backend_gate()`**: Receives `provider_id`, `approval_state`, `send_allowed_by_user` as Tauri command params. Blocks before network if: provider_id != "openai_compatible_ephemeral", approval_state != "approved_but_blocked", send_allowed_by_user == false, or api_key is empty.
- **Endpoint hardening**: `validate_endpoint_url()` uses `url::Url` parsing. Rejects private IPv4 (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8, 0.0.0.0), localhost, ::1. Rejects query params containing api_key/key/token/password/secret.
- **`blocked_before_network()`**: Unified helper for gate/endpoint failures — returns safe result with redacted error, never calls reqwest.

### TypeScript Frontend
- **`provider_allowed` condition**: `evaluateRealSendGate()` now has 6 conditions (was 5). `provider_id` must be exactly `"openai_compatible_ephemeral"`.
- **UI consent fix**: `evaluateT047SendGate(session, sendAllowedByUser)` — session config and panel open pass `false`. Only the "确认发送一次" button handler passes `true` after confirmation dialog. The consent condition shows ✗ until user explicitly confirms.
- **`redactUiErrorPreview()`**: Frontend catch block uses this instead of `String(err)`. Covers sk-/ghp_/xoxb-/Bearer/Authorization/api_key=/apiKey=/token=/password= with 1000-char cap.

### Verification (T047.1)

```bash
# TypeScript tests
cd apps/fpga-devmind-tauri
npm test -- --run
# → 289 tests passed (17 test files)

# Rust tests
cd src-tauri
cargo test
# → 47 tests passed (12 artifact_loader + 35 provider_runtime)

cargo check
# → clean

npm run build
# → clean (tsc + vite)
```

## Limitations

- T047 only supports single-shot send (non-streaming).
- Default transport remains mock/blocked — real send requires explicit user configuration + confirmation.
- No key persistence across app restarts (by design).
- No retry logic or backoff.
- Only OpenAI-compatible `/v1/chat/completions` contract.
- No provider response caching.

## Next Steps

- Wait for Web GPT review before proceeding to T048.
- Do NOT merge T048 or any subsequent tasks until review is complete.