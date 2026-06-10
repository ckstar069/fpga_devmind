/* ------------------------------------------------------------------ */
/*  T043: Provider Run Audit Event                                    */
/*  Local run log — NOT project audit/finding.                        */
/*  Records what happened during each provider invocation.            */
/*  No disk write, no API key, no sensitive input.                    */
/* ------------------------------------------------------------------ */

import type { AgentProviderKind, AgentRunResult } from "./providers";
import type { ProviderPolicyResult } from "./policy";

/** A single provider run audit event */
export interface ProviderRunAuditEvent {
  event_id: string;
  timestamp: string;
  provider_kind: AgentProviderKind;
  question_preview: string;
  policy_allowed: boolean;
  policy_reason: string;
  external_calls_made: boolean;
  network_allowed: boolean;
  artifacts_used: string[];
  trace_id: string;
  limitations: string[];
  policy_version: string;
}

/** Build a preview of the question (max 80 chars) */
export function buildQuestionPreview(question: string): string {
  const trimmed = question.trim();
  if (trimmed.length <= 80) return trimmed;
  return trimmed.slice(0, 77) + "...";
}

/** Generate an event ID */
function generateEventId(): string {
  const now = Date.now();
  const rand = Math.floor(Math.random() * 10000)
    .toString(16)
    .padStart(4, "0");
  return `audit-${now}-${rand}`;
}

/** Build an audit event from a completed run.
 *
 * Does NOT write to disk.
 * Does NOT include full question (only preview).
 * Does NOT include API key or any secret.
 */
export function buildProviderRunAuditEvent(
  runResult: AgentRunResult,
  policyResult: ProviderPolicyResult,
  question: string
): ProviderRunAuditEvent {
  return {
    event_id: generateEventId(),
    timestamp: new Date().toISOString(),
    provider_kind: runResult.provider,
    question_preview: buildQuestionPreview(question),
    policy_allowed: policyResult.allowed,
    policy_reason: policyResult.reason,
    external_calls_made: runResult.external_calls_made,
    network_allowed: policyResult.network_allowed,
    artifacts_used: runResult.artifacts_used,
    trace_id: runResult.trace.trace_id,
    limitations: [...runResult.limitations, ...policyResult.limitations],
    policy_version: policyResult.policy_version,
  };
}

/** In-memory audit log — session only, not persisted.
 *  This is a singleton-like module-level array.
 *  In a real app this might be a React context or a service.
 */
const _inMemoryAuditLog: ProviderRunAuditEvent[] = [];

/** Append an event to the in-memory audit log */
export function appendAuditEvent(event: ProviderRunAuditEvent): void {
  _inMemoryAuditLog.push(event);
}

/** Get a copy of all audit events */
export function getAuditEvents(): ProviderRunAuditEvent[] {
  return [..._inMemoryAuditLog];
}

/** Get the last N audit events (most recent first) */
export function getRecentAuditEvents(n: number): ProviderRunAuditEvent[] {
  return [..._inMemoryAuditLog].reverse().slice(0, n);
}

/** Count how many runs each provider had */
export function getAuditStats(): Record<
  AgentProviderKind,
  { runs: number; allowed: number; denied: number }
> {
  const stats: Record<
    AgentProviderKind,
    { runs: number; allowed: number; denied: number }
  > = {
    deterministic: { runs: 0, allowed: 0, denied: 0 },
    offline_mock: { runs: 0, allowed: 0, denied: 0 },
    external_disabled: { runs: 0, allowed: 0, denied: 0 },
  };
  for (const ev of _inMemoryAuditLog) {
    const s = stats[ev.provider_kind];
    s.runs += 1;
    if (ev.policy_allowed) s.allowed += 1;
    else s.denied += 1;
  }
  return stats;
}

/** Clear the audit log (useful for testing) */
export function clearAuditLog(): void {
  _inMemoryAuditLog.length = 0;
}
