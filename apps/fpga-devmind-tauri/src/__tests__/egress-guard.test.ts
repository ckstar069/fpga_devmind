import { describe, it, expect } from "vitest";
import {
  evaluateEgressGuard,
  EGRESS_GUARD_VERSION,
} from "../agent/egressGuard";

describe("T046 Egress Guard", () => {
  it("version is correct", () => {
    expect(EGRESS_GUARD_VERSION).toBe("egress-guard-0.1");
  });

  it("always returns allowed=false", () => {
    const states = [
      "not_requested",
      "previewed",
      "approved_but_blocked",
      "denied",
    ] as const;

    for (const state of states) {
      const decision = evaluateEgressGuard({
        provider_id: "mock_external_llm",
        request_id: "req-test-123",
        approval_state: state,
        send_allowed: false,
        policy_version: "t043.0",
      });
      expect(decision.allowed, `state=${state} should be blocked`).toBe(false);
    }
  });

  it("approved_but_blocked reason mentions T046", () => {
    const decision = evaluateEgressGuard({
      provider_id: "mock_external_llm",
      request_id: "req-test-123",
      approval_state: "approved_but_blocked",
      send_allowed: false,
      policy_version: "t043.0",
    });
    expect(decision.reason).toContain("T046");
    expect(decision.reason).toContain("blocked");
    expect(decision.reason).toContain("network");
  });

  it("previewed reason mentions previewed state", () => {
    const decision = evaluateEgressGuard({
      provider_id: "mock_external_llm",
      request_id: "req-test-123",
      approval_state: "previewed",
      send_allowed: false,
      policy_version: "t043.0",
    });
    expect(decision.reason).toContain("previewed");
    expect(decision.reason).toContain("Blocked");
  });

  it("denied reason mentions denied state", () => {
    const decision = evaluateEgressGuard({
      provider_id: "mock_external_llm",
      request_id: "req-test-123",
      approval_state: "denied",
      send_allowed: false,
      policy_version: "t043.0",
    });
    expect(decision.reason).toContain("denied");
    expect(decision.reason).toContain("Blocked");
  });

  it("not_requested reason mentions not requested", () => {
    const decision = evaluateEgressGuard({
      provider_id: "mock_external_llm",
      request_id: "req-test-123",
      approval_state: "not_requested",
      send_allowed: false,
      policy_version: "t043.0",
    });
    expect(decision.reason).toContain("not requested");
    expect(decision.reason).toContain("Blocked");
  });

  it("future provider reason mentions placeholder", () => {
    const decision = evaluateEgressGuard({
      provider_id: "future_openai",
      request_id: "req-test-123",
      approval_state: "approved_but_blocked",
      send_allowed: false,
      policy_version: "t043.0",
    });
    expect(decision.reason).toContain("placeholder");
    expect(decision.reason).toContain("future");
  });

  it("forged send_allowed=true still blocked", () => {
    const decision = evaluateEgressGuard({
      provider_id: "mock_external_llm",
      request_id: "req-test-123",
      approval_state: "approved_but_blocked",
      send_allowed: true,
      policy_version: "t043.0",
    });
    expect(decision.allowed).toBe(false);
    expect(decision.reason).toContain("send_allowed=true");
    expect(decision.reason).toContain("overridden");
  });

  it("decision contains required fields", () => {
    const decision = evaluateEgressGuard({
      provider_id: "mock_external_llm",
      request_id: "req-test-456",
      approval_state: "previewed",
      send_allowed: false,
      policy_version: "t043.0",
    });
    expect(decision.schema_version).toBe(EGRESS_GUARD_VERSION);
    expect(decision.network_allowed).toBe(false);
    expect(decision.external_calls_allowed).toBe(false);
    expect(decision.provider_id).toBe("mock_external_llm");
    expect(decision.request_id).toBe("req-test-456");
    expect(decision.checked_at).toBeTruthy();
    expect(new Date(decision.checked_at).toISOString()).toBe(decision.checked_at);
  });

  it("JSON serialization does not contain raw sensitive question", () => {
    const decision = evaluateEgressGuard({
      provider_id: "mock_external_llm",
      request_id: "req-test-789",
      approval_state: "approved_but_blocked",
      send_allowed: false,
      policy_version: "t043.0",
    });
    const serialized = JSON.stringify(decision);
    expect(serialized).not.toContain("api_key");
    expect(serialized).not.toContain("sk-");
    expect(serialized).not.toContain("ghp_");
    expect(serialized).not.toContain("token");
    expect(serialized).not.toContain("bearer");
    expect(serialized).not.toContain("password");
  });
});
