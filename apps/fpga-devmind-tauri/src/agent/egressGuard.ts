/* ------------------------------------------------------------------ */
/*  T046: Egress Guard                                                */
/*  Final network-send gate.  All paths return allowed=false.         */
/*  No real external calls can pass through.                          */
/* ------------------------------------------------------------------ */

import type { ExternalProviderId } from "./externalProviderRegistry";
import { getExternalProviderDescriptor } from "./externalProviderRegistry";
import type { ApprovalState } from "./approvalGate";

export const EGRESS_GUARD_VERSION = "egress-guard-0.1";

export interface EgressGuardInput {
  provider_id: ExternalProviderId;
  request_id: string;
  approval_state: ApprovalState;
  send_allowed: boolean;
  policy_version: string;
}

export interface EgressGuardDecision {
  schema_version: string;
  allowed: false;
  reason: string;
  network_allowed: false;
  external_calls_allowed: false;
  provider_id: string;
  request_id: string;
  checked_at: string;
}

/** Evaluate the egress guard for a given request.
 *
 *  This is the FINAL gate before any network call would be made.
 *  In T046, it ALWAYS returns allowed=false.
 *
 *  Rules:
 *  - approved_but_blocked → approved by user but blocked before network in T046
 *  - future provider → future provider placeholder only
 *  - any other state → blocked by T046 egress guard
 *  - Even if send_allowed=true is forged, still blocked.
 */
export function evaluateEgressGuard(input: EgressGuardInput): EgressGuardDecision {
  const descriptor = getExternalProviderDescriptor(input.provider_id);

  // Determine reason based on state and provider type
  let reason: string;

  if (descriptor?.status === "future") {
    reason = `Future provider "${input.provider_id}" is a placeholder only. Real adapter not implemented in T046.`;
  } else if (input.approval_state === "approved_but_blocked") {
    reason =
      "Approved by user but blocked before network in T046. " +
      "External provider execution pipeline is still a mock/block shell. " +
      "No real network call is available.";
  } else if (input.approval_state === "denied") {
    reason = "Request was denied by user. Blocked at egress guard.";
  } else if (input.approval_state === "previewed") {
    reason = "Request was only previewed, not approved. Blocked at egress guard.";
  } else if (input.approval_state === "not_requested") {
    reason = "Approval was not requested. Blocked at egress guard.";
  } else {
    reason = "Blocked by T046 egress guard — no network send is allowed.";
  }

  // Defense in depth: explicitly note forged send_allowed
  if (input.send_allowed === true) {
    reason += " (Note: send_allowed=true was detected but overridden by egress guard policy.)";
  }

  return {
    schema_version: EGRESS_GUARD_VERSION,
    allowed: false,
    reason,
    network_allowed: false,
    external_calls_allowed: false,
    provider_id: input.provider_id,
    request_id: input.request_id,
    checked_at: new Date().toISOString(),
  };
}
