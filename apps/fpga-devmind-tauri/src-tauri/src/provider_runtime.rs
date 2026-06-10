/* ------------------------------------------------------------------ */
/*  T047: Ephemeral Real Provider Runtime                             */
/*  Rust Tauri command for OpenAI-compatible provider invocation.     */
/*  API key is received as parameter but NEVER returned or logged.    */
/* ------------------------------------------------------------------ */

use serde::{Deserialize, Serialize};

/// Request body for OpenAI-compatible chat completions API.
#[derive(Serialize)]
struct OpenAiChatRequest {
    model: String,
    messages: Vec<OpenAiMessage>,
    #[serde(skip_serializing_if = "Option::is_none")]
    max_tokens: Option<u32>,
}

#[derive(Serialize)]
struct OpenAiMessage {
    role: String,
    content: String,
}

/// Minimal response structure — we only extract the text preview.
#[derive(Deserialize, Debug)]
struct OpenAiChatResponse {
    choices: Vec<OpenAiChoice>,
}

#[derive(Deserialize, Debug)]
struct OpenAiChoice {
    message: Option<OpenAiChoiceMessage>,
}

#[derive(Deserialize, Debug)]
struct OpenAiChoiceMessage {
    content: Option<String>,
}

/// Result returned to the frontend.
/// Never contains the API key.
#[derive(Serialize, Debug, Clone)]
pub struct RealProviderInvocationResult {
    pub schema_version: String,
    pub request_id: String,
    pub provider_id: String,
    pub sent: bool,
    pub blocked: bool,
    pub status: String,
    pub answer_text_preview: String,
    pub error_preview: Option<String>,
    pub raw_response_stored: bool,
    pub audit_redacted: bool,
    pub created_at: String,
}

const RESULT_SCHEMA_VERSION: &str = "real-provider-contract-0.1";
const RESPONSE_PREVIEW_MAX_CHARS: usize = 4000;
const REQUEST_TIMEOUT_SECS: u64 = 60;

/// Validate an endpoint URL for security.
///
/// Rules:
/// - Must start with https://
/// - Must NOT start with http://, file://, ftp://
/// - Must NOT be localhost (unless explicitly allowed for dev)
fn validate_endpoint_url(url: &str) -> Result<(), String> {
    let trimmed = url.trim();
    if trimmed.is_empty() {
        return Err("Endpoint URL is empty".to_string());
    }
    if !trimmed.starts_with("https://") {
        return Err("Endpoint URL must use HTTPS".to_string());
    }
    if trimmed.starts_with("http://")
        || trimmed.starts_with("file://")
        || trimmed.starts_with("ftp://")
    {
        return Err("Endpoint URL scheme is not allowed".to_string());
    }
    // Block localhost / 127.0.0.1 to prevent accidental local service calls
    let lower = trimmed.to_lowercase();
    if lower.contains("localhost")
        || lower.contains("127.0.0.1")
        || lower.contains("::1")
    {
        return Err("Localhost endpoints are not allowed in T047".to_string());
    }
    Ok(())
}

/// Redact an error message to ensure no API key or sensitive data leaks.
fn redact_error(err: &str) -> String {
    let mut redacted = err.to_string();
    // Replace common API key prefixes
    for prefix in ["sk-", "sk_live_", "sk_test_", "Bearer ", "Authorization: "] {
        if let Some(idx) = redacted.find(prefix) {
            let end = redacted[idx..]
                .find(|c: char| c.is_whitespace() || c == '\n' || c == '\r' || c == '"' || c == '\'')
                .map(|i| idx + i)
                .unwrap_or(redacted.len());
            if end > idx + prefix.len() + 4 {
                redacted.replace_range(idx + prefix.len()..end, "***REDACTED***");
            }
        }
    }
    // If the error still looks like it contains a key, replace the whole thing
    if redacted.contains("sk-") || redacted.contains("Bearer ") {
        redacted = "Error redacted: possible sensitive content detected.".to_string();
    }
    redacted
}

/// Truncate a response to the preview max length.
fn truncate_preview(text: &str) -> String {
    if text.len() <= RESPONSE_PREVIEW_MAX_CHARS {
        text.to_string()
    } else {
        format!("{}...(truncated)", &text[..RESPONSE_PREVIEW_MAX_CHARS])
    }
}

