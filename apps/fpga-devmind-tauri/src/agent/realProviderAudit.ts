/* ------------------------------------------------------------------ */
/*  T047: Real Provider Audit                                         */
/*  Redacted audit summary — no raw key, no raw prompt, no raw response. */
/* ------------------------------------------------------------------ */

export const REAL_PROVIDER_AUDIT_VERSION = "real-provider-audit-0.1";

export interface RealProviderAuditSummary {
  schema_version: string;
  request_id: string;
  provider_id: string;
  model_name: string;
  /** Origin preview only (scheme + host), no path/query */
  endpoint_origin_preview: string;
  /** Key fingerprint (irreversible), never the raw key */
  key_fingerprint: string | null;
  sent: boolean;
  status: string;
  /** Length of the answer preview in characters */
  answer_preview_chars: number;
  /** Always false — raw key is never stored */
  raw_key_stored: false;
  /** Always false — raw prompt is never stored */
  raw_prompt_stored: false;
  /** Always false — raw response is never stored */
  raw_response_stored: false;
  created_at: string;
}

/** Build a redacted audit summary from a real provider result.
 *
 *  Does NOT store:
 *  - raw API key
 *  - raw prompt / messages
 *  - raw provider response
 */
export function buildRealProviderAuditSummary(
  requestId: string,
  providerId: string,
  modelName: string,
  endpointOriginPreview: string,
  keyFingerprint: string | null,
  sent: boolean,
  status: string,
  answerPreview: string
): RealProviderAuditSummary {
  return {
    schema_version: REAL_PROVIDER_AUDIT_VERSION,
    request_id: requestId,
    provider_id: providerId,
    model_name: modelName,
    endpoint_origin_preview: endpointOriginPreview,
    key_fingerprint: keyFingerprint,
    sent,
    status,
    answer_preview_chars: answerPreview.length,
    raw_key_stored: false,
    raw_prompt_stored: false,
    raw_response_stored: false,
    created_at: new Date().toISOString(),
  };
}

/** In-memory audit log for real provider runs — NOT persisted to disk. */
const _realProviderAuditLog: RealProviderAuditSummary[] = [];

/** Append a redacted audit summary to the in-memory log. */
export function appendRealProviderAudit(summary: RealProviderAuditSummary): void {
  _realProviderAuditLog.push(summary);
}

/** Get all redacted audit summaries. */
export function getRealProviderAudits(): RealProviderAuditSummary[] {
  return [..._realProviderAuditLog];
}

/** Clear the in-memory audit log (useful for testing). */
export function clearRealProviderAudits(): void {
  _realProviderAuditLog.length = 0;
}
