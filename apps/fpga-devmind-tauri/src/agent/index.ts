/* ------------------------------------------------------------------ */
/*  T042/T043: Agent Provider Boundary — entry point                  */
/* ------------------------------------------------------------------ */

export type {
  AgentProviderKind,
  ProviderCapabilities,
  AgentRunRequest,
  AgentRunResult,
  AgentRunTrace,
  AgentTraceStep,
  AgentProvider,
  AgentRunPolicyResult,
  AgentRunAuditEvent,
} from "./providers";

export {
  PROVIDER_CAPABILITIES,
  generateTraceId,
  collectArtifactsUsed,
} from "./providers";

export { deterministicProvider } from "./deterministicProvider";
export { offlineMockProvider } from "./offlineMockProvider";
export { externalDisabledProvider } from "./externalDisabledProvider";

// T043 policy + audit
export type {
  ProviderPolicyInput,
  ProviderPolicyResult,
} from "./policy";

export {
  PROVIDER_POLICY_VERSION,
  evaluateProviderPolicy,
  isExternalCallsAllowed,
  isProviderAllowed,
} from "./policy";

export type { ProviderRunAuditEvent } from "./audit";

export {
  buildProviderRunAuditEvent,
  buildQuestionPreview,
  appendAuditEvent,
  getAuditEvents,
  getRecentAuditEvents,
  getAuditStats,
  clearAuditLog,
} from "./audit";

// T043 config
export type { ProviderConfig } from "./config";

export {
  DEFAULT_PROVIDER_CONFIGS,
  FORBIDDEN_CONFIG_FIELDS,
  validateProviderConfig,
  containsSecretKeys,
} from "./config";

import type { AgentRunRequest, AgentRunResult, AgentProviderKind } from "./providers";
import { deterministicProvider } from "./deterministicProvider";
import { offlineMockProvider } from "./offlineMockProvider";
import { externalDisabledProvider } from "./externalDisabledProvider";
import { evaluateProviderPolicy } from "./policy";
import { buildProviderRunAuditEvent, appendAuditEvent } from "./audit";

/** Dispatch request to the appropriate provider with policy gating (T043) */
export function runAgent(request: AgentRunRequest): AgentRunResult {
  // T043: Evaluate policy BEFORE running any provider
  const policyResult = evaluateProviderPolicy({
    provider_kind: request.providerKind,
    question: request.question,
  });

  let result: AgentRunResult;

  if (!policyResult.allowed) {
    // Policy denied — route to externalDisabledProvider regardless of requested kind
    result = externalDisabledProvider.run(request);
  } else {
    switch (request.providerKind) {
      case "offline_mock":
        result = offlineMockProvider.run(request);
        break;
      case "external_disabled":
        // Should not reach here because policy denies external_disabled,
        // but handle defensively
        result = externalDisabledProvider.run(request);
        break;
      case "deterministic":
      default:
        result = deterministicProvider.run(request);
        break;
    }
  }

  // T043.1: Canonical policy_result comes from runAgent evaluation,
  // not from the provider's internal fallback.
  const canonicalResult: AgentRunResult = {
    ...result,
    policy_result: policyResult,
  };

  // T043: Build and record canonical audit event using the runAgent policy
  const auditEvent = buildProviderRunAuditEvent(
    canonicalResult,
    policyResult,
    request.question
  );

  const canonicalResultWithAudit: AgentRunResult = {
    ...canonicalResult,
    audit_event: auditEvent,
  };

  appendAuditEvent(auditEvent);

  return canonicalResultWithAudit;
}

/** Get a list of available provider kinds for UI selection */
export function getAvailableProviderKinds(): AgentProviderKind[] {
  return ["deterministic", "offline_mock", "external_disabled"];
}
