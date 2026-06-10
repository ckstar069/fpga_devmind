/* ------------------------------------------------------------------ */
/*  T046: External Transport Abstraction                              */
/*  Blocked and Mock transports.  No real network calls.              */
/* ------------------------------------------------------------------ */

import type { ExternalProviderId } from "./externalProviderRegistry";
import type { ExternalRequestPackage } from "./externalRequestPackage";
import type { ApprovalDecision } from "./approvalGate";
import { evaluateEgressGuard, type EgressGuardDecision } from "./egressGuard";

export const EXTERNAL_TRANSPORT_VERSION = "external-transport-0.1";

export type ExternalTransportKind = "blocked" | "mock";

export interface ExternalTransportRequest {
  request_id: string;
  provider_id: ExternalProviderId;
  request_package: ExternalRequestPackage;
  approval_decision: ApprovalDecision;
}

export interface ExternalTransportResponse {
  schema_version: string;
  transport_kind: ExternalTransportKind;
  request_id: string;
  sent: false;
  blocked: true;
  mock_response: boolean;
  answer_preview: string;
  reason: string;
  egress_guard: EgressGuardDecision;
  created_at: string;
}

/** Execute the blocked transport.
 *
 *  Always returns blocked=true, sent=false, mock_response=false.
 *  Calls egress guard for defense-in-depth logging.
 */
export function executeBlockedTransport(
  request: ExternalTransportRequest
): ExternalTransportResponse {
  const egress = evaluateEgressGuard({
    provider_id: request.provider_id,
    request_id: request.request_id,
    approval_state: request.approval_decision.state,
    send_allowed: request.approval_decision.send_allowed,
    policy_version: request.approval_decision.policy_version,
  });

  return {
    schema_version: EXTERNAL_TRANSPORT_VERSION,
    transport_kind: "blocked",
    request_id: request.request_id,
    sent: false,
    blocked: true,
    mock_response: false,
    answer_preview: "",
    reason:
      "Blocked transport: no request was sent. " +
      egress.reason,
    egress_guard: egress,
    created_at: new Date().toISOString(),
  };
}

/** Execute the mock transport.
 *
 *  Returns a deterministic mock answer preview but still blocked=true, sent=false.
 *  mock_response=true indicates the answer is synthetic/offline.
 *  Calls egress guard for defense-in-depth logging.
 */
export function executeMockTransport(
  request: ExternalTransportRequest
): ExternalTransportResponse {
  const egress = evaluateEgressGuard({
    provider_id: request.provider_id,
    request_id: request.request_id,
    approval_state: request.approval_decision.state,
    send_allowed: request.approval_decision.send_allowed,
    policy_version: request.approval_decision.policy_version,
  });

  const pkg = request.request_package;
  const itemCount = pkg.request_body_preview.context_items_count;
  const tokenEstimate = pkg.request_body_preview.total_tokens_estimate;

  // Deterministic mock answer based on request content
  const mockAnswer = buildMockAnswer(pkg.question_preview, itemCount, tokenEstimate);

  return {
    schema_version: EXTERNAL_TRANSPORT_VERSION,
    transport_kind: "mock",
    request_id: request.request_id,
    sent: false,
    blocked: true,
    mock_response: true,
    answer_preview: mockAnswer,
    reason:
      "Mock transport: a deterministic offline response was generated, " +
      "but no real network request was sent. " +
      egress.reason,
    egress_guard: egress,
    created_at: new Date().toISOString(),
  };
}

function buildMockAnswer(questionPreview: string, itemCount: number, tokenEstimate: number): string {
  const lines = [
    "[MOCK RESPONSE — T046 Offline Only]",
    "",
    `This is a deterministic mock answer for: "${questionPreview}"`,
    "",
    `Context used: ${itemCount} items (~${tokenEstimate} tokens estimated)`,
    "",
    "In a real implementation, this would be the external LLM response. " +
    "T046 only provides the transport shell — no actual model inference occurs.",
    "",
    "Mock answer characteristics:",
    "- Generated entirely offline",
    "- No API key was used",
    "- No network call was made",
    "- Response is deterministic for the same input",
  ];
  return lines.join("\n");
}
