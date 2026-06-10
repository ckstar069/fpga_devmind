/* ------------------------------------------------------------------ */
/*  T043: Provider Config Schema — Non-secret only                     */
/*  Defines allowed config fields and rejects any secret storage       */
/* ------------------------------------------------------------------ */

import type { AgentProviderKind } from "./providers";

/** Provider configuration — NO secret fields allowed */
export interface ProviderConfig {
  provider_kind: AgentProviderKind;
  enabled: boolean;
  display_name: string;
  policy_version: string;
  allow_network: boolean;
  allow_external_calls: boolean;
}

/** Default in-memory configs for all providers.
 *  No persistence, no localStorage, no env-var reading.
 */
export const DEFAULT_PROVIDER_CONFIGS: Record<AgentProviderKind, ProviderConfig> = {
  deterministic: {
    provider_kind: "deterministic",
    enabled: true,
    display_name: "确定性 Agent",
    policy_version: "t043.0",
    allow_network: false,
    allow_external_calls: false,
  },
  offline_mock: {
    provider_kind: "offline_mock",
    enabled: true,
    display_name: "Offline Mock Agent",
    policy_version: "t043.0",
    allow_network: false,
    allow_external_calls: false,
  },
  external_disabled: {
    provider_kind: "external_disabled",
    enabled: false,
    display_name: "External Provider (Disabled)",
    policy_version: "t043.0",
    allow_network: false,
    allow_external_calls: false,
  },
};

/** Forbidden field names — any config containing these is rejected.
 *  This is a defense-in-depth check to prevent accidental secret storage.
 */
export const FORBIDDEN_CONFIG_FIELDS: string[] = [
  "api_key",
  "apiKey",
  "secret",
  "token",
  "bearer",
  "password",
  "endpoint",
  "base_url",
  "headers",
];

/** Validate a provider config object.
 *
 * Returns { valid: true } or { valid: false, errors: string[] }.
 *
 * Checks:
 * 1. No forbidden (secret-related) field names.
 * 2. external_disabled must have enabled=false.
 * 3. No allow_network=true for any provider.
 * 4. No allow_external_calls=true for any provider.
 */
export function validateProviderConfig(
  config: Record<string, unknown>
): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  // 1. Reject forbidden field names
  for (const key of Object.keys(config)) {
    const lower = key.toLowerCase();
    for (const forbidden of FORBIDDEN_CONFIG_FIELDS) {
      if (lower.includes(forbidden.toLowerCase())) {
        errors.push(
          `Config field "${key}" contains forbidden keyword "${forbidden}" — secret storage is prohibited in T043`
        );
      }
    }
  }

  // 2. external_disabled must be disabled
  const kind = config.provider_kind as AgentProviderKind | undefined;
  if (kind === "external_disabled" && config.enabled === true) {
    errors.push(
      `Provider "external_disabled" must have enabled=false per safety policy`
    );
  }

  // 3. No network allowed
  if (config.allow_network === true) {
    errors.push(
      `allow_network=true is prohibited — all providers must run offline in T043`
    );
  }

  // 4. No external calls allowed
  if (config.allow_external_calls === true) {
    errors.push(
      `allow_external_calls=true is prohibited — external LLM calls are disabled in T043`
    );
  }

  return { valid: errors.length === 0, errors };
}

/** Check if a raw object contains any secret-related keys.
 *  Used as an extra guard before processing untrusted config input.
 */
export function containsSecretKeys(obj: Record<string, unknown>): boolean {
  const keys = Object.keys(obj);
  for (const key of keys) {
    const lower = key.toLowerCase();
    for (const forbidden of FORBIDDEN_CONFIG_FIELDS) {
      if (lower.includes(forbidden.toLowerCase())) return true;
    }
    // Recurse into nested objects (one level)
    const val = obj[key];
    if (val && typeof val === "object" && !Array.isArray(val)) {
      if (containsSecretKeys(val as Record<string, unknown>)) return true;
    }
  }
  return false;
}
