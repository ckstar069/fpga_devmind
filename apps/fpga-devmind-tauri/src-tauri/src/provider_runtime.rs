/* ------------------------------------------------------------------ */
/*  T047/T047.1: Ephemeral Real Provider Runtime                      */
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
const ERROR_PREVIEW_MAX_CHARS: usize = 1000;
const REQUEST_TIMEOUT_SECS: u64 = 60;

/// Blocked before network: build a safe result without calling the provider.
fn blocked_before_network(
    request_id: &str,
    error_preview: &str,
    created_at: &str,
) -> Result<RealProviderInvocationResult, String> {
    Ok(RealProviderInvocationResult {
        schema_version: RESULT_SCHEMA_VERSION.to_string(),
        request_id: request_id.to_string(),
        provider_id: "openai_compatible_ephemeral".to_string(),
        sent: false,
        blocked: true,
        status: "blocked".to_string(),
        answer_text_preview: String::new(),
        error_preview: Some(redact_error(error_preview).to_string()),
        raw_response_stored: false,
        audit_redacted: true,
        created_at: created_at.to_string(),
    })
}

/* ------------------------------------------------------------------ */
/*  Endpoint validation                                               */
/* ------------------------------------------------------------------ */

/// Validate an endpoint URL for security.
///
/// Rules:
/// - Must be parseable as URL
/// - Scheme must be https
/// - Must NOT use http://, file://, ftp://, etc.
/// - Must NOT be localhost, 127.0.0.0/8, ::1, 0.0.0.0
/// - Must NOT be private IPv4 ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
/// - Query string must NOT contain secret-like parameters (api_key, key, token, password, secret)
fn validate_endpoint_url(url: &str) -> Result<(), String> {
    let trimmed = url.trim();
    if trimmed.is_empty() {
        return Err("Endpoint URL is empty".to_string());
    }

    let parsed = match url::Url::parse(trimmed) {
        Ok(u) => u,
        Err(_) => return Err("Endpoint URL is not valid".to_string()),
    };

    // Scheme must be https
    if parsed.scheme() != "https" {
        return Err("Endpoint URL must use HTTPS".to_string());
    }

    // Host must exist
    let host = match parsed.host_str() {
        Some(h) => h.to_lowercase(),
        None => return Err("Endpoint URL has no host".to_string()),
    };

    // Block localhost
    if host == "localhost" {
        return Err("Localhost endpoints are not allowed in T047".to_string());
    }

    // Block loopback / private IPv4
    if let Ok(ip) = host.parse::<std::net::IpAddr>() {
        if is_forbidden_ip(ip) {
            return Err("Private or loopback IP endpoints are not allowed in T047".to_string());
        }
    }

    // If host looks like an IP but wasn't parsed, do additional string checks
    if host.starts_with("127.")
        || host.starts_with("10.")
        || host.starts_with("192.168.")
        || host.starts_with("0.")
        || host == "::1"
    {
        return Err("Private or loopback IP endpoints are not allowed in T047".to_string());
    }

    // Block 172.16.0.0/12
    if host.starts_with("172.") {
        if let Some(second_octet_str) = host.split('.').nth(1) {
            if let Ok(second_octet) = second_octet_str.parse::<u8>() {
                if (16..=31).contains(&second_octet) {
                    return Err("Private IP endpoints are not allowed in T047".to_string());
                }
            }
        }
    }

    // Query string must not contain secret-like parameters
    let query = parsed.query().unwrap_or("");
    let lower_query = query.to_lowercase();
    let forbidden_query_params = ["api_key", "key", "token", "password", "secret"];
    for param in &forbidden_query_params {
        // Match ?param= or &param=
        let prefix1 = format!("{}=", param);
        let prefix2 = format!("&{}=", param);
        if lower_query.contains(&prefix1) || lower_query.contains(&prefix2) {
            return Err(format!(
                "Endpoint URL query contains forbidden parameter '{}'. Secret parameters are not allowed in the URL.",
                param
            ));
        }
    }

    Ok(())
}

