import { describe, it, expect } from "vitest";
import {
  EXTERNAL_PROVIDER_REGISTRY_VERSION,
  getExternalProviderDescriptors,
  getExternalProviderDescriptor,
  isExternalProviderSendAllowed,
  getSelectableExternalProviderIds,
} from "../agent/externalProviderRegistry";
import type { ExternalProviderId } from "../agent/externalProviderRegistry";

describe("T046 External Provider Registry", () => {
  it("registry version is correct", () => {
    expect(EXTERNAL_PROVIDER_REGISTRY_VERSION).toBe("external-provider-registry-0.1");
  });

  it("contains expected providers", () => {
    const descriptors = getExternalProviderDescriptors();
    const ids = descriptors.map((d) => d.id);

    expect(ids).toContain("external_disabled");
    expect(ids).toContain("mock_external_llm");
    expect(ids).toContain("future_openai");
    expect(ids).toContain("future_anthropic");
    expect(ids).toContain("future_deepseek");
    expect(ids).toContain("future_gemini");
    expect(ids).toContain("future_glm");
  });

  it("all providers have send_allowed=false", () => {
    const descriptors = getExternalProviderDescriptors();
    for (const desc of descriptors) {
      expect(desc.send_allowed, `Provider ${desc.id} should have send_allowed=false`).toBe(false);
    }
  });

  it("all providers have network_allowed=false", () => {
    const descriptors = getExternalProviderDescriptors();
    for (const desc of descriptors) {
      expect(desc.network_allowed, `Provider ${desc.id} should have network_allowed=false`).toBe(false);
    }
  });

  it("all providers have secret_storage_allowed=false", () => {
    const descriptors = getExternalProviderDescriptors();
    for (const desc of descriptors) {
      expect(desc.secret_storage_allowed, `Provider ${desc.id} should have secret_storage_allowed=false`).toBe(false);
    }
  });

  it("mock_external_llm status is mock_only", () => {
    const desc = getExternalProviderDescriptor("mock_external_llm");
    expect(desc).toBeDefined();
    expect(desc!.status).toBe("mock_only");
    expect(desc!.requires_api_key).toBe(false);
  });

  it("future providers status is future", () => {
    const futureIds: ExternalProviderId[] = [
      "future_openai",
      "future_anthropic",
      "future_deepseek",
      "future_gemini",
      "future_glm",
    ];
    for (const id of futureIds) {
      const desc = getExternalProviderDescriptor(id);
      expect(desc, `Provider ${id} should exist`).toBeDefined();
      expect(desc!.status).toBe("future");
      expect(desc!.requires_api_key).toBe(true);
    }
  });

  it("external_disabled status is blocked", () => {
    const desc = getExternalProviderDescriptor("external_disabled");
    expect(desc).toBeDefined();
    expect(desc!.status).toBe("blocked");
    expect(desc!.requires_api_key).toBe(false);
  });

  it("isExternalProviderSendAllowed always returns false", () => {
    const allIds: ExternalProviderId[] = [
      "external_disabled",
      "mock_external_llm",
      "future_openai",
      "future_anthropic",
      "future_deepseek",
      "future_gemini",
      "future_glm",
    ];
    for (const id of allIds) {
      expect(isExternalProviderSendAllowed(id), `Provider ${id} should not allow send`).toBe(false);
    }
  });

  it("getExternalProviderDescriptor returns undefined for unknown id", () => {
    const desc = getExternalProviderDescriptor("unknown_provider" as ExternalProviderId);
    expect(desc).toBeUndefined();
  });

  it("selectable providers include mock and future placeholders", () => {
    const selectable = getSelectableExternalProviderIds();
    expect(selectable).toContain("mock_external_llm");
    expect(selectable).toContain("future_openai");
    expect(selectable).toContain("future_anthropic");
    expect(selectable).toContain("future_deepseek");
    // external_disabled is not selectable (it's the baseline)
    expect(selectable).not.toContain("external_disabled");
  });

  it("no provider contains real endpoint or api URL", () => {
    const descriptors = getExternalProviderDescriptors();
    for (const desc of descriptors) {
      const json = JSON.stringify(desc);
      expect(json).not.toContain("https://");
      expect(json).not.toContain("api.openai.com");
      expect(json).not.toContain("api.anthropic.com");
      expect(json).not.toContain("api.deepseek.com");
      expect(json).not.toContain("api.gemini.com");
    }
  });

  it("no provider descriptor leaks secret values in JSON", () => {
    const descriptors = getExternalProviderDescriptors();
    for (const desc of descriptors) {
      const json = JSON.stringify(desc);
      // Field names like requires_api_key are schema metadata, not secrets.
      // We check there are no actual secret values (patterns like sk-, ghp_, bearer, passwords).
      expect(json).not.toContain("sk-");
      expect(json).not.toContain("ghp_");
      expect(json).not.toContain("xoxb-");
      expect(json).not.toContain("eyJ");
      expect(json).not.toContain("bearer ");
      expect(json).not.toContain("password ");
    }
  });
});
