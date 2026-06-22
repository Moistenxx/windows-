import { useEffect, useState } from "react";

import { defaultApiBase, fetchHealth, type HealthPayload } from "./api";
import "./styles.css";

const apiBase = import.meta.env.VITE_API_BASE_URL || defaultApiBase;

type HealthState =
  | { status: "loading" }
  | { status: "online"; payload: HealthPayload }
  | { status: "offline"; message: string };

export function App() {
  const [health, setHealth] = useState<HealthState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchHealth(apiBase)
      .then((payload) => {
        if (!cancelled) setHealth({ status: "online", payload });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setHealth({
            status: "offline",
            message: error instanceof Error ? error.message : "Unknown API error",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="app-shell">
      <section className="hero-card">
        <p className="eyebrow">Windows client shell</p>
        <h1>AI 短视频批量生产工作台</h1>
        <p className="subtitle">
          这是 Issue #1 的烟囱链路：Tauri React 客户端请求 Django API 健康检查。
        </p>
        <div className="status-card" data-state={health.status}>
          <span className="status-dot" />
          <div>
            <strong>{health.status === "online" ? "API online" : health.status === "loading" ? "Checking API" : "API offline"}</strong>
            <p>
              {health.status === "online"
                ? `${health.payload.service} · ${health.payload.app}`
                : health.status === "loading"
                  ? `Checking ${apiBase}`
                  : health.message}
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