/// Check if an IP address is in a forbidden range (loopback or private).
fn is_forbidden_ip(ip: std::net::IpAddr) -> bool {
    match ip {
        std::net::IpAddr::V4(ipv4) => {
            let octets = ipv4.octets();
            // 127.0.0.0/8
            if octets[0] == 127 {
                return true;
            }
            // 10.0.0.0/8
            if octets[0] == 10 {
                return true;
            }
            // 172.16.0.0/12
            if octets[0] == 172 && (16..=31).contains(&octets[1]) {
                return true;
            }
            // 192.168.0.0/16
            if octets[0] == 192 && octets[1] == 168 {
                return true;
            }
            // 0.0.0.0
            if octets == [0, 0, 0, 0] {
                return true;
            }
            false
        }
        std::net::IpAddr::V6(ipv6) => {
            // ::1
            ipv6.is_loopback()
        }
    }
}

/* ------------------------------------------------------------------ */
/*  Redaction helpers                                                 */
/* ------------------------------------------------------------------ */

/// Redact an error message to ensure no API key or sensitive data leaks.
fn redact_error(err: &str) -> String {
    let mut redacted = err.to_string();

    // Replace patterns that are followed by what looks like a secret value
    for pattern in [
        "sk-",
        "sk_live_",
        "sk_test_",
        "ghp_",
        "github_pat_",
        "xoxb-",
        "Bearer ",
        "Authorization: ",
        "api_key=",
        "apiKey=",
        "token=",
        "password=",
    ] {
        redacted = redact_after_pattern(&redacted, pattern);
    }

    // Replace JWT-like tokens (eyJ...)
    let jwt_regex = regex::Regex::new(r"eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\.?[A-Za-z0-9_-]*").unwrap_or_else(|_| regex::Regex::new("$^").unwrap());
    redacted = jwt_regex.replace_all(&redacted, "***JWT_REDACTED***").to_string();

    // If anything still looks suspicious, blanket redact
    if redacted.contains("sk-")
        || redacted.contains("Bearer ")
        || redacted.contains("Authorization")
        || redacted.contains("api_key=")
        || redacted.contains("apiKey=")
        || redacted.contains("token=")
        || redacted.contains("password=")
        || redacted.contains("ghp_")
        || redacted.contains("xoxb-")
    {
        return "Error redacted: possible sensitive content detected.".to_string();
    }

    redacted
}

fn redact_after_pattern(text: &str, pattern: &str) -> String {
    let mut result = String::new();
    let mut remaining = text;
    while let Some(start) = remaining.find(pattern) {
        result.push_str(&remaining[..start + pattern.len()]);
        remaining = &remaining[start + pattern.len()..];
        // Find end of what looks like a secret (whitespace, newline, quote, or end of string)
        let end = remaining
            .find(|c: char| c.is_whitespace() || c == '\n' || c == '\r' || c == '"' || c == '\'')
            .unwrap_or(remaining.len());
        if end > 0 {
            result.push_str("***REDACTED***");
        }
        remaining = &remaining[end..];
    }
    result.push_str(remaining);
    result
}

/* ------------------------------------------------------------------ */
/*  Truncation helpers (char-safe)                                    */
/* ------------------------------------------------------------------ */

/// Truncate a string to at most max_chars characters, safely handling Unicode.
fn truncate_chars(text: &str, max_chars: usize) -> String {
    let char_count = text.chars().count();
    if char_count <= max_chars {
        text.to_string()
    } else {
        let mut out: String = text.chars().take(max_chars).collect();
        out.push_str("...(truncated)");
        out
    }
}

/// Truncate a response preview.
fn truncate_preview(text: &str) -> String {
    truncate_chars(text, RESPONSE_PREVIEW_MAX_CHARS)
}

/// Build a safe provider error preview from a non-2xx response.
/// Does NOT return the raw body text.
fn build_provider_error_preview(status: reqwest::StatusCode, body_text: &str) -> String {
    // Redact the body first, then truncate
    let redacted = redact_error(body_text);
    let preview = truncate_chars(&redacted, 500); // short preview
    if preview.len() < redacted.len() {
        format!(
            "Provider returned HTTP {}. Partial response preview (redacted): {}",
            status, preview
        )
    } else {
        format!(
            "Provider returned HTTP {}. Response preview (redacted): {}",
            status, preview
        )
    }
}

/* ------------------------------------------------------------------ */
/*  Backend pre-flight gate                                           */
/* ------------------------------------------------------------------ */

