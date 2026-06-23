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
  fetchJobs,
  fetchMe,
  fetchScriptAssets,
  generateScripts,
  login,
  registerWithInvite,
  saveCustomer,
  saveViralSample,
  confirmScript,
  createJob,
  configureJobVoiceover,
  submitCreditTask,
  transitionJob,
  updateJobSubtitles,
  updateAssetTags,
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

  it("updates corrected asset tags", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, tags: ["price", "detail"] }),
    });

    const result = await updateAssetTags("http://127.0.0.1:8000", "abc", 1, ["price", "detail"], fetchMock);

    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/assets/1/tags/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer abc" },
      body: JSON.stringify({ tags: ["price", "detail"] }),
    });
    expect(result.tags).toEqual(["price", "detail"]);
  });
});

describe("script asset API helpers", () => {
  it("fetches industry templates and viral samples", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ templates: [{ id: 1, name: "Jewelry" }], samples: [{ id: 2, copy: "hook" }] }),
    });

    const result = await fetchScriptAssets("http://127.0.0.1:8000", "abc", fetchMock);

    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/script-assets/", {
      headers: { Authorization: "Bearer abc" },
    });
    expect(result.templates[0].name).toBe("Jewelry");
  });

  it("saves a private viral sample", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, scope: "workspace", copy: "viral" }),
    });

    await saveViralSample("http://127.0.0.1:8000", "abc", { customer_id: 1, copy: "viral" }, fetchMock);

    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/viral-samples/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer abc" },
      body: JSON.stringify({ customer_id: 1, copy: "viral" }),
    });
  });
});

describe("script generation API helpers", () => {
  it("generates script candidates and confirms the edited final script", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: 9, candidates: ["draft"], confirmed_script: "", render_ready: false }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: 9, candidates: ["draft"], confirmed_script: "edited", render_ready: true }),
      });

    const draft = await generateScripts("http://127.0.0.1:8000", "abc", {
      customerId: 1,
      templateId: 2,
      providerId: 3,
      durationSeconds: 30,
      sampleIds: [4],
    }, fetchMock);
    const confirmed = await confirmScript("http://127.0.0.1:8000", "abc", 9, "edited", fetchMock);

    expect(fetchMock).toHaveBeenNthCalledWith(1, "http://127.0.0.1:8000/api/scripts/generate/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer abc" },
      body: JSON.stringify({
        customer_id: 1,
        template_id: 2,
        provider_id: 3,
        duration_seconds: 30,
        sample_ids: [4],
      }),
    });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "http://127.0.0.1:8000/api/scripts/9/confirm/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer abc" },
      body: JSON.stringify({ script: "edited" }),
    });
    expect(draft.render_ready).toBe(false);
    expect(confirmed.render_ready).toBe(true);
  });
});

describe("job API helpers", () => {
  it("creates, lists, and transitions queued jobs", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ job: { id: 1, status: "pending" }, credits: { balance: 380, frozen: 120 } }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ jobs: [{ id: 1, status: "pending" }], concurrency_limits: { global: 2, workspace: 1 } }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ job: { id: 1, status: "running" }, credits: { balance: 380, frozen: 120 } }) });

    await createJob("http://127.0.0.1:8000", "abc", { title: "render", estimatedCredits: 120 }, fetchMock);
    const list = await fetchJobs("http://127.0.0.1:8000", "abc", fetchMock);
    const running = await transitionJob("http://127.0.0.1:8000", "abc", 1, "running", "subtitle", fetchMock);

    expect(fetchMock).toHaveBeenNthCalledWith(1, "http://127.0.0.1:8000/api/jobs/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer abc" },
      body: JSON.stringify({ title: "render", estimated_credits: 120 }),
    });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "http://127.0.0.1:8000/api/jobs/", {
      headers: { Authorization: "Bearer abc" },
    });
    expect(fetchMock).toHaveBeenNthCalledWith(3, "http://127.0.0.1:8000/api/jobs/1/transition/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer abc" },
      body: JSON.stringify({ status: "running", current_step: "subtitle" }),
    });
    expect(list.concurrency_limits.workspace).toBe(1);
    expect(running.job.status).toBe("running");
  });
});

describe("voiceover and subtitle API helpers", () => {
  it("configures job voiceover and edits subtitles", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ job: { id: 1, voiceover_mode: "tts", subtitles: [] }, credits: { balance: 1, frozen: 0 } }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ job: { id: 1, subtitles: [{ text: "edited" }] }, credits: { balance: 1, frozen: 0 } }) });

    await configureJobVoiceover("http://127.0.0.1:8000", "abc", 1, { mode: "tts", providerId: 2, script: "hello" }, fetchMock);
    const edited = await updateJobSubtitles("http://127.0.0.1:8000", "abc", 1, [{ start: 0, end: 2, text: "edited" }], fetchMock);

    expect(fetchMock).toHaveBeenNthCalledWith(1, "http://127.0.0.1:8000/api/jobs/1/voiceover/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer abc" },
      body: JSON.stringify({ mode: "tts", provider_id: 2, script: "hello", asset_id: undefined, subtitles: undefined }),
    });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "http://127.0.0.1:8000/api/jobs/1/subtitles/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer abc" },
      body: JSON.stringify({ subtitles: [{ start: 0, end: 2, text: "edited" }] }),
    });
    expect(edited.job.subtitles?.[0].text).toBe("edited");
  });
});
