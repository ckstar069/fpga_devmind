/* ------------------------------------------------------------------ */
/*  T047: Ephemeral Provider Session                                  */
/*  Runtime-only session — no persistence, no disk, no localStorage.  */
/*  Only stores a key fingerprint, never the raw API key.             */
/* ------------------------------------------------------------------ */

export const EPHEMERAL_PROVIDER_SESSION_VERSION = "ephemeral-provider-session-0.1";

export type RuntimeProviderId = "openai_compatible_ephemeral";

export interface EphemeralProviderSessionState {
  schema_version: string;
  provider_id: RuntimeProviderId;
  configured: boolean;
  key_present: boolean;
  /** Irreversible fingerprint preview of the key (e.g. "sk-...abcd" or hash prefix) */
  key_fingerprint: string | null;
  /** Origin preview of the endpoint (domain only, no path/query) */
  endpoint_origin_preview: string;
  model_name: string;
  /** Always memory_only — no disk, no localStorage, no IndexedDB */
  storage: "memory_only";
  created_at: string | null;
  last_used_at: string | null;
}

/** Create an empty ephemeral provider session. */
export function createEmptyEphemeralProviderSession(): EphemeralProviderSessionState {
  return {
    schema_version: EPHEMERAL_PROVIDER_SESSION_VERSION,
    provider_id: "openai_compatible_ephemeral",
    configured: false,
    key_present: false,
    key_fingerprint: null,
    endpoint_origin_preview: "",
    model_name: "gpt-4o-mini",
    storage: "memory_only",
    created_at: null,
    last_used_at: null,
  };
}

export interface EphemeralProviderSessionInput {
  api_key: string;
  endpoint_url: string;
  model_name: string;
}

/** Build a non-reversible fingerprint from an API key.
 *
 *  Shows the first 4 chars and last 4 chars with ellipsis.
 *  Never stores the full key.
 */
export function buildKeyFingerprint(apiKey: string): string {
  const trimmed = apiKey.trim();
  if (trimmed.length <= 8) {
    return "...";
  }
  return `${trimmed.slice(0, 4)}...${trimmed.slice(-4)}`;
}

/** Extract origin preview from a full endpoint URL.
 *
 *  Returns just the origin (scheme + host), no path, no query, no fragment.
 */
export function buildEndpointOriginPreview(url: string): string {
  try {
    const u = new URL(url.trim());
    return `${u.protocol}//${u.host}`;
  } catch {
    return "";
  }
}

/** Create an ephemeral provider session from user input.
 *
 *  The raw api_key is NOT stored in the returned state.
 *  Only a fingerprint is kept.
 */
export function createEphemeralProviderSession(
  input: EphemeralProviderSessionInput
): EphemeralProviderSessionState {
  const now = new Date().toISOString();
  return {
    schema_version: EPHEMERAL_PROVIDER_SESSION_VERSION,
    provider_id: "openai_compatible_ephemeral",
    configured: true,
    key_present: input.api_key.trim().length > 0,
    key_fingerprint: buildKeyFingerprint(input.api_key),
    endpoint_origin_preview: buildEndpointOriginPreview(input.endpoint_url),
    model_name: input.model_name.trim() || "gpt-4o-mini",
    storage: "memory_only",
    created_at: now,
    last_used_at: now,
  };
}

/** Clear an ephemeral provider session — wipes all session state. */
export function clearEphemeralProviderSession(
  _state: EphemeralProviderSessionState
): EphemeralProviderSessionState {
  return createEmptyEphemeralProviderSession();
}

/** Mark session as used (updates last_used_at). */
export function touchEphemeralProviderSession(
  state: EphemeralProviderSessionState
): EphemeralProviderSessionState {
  return {
    ...state,
    last_used_at: new Date().toISOString(),
  };
}
