import { describe, expect, it, vi } from "vitest";

import {
  estimateAiCredits,
  createAssetUpload,
  deleteAsset,
  contentTypeFor,
  fetchAiProviders,
  fetchAssets,
  fetchCredits,
  fetchCustomers,
  fetchHealth,
  fetchMe,
  login,
  registerWithInvite,
  saveCustomer,
  submitCreditTask,
} from "./api";

describe("fetchHealth", () => {
  it("reads backend health JSON from the configured API base", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "ok", service: "api", app: "ai-video-workbench" }),
    });

    const health = await fetchHealth("http://127.0.0.1:8000", fetchMock);

    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/health/");
    expect(health.status).toBe("ok");
    expect(health.app).toBe("ai-video-workbench");
  });
});

describe("auth API helpers", () => {
  it("registers with an invite code", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ token: "abc", user: { email: "owner@example.com" }, workspace: { id: 1, name: "owner workspace" }, workspaces: [] }),
    });

    const result = await registerWithInvite("http://127.0.0.1:8000", {
      email: "owner@example.com",
      password: "secret123",
      inviteCode: "ALPHA-1",
    }, fetchMock);

    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/auth/register/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "owner@example.com", password: "secret123", invite_code: "ALPHA-1" }),
    });
    expect(result.token).toBe("abc");
  });

  it("logs in with email and password", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ token: "abc", user: { email: "owner@example.com" }, workspace: { id: 1, name: "owner workspace" }, workspaces: [] }),
    });

    const result = await login("http://127.0.0.1:8000", "owner@example.com", "secret123", fetchMock);

    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/auth/login/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "owner@example.com", password: "secret123" }),
    });
    expect(result.workspace.name).toBe("owner workspace");
  });

  it("fetches the authenticated workspace list", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ user: { email: "owner@example.com" }, workspaces: [{ id: 1, name: "owner workspace", role: "owner" }] }),
    });

    const result = await fetchMe("http://127.0.0.1:8000", "abc", fetchMock);

    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/auth/me/", {
      headers: { Authorization: "Bearer abc" },
    });
    expect(result.workspaces).toEqual([{ id: 1, name: "owner workspace", role: "owner" }]);
  });
});

describe("credit API helpers", () => {
  it("fetches the authenticated workspace credit balance", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ workspace_id: 1, balance: 380, frozen: 120 }),
    });

    const result = await fetchCredits("http://127.0.0.1:8000", "abc", fetchMock);

    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/credits/", {
      headers: { Authorization: "Bearer abc" },
    });
    expect(result).toEqual({ workspace_id: 1, balance: 380, frozen: 120 });
  });

  it("submits a paid task to freeze estimated credits", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        task: { id: 7, title: "test render", status: "pending", estimated_credits: 120 },
        credits: { workspace_id: 1, balance: 380, frozen: 120 },
      }),
    });

    const result = await submitCreditTask("http://127.0.0.1:8000", "abc", {
      title: "test render",
      estimatedCredits: 120,
    }, fetchMock);

    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/credit-tasks/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer abc" },
      body: JSON.stringify({ title: "test render", estimated_credits: 120 }),
    });
    expect(result.credits).toEqual({ workspace_id: 1, balance: 380, frozen: 120 });
  });
});

describe("AI provider API helpers", () => {
  it("fetches enabled providers without secrets", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ providers: [{ id: 1, capability: "llm", name: "Volcengine", model_name: "doubao", price_coefficient: "2.00" }] }),
    });

    const result = await fetchAiProviders("http://127.0.0.1:8000", "abc", fetchMock);

    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/ai/providers/", {
      headers: { Authorization: "Bearer abc" },
    });
    expect(JSON.stringify(result)).not.toContain("api_key");
  });

  it("estimates credits with the selected provider", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ provider_id: 1, estimated_credits: 100 }),
    });

    const result = await estimateAiCredits("http://127.0.0.1:8000", "abc", 1, 40, fetchMock);

    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/ai/estimate/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer abc" },
      body: JSON.stringify({ provider_id: 1, base_credits: 40 }),
    });
    expect(result.estimated_credits).toBe(100);
  });
});

describe("customer API helpers", () => {
  it("fetches workspace customer profiles", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ customers: [{ id: 1, name: "Acme", industry: "jewelry" }] }),
    });

    const result = await fetchCustomers("http://127.0.0.1:8000", "abc", fetchMock);

    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/customers/", {
      headers: { Authorization: "Bearer abc" },
    });
    expect(result.customers[0].name).toBe("Acme");
  });

  it("creates or updates a customer profile", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, name: "Acme", industry: "jewelry" }),
    });

    await saveCustomer("http://127.0.0.1:8000", "abc", { id: 1, name: "Acme", industry: "jewelry" }, fetchMock);

    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/customers/1/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer abc" },
      body: JSON.stringify({ name: "Acme", industry: "jewelry" }),
    });
  });
});

describe("asset API helpers", () => {
  it("falls back to content type by filename", () => {
    expect(contentTypeFor("clip.mov")).toBe("video/quicktime");
    expect(contentTypeFor("voice.wav", "")).toBe("audio/wav");
  });

  it("creates upload instructions for an asset", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        asset: { id: 1, filename: "clip.mp4", asset_type: "video", deleted: false },
        upload: { method: "PUT", url: "local://x", headers: { "Content-Type": "video/mp4" } },
      }),
    });

    const result = await createAssetUpload("http://127.0.0.1:8000", "abc", "clip.mp4", "video/mp4", fetchMock);

    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/assets/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer abc" },
      body: JSON.stringify({ filename: "clip.mp4", content_type: "video/mp4" }),
    });
    expect(result.upload.method).toBe("PUT");
  });

  it("fetches and deletes assets", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ assets: [{ id: 1, filename: "clip.mp4" }] }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ id: 1, deleted: true }) });

    await fetchAssets("http://127.0.0.1:8000", "abc", fetchMock);
    await deleteAsset("http://127.0.0.1:8000", "abc", 1, fetchMock);

    expect(fetchMock).toHaveBeenLastCalledWith("http://127.0.0.1:8000/api/assets/1/delete/", {
      method: "POST",
      headers: { Authorization: "Bearer abc" },
    });
  });
});
