import { describe, expect, it, vi } from "vitest";

import { fetchHealth } from "./api";

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
