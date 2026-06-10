/* ------------------------------------------------------------------ */
/*  T046: External Provider Registry                                  */
/*  Catalog of all external providers — none allow real network send. */
/*  Future providers are placeholders only. No API keys. No secrets.  */
/* ------------------------------------------------------------------ */

export const EXTERNAL_PROVIDER_REGISTRY_VERSION = "external-provider-registry-0.1";

export type ExternalProviderId =
  | "external_disabled"
  | "mock_external_llm"
  | "future_openai"
  | "future_anthropic"
  | "future_deepseek"
  | "future_gemini"
  | "future_glm";

export interface ExternalProviderDescriptor {
  id: ExternalProviderId;
  label: string;
  status: "blocked" | "mock_only" | "future";
  requires_api_key: boolean;
  network_allowed: false;
  secret_storage_allowed: false;
  send_allowed: false;
  description: string;
}

/** Registry of all known external providers.
 *
 *  - external_disabled: permanently blocked baseline
 *  - mock_external_llm: mock-only, deterministic offline responses
 *  - future_*: placeholders for future real provider adapters
 *
 *  All entries: send_allowed=false, network_allowed=false, secret_storage_allowed=false.
 */
const REGISTRY: Record<ExternalProviderId, ExternalProviderDescriptor> = {
  external_disabled: {
    id: "external_disabled",
    label: "External Provider (Disabled)",
    status: "blocked",
    requires_api_key: false,
    network_allowed: false,
    secret_storage_allowed: false,
    send_allowed: false,
    description: "Baseline disabled provider. No network, no API key, no send.",
  },
  mock_external_llm: {
    id: "mock_external_llm",
    label: "Mock External LLM",
    status: "mock_only",
    requires_api_key: false,
    network_allowed: false,
    secret_storage_allowed: false,
    send_allowed: false,
    description: "Deterministic mock provider for offline testing. No real network calls.",
  },
  future_openai: {
    id: "future_openai",
    label: "OpenAI (Future)",
    status: "future",
    requires_api_key: true,
    network_allowed: false,
    secret_storage_allowed: false,
    send_allowed: false,
    description: "Future placeholder for OpenAI adapter. Not implemented in T046.",
  },
  future_anthropic: {
    id: "future_anthropic",
    label: "Anthropic (Future)",
    status: "future",
    requires_api_key: true,
    network_allowed: false,
    secret_storage_allowed: false,
    send_allowed: false,
    description: "Future placeholder for Anthropic adapter. Not implemented in T046.",
  },
  future_deepseek: {
    id: "future_deepseek",
    label: "DeepSeek (Future)",
    status: "future",
    requires_api_key: true,
    network_allowed: false,
    secret_storage_allowed: false,
    send_allowed: false,
    description: "Future placeholder for DeepSeek adapter. Not implemented in T046.",
  },
  future_gemini: {
    id: "future_gemini",
    label: "Gemini (Future)",
    status: "future",
    requires_api_key: true,
    network_allowed: false,
    secret_storage_allowed: false,
    send_allowed: false,
    description: "Future placeholder for Gemini adapter. Not implemented in T046.",
  },
  future_glm: {
    id: "future_glm",
    label: "GLM (Future)",
    status: "future",
    requires_api_key: true,
    network_allowed: false,
    secret_storage_allowed: false,
    send_allowed: false,
    description: "Future placeholder for GLM adapter. Not implemented in T046.",
  },
};

/** Get descriptors for all registered external providers. */
export function getExternalProviderDescriptors(): ExternalProviderDescriptor[] {
  return Object.values(REGISTRY);
}

/** Get a single provider descriptor by ID. */
export function getExternalProviderDescriptor(
  id: ExternalProviderId
): ExternalProviderDescriptor | undefined {
  return REGISTRY[id];
}

/** Check if any external provider allows send.
 *
 *  Always returns false in T046.
 */
export function isExternalProviderSendAllowed(_id: ExternalProviderId): false {
  return false;
}

/** Get the list of provider IDs that can be selected in the UI.
 *
 *  In T046: mock_external_llm is selectable for testing.
 *  Future providers are also listed for visibility but blocked.
 */
export function getSelectableExternalProviderIds(): ExternalProviderId[] {
  return [
    "mock_external_llm",
    "future_openai",
    "future_anthropic",
    "future_deepseek",
  ];
}
