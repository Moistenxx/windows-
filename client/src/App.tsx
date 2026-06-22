import { FormEvent, useEffect, useState } from "react";

import {
  defaultApiBase,
  fetchHealth,
  fetchMe,
  login,
  registerWithInvite,
  type AuthPayload,
  type HealthPayload,
  type MePayload,
} from "./api";
import "./styles.css";

const apiBase = import.meta.env.VITE_API_BASE_URL || defaultApiBase;
const tokenKey = "ai-video-workbench-token";

type HealthState =
  | { status: "loading" }
  | { status: "online"; payload: HealthPayload }
  | { status: "offline"; message: string };

type AuthState =
  | { status: "anonymous" }
  | { status: "loading" }
  | { status: "authenticated"; token: string; user: MePayload["user"]; workspaces: MePayload["workspaces"] }
  | { status: "error"; message: string };

function authFromPayload(payload: AuthPayload): AuthState {
  return {
    status: "authenticated",
    token: payload.token,
    user: payload.user,
    workspaces: payload.workspaces.length
      ? payload.workspaces
      : payload.workspace
        ? [{ ...payload.workspace, role: "owner" }]
        : [],
  };
}

export function App() {
  const [health, setHealth] = useState<HealthState>({ status: "loading" });
  const [auth, setAuth] = useState<AuthState>({ status: "anonymous" });
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("owner@example.com");
  const [password, setPassword] = useState("secret123");
  const [inviteCode, setInviteCode] = useState("ALPHA-1");

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

  useEffect(() => {
    const token = localStorage.getItem(tokenKey);
    if (!token) return;
    setAuth({ status: "loading" });
    fetchMe(apiBase, token)
      .then((payload) => setAuth({ status: "authenticated", token, ...payload }))
      .catch(() => {
        localStorage.removeItem(tokenKey);
        setAuth({ status: "anonymous" });
      });
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setAuth({ status: "loading" });
    try {
      const payload = mode === "register"
        ? await registerWithInvite(apiBase, { email, password, inviteCode })
        : await login(apiBase, email, password);
      localStorage.setItem(tokenKey, payload.token);
      setAuth(authFromPayload(payload));
    } catch (error) {
      setAuth({ status: "error", message: error instanceof Error ? error.message : "Auth failed" });
    }
  }

  function logout() {
    localStorage.removeItem(tokenKey);
    setAuth({ status: "anonymous" });
  }

  return (
    <main className="app-shell">
      <section className="hero-card">
        <p className="eyebrow">Windows client shell</p>
        <h1>AI 短视频批量生产工作台</h1>
        <p className="subtitle">
          Issue #2 烟囱链路：邀请码注册、邮箱登录、默认团队空间。
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

        {auth.status === "authenticated" ? (
          <section className="auth-panel">
            <div>
              <p className="eyebrow">Signed in</p>
              <h2>{auth.user.email}</h2>
              <p className="subtitle small">当前 workspace</p>
              <ul className="workspace-list">
                {auth.workspaces.map((workspace) => (
                  <li key={workspace.id}>{workspace.name} <span>{workspace.role}</span></li>
                ))}
              </ul>
            </div>
            <button className="ghost" onClick={logout}>退出登录</button>
          </section>
        ) : (
          <form className="auth-panel" onSubmit={submit}>
            <div className="mode-row">
              <button type="button" className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>登录</button>
              <button type="button" className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>邀请码注册</button>
            </div>
            <label>邮箱<input value={email} onChange={(event) => setEmail(event.target.value)} /></label>
            <label>密码<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
            {mode === "register" && <label>邀请码<input value={inviteCode} onChange={(event) => setInviteCode(event.target.value)} /></label>}
            <button className="primary-action" disabled={auth.status === "loading"}>{auth.status === "loading" ? "处理中..." : mode === "register" ? "注册并进入工作台" : "登录工作台"}</button>
            {auth.status === "error" && <p className="error-text">{auth.message}</p>}
          </form>
        )}
      </section>
    </main>
  );
}
