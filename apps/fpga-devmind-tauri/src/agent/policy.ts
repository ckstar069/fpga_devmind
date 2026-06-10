/* ------------------------------------------------------------------ */
/*  T043: Provider Policy — Safety Gate                               */
/*  Runtime policy evaluation before any provider can execute         */
/* ------------------------------------------------------------------ */

import type { AgentProviderKind } from "./providers";

export const PROVIDER_POLICY_VERSION = "t043.0";

/** Input to the policy evaluator */
export interface ProviderPolicyInput {
  provider_kind: AgentProviderKind;
  question: string;
}

/** Result of policy evaluation — gates all provider runs */
export interface ProviderPolicyResult {
  allowed: boolean;
  provider_kind: AgentProviderKind;
  reason: string;
  network_allowed: boolean;
  requires_api_key: boolean;
  external_calls_allowed: boolean;
  secret_storage_allowed: boolean;
  policy_version: string;
  limitations: string[];
}

/** Evaluate whether a provider run is allowed by current policy.
 *
 * Rules (T043):
 * - deterministic: allowed=true, external_calls_allowed=false
 * - offline_mock: allowed=true, external_calls_allowed=false
 * - external_disabled: allowed=false, external_calls_allowed=false
 * - unknown: allowed=false
 *
 * All providers: network_allowed=false, secret_storage_allowed=false.
 */
export function evaluateProviderPolicy(
  input: ProviderPolicyInput
): ProviderPolicyResult {
  const kind = input.provider_kind;

  switch (kind) {
    case "deterministic":
      return {
        allowed: true,
        provider_kind: kind,
        reason: "确定性 provider 基于本地规则匹配，不调用外部 API，允许运行",
        network_allowed: false,
        requires_api_key: false,
        external_calls_allowed: false,
        secret_storage_allowed: false,
        policy_version: PROVIDER_POLICY_VERSION,
        limitations: [
          "确定性 provider 仅执行预定义规则匹配，不提供语义推理",
          "回答质量取决于本地 artifacts 的完整性和准确性",
        ],
      };

    case "offline_mock":
      return {
        allowed: true,
        provider_kind: kind,
        reason: "Offline Mock provider 仅读取本地 artifacts，不调用外部 API，允许运行",
        network_allowed: false,
        requires_api_key: false,
        external_calls_allowed: false,
        secret_storage_allowed: false,
        policy_version: PROVIDER_POLICY_VERSION,
        limitations: [
          "Offline Mock 回答由预定义模板和本地数据拼接生成，不执行语义推理",
          "用于验证 provider 生命周期，不替代真实 Agent 推理",
        ],
      };

    case "external_disabled":
      return {
        allowed: false,
        provider_kind: kind,
        reason: "外部 provider 在 T043 中被安全策略禁用，等待后续安全评估后启用",
        network_allowed: false,
        requires_api_key: true,
        external_calls_allowed: false,
        secret_storage_allowed: false,
        policy_version: PROVIDER_POLICY_VERSION,
        limitations: [
          "外部 LLM provider 未通过安全门禁评估",
          "需要完成 API key 安全策略、调用审计、风险审查后方可启用",
          "当前版本禁止存储、读取或使用任何 API key",
        ],
      };

    default:
      // Unknown provider — treat as denied
      return {
        allowed: false,
        provider_kind: kind,
        reason: `未知 provider "${kind}" 未在策略白名单中，拒绝运行`,
        network_allowed: false,
        requires_api_key: false,
        external_calls_allowed: false,
        secret_storage_allowed: false,
        policy_version: PROVIDER_POLICY_VERSION,
        limitations: [
          "未知 provider 类型不被信任",
          "如需使用，请先将其加入 provider policy 白名单",
        ],
      };
  }
}

/** Quick helper: is this provider allowed to make external calls? */
export function isExternalCallsAllowed(kind: AgentProviderKind): boolean {
  return evaluateProviderPolicy({ provider_kind: kind, question: "" })
    .external_calls_allowed;
}

/** Quick helper: is this provider allowed at all? */
export function isProviderAllowed(kind: AgentProviderKind): boolean {
  return evaluateProviderPolicy({ provider_kind: kind, question: "" }).allowed;
}
