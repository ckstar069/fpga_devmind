# Provider Safety Policy (T043)

> **Status:** Active  
> **Version:** t043.0  
> **Applies to:** All agent provider runs

## Policy Goal

Before any external LLM provider can be integrated, a safety gate must be in place that:

1. Explicitly controls which providers are allowed to run.
2. Prevents accidental external network calls.
3. Prevents secret (API key) storage in any persistent or in-memory config.
4. Records an audit trail of every provider run.

## Provider Kinds

| Kind | Enabled | Network | API Key | External Calls | Policy Decision |
|------|---------|---------|---------|----------------|-----------------|
| `deterministic` | ✅ true | ❌ false | ❌ false | ❌ false | ✅ Allowed |
| `offline_mock` | ✅ true | ❌ false | ❌ false | ❌ false | ✅ Allowed |
| `external_disabled` | ❌ false | ❌ false | ✅ true (required but not used) | ❌ false | ❌ Denied |
| Unknown | — | ❌ false | ❌ false | ❌ false | ❌ Denied |

## Rules

### R1: External Provider Disabled

The `external_disabled` provider is **intentionally disabled** in T043. It will be denied by policy evaluation regardless of any other settings. Enabling it requires:

- Completion of API key security strategy (T044+).
- Call audit and risk review.
- Explicit opt-in via policy version bump.

### R2: No Network Calls

All providers must have `network_allowed = false`. No provider may initiate HTTP, WebSocket, or any other network request.

### R3: No Secret Storage

The following fields are **forbidden** in any provider config:

- `api_key` / `apiKey`
- `secret`
- `token`
- `bearer`
- `password`
- `endpoint`
- `base_url`
- `headers`

Config validation rejects any object containing these fields. No localStorage, no env-var reading, no file-based secret storage.

### R4: Audit Every Run

Every `runAgent()` invocation produces an audit event with:

- `event_id` — unique identifier
- `timestamp` — ISO 8601
- `provider_kind`
- `question_preview` — max 80 chars (not full input)
- `policy_allowed` — true/false
- `policy_reason` — human-readable decision rationale
- `external_calls_made` — always false in T043
- `network_allowed` — always false in T043
- `artifacts_used` — list of artifact names
- `trace_id` — links to run trace
- `limitations` — combined provider + policy limitations
- `policy_version` — e.g. "t043.0"

Audit events are kept in-memory only (session scope). They are not written to disk.

### R5: Policy Precedes Execution

`runAgent()` evaluates policy **before** dispatching to any provider. If policy denies:

- The request is routed to `externalDisabledProvider`.
- An audit event is still recorded with `policy_allowed = false`.
- No provider code from the requested kind is executed.

## Before T044

Before any real external provider can be enabled:

1. Policy version must be bumped beyond "t043.0".
2. A secure API key storage strategy must be designed and reviewed.
3. Network call audit must be implemented.
4. Risk assessment document must be approved.
5. The `external_disabled` provider must be renamed/replaced with a real provider adapter.

## Verification Commands

```bash
cd apps/fpga-devmind-tauri
npm test -- --run
npm run build
```

```bash
cd apps/fpga-devmind-tauri/src-tauri
cargo check
```

```bash
rg -n "api_key|apiKey|secret|token|bearer|password|endpoint|base_url|headers|fetch\(|WebSocket|EventSource|axios|https://" \
  apps/fpga-devmind-tauri/src/agent/
```

Expected: zero matches in `src/agent/` (the provider boundary layer).

## T043.1 Hardening

### R6: Audit Question Redaction

`buildQuestionPreview()` scans for sensitive keywords and token patterns before truncation. If detected, it returns `[redacted sensitive-looking question]` instead of any raw text.

Detected patterns:
- Keywords: `api_key`, `apiKey`, `secret`, `token`, `bearer`, `password`, `auth`
- Token prefixes: `sk-` (OpenAI), `xoxb-` (Slack), `ghp_` (GitHub PAT), `github_pat_` (GitHub fine-grained), `eyJ` (JWT)

### R7: Canonical Policy & Audit Event

Only `runAgent()` produces the canonical `policy_result` and `audit_event`. Provider implementations (`.run()`) may contain fallback values, but `runAgent()` overwrites them with the policy evaluation result before returning to the caller.

This ensures:
- Unknown provider requests retain the original provider kind in `policy_result.provider_kind` while the response still comes from `externalDisabledProvider`.
- The audit log always reflects the policy decision made at the dispatcher level, not any internal provider state.

### R8: No Global Audit Side Effects from Provider Direct Calls

Calling `deterministicProvider.run()`, `offlineMockProvider.run()`, or `externalDisabledProvider.run()` directly does **not** append to the global audit log. Only `runAgent()` appends audit events.

## Verification Commands (T043.1)

```bash
cd apps/fpga-devmind-tauri
npm test -- --run   # 115 passed
npm run build       # pass
```

```bash
cd apps/fpga-devmind-tauri/src-tauri
cargo check         # pass
```

```bash
rg -n "api_key|apiKey|secret|token|bearer|password|endpoint|base_url|headers|fetch\(|WebSocket|EventSource|axios|https://" \
  apps/fpga-devmind-tauri/src/agent/
# Expected: no matches in src/agent/
```
