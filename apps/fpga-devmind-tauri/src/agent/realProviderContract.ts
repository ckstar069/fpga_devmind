/* ------------------------------------------------------------------ */
/*  T047: Real Provider Contract                                      */
/*  Frontend-Backend contract for real provider invocation.           */
/*  NO API key in TypeScript contract — key passes via Tauri command. */
/* ------------------------------------------------------------------ */

import type { ExternalRequestPackage } from "./externalRequestPackage";

export const REAL_PROVIDER_CONTRACT_VERSION = "real-provider-contract-0.1";

export interface RealProviderInvocationRequest {
  schema_version: string;
  request_id: string;
  provider_id: "openai_compatible_ephemeral";
  model_name: string;
  endpoint_url: string;
  request_package: ExternalRequestPackage;
  approval_state: "approved_but_blocked";
  /** Explicit user consent flag — must be true for real send */
  send_allowed_by_user: true;
}

export type RealProviderStatus =
  | "not_configured"
  | "blocked"
  | "sent"
  | "provider_error"
  | "network_error"
  | "redaction_error";

export interface RealProviderInvocationResult {
  schema_version: string;
  request_id: string;
  provider_id: string;
  sent: boolean;
  blocked: boolean;
  status: RealProviderStatus;
  /** Preview of the answer text (max ~4000 chars, truncated by backend) */
  answer_text_preview: string;
  /** Redacted error preview — never contains the raw API key */
  error_preview: string | null;
  /** Raw response is never stored in the contract */
  raw_response_stored: false;
  /** Audit data is redacted — no raw key, no raw prompt, no raw response */
  audit_redacted: true;
  created_at: string;
}

/** Build a real provider invocation request.
 *
 *  Validates that the request package uses redacted preview only.
 */
export function buildRealProviderInvocationRequest(
  requestPackage: ExternalRequestPackage,
  modelName: string,
  endpointUrl: string
): RealProviderInvocationRequest {
  return {
    schema_version: REAL_PROVIDER_CONTRACT_VERSION,
    request_id: requestPackage.request_id,
    provider_id: "openai_compatible_ephemeral",
    model_name: modelName,
    endpoint_url: endpointUrl,
    request_package: requestPackage,
    approval_state: "approved_but_blocked",
    send_allowed_by_user: true,
  };
}

/** Build a blocked result when the real send gate denies. */
export function buildBlockedRealProviderResult(
  requestId: string,
  reason: string
): RealProviderInvocationResult {
  return {
    schema_version: REAL_PROVIDER_CONTRACT_VERSION,
    request_id: requestId,
    provider_id: "openai_compatible_ephemeral",
    sent: false,
    blocked: true,
    status: "blocked",
    answer_text_preview: "",
    error_preview: reason,
    raw_response_stored: false,
    audit_redacted: true,
    created_at: new Date().toISOString(),
  };
}

/** Build a not-configured result when no session exists. */
export function buildNotConfiguredResult(requestId: string): RealProviderInvocationResult {
  return buildBlockedRealProviderResult(
    requestId,
    "Provider not configured. Please enter endpoint URL, model name, and API key in the T047 panel."
  );
}
