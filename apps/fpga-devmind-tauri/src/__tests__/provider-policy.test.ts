import { describe, it, expect } from "vitest";
import {
  evaluateProviderPolicy,
  isExternalCallsAllowed,
  isProviderAllowed,
  PROVIDER_POLICY_VERSION,
} from "../agent/policy";

describe("T043 Provider Policy", () => {
  it("PROVIDER_POLICY_VERSION is t043.0", () => {
    expect(PROVIDER_POLICY_VERSION).toBe("t043.0");
  });

  it("deterministic is allowed", () => {
    const result = evaluateProviderPolicy({
      provider_kind: "deterministic",
      question: "test",
    });
    expect(result.allowed).toBe(true);
    expect(result.provider_kind).toBe("deterministic");
    expect(result.network_allowed).toBe(false);
    expect(result.requires_api_key).toBe(false);
    expect(result.external_calls_allowed).toBe(false);
    expect(result.secret_storage_allowed).toBe(false);
    expect(result.policy_version).toBe("t043.0");
    expect(result.reason).toContain("确定性");
    expect(result.limitations.length).toBeGreaterThan(0);
  });

  it("offline_mock is allowed", () => {
    const result = evaluateProviderPolicy({
      provider_kind: "offline_mock",
      question: "test",
    });
    expect(result.allowed).toBe(true);
    expect(result.provider_kind).toBe("offline_mock");
    expect(result.network_allowed).toBe(false);
    expect(result.requires_api_key).toBe(false);
    expect(result.external_calls_allowed).toBe(false);
    expect(result.secret_storage_allowed).toBe(false);
    expect(result.policy_version).toBe("t043.0");
    expect(result.reason).toContain("Offline Mock");
    expect(result.limitations.length).toBeGreaterThan(0);
  });

  it("external_disabled is denied", () => {
    const result = evaluateProviderPolicy({
      provider_kind: "external_disabled",
      question: "test",
    });
    expect(result.allowed).toBe(false);
    expect(result.provider_kind).toBe("external_disabled");
    expect(result.network_allowed).toBe(false);
    expect(result.requires_api_key).toBe(true);
    expect(result.external_calls_allowed).toBe(false);
    expect(result.secret_storage_allowed).toBe(false);
    expect(result.policy_version).toBe("t043.0");
    expect(result.reason).toContain("禁用");
    expect(result.limitations.length).toBeGreaterThanOrEqual(2);
  });

  it("unknown provider is denied", () => {
    const result = evaluateProviderPolicy({
      provider_kind: "llm_gpt4" as any,
      question: "test",
    });
    expect(result.allowed).toBe(false);
    expect(result.provider_kind).toBe("llm_gpt4");
    expect(result.network_allowed).toBe(false);
    expect(result.external_calls_allowed).toBe(false);
    expect(result.secret_storage_allowed).toBe(false);
    expect(result.reason).toContain("未知");
  });

  it("all providers have network_allowed=false", () => {
    const kinds = ["deterministic", "offline_mock", "external_disabled"] as const;
    for (const kind of kinds) {
      const result = evaluateProviderPolicy({ provider_kind: kind, question: "" });
      expect(result.network_allowed).toBe(false);
    }
  });

  it("all providers have secret_storage_allowed=false", () => {
    const kinds = ["deterministic", "offline_mock", "external_disabled"] as const;
    for (const kind of kinds) {
      const result = evaluateProviderPolicy({ provider_kind: kind, question: "" });
      expect(result.secret_storage_allowed).toBe(false);
    }
  });

  it("isExternalCallsAllowed returns false for all", () => {
    expect(isExternalCallsAllowed("deterministic")).toBe(false);
    expect(isExternalCallsAllowed("offline_mock")).toBe(false);
    expect(isExternalCallsAllowed("external_disabled")).toBe(false);
  });

  it("isProviderAllowed matches evaluateProviderPolicy", () => {
    expect(isProviderAllowed("deterministic")).toBe(true);
    expect(isProviderAllowed("offline_mock")).toBe(true);
    expect(isProviderAllowed("external_disabled")).toBe(false);
  });
});
