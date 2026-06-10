import { describe, it, expect } from "vitest";
import {
  evaluateEgressGuard,
  evaluateRealSendGate,
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

describe("T047 Real Send Gate", () => {
  const makeSession = (configured: boolean): any => ({
    configured,
    key_present: configured,
    key_fingerprint: configured ? "sk-a...wxyz" : null,
    endpoint_origin_preview: configured ? "https://api.openai.com" : "",
  });

  it("rejects future_openai provider_id", () => {
    const gate = evaluateRealSendGate({
      provider_id: "future_openai",
      request_id: "req-test",
      approval_state: "approved_but_blocked",
      send_allowed_by_user: true,
      session: makeSession(true),
      endpoint_url: "https://api.openai.com/v1",
    });
    expect(gate.allowed).toBe(false);
    expect(gate.reason).toContain("provider is not openai_compatible_ephemeral");
    expect(gate.conditions_met.provider_allowed).toBe(false);
  });

  it("rejects mock_external_llm provider_id", () => {
    const gate = evaluateRealSendGate({
      provider_id: "mock_external_llm",
      request_id: "req-test",
      approval_state: "approved_but_blocked",
      send_allowed_by_user: true,
      session: makeSession(true),
      endpoint_url: "https://api.openai.com/v1",
    });
    expect(gate.allowed).toBe(false);
    expect(gate.conditions_met.provider_allowed).toBe(false);
  });

  it("rejects send_allowed_by_user=false", () => {
    const gate = evaluateRealSendGate({
      provider_id: "openai_compatible_ephemeral",
      request_id: "req-test",
      approval_state: "approved_but_blocked",
      send_allowed_by_user: false,
      session: makeSession(true),
      endpoint_url: "https://api.openai.com/v1",
    });
    expect(gate.allowed).toBe(false);
    expect(gate.reason).toContain("user did not explicitly allow send");
  });

  it("allows only when all 6 conditions are met", () => {
    const gate = evaluateRealSendGate({
      provider_id: "openai_compatible_ephemeral",
      request_id: "req-test",
      approval_state: "approved_but_blocked",
      send_allowed_by_user: true,
      session: makeSession(true),
      endpoint_url: "https://api.openai.com/v1",
    });
    expect(gate.allowed).toBe(true);
    expect(gate.conditions_met.provider_allowed).toBe(true);
    expect(gate.conditions_met.session_configured).toBe(true);
    expect(gate.conditions_met.key_present).toBe(true);
    expect(gate.conditions_met.endpoint_https).toBe(true);
    expect(gate.conditions_met.approval_adequate).toBe(true);
    expect(gate.conditions_met.user_explicit_consent).toBe(true);
  });

  it("conditions_met contains provider_allowed field", () => {
    const gate = evaluateRealSendGate({
      provider_id: "openai_compatible_ephemeral",
      request_id: "req-test",
      approval_state: "approved_but_blocked",
      send_allowed_by_user: false,
      session: makeSession(true),
      endpoint_url: "https://api.openai.com/v1",
    });
    expect(gate.conditions_met).toHaveProperty("provider_allowed");
  });

  it("rejects missing session", () => {
    const gate = evaluateRealSendGate({
      provider_id: "openai_compatible_ephemeral",
      request_id: "req-test",
      approval_state: "approved_but_blocked",
      send_allowed_by_user: true,
      session: null,
      endpoint_url: "https://api.openai.com/v1",
    });
    expect(gate.allowed).toBe(false);
    expect(gate.conditions_met.session_configured).toBe(false);
    expect(gate.conditions_met.key_present).toBe(false);
  });

  it("rejects non-HTTPS endpoint", () => {
    const gate = evaluateRealSendGate({
      provider_id: "openai_compatible_ephemeral",
      request_id: "req-test",
      approval_state: "approved_but_blocked",
      send_allowed_by_user: true,
      session: makeSession(true),
      endpoint_url: "http://api.openai.com/v1",
    });
    expect(gate.allowed).toBe(false);
    expect(gate.conditions_met.endpoint_https).toBe(false);
  });

  it("rejects non-approved approval_state", () => {
    const gate = evaluateRealSendGate({
      provider_id: "openai_compatible_ephemeral",
      request_id: "req-test",
      approval_state: "previewed",
      send_allowed_by_user: true,
      session: makeSession(true),
      endpoint_url: "https://api.openai.com/v1",
    });
    expect(gate.allowed).toBe(false);
    expect(gate.conditions_met.approval_adequate).toBe(false);
  });
});
