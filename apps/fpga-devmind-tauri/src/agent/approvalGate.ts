/* ------------------------------------------------------------------ */
/*  T045: Approval Gate State Machine                                 */
/*  Manual approval workflow for external request packages.           */
/*  All states block network send.  No real external calls.           */
/* ------------------------------------------------------------------ */

import { PROVIDER_POLICY_VERSION } from "./policy";
import type { ExternalRequestPackage } from "./externalRequestPackage";

export const APPROVAL_GATE_VERSION = "approval-gate-0.1";

export type ApprovalState =
  | "not_requested"
  | "previewed"
  | "approved_but_blocked"
  | "denied";

export interface ApprovalDecision {
  schema_version: string;
  state: ApprovalState;
  send_allowed: false;
  reason: string;
  decided_at: string;
  policy_version: string;
  request_id: string;
}

/** Create a preview decision — user has viewed the request package. */
export function createPreviewDecision(
  requestPackage: ExternalRequestPackage
): ApprovalDecision {
  return {
    schema_version: APPROVAL_GATE_VERSION,
    state: "previewed",
    send_allowed: false,
    reason: "Request package previewed. Approval required before any further action.",
    decided_at: new Date().toISOString(),
    policy_version: PROVIDER_POLICY_VERSION,
    request_id: requestPackage.request_id,
  };
}

/** Approve an external request — but it remains blocked before network. */
export function approveExternalRequest(
  requestPackage: ExternalRequestPackage
): ApprovalDecision {
  return {
    schema_version: APPROVAL_GATE_VERSION,
    state: "approved_but_blocked",
    send_allowed: false,
    reason:
      "Approved by user, but network send is still blocked in T045. " +
      "External provider remains disabled by policy. " +
      "This is a simulated approval for workflow validation only.",
    decided_at: new Date().toISOString(),
    policy_version: PROVIDER_POLICY_VERSION,
    request_id: requestPackage.request_id,
  };
}

/** Deny an external request. */
export function denyExternalRequest(
  requestPackage: ExternalRequestPackage,
  reason?: string
): ApprovalDecision {
  return {
    schema_version: APPROVAL_GATE_VERSION,
    state: "denied",
    send_allowed: false,
    reason:
      reason ||
      "Denied by user. External provider remains disabled. No network request was made.",
    decided_at: new Date().toISOString(),
    policy_version: PROVIDER_POLICY_VERSION,
    request_id: requestPackage.request_id,
  };
}
