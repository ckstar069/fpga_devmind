import { describe, it, expect, beforeEach } from "vitest";
import {
  buildProviderRunAuditEvent,
  buildQuestionPreview,
  appendAuditEvent,
  getAuditEvents,
  getRecentAuditEvents,
  getAuditStats,
  clearAuditLog,
} from "../agent/audit";
import { evaluateProviderPolicy } from "../agent/policy";
import { deterministicProvider } from "../agent/deterministicProvider";
import { externalDisabledProvider } from "../agent/externalDisabledProvider";
import type { ProjectBundle } from "../types";

function makeTestBundle(): ProjectBundle {
  return {
    path: "/tmp/test_bundle",
    graph: {
      schema_version: "project-understanding-0.1",
      project_id: "test_project",
      nodes: [
        { node_id: "P1", label: "test_project", kind: "project", stage: "", confidence: "supported" },
      ],
      edges: [],
    },
    index: {
      schema_version: "project-understanding-0.1",
      project_id: "test_project",
      concept_index: {},
      claim_index: {},
      evidence_index: {},
    },
    metadata: {
      schema_version: "p1b-project-run-metadata-0.1",
      command: "p1b-trace-project",
      project_root: "/tmp/test",
      concepts_processed: [],
      status: "ok",
      mapping_claims: 0,
      evidence_items: 0,
      diagnostics: 0,
    },
  };
}

