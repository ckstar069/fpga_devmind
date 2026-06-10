/* ------------------------------------------------------------------ */
/*  T046: External Execution Pipeline                                 */
/*  End-to-end pipeline shell: package → approval → transport → result */
/*  No real network calls. No API keys. No secrets.                   */
/* ------------------------------------------------------------------ */

import type { ProjectBundle } from "../types";
import type { ExternalProviderId } from "./externalProviderRegistry";
import { getExternalProviderDescriptor } from "./externalProviderRegistry";
import { buildExternalRequestPackage } from "./externalRequestPackage";
import {
  createPreviewDecision,
  approveExternalRequest,
  denyExternalRequest,
  type ApprovalState,
  type ApprovalDecision,
} from "./approvalGate";
import {
  executeBlockedTransport,
  executeMockTransport,
  type ExternalTransportKind,
  type ExternalTransportResponse,
} from "./externalTransport";
import type { EgressGuardDecision } from "./egressGuard";
import { PROVIDER_POLICY_VERSION } from "./policy";

export const EXTERNAL_EXECUTION_VERSION = "external-execution-0.1";

export type ExternalApprovalAction = "preview_only" | "simulate_approve" | "deny";

export interface ExternalExecutionInput {
  bundle: ProjectBundle | null;
  question: string;
  selectedNodeId: string | null;
  provider_id: ExternalProviderId;
  transport_kind: ExternalTransportKind;
  approval_action: ExternalApprovalAction;
}

export interface ExternalExecutionResult {
  schema_version: string;
  request_id: string;
  provider_id: ExternalProviderId;
  approval_state: ApprovalState;
  send_allowed: false;
  sent: false;
  blocked: true;
  mock_response: boolean;
  answer_preview: string;
  policy_version: string;
  egress_guard: EgressGuardDecision;
  transport_response: ExternalTransportResponse;
  artifacts_used: string[];
  evidence_ids: string[];
  limitations: string[];
}

/** Execute the external provider pipeline.
 *
 *  Flow:
 *  1. Build external request package (reuses T044/T045)
 *  2. Apply approval action (preview / approve / deny)
 *  3. Execute transport (blocked or mock)
 *  4. Return full execution result
 *
 *  Guarantees:
 *  - send_allowed is always false
 *  - sent is always false
 *  - blocked is always true
 *  - No real network calls
 *  - No API key access
 */
export function executeExternalProviderPipeline(
  input: ExternalExecutionInput
): ExternalExecutionResult {
  // Step 1: Build request package
  const requestPackage = buildExternalRequestPackage(
    input.bundle,
    input.question,
    input.selectedNodeId
  );

  // Step 2: Apply approval action
  let approvalDecision: ApprovalDecision;
  switch (input.approval_action) {
    case "simulate_approve":
      approvalDecision = approveExternalRequest(requestPackage);
      break;
    case "deny":
      approvalDecision = denyExternalRequest(requestPackage, "Denied by user via T046 execution panel.");
      break;
    case "preview_only":
    default:
      approvalDecision = createPreviewDecision(requestPackage);
      break;
  }

  // Step 3: Execute transport
  const transportRequest = {
    request_id: requestPackage.request_id,
    provider_id: input.provider_id,
    request_package: requestPackage,
    approval_decision: approvalDecision,
  };

  const transportResponse =
    input.transport_kind === "mock"
      ? executeMockTransport(transportRequest)
      : executeBlockedTransport(transportRequest);

  // Step 4: Build execution result
  const limitations: string[] = [
    "T046: External execution pipeline is a shell — no real provider adapter exists yet.",
    `Transport: ${input.transport_kind} (offline only)`,
    `Provider: ${input.provider_id} (${getExternalProviderDescriptor(input.provider_id)?.status || "unknown"})`,
    "No network call was made.",
    "No API key was used.",
    ...requestPackage.limitations,
  ];

  return {
    schema_version: EXTERNAL_EXECUTION_VERSION,
    request_id: requestPackage.request_id,
    provider_id: input.provider_id,
    approval_state: approvalDecision.state,
    send_allowed: false,
    sent: false,
    blocked: true,
    mock_response: transportResponse.mock_response,
    answer_preview: transportResponse.answer_preview,
    policy_version: PROVIDER_POLICY_VERSION,
    egress_guard: transportResponse.egress_guard,
    transport_response: transportResponse,
    artifacts_used: requestPackage.artifacts_used,
    evidence_ids: requestPackage.evidence_ids,
    limitations,
  };
}