/// Validate backend-side pre-flight conditions before making any network call.
/// Returns Ok(()) only when all conditions are met; otherwise returns a safe error string.
fn validate_backend_gate(
    provider_id: &str,
    approval_state: &str,
    send_allowed_by_user: bool,
    api_key: &str,
) -> Result<(), String> {
    if provider_id != "openai_compatible_ephemeral" {
        return Err(format!(
            "Backend gate blocked: provider_id '{}' is not supported by this command.",
            provider_id
        ));
    }
    if approval_state != "approved_but_blocked" {
        return Err(format!(
            "Backend gate blocked: approval_state '{}' is not allowed. Only 'approved_but_blocked' is accepted.",
            approval_state
        ));
    }
    if !send_allowed_by_user {
        return Err("Backend gate blocked: send_allowed_by_user is false. User must explicitly confirm the send.".to_string());
    }
    if api_key.trim().is_empty() {
        return Err("Backend gate blocked: API key is empty.".to_string());
    }
    Ok(())
}

/* ------------------------------------------------------------------ */
/*  Tauri command                                                     */
/* ------------------------------------------------------------------ */

/// Invoke an OpenAI-compatible provider via the Tauri backend.
///
/// # Security guarantees
/// - API key is a function-local String, never logged, never returned.
/// - Only HTTPS endpoints are allowed (with private-IP rejection).
/// - Response is truncated to a char-safe preview.
/// - Errors are redacted before return.
/// - No raw response is stored on disk.
/// - Backend validates provider_id, approval_state, and send_allowed_by_user
///   before making any network call.
#[tauri::command]
pub async fn invoke_openai_compatible_ephemeral(
    endpoint_url: String,
    model_name: String,
    api_key: String,
    system_prompt: String,
    user_prompt: String,
    request_id: String,
    provider_id: String,
    approval_state: String,
    send_allowed_by_user: bool,
) -> Result<RealProviderInvocationResult, String> {
    let created_at = chrono::Utc::now().to_rfc3339();

    // 0. Backend pre-flight gate
    if let Err(gate_err) = validate_backend_gate(
        &provider_id,
        &approval_state,
        send_allowed_by_user,
        &api_key,
    ) {
        return blocked_before_network(&request_id, &gate_err, &created_at);
    }

    // 1. Validate endpoint
    if let Err(e) = validate_endpoint_url(&endpoint_url) {
        return blocked_before_network(&request_id, &e, &created_at);
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
                        error_preview: Some(truncate_chars(
                            &redact_error(&format!(
                                "Provider returned success but response could not be parsed: {}",
                                parse_err
                            )),
                            ERROR_PREVIEW_MAX_CHARS,
                        )),
                        raw_response_stored: false,
                        audit_redacted: true,
                        created_at,
                    }),
                }
            } else {
                // Provider error (non-2xx) — do NOT return raw body
                let error_preview = build_provider_error_preview(status, &body_text);
                Ok(RealProviderInvocationResult {
                    schema_version: RESULT_SCHEMA_VERSION.to_string(),
                    request_id: request_id.clone(),
                    provider_id: "openai_compatible_ephemeral".to_string(),
                    sent: true,
                    blocked: false,
                    status: "provider_error".to_string(),
                    answer_text_preview: String::new(),
                    error_preview: Some(error_preview),
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
                error_preview: Some(truncate_chars(
                    &redact_error(&err_msg),
                    ERROR_PREVIEW_MAX_CHARS,
                )),
                raw_response_stored: false,
                audit_redacted: true,
                created_at,
            })
        }
    }
}

