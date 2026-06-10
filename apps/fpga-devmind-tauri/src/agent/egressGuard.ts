/* ------------------------------------------------------------------ */
/*  T046/T047: Egress Guard + Real Send Gate                          */
/*  T046: All paths return allowed=false.                             */
/*  T047: Real send gate can return allowed=true ONLY when all        */
/*        ephemeral session conditions are met.                       */
/* ------------------------------------------------------------------ */

import type { ExternalProviderId } from "./externalProviderRegistry";
import { getExternalProviderDescriptor } from "./externalProviderRegistry";
import type { ApprovalState } from "./approvalGate";
import type { EphemeralProviderSessionState } from "./ephemeralProviderSession";

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

/* ------------------------------------------------------------------ */
/*  T047: Real Send Gate                                              */
/*  Separate gate for ephemeral real provider adapter.                */
/*  Can return allowed=true ONLY when all conditions are met.         */
/* ------------------------------------------------------------------ */

export const REAL_SEND_GATE_VERSION = "real-send-gate-0.1";

export interface RealSendGateInput {
  provider_id: ExternalProviderId | "openai_compatible_ephemeral";
  request_id: string;
  approval_state: ApprovalState;
  send_allowed_by_user: boolean;
  session: EphemeralProviderSessionState | null;
  endpoint_url: string;
}

export interface RealSendGateDecision {
  schema_version: string;
  allowed: boolean;
  reason: string;
  network_allowed: boolean;
  external_calls_allowed: boolean;
  provider_id: string;
  request_id: string;
  checked_at: string;
  conditions_met: {
    session_configured: boolean;
    key_present: boolean;
    endpoint_https: boolean;
    approval_adequate: boolean;
    user_explicit_consent: boolean;
  };
}

/** Evaluate the real send gate for ephemeral provider adapter.
 *
 *  This is the T047 gate that CAN allow real network calls,
 *  but ONLY when ALL of the following conditions are met:
 *  1. Session is configured
 *  2. Key is present (fingerprint exists)
 *  3. Endpoint is HTTPS
 *  4. Approval state is approved_but_blocked
 *  5. User explicitly clicked send (send_allowed_by_user=true)
 *
 *  If any condition is not met, returns allowed=false with a detailed reason.
 */
export function evaluateRealSendGate(input: RealSendGateInput): RealSendGateDecision {
  const now = new Date().toISOString();
  const conditions = {
    session_configured: input.session?.configured === true,
    key_present: input.session?.key_present === true,
    endpoint_https: input.endpoint_url.trim().startsWith("https://"),
    approval_adequate: input.approval_state === "approved_but_blocked",
    user_explicit_consent: input.send_allowed_by_user === true,
  };

  const allMet =
    conditions.session_configured &&
    conditions.key_present &&
    conditions.endpoint_https &&
    conditions.approval_adequate &&
    conditions.user_explicit_consent;

  if (allMet) {
    return {
      schema_version: REAL_SEND_GATE_VERSION,
      allowed: true,
      reason:
        "T047 real send gate: all conditions met. " +
        "Session configured, key present, HTTPS endpoint, approved, user consent given. " +
        "Network call will proceed via Tauri backend command.",
      network_allowed: true,
      external_calls_allowed: true,
      provider_id: input.provider_id,
      request_id: input.request_id,
      checked_at: now,
      conditions_met: conditions,
    };
  }

  // Build reason listing which conditions failed
  const failures: string[] = [];
  if (!conditions.session_configured) failures.push("session not configured");
  if (!conditions.key_present) failures.push("API key not present");
  if (!conditions.endpoint_https) failures.push("endpoint is not HTTPS");
  if (!conditions.approval_adequate) failures.push("approval state is not approved_but_blocked");
  if (!conditions.user_explicit_consent) failures.push("user did not explicitly allow send");

  const reason =
    "T047 real send gate blocked: " +
    failures.join("; ") +
    ". Real network call will NOT proceed.";

  return {
    schema_version: REAL_SEND_GATE_VERSION,
    allowed: false,
    reason,
    network_allowed: false,
    external_calls_allowed: false,
    provider_id: input.provider_id,
    request_id: input.request_id,
    checked_at: now,
    conditions_met: conditions,
  };
}