/// Invoke an OpenAI-compatible provider via the Tauri backend.
///
/// # Security guarantees
/// - API key is a function-local String, never logged, never returned.
/// - Only HTTPS endpoints are allowed.
/// - Response is truncated to a preview.
/// - Errors are redacted.
/// - No raw response is stored on disk.
#[tauri::command]
pub async fn invoke_openai_compatible_ephemeral(
    endpoint_url: String,
    model_name: String,
    api_key: String,
    system_prompt: String,
    user_prompt: String,
    request_id: String,
) -> Result<RealProviderInvocationResult, String> {
    let created_at = chrono::Utc::now().to_rfc3339();

    // 1. Validate endpoint
    if let Err(e) = validate_endpoint_url(&endpoint_url) {
        return Ok(RealProviderInvocationResult {
            schema_version: RESULT_SCHEMA_VERSION.to_string(),
            request_id: request_id.clone(),
            provider_id: "openai_compatible_ephemeral".to_string(),
            sent: false,
            blocked: true,
            status: "blocked".to_string(),
            answer_text_preview: String::new(),
            error_preview: Some(e),
            raw_response_stored: false,
            audit_redacted: true,
            created_at,
        });
    }

    // 2. Build request body
    let chat_request = OpenAiChatRequest {
        model: model_name.clone(),
        messages: vec![
            OpenAiMessage {
                role: "system".to_string(),
                content: system_prompt,
            },
            OpenAiMessage {
                role: "user".to_string(),
                content: user_prompt,
            },
        ],
        max_tokens: Some(2048),
    };

    let request_body = serde_json::to_string(&chat_request)
        .map_err(|e| format!("Failed to serialize request: {}", e))?;

    // 3. Create HTTP client with timeout
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(REQUEST_TIMEOUT_SECS))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    // 4. Send request — api_key is used in the header but never logged
    let response = client
        .post(&endpoint_url)
        .header("Content-Type", "application/json")
        .header("Authorization", format!("Bearer {}", api_key))
        .body(request_body)
        .send()
        .await;

    match response {
        Ok(resp) => {
            let status = resp.status();
            let body_text = resp
                .text()
                .await
                .unwrap_or_else(|_| "(empty body)".to_string());

            if status.is_success() {
                // Parse response
                match serde_json::from_str::<OpenAiChatResponse>(&body_text) {
                    Ok(chat_resp) => {
                        let answer = chat_resp
                            .choices
                            .get(0)
                            .and_then(|c| c.message.as_ref())
                            .and_then(|m| m.content.as_ref())
                            .map(|s| s.as_str())
                            .unwrap_or("(no content in response)");

                        Ok(RealProviderInvocationResult {
                            schema_version: RESULT_SCHEMA_VERSION.to_string(),
                            request_id: request_id.clone(),
                            provider_id: "openai_compatible_ephemeral".to_string(),
                            sent: true,
                            blocked: false,
                            status: "sent".to_string(),
                            answer_text_preview: truncate_preview(answer),
                            error_preview: None,
                            raw_response_stored: false,
                            audit_redacted: true,
                            created_at,
                        })
                    }
                    Err(parse_err) => Ok(RealProviderInvocationResult {
                        schema_version: RESULT_SCHEMA_VERSION.to_string(),
                        request_id: request_id.clone(),
                        provider_id: "openai_compatible_ephemeral".to_string(),
                        sent: true,
                        blocked: false,
                        status: "redaction_error".to_string(),
                        answer_text_preview: String::new(),
                        error_preview: Some(format!(
                            "Provider returned success but response could not be parsed: {}",
                            parse_err
                        )),
                        raw_response_stored: false,
                        audit_redacted: true,
                        created_at,
                    }),
                }
            } else {
                // Provider error (non-2xx)
                let err_msg = format!("Provider returned HTTP {}: {}", status, body_text);
                Ok(RealProviderInvocationResult {
                    schema_version: RESULT_SCHEMA_VERSION.to_string(),
                    request_id: request_id.clone(),
                    provider_id: "openai_compatible_ephemeral".to_string(),
                    sent: true,
                    blocked: false,
                    status: "provider_error".to_string(),
                    answer_text_preview: String::new(),
                    error_preview: Some(redact_error(&err_msg)),
                    raw_response_stored: false,
                    audit_redacted: true,
                    created_at,
                })
            }
        }
        Err(network_err) => {
            let err_msg = format!("Network error: {}", network_err);
            Ok(RealProviderInvocationResult {
                schema_version: RESULT_SCHEMA_VERSION.to_string(),
                request_id: request_id.clone(),
                provider_id: "openai_compatible_ephemeral".to_string(),
                sent: false,
                blocked: true,
                status: "network_error".to_string(),
                answer_text_preview: String::new(),
                error_preview: Some(redact_error(&err_msg)),
                raw_response_stored: false,
                audit_redacted: true,
                created_at,
            })
        }
    }
}
