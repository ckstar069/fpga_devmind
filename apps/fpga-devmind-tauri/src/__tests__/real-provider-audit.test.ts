import { describe, it, expect, beforeEach } from "vitest";
import {
  buildRealProviderAuditSummary,
  appendRealProviderAudit,
  getRealProviderAudits,
  clearRealProviderAudits,
  REAL_PROVIDER_AUDIT_VERSION,
} from "../agent/realProviderAudit";

describe("T047 Real Provider Audit", () => {
  beforeEach(() => {
    clearRealProviderAudits();
  });

  it("audit version is correct", () => {
    expect(REAL_PROVIDER_AUDIT_VERSION).toBe("real-provider-audit-0.1");
  });

  it("audit summary does not contain raw key", () => {
    const summary = buildRealProviderAuditSummary(
      "req-test",
      "openai_compatible_ephemeral",
      "gpt-4o-mini",
      "https://api.example.com",
      "sk-...abcd",
      true,
      "sent",
      "This is the answer preview."
    );
    const serialized = JSON.stringify(summary);
    expect(serialized).not.toContain("sk-live-");
    expect(serialized).not.toContain("sk-test-");
    expect(serialized).not.toContain("secret");
  });

  it("audit summary does not contain raw prompt", () => {
    const summary = buildRealProviderAuditSummary(
      "req-test",
      "openai_compatible_ephemeral",
      "gpt-4o-mini",
      "https://api.example.com",
      "sk-...abcd",
      true,
      "sent",
      "Answer preview only."
    );
    const serialized = JSON.stringify(summary);
    // There should be no full messages, no system prompt, no user prompt
    expect(serialized).not.toContain("system prompt");
    expect(serialized).not.toContain("user prompt");
    // Only answer_preview_chars is stored, not the text itself
    expect(summary.answer_preview_chars).toBe(20);
  });

  it("audit summary does not contain raw response", () => {
    const summary = buildRealProviderAuditSummary(
      "req-test",
      "openai_compatible_ephemeral",
      "gpt-4o-mini",
      "https://api.example.com",
      "sk-...abcd",
      true,
      "sent",
      "Short preview."
    );
    expect(summary.raw_response_stored).toBe(false);
    expect(summary.raw_prompt_stored).toBe(false);
    expect(summary.raw_key_stored).toBe(false);
  });

  it("raw_key_stored is always false", () => {
    const summary = buildRealProviderAuditSummary(
      "req-test",
      "openai_compatible_ephemeral",
      "gpt-4o-mini",
      "https://api.example.com",
      "sk-...abcd",
      false,
      "blocked",
      ""
    );
    expect(summary.raw_key_stored).toBe(false);
  });

  it("raw_prompt_stored is always false", () => {
    const summary = buildRealProviderAuditSummary(
      "req-test",
      "openai_compatible_ephemeral",
      "gpt-4o-mini",
      "https://api.example.com",
      "sk-...abcd",
      true,
      "sent",
      "Answer."
    );
    expect(summary.raw_prompt_stored).toBe(false);
  });

  it("raw_response_stored is always false", () => {
    const summary = buildRealProviderAuditSummary(
      "req-test",
      "openai_compatible_ephemeral",
      "gpt-4o-mini",
      "https://api.example.com",
      "sk-...abcd",
      true,
      "sent",
      "Answer."
    );
    expect(summary.raw_response_stored).toBe(false);
  });

  it("key_fingerprint can be displayed", () => {
    const summary = buildRealProviderAuditSummary(
      "req-test",
      "openai_compatible_ephemeral",
      "gpt-4o-mini",
      "https://api.example.com",
      "sk-...abcd",
      true,
      "sent",
      "Answer."
    );
    expect(summary.key_fingerprint).toBe("sk-...abcd");
  });

  it("endpoint_origin_preview does not contain full path or query", () => {
    const summary = buildRealProviderAuditSummary(
      "req-test",
      "openai_compatible_ephemeral",
      "gpt-4o-mini",
      "https://api.example.com",
      null,
      true,
      "sent",
      "Answer."
    );
    // The origin preview should be just scheme + host
    expect(summary.endpoint_origin_preview).not.toContain("/v1/");
    expect(summary.endpoint_origin_preview).not.toContain("?key=");
  });

  it("audit log append and get work", () => {
    const summary = buildRealProviderAuditSummary(
      "req-1",
      "openai_compatible_ephemeral",
      "gpt-4o-mini",
      "https://api.example.com",
      "sk-...abcd",
      true,
      "sent",
      "Answer."
    );
    appendRealProviderAudit(summary);
    const audits = getRealProviderAudits();
    expect(audits.length).toBe(1);
    expect(audits[0].request_id).toBe("req-1");
  });

  it("audit log clear works", () => {
    const summary = buildRealProviderAuditSummary(
      "req-1",
      "openai_compatible_ephemeral",
      "gpt-4o-mini",
      "https://api.example.com",
      "sk-...abcd",
      true,
      "sent",
      "Answer."
    );
    appendRealProviderAudit(summary);
    expect(getRealProviderAudits().length).toBe(1);
    clearRealProviderAudits();
    expect(getRealProviderAudits().length).toBe(0);
  });

  it("audit summary created_at is valid ISO string", () => {
    const summary = buildRealProviderAuditSummary(
      "req-test",
      "openai_compatible_ephemeral",
      "gpt-4o-mini",
      "https://api.example.com",
      "sk-...abcd",
      true,
      "sent",
      "Answer."
    );
    expect(new Date(summary.created_at).toISOString()).toBe(summary.created_at);
  });
});