/* ------------------------------------------------------------------ */
/*  Tests                                                             */
/* ------------------------------------------------------------------ */

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_endpoint_url_accepts_valid_https() {
        assert!(validate_endpoint_url("https://api.openai.com/v1/chat/completions").is_ok());
        assert!(validate_endpoint_url("https://example.com:8080/path").is_ok());
    }

    #[test]
    fn test_validate_endpoint_url_rejects_http() {
        assert!(validate_endpoint_url("http://api.openai.com/v1/chat/completions").is_err());
    }

    #[test]
    fn test_validate_endpoint_url_rejects_file() {
        assert!(validate_endpoint_url("file:///etc/passwd").is_err());
    }

    #[test]
    fn test_validate_endpoint_url_rejects_ftp() {
        assert!(validate_endpoint_url("ftp://example.com").is_err());
    }

    #[test]
    fn test_validate_endpoint_url_rejects_localhost() {
        assert!(validate_endpoint_url("https://localhost:8080/v1").is_err());
    }

    #[test]
    fn test_validate_endpoint_url_rejects_127_0_0_1() {
        assert!(validate_endpoint_url("https://127.0.0.1/v1").is_err());
    }

    #[test]
    fn test_validate_endpoint_url_rejects_10_x() {
        assert!(validate_endpoint_url("https://10.0.0.1/v1").is_err());
        assert!(validate_endpoint_url("https://10.255.255.255/v1").is_err());
    }

    #[test]
    fn test_validate_endpoint_url_rejects_172_16_to_31() {
        assert!(validate_endpoint_url("https://172.16.0.1/v1").is_err());
        assert!(validate_endpoint_url("https://172.20.0.1/v1").is_err());
        assert!(validate_endpoint_url("https://172.31.255.255/v1").is_err());
    }

    #[test]
    fn test_validate_endpoint_url_accepts_172_outside_private() {
        assert!(validate_endpoint_url("https://172.15.0.1/v1").is_ok());
        assert!(validate_endpoint_url("https://172.32.0.1/v1").is_ok());
    }

    #[test]
    fn test_validate_endpoint_url_rejects_192_168() {
        assert!(validate_endpoint_url("https://192.168.1.1/v1").is_err());
    }

    #[test]
    fn test_validate_endpoint_url_rejects_0_0_0_0() {
        assert!(validate_endpoint_url("https://0.0.0.0/v1").is_err());
    }

    #[test]
    fn test_validate_endpoint_url_rejects_query_api_key() {
        assert!(validate_endpoint_url("https://api.example.com/v1?api_key=sk-xxx").is_err());
    }

    #[test]
    fn test_validate_endpoint_url_rejects_query_token() {
        assert!(validate_endpoint_url("https://api.example.com/v1?token=abc").is_err());
    }

    #[test]
    fn test_validate_endpoint_url_rejects_query_password() {
        assert!(validate_endpoint_url("https://api.example.com/v1?password=secret").is_err());
    }

    #[test]
    fn test_validate_endpoint_url_rejects_query_secret() {
        assert!(validate_endpoint_url("https://api.example.com/v1?secret=xyz").is_err());
    }

    #[test]
    fn test_validate_endpoint_url_rejects_query_key() {
        assert!(validate_endpoint_url("https://api.example.com/v1?key=val").is_err());
    }

    #[test]
    fn test_validate_endpoint_url_accepts_safe_query() {
        assert!(validate_endpoint_url("https://api.example.com/v1?version=2").is_ok());
    }

    #[test]
    fn test_redact_error_removes_sk_prefix() {
        let input = "Error: invalid key sk-abc123def";
        let result = redact_error(input);
        assert!(!result.contains("abc123def"), "secret leaked: {}", result);
        assert!(result.contains("REDACTED") || result.contains("Error redacted"));
    }

    #[test]
    fn test_redact_error_removes_bearer() {
        let input = "Authorization: Bearer abc-secret-token";
        let result = redact_error(input);
        assert!(!result.contains("secret-token"), "secret leaked: {}", result);
        assert!(result.contains("REDACTED") || result.contains("Error redacted"));
    }

    #[test]
    fn test_redact_error_removes_api_key_param() {
        let input = "body: api_key=sk-live-12345";
        let result = redact_error(input);
        assert!(!result.contains("sk-live-12345"), "secret leaked: {}", result);
        assert!(result.contains("REDACTED") || result.contains("Error redacted"));
    }

    #[test]
    fn test_redact_error_removes_token_param() {
        let input = "response: token=my-secret";
        let result = redact_error(input);
        assert!(!result.contains("my-secret"), "secret leaked: {}", result);
        assert!(result.contains("REDACTED") || result.contains("Error redacted"));
    }

    #[test]
    fn test_redact_error_removes_password_param() {
        let input = "response: password=hunter2";
        let result = redact_error(input);
        assert!(!result.contains("hunter2"), "secret leaked: {}", result);
        assert!(result.contains("REDACTED") || result.contains("Error redacted"));
    }

    #[test]
    fn test_redact_error_removes_ghp() {
        let input = "Error: token is ghp_abc123def456";
        let result = redact_error(input);
        assert!(!result.contains("ghp_"), "ghp prefix leaked: {}", result);
        assert!(result.contains("REDACTED") || result.contains("Error redacted"));
    }

    #[test]
    fn test_redact_error_removes_xoxb() {
        let input = "Error: xoxb-token123";
        let result = redact_error(input);
        assert!(!result.contains("xoxb-"), "xoxb prefix leaked: {}", result);
        assert!(result.contains("REDACTED") || result.contains("Error redacted"));
    }

    #[test]
    fn test_truncate_chars_does_not_panic_on_chinese() {
        let text = "这是一个很长的中文文本，用于测试截断功能。";
        let result = truncate_chars(text, 5);
        assert!(result.ends_with("...(truncated)"));
        assert!(result.chars().count() <= 20); // reasonable bound
    }

    #[test]
    fn test_truncate_chars_does_not_panic_on_emoji() {
        let text = "Hello 👋🌍 this is a test with emoji 😊";
        let result = truncate_chars(text, 10);
        assert!(result.ends_with("...(truncated)"));
        assert!(result.chars().count() <= 30); // 10 + "...(truncated)"
    }

    #[test]
    fn test_truncate_chars_short_text_preserved() {
        let text = "Short";
        assert_eq!(truncate_chars(text, 100), "Short");
    }

    #[test]
    fn test_build_provider_error_preview_capped_and_redacted() {
        let body = "Provider error: invalid key sk-1234567890abcdef and token=secret";
        let preview = build_provider_error_preview(
            reqwest::StatusCode::UNAUTHORIZED,
            body,
        );
        assert!(preview.contains("401"), "status should appear");
        assert!(!preview.contains("sk-1234567890abcdef"), "secret should be redacted");
        assert!(!preview.contains("token=secret"), "token should be redacted");
    }

    #[test]
    fn test_validate_backend_gate_blocks_invalid_provider() {
        let result = validate_backend_gate("future_openai", "approved_but_blocked", true, "sk-xxx");
        assert!(result.is_err());
        let msg = result.unwrap_err();
        assert!(msg.contains("provider_id"));
        assert!(msg.contains("future_openai"));
    }

    #[test]
    fn test_validate_backend_gate_blocks_wrong_approval() {
        let result = validate_backend_gate(
            "openai_compatible_ephemeral",
            "previewed",
            true,
            "sk-xxx",
        );
        assert!(result.is_err());
        let msg = result.unwrap_err();
        assert!(msg.contains("approval_state"));
    }

    #[test]
    fn test_validate_backend_gate_blocks_no_consent() {
        let result = validate_backend_gate(
            "openai_compatible_ephemeral",
            "approved_but_blocked",
            false,
            "sk-xxx",
        );
        assert!(result.is_err());
        let msg = result.unwrap_err();
        assert!(msg.contains("send_allowed_by_user"));
    }

    #[test]
    fn test_validate_backend_gate_blocks_empty_key() {
        let result = validate_backend_gate(
            "openai_compatible_ephemeral",
            "approved_but_blocked",
            true,
            "",
        );
        assert!(result.is_err());
        let msg = result.unwrap_err();
        assert!(msg.contains("API key"));
    }

    #[test]
    fn test_validate_backend_gate_allows_valid() {
        let result = validate_backend_gate(
            "openai_compatible_ephemeral",
            "approved_but_blocked",
            true,
            "sk-xxx",
        );
        assert!(result.is_ok());
    }

    #[test]
    fn test_blocked_before_network_returns_safe_result() {
        let result = blocked_before_network("req-test", "some error", "2024-01-01T00:00:00Z")
            .unwrap();
        assert_eq!(result.sent, false);
        assert_eq!(result.blocked, true);
        assert_eq!(result.status, "blocked");
        assert_eq!(result.raw_response_stored, false);
        assert_eq!(result.audit_redacted, true);
    }

    #[test]
    fn test_blocked_before_network_error_is_redacted() {
        let result = blocked_before_network(
            "req-test",
            "error with sk-12345 secret",
            "2024-01-01T00:00:00Z",
        )
        .unwrap();
        let err = result.error_preview.unwrap();
        assert!(!err.contains("sk-12345"));
        assert!(err.contains("REDACTED") || err.contains("Error redacted"));
    }
}
