/* ------------------------------------------------------------------ */
/*  T045: External Request Package                                    */
/*  Standardized request package for future external provider review. */
/*  Still blocked by policy.  No network send.  No secrets.           */
/* ------------------------------------------------------------------ */

import type { ProjectBundle } from "../types";
import { buildDryRunExternalRequestPlan, type ExternalRequestPlan } from "./requestPlan";
import type { LlmContextBundle } from "./contextBuilder";
import { PROVIDER_POLICY_VERSION } from "./policy";

export const EXTERNAL_REQUEST_PACKAGE_VERSION = "external-request-package-0.1";

export interface ExternalRequestPackage {
  schema_version: string;
  dry_run: true;
  send_allowed: false;
  approval_required: true;
  approval_state: "not_requested" | "previewed" | "approved_but_blocked" | "denied";
  provider_kind: "external_disabled";
  policy_version: string;
  created_at: string;
  request_id: string;

  /** Question preview (redacted if sensitive) */
  question_preview: string;
  selected_node_id: string | null;

  context_bundle: LlmContextBundle;
  request_plan: ExternalRequestPlan;

  request_body_preview: {
    model_name: string;
    messages_preview: {
      role: "system" | "user";
      content_preview: string;
    }[];
    context_items_count: number;
    total_tokens_estimate: number;
  };

  risk_summary: {
    contains_sensitive_question: boolean;
    raw_question_included: false;
    api_key_required: false;
    network_call_planned: false;
    secret_storage_planned: false;
    external_call_blocked_by_policy: true;
  };

  artifacts_used: string[];
  evidence_ids: string[];
  source_files: string[];
  limitations: string[];
}

/** Build an external request package for developer review.
 *
 *  This function NEVER calls an external API.
 *  The package is always blocked by policy (send_allowed=false).
 *  The question_preview is always redacted if it contains sensitive content.
 */
export function buildExternalRequestPackage(
  bundle: ProjectBundle | null,
  question: string,
  selectedNodeId: string | null
): ExternalRequestPackage {
  // T044: Build the dry-run request plan (already redacts question)
  const requestPlan = buildDryRunExternalRequestPlan(bundle, question, selectedNodeId);
  const contextBundle = requestPlan.context_bundle;

  // T045: Determine if the question is sensitive from the preview
  const isSensitive = contextBundle.question_preview.includes("redacted");

  // Build request body preview — only use redacted preview
  const messagesPreview = [
    {
      role: "system" as const,
      content_preview: requestPlan.hypothetical_request_preview.system_prompt_preview,
    },
    {
      role: "user" as const,
      content_preview: requestPlan.hypothetical_request_preview.user_prompt_preview,
    },
  ];

  const requestId = generateRequestId();

  return {
    schema_version: EXTERNAL_REQUEST_PACKAGE_VERSION,
    dry_run: true,
    send_allowed: false,
    approval_required: true,
    approval_state: "not_requested",
    provider_kind: "external_disabled",
    policy_version: PROVIDER_POLICY_VERSION,
    created_at: new Date().toISOString(),
    request_id: requestId,
    question_preview: contextBundle.question_preview,
    selected_node_id: selectedNodeId,
    context_bundle: contextBundle,
    request_plan: requestPlan,
    request_body_preview: {
      model_name: requestPlan.hypothetical_request_preview.model_name,
      messages_preview: messagesPreview,
      context_items_count: contextBundle.context_items.length,
      total_tokens_estimate: contextBundle.token_estimate_rough,
    },
    risk_summary: {
      contains_sensitive_question: isSensitive,
      raw_question_included: false,
      api_key_required: false,
      network_call_planned: false,
      secret_storage_planned: false,
      external_call_blocked_by_policy: true,
    },
    artifacts_used: requestPlan.artifacts_used,
    evidence_ids: requestPlan.evidence_ids,
    source_files: requestPlan.source_files,
    limitations: [
      "T045: External request package is for developer review only — no network send.",
      "Approval is required but even approved requests remain blocked before network.",
      ...requestPlan.limitations,
    ],
  };
}

function generateRequestId(): string {
  const now = Date.now();
  const rand = Math.floor(Math.random() * 10000)
    .toString(16)
    .padStart(4, "0");
  return `req-${now}-${rand}`;
}
