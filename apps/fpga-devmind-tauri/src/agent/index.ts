/* ------------------------------------------------------------------ */
/*  T042: Agent Provider Boundary — entry point                       */
/* ------------------------------------------------------------------ */

export type {
  AgentProviderKind,
  ProviderCapabilities,
  AgentRunRequest,
  AgentRunResult,
  AgentRunTrace,
  AgentTraceStep,
  AgentProvider,
} from "./providers";

export {
  PROVIDER_CAPABILITIES,
  generateTraceId,
  collectArtifactsUsed,
} from "./providers";

export { deterministicProvider } from "./deterministicProvider";
export { offlineMockProvider } from "./offlineMockProvider";
export { externalDisabledProvider } from "./externalDisabledProvider";

import type { AgentRunRequest, AgentRunResult, AgentProviderKind } from "./providers";
import { deterministicProvider } from "./deterministicProvider";
import { offlineMockProvider } from "./offlineMockProvider";
import { externalDisabledProvider } from "./externalDisabledProvider";

/** Dispatch request to the appropriate provider */
export function runAgent(request: AgentRunRequest): AgentRunResult {
  switch (request.providerKind) {
    case "offline_mock":
      return offlineMockProvider.run(request);
    case "external_disabled":
      return externalDisabledProvider.run(request);
    case "deterministic":
    default:
      return deterministicProvider.run(request);
  }
}

/** Get a list of available provider kinds for UI selection */
export function getAvailableProviderKinds(): AgentProviderKind[] {
  return ["deterministic", "offline_mock", "external_disabled"];
}
