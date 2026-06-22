import { describe, expect, it, vi } from "vitest";

import { fetchHealth, fetchMe, login, registerWithInvite } from "./api";

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
