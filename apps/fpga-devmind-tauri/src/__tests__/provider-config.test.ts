import { describe, it, expect } from "vitest";
import {
  DEFAULT_PROVIDER_CONFIGS,
  FORBIDDEN_CONFIG_FIELDS,
  validateProviderConfig,
  containsSecretKeys,
} from "../agent/config";

describe("T043 Provider Config", () => {
  it("DEFAULT_PROVIDER_CONFIGS has no secret fields", () => {
    for (const [_kind, config] of Object.entries(DEFAULT_PROVIDER_CONFIGS)) {
      const keys = Object.keys(config);
      for (const key of keys) {
        const lower = key.toLowerCase();
        for (const forbidden of FORBIDDEN_CONFIG_FIELDS) {
          expect(lower).not.toContain(forbidden.toLowerCase());
        }
      }
      // All providers must have allow_network=false
      expect(config.allow_network).toBe(false);
      // All providers must have allow_external_calls=false
      expect(config.allow_external_calls).toBe(false);
    }
  });

  it("external_disabled config has enabled=false", () => {
    expect(DEFAULT_PROVIDER_CONFIGS.external_disabled.enabled).toBe(false);
  });

  it("deterministic config has enabled=true", () => {
    expect(DEFAULT_PROVIDER_CONFIGS.deterministic.enabled).toBe(true);
  });

  it("offline_mock config has enabled=true", () => {
    expect(DEFAULT_PROVIDER_CONFIGS.offline_mock.enabled).toBe(true);
  });

  it("validateProviderConfig rejects api_key field", () => {
    const result = validateProviderConfig({
      provider_kind: "deterministic",
      enabled: true,
      api_key: "sk-123",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
    expect(result.errors[0]).toContain("api_key");
  });

  it("validateProviderConfig rejects token field", () => {
    const result = validateProviderConfig({
      provider_kind: "deterministic",
      enabled: true,
      token: "abc",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("token"))).toBe(true);
  });

  it("validateProviderConfig rejects endpoint field", () => {
    const result = validateProviderConfig({
      provider_kind: "deterministic",
      enabled: true,
      endpoint: "https://api.openai.com",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("endpoint"))).toBe(true);
  });

  it("validateProviderConfig rejects headers field", () => {
    const result = validateProviderConfig({
      provider_kind: "deterministic",
      enabled: true,
      headers: { Authorization: "Bearer xxx" },
    });
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("headers"))).toBe(true);
  });

  it("validateProviderConfig rejects base_url field", () => {
    const result = validateProviderConfig({
      provider_kind: "deterministic",
      enabled: true,
      base_url: "https://example.com",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("base_url"))).toBe(true);
  });

  it("validateProviderConfig rejects secret field", () => {
    const result = validateProviderConfig({
      provider_kind: "deterministic",
      enabled: true,
      secret: "shh",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("secret"))).toBe(true);
  });

  it("validateProviderConfig rejects external_disabled enabled=true", () => {
    const result = validateProviderConfig({
      provider_kind: "external_disabled",
      enabled: true,
    });
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("external_disabled"))).toBe(true);
  });

  it("validateProviderConfig rejects allow_network=true", () => {
    const result = validateProviderConfig({
      provider_kind: "deterministic",
      enabled: true,
      allow_network: true,
    });
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("allow_network"))).toBe(true);
  });

  it("validateProviderConfig rejects allow_external_calls=true", () => {
    const result = validateProviderConfig({
      provider_kind: "deterministic",
      enabled: true,
      allow_external_calls: true,
    });
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("allow_external_calls"))).toBe(true);
  });

  it("validateProviderConfig passes for valid deterministic config", () => {
    const result = validateProviderConfig({
      provider_kind: "deterministic",
      enabled: true,
      display_name: "确定性 Agent",
      policy_version: "t043.0",
      allow_network: false,
      allow_external_calls: false,
    });
    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it("containsSecretKeys detects api_key", () => {
    expect(containsSecretKeys({ api_key: "x" })).toBe(true);
    expect(containsSecretKeys({ token: "x" })).toBe(true);
    expect(containsSecretKeys({ password: "x" })).toBe(true);
  });

  it("containsSecretKeys detects nested secrets", () => {
    expect(containsSecretKeys({ outer: { secret: "x" } })).toBe(true);
  });

  it("containsSecretKeys returns false for clean objects", () => {
    expect(containsSecretKeys({ enabled: true, name: "ok" })).toBe(false);
  });
});
