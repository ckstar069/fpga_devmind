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

// T044: Context Builder + Source Evidence Pack + Dry-run Request Plan
export type { SourceEvidencePack, SourceEvidenceItem } from "./sourcePack";
export { buildSourceEvidencePack, SOURCE_EVIDENCE_PACK_VERSION } from "./sourcePack";

export type { LlmContextBundle, LlmContextItem } from "./contextBuilder";
export { buildLlmContext, LLM_CONTEXT_VERSION } from "./contextBuilder";

export type { ExternalRequestPlan } from "./requestPlan";
export { buildDryRunExternalRequestPlan, REQUEST_PLAN_VERSION } from "./requestPlan";

// T045: External Request Package + Approval Gate
export type { ExternalRequestPackage } from "./externalRequestPackage";
export { buildExternalRequestPackage, EXTERNAL_REQUEST_PACKAGE_VERSION } from "./externalRequestPackage";

export type { ApprovalState, ApprovalDecision } from "./approvalGate";
export {
  APPROVAL_GATE_VERSION,
  createPreviewDecision,
  approveExternalRequest,
  denyExternalRequest,
} from "./approvalGate";

// T046: External Provider Execution Pipeline
export type {
  ExternalProviderId,
  ExternalProviderDescriptor,
} from "./externalProviderRegistry";
export {
  EXTERNAL_PROVIDER_REGISTRY_VERSION,
  getExternalProviderDescriptors,
  getExternalProviderDescriptor,
  isExternalProviderSendAllowed,
  getSelectableExternalProviderIds,
} from "./externalProviderRegistry";

export type { EgressGuardInput, EgressGuardDecision } from "./egressGuard";
export { EGRESS_GUARD_VERSION, evaluateEgressGuard } from "./egressGuard";

export type {
  ExternalTransportKind,
  ExternalTransportRequest,
  ExternalTransportResponse,
} from "./externalTransport";
export {
  EXTERNAL_TRANSPORT_VERSION,
  executeBlockedTransport,
  executeMockTransport,
} from "./externalTransport";

export type {
  ExternalExecutionInput,
  ExternalExecutionResult,
  ExternalApprovalAction,
} from "./externalExecution";
export {
  EXTERNAL_EXECUTION_VERSION,
  executeExternalProviderPipeline,
} from "./externalExecution";

// T047: Ephemeral Real Provider Adapter
export type {
  EphemeralProviderSessionState,
  EphemeralProviderSessionInput,
  RuntimeProviderId,
} from "./ephemeralProviderSession";
export {
  EPHEMERAL_PROVIDER_SESSION_VERSION,
  createEmptyEphemeralProviderSession,
  createEphemeralProviderSession,
  clearEphemeralProviderSession,
  touchEphemeralProviderSession,
  buildKeyFingerprint,
  buildEndpointOriginPreview,
} from "./ephemeralProviderSession";

export type {
  RealProviderInvocationRequest,
  RealProviderInvocationResult,
  RealProviderStatus,
} from "./realProviderContract";
export {
  REAL_PROVIDER_CONTRACT_VERSION,
  buildRealProviderInvocationRequest,
  buildBlockedRealProviderResult,
  buildNotConfiguredResult,
} from "./realProviderContract";

export type { RealProviderAuditSummary } from "./realProviderAudit";
export {
  REAL_PROVIDER_AUDIT_VERSION,
  buildRealProviderAuditSummary,
  appendRealProviderAudit,
  getRealProviderAudits,
  clearRealProviderAudits,
} from "./realProviderAudit";

// T047: Real Send Gate
export type { RealSendGateInput, RealSendGateDecision } from "./egressGuard";
export {
  REAL_SEND_GATE_VERSION,
  evaluateRealSendGate,
} from "./egressGuard";

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
