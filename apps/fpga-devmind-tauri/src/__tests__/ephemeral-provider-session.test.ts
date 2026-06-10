import { describe, it, expect } from "vitest";
import {
  createEmptyEphemeralProviderSession,
  createEphemeralProviderSession,
  clearEphemeralProviderSession,
  touchEphemeralProviderSession,
  buildKeyFingerprint,
  buildEndpointOriginPreview,
  EPHEMERAL_PROVIDER_SESSION_VERSION,
} from "../agent/ephemeralProviderSession";

describe("T047 Ephemeral Provider Session", () => {
  it("empty session has configured=false", () => {
    const session = createEmptyEphemeralProviderSession();
    expect(session.configured).toBe(false);
    expect(session.key_present).toBe(false);
    expect(session.key_fingerprint).toBeNull();
    expect(session.storage).toBe("memory_only");
    expect(session.created_at).toBeNull();
  });

  it("schema version is correct", () => {
    const session = createEmptyEphemeralProviderSession();
    expect(session.schema_version).toBe(EPHEMERAL_PROVIDER_SESSION_VERSION);
  });

  it("create session sets key_present=true", () => {
    const session = createEphemeralProviderSession({
      api_key: "sk-test1234567890abcdef",
      endpoint_url: "https://api.example.com/v1/chat/completions",
      model_name: "gpt-4o-mini",
    });
    expect(session.configured).toBe(true);
    expect(session.key_present).toBe(true);
    expect(session.storage).toBe("memory_only");
  });

  it("JSON.stringify(session) does not contain raw key", () => {
    const rawKey = "sk-live-abcdefghijklmnopqrstuvwxyz123456";
    const session = createEphemeralProviderSession({
      api_key: rawKey,
      endpoint_url: "https://api.example.com/v1/chat/completions",
      model_name: "gpt-4o-mini",
    });
    const serialized = JSON.stringify(session);
    expect(serialized).not.toContain(rawKey);
    expect(serialized).not.toContain("sk-live-abcdefghijklmnopqrstuvwxyz123456");
  });

  it("fingerprint exists but is irreversible", () => {
    const rawKey = "sk-abcdefghijklmnopqrstuvwxyz123456";
    const session = createEphemeralProviderSession({
      api_key: rawKey,
      endpoint_url: "https://api.example.com/v1/chat/completions",
      model_name: "gpt-4o-mini",
    });
    expect(session.key_fingerprint).toBeTruthy();
    expect(session.key_fingerprint).not.toBe(rawKey);
    // Fingerprint should show first 4 and last 4 chars
    expect(session.key_fingerprint).toContain("...");
  });

  it("clear session resets to empty", () => {
    const session = createEphemeralProviderSession({
      api_key: "sk-test1234567890abcdef",
      endpoint_url: "https://api.example.com/v1/chat/completions",
      model_name: "gpt-4o-mini",
    });
    const cleared = clearEphemeralProviderSession(session);
    expect(cleared.configured).toBe(false);
    expect(cleared.key_present).toBe(false);
    expect(cleared.key_fingerprint).toBeNull();
    expect(cleared.endpoint_origin_preview).toBe("");
  });

  it("touch updates last_used_at", async () => {
    const session = createEphemeralProviderSession({
      api_key: "sk-test1234567890abcdef",
      endpoint_url: "https://api.example.com/v1/chat/completions",
      model_name: "gpt-4o-mini",
    });
    const before = session.last_used_at;
    // Small delay to ensure timestamp changes
    await new Promise((r) => setTimeout(r, 10));
    const touched = touchEphemeralProviderSession(session);
    expect(touched.last_used_at).toBeTruthy();
    expect(touched.last_used_at).not.toBe(before);
  });

  it("buildKeyFingerprint short key returns ellipsis", () => {
    expect(buildKeyFingerprint("abc")).toBe("...");
    expect(buildKeyFingerprint("abcdefgh")).toBe("...");
  });

  it("buildKeyFingerprint long key returns prefix...suffix", () => {
    const fp = buildKeyFingerprint("sk-abcdefghijklmnopqrstuvwxyz");
    expect(fp).toBe("sk-a...wxyz");
    expect(fp).not.toContain("sk-abcdefghijklmnopqrstuvwxyz");
  });

  it("buildEndpointOriginPreview extracts origin only", () => {
    expect(buildEndpointOriginPreview("https://api.openai.com/v1/chat/completions")).toBe("https://api.openai.com");
    expect(buildEndpointOriginPreview("https://example.com:8080/path?key=secret")).toBe("https://example.com:8080");
  });

  it("buildEndpointOriginPreview invalid URL returns empty", () => {
    expect(buildEndpointOriginPreview("not-a-url")).toBe("");
  });

  it("storage is always memory_only", () => {
    const empty = createEmptyEphemeralProviderSession();
    const configured = createEphemeralProviderSession({
      api_key: "sk-test",
      endpoint_url: "https://api.example.com",
      model_name: "gpt-4",
    });
    expect(empty.storage).toBe("memory_only");
    expect(configured.storage).toBe("memory_only");
  });

  it("model name defaults when empty", () => {
    const session = createEphemeralProviderSession({
      api_key: "sk-test",
      endpoint_url: "https://api.example.com",
      model_name: "",
    });
    expect(session.model_name).toBe("gpt-4o-mini");
  });

  it("JSON of cleared session has no sensitive data", () => {
    const session = createEphemeralProviderSession({
      api_key: "sk-secret1234567890abcdef",
      endpoint_url: "https://api.example.com",
      model_name: "gpt-4",
    });
    const cleared = clearEphemeralProviderSession(session);
    const serialized = JSON.stringify(cleared);
    expect(serialized).not.toContain("sk-secret");
    expect(serialized).not.toContain("secret123");
  });
});