describe("T043 Provider Audit", () => {
  beforeEach(() => {
    clearAuditLog();
  });

  it("buildQuestionPreview truncates at 80 chars", () => {
    const short = "hello world";
    expect(buildQuestionPreview(short)).toBe("hello world");

    const long = "a".repeat(100);
    const preview = buildQuestionPreview(long);
    expect(preview.length).toBe(80);
    expect(preview.endsWith("...")).toBe(true);
  });

  it("buildQuestionPreview does not modify short questions", () => {
    const q = "这个项目整体实现了什么？";
    expect(buildQuestionPreview(q)).toBe(q);
  });

  it("buildProviderRunAuditEvent generates event_id", () => {
    const bundle = makeTestBundle();
    const result = deterministicProvider.run({
      question: "test",
      selectedNodeId: null,
      bundle,
      providerKind: "deterministic",
    });
    const policy = evaluateProviderPolicy({ provider_kind: "deterministic", question: "test" });
    const event = buildProviderRunAuditEvent(result, policy, "test");

    expect(event.event_id).toMatch(/^audit-/);
    expect(event.timestamp).toBeTruthy();
    expect(event.provider_kind).toBe("deterministic");
    expect(event.policy_allowed).toBe(true);
    expect(event.external_calls_made).toBe(false);
    expect(event.network_allowed).toBe(false);
    expect(event.artifacts_used.length).toBeGreaterThanOrEqual(0);
    expect(event.trace_id).toBe(result.trace.trace_id);
    expect(event.policy_version).toBe("t043.0");
  });

  it("audit event question_preview does not contain full long question", () => {
    const bundle = makeTestBundle();
    const longQuestion = "a".repeat(200);
    const result = deterministicProvider.run({
      question: longQuestion,
      selectedNodeId: null,
      bundle,
      providerKind: "deterministic",
    });
    const policy = evaluateProviderPolicy({ provider_kind: "deterministic", question: longQuestion });
    const event = buildProviderRunAuditEvent(result, policy, longQuestion);

    expect(event.question_preview.length).toBeLessThanOrEqual(80);
    expect(event.question_preview).not.toBe(longQuestion);
  });

  it("audit event for denied provider records denied status", () => {
    const result = externalDisabledProvider.run({
      question: "test",
      selectedNodeId: null,
      bundle: null,
      providerKind: "external_disabled",
    });
    const policy = evaluateProviderPolicy({ provider_kind: "external_disabled", question: "test" });
    const event = buildProviderRunAuditEvent(result, policy, "test");

    expect(event.policy_allowed).toBe(false);
    expect(event.external_calls_made).toBe(false);
    expect(event.artifacts_used).toEqual([]);
    expect(event.policy_reason).toContain("禁用");
  });

  it("audit event does not contain api key or secret", () => {
    const bundle = makeTestBundle();
    const result = deterministicProvider.run({
      question: "test",
      selectedNodeId: null,
      bundle,
      providerKind: "deterministic",
    });
    const policy = evaluateProviderPolicy({ provider_kind: "deterministic", question: "test" });
    const event = buildProviderRunAuditEvent(result, policy, "test");

    const eventJson = JSON.stringify(event).toLowerCase();
    expect(eventJson).not.toContain("api_key");
    expect(eventJson).not.toContain("apikey");
    expect(eventJson).not.toContain("secret");
    expect(eventJson).not.toContain("token");
    expect(eventJson).not.toContain("bearer");
    expect(eventJson).not.toContain("password");
  });

  it("in-memory audit log accumulates events", () => {
    expect(getAuditEvents().length).toBe(0);

    const bundle = makeTestBundle();
    const result = deterministicProvider.run({
      question: "q1",
      selectedNodeId: null,
      bundle,
      providerKind: "deterministic",
    });
    const policy = evaluateProviderPolicy({ provider_kind: "deterministic", question: "q1" });
    appendAuditEvent(buildProviderRunAuditEvent(result, policy, "q1"));

    expect(getAuditEvents().length).toBe(1);

    const result2 = deterministicProvider.run({
      question: "q2",
      selectedNodeId: null,
      bundle,
      providerKind: "deterministic",
    });
    const policy2 = evaluateProviderPolicy({ provider_kind: "deterministic", question: "q2" });
    appendAuditEvent(buildProviderRunAuditEvent(result2, policy2, "q2"));

    expect(getAuditEvents().length).toBe(2);
  });

  it("getRecentAuditEvents returns most recent first", () => {
    const bundle = makeTestBundle();
    for (let i = 0; i < 3; i++) {
      const result = deterministicProvider.run({
        question: `q${i}`,
        selectedNodeId: null,
        bundle,
        providerKind: "deterministic",
      });
      const policy = evaluateProviderPolicy({ provider_kind: "deterministic", question: `q${i}` });
      appendAuditEvent(buildProviderRunAuditEvent(result, policy, `q${i}`));
    }

    const recent = getRecentAuditEvents(2);
    expect(recent.length).toBe(2);
    // Most recent first
    expect(recent[0].question_preview).toBe("q2");
    expect(recent[1].question_preview).toBe("q1");
  });

  it("getAuditStats counts runs per provider", () => {
    const bundle = makeTestBundle();

    // deterministic run
    const r1 = deterministicProvider.run({ question: "d1", selectedNodeId: null, bundle, providerKind: "deterministic" });
    const p1 = evaluateProviderPolicy({ provider_kind: "deterministic", question: "d1" });
    appendAuditEvent(buildProviderRunAuditEvent(r1, p1, "d1"));

    // external_disabled run
    const r2 = externalDisabledProvider.run({ question: "e1", selectedNodeId: null, bundle: null, providerKind: "external_disabled" });
    const p2 = evaluateProviderPolicy({ provider_kind: "external_disabled", question: "e1" });
    appendAuditEvent(buildProviderRunAuditEvent(r2, p2, "e1"));

    const stats = getAuditStats();
    expect(stats.deterministic.runs).toBe(1);
    expect(stats.deterministic.allowed).toBe(1);
    expect(stats.external_disabled.runs).toBe(1);
    expect(stats.external_disabled.denied).toBe(1);
  });

  it("clearAuditLog empties the log", () => {
    const bundle = makeTestBundle();
    const result = deterministicProvider.run({ question: "test", selectedNodeId: null, bundle, providerKind: "deterministic" });
    const policy = evaluateProviderPolicy({ provider_kind: "deterministic", question: "test" });
    appendAuditEvent(buildProviderRunAuditEvent(result, policy, "test"));

    expect(getAuditEvents().length).toBe(1);
    clearAuditLog();
    expect(getAuditEvents().length).toBe(0);
  });
});
