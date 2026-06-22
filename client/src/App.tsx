import { FormEvent, useEffect, useState } from "react";

import {
  createAssetUpload,
  contentTypeFor,
  deleteAsset,
  defaultApiBase,
  estimateAiCredits,
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
  updateAssetTags,
  type AiProvider,
  type Asset,
  type AuthPayload,
  type CreditPayload,
  type CustomerProfile,
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

type CreditState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; payload: CreditPayload }
  | { status: "error"; message: string };

type ProviderState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; providers: AiProvider[]; selectedId: number | null; estimate?: number }
  | { status: "error"; message: string };

type CustomerState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; customers: CustomerProfile[]; selectedId: number | null }
  | { status: "error"; message: string };

type AssetState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; assets: Asset[]; message?: string }
  | { status: "error"; message: string };

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
  const [credits, setCredits] = useState<CreditState>({ status: "idle" });
  const [providers, setProviders] = useState<ProviderState>({ status: "idle" });
  const [customers, setCustomers] = useState<CustomerState>({ status: "idle" });
  const [assets, setAssets] = useState<AssetState>({ status: "idle" });
  const [customerForm, setCustomerForm] = useState<CustomerProfile>({ name: "", industry: "", products: "", selling_points: "" });
  const [taskMessage, setTaskMessage] = useState("");
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

  useEffect(() => {
    if (auth.status !== "authenticated") {
      setCredits({ status: "idle" });
      setProviders({ status: "idle" });
      setCustomers({ status: "idle" });
      setAssets({ status: "idle" });
      return;
    }
    setCredits({ status: "loading" });
    fetchCredits(apiBase, auth.token)
      .then((payload) => setCredits({ status: "ready", payload }))
      .catch((error) => setCredits({ status: "error", message: error instanceof Error ? error.message : "Credit load failed" }));
    setProviders({ status: "loading" });
    fetchAiProviders(apiBase, auth.token)
      .then((payload) => setProviders({
        status: "ready",
        providers: payload.providers,
        selectedId: payload.providers[0]?.id ?? null,
      }))
      .catch((error) => setProviders({ status: "error", message: error instanceof Error ? error.message : "Provider load failed" }));
    setCustomers({ status: "loading" });
    fetchCustomers(apiBase, auth.token)
      .then((payload) => {
        if (payload.customers[0]) setCustomerForm(payload.customers[0]);
        setCustomers({
          status: "ready",
          customers: payload.customers,
          selectedId: payload.customers[0]?.id ?? null,
        });
      })
      .catch((error) => setCustomers({ status: "error", message: error instanceof Error ? error.message : "Customer load failed" }));
    setAssets({ status: "loading" });
    fetchAssets(apiBase, auth.token)
      .then((payload) => setAssets({ status: "ready", assets: payload.assets }))
      .catch((error) => setAssets({ status: "error", message: error instanceof Error ? error.message : "Asset load failed" }));
  }, [auth]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setAuth({ status: "loading" });
    try {
      const payload = mode === "register"
        ? await registerWithInvite(apiBase, { email, password, inviteCode })
        : await login(apiBase, email, password);
      localStorage.setItem(tokenKey, payload.token);
      setTaskMessage("");
      setAuth(authFromPayload(payload));
    } catch (error) {
      setAuth({ status: "error", message: error instanceof Error ? error.message : "Auth failed" });
    }
  }

  function logout() {
    localStorage.removeItem(tokenKey);
    setTaskMessage("");
    setAuth({ status: "anonymous" });
  }

  async function submitDemoTask() {
    if (auth.status !== "authenticated") return;
    setTaskMessage("正在提交 120 积分测试任务...");
    try {
      const payload = await submitCreditTask(apiBase, auth.token, {
        title: "Issue #3 credit smoke task",
        estimatedCredits: 120,
      });
      setCredits({ status: "ready", payload: payload.credits });
      setTaskMessage(`任务 #${payload.task.id} 已冻结 ${payload.task.estimated_credits} 积分`);
    } catch (error) {
      setTaskMessage(error instanceof Error ? error.message : "Task submit failed");
    }
  }

  async function estimateSelectedProvider(providerId: number) {
    if (auth.status !== "authenticated" || providers.status !== "ready") return;
    setProviders({ ...providers, selectedId: providerId });
    const payload = await estimateAiCredits(apiBase, auth.token, providerId, 40);
    setProviders({ ...providers, selectedId: providerId, estimate: payload.estimated_credits });
  }

  function selectCustomer(customerId: number) {
    if (customers.status !== "ready") return;
    const customer = customers.customers.find((item) => item.id === customerId);
    if (customer) setCustomerForm(customer);
    setCustomers({ ...customers, selectedId: customerId });
  }

  async function submitCustomer(event: FormEvent) {
    event.preventDefault();
    if (auth.status !== "authenticated") return;
    const saved = await saveCustomer(apiBase, auth.token, customerForm);
    if (customers.status === "ready") {
      const rest = customers.customers.filter((item) => item.id !== saved.id);
      setCustomers({ status: "ready", customers: [saved, ...rest], selectedId: saved.id ?? null });
    }
    setCustomerForm(saved);
  }

  async function addAsset(file: File | undefined) {
    if (!file || auth.status !== "authenticated") return;
    const payload = await createAssetUpload(apiBase, auth.token, file.name, contentTypeFor(file.name, file.type));
    setAssets({
      status: "ready",
      assets: assets.status === "ready" ? [payload.asset, ...assets.assets] : [payload.asset],
      message: `已生成直传地址：${payload.upload.url}`,
    });
  }

  async function removeAsset(assetId: number) {
    if (auth.status !== "authenticated" || assets.status !== "ready") return;
    await deleteAsset(apiBase, auth.token, assetId);
    setAssets({ status: "ready", assets: assets.assets.filter((asset) => asset.id !== assetId), message: "素材已删除" });
  }

  async function saveAssetTags(assetId: number, value: string) {
    if (auth.status !== "authenticated" || assets.status !== "ready") return;
    const tags = value.split(",").map((tag) => tag.trim()).filter(Boolean);
    const saved = await updateAssetTags(apiBase, auth.token, assetId, tags);
    setAssets({
      status: "ready",
      assets: assets.assets.map((asset) => asset.id === assetId ? saved : asset),
      message: "标签已更新",
    });
  }

  return (
    <main className="app-shell">
      <section className="hero-card">
        <p className="eyebrow">Windows client shell</p>
        <h1>AI 短视频批量生产工作台</h1>
        <p className="subtitle">
          Issue #3 烟囱链路：workspace 积分、人工充值、冻结、扣除、退回。
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
              <div className="credit-card">
                <b>团队积分</b>
                {credits.status === "ready" && <p>可用 {credits.payload.balance} · 冻结 {credits.payload.frozen}</p>}
                {credits.status === "loading" && <p>积分加载中...</p>}
                {credits.status === "error" && <p>{credits.message}</p>}
                {credits.status === "idle" && <p>登录后显示</p>}
                <button className="mini-action" onClick={submitDemoTask}>提交 120 积分测试任务</button>
                {taskMessage && <p>{taskMessage}</p>}
              </div>
              <div className="credit-card">
                <b>客户/品牌档案</b>
                {customers.status === "loading" && <p>客户加载中...</p>}
                {customers.status === "error" && <p>{customers.message}</p>}
                {customers.status === "ready" && customers.customers.length > 0 && (
                  <select value={customers.selectedId ?? ""} onChange={(event) => selectCustomer(Number(event.target.value))}>
                    {customers.customers.map((customer) => (
                      <option key={customer.id} value={customer.id}>{customer.name} · {customer.industry || "未填行业"}</option>
                    ))}
                  </select>
                )}
                <form className="mini-form" onSubmit={submitCustomer}>
                  <input placeholder="客户/品牌名称" value={customerForm.name} onChange={(event) => setCustomerForm({ ...customerForm, name: event.target.value })} />
                  <input placeholder="行业" value={customerForm.industry ?? ""} onChange={(event) => setCustomerForm({ ...customerForm, industry: event.target.value })} />
                  <input placeholder="产品/服务" value={customerForm.products ?? ""} onChange={(event) => setCustomerForm({ ...customerForm, products: event.target.value })} />
                  <input placeholder="目标人群" value={customerForm.target_audience ?? ""} onChange={(event) => setCustomerForm({ ...customerForm, target_audience: event.target.value })} />
                  <input placeholder="核心卖点" value={customerForm.selling_points ?? ""} onChange={(event) => setCustomerForm({ ...customerForm, selling_points: event.target.value })} />
                  <input placeholder="禁用词/不能说的话" value={customerForm.forbidden_words ?? ""} onChange={(event) => setCustomerForm({ ...customerForm, forbidden_words: event.target.value })} />
                  <input placeholder="联系方式/引流话术" value={customerForm.contact_hooks ?? ""} onChange={(event) => setCustomerForm({ ...customerForm, contact_hooks: event.target.value })} />
                  <input placeholder="文案风格偏好" value={customerForm.style_preference ?? ""} onChange={(event) => setCustomerForm({ ...customerForm, style_preference: event.target.value })} />
                  <input placeholder="Logo/常用素材备注" value={customerForm.logo_or_common_assets ?? ""} onChange={(event) => setCustomerForm({ ...customerForm, logo_or_common_assets: event.target.value })} />
                  <button className="mini-action">保存档案</button>
                </form>
                {customers.status === "ready" && customers.selectedId && <p>项目创建将使用当前选中的客户档案。</p>}
              </div>
              <div className="credit-card">
                <b>团队素材库</b>
                <input
                  type="file"
                  accept=".mp4,.mov,.jpg,.jpeg,.png,.webp,.mp3,.wav,video/mp4,video/quicktime,image/jpeg,image/png,image/webp,audio/mpeg,audio/wav"
                  onChange={(event) => addAsset(event.target.files?.[0])}
                />
                {assets.status === "loading" && <p>素材加载中...</p>}
                {assets.status === "error" && <p>{assets.message}</p>}
                {assets.status === "ready" && assets.message && <p>{assets.message}</p>}
                {assets.status === "ready" && assets.assets.length === 0 && <p>暂无素材</p>}
                {assets.status === "ready" && assets.assets.length > 0 && (
                  <ul className="workspace-list">
                    {assets.assets.map((asset) => (
                      <li key={asset.id}>
                        <div>
                          {asset.filename} <span>{asset.asset_type} · {asset.retention_days}天</span>
                          <p>建议：{asset.suggested_tags?.join(", ") || "无"} / 当前：{asset.tags?.join(", ") || "无"}</p>
                          <input
                            defaultValue={asset.tags?.join(", ") ?? ""}
                            placeholder="product, storefront"
                            onBlur={(event) => saveAssetTags(asset.id, event.target.value)}
                          />
                        </div>
                        <button className="mini-action" onClick={() => removeAsset(asset.id)}>删除</button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="credit-card">
                <b>高级模型</b>
                {providers.status === "loading" && <p>模型加载中...</p>}
                {providers.status === "error" && <p>{providers.message}</p>}
                {providers.status === "ready" && providers.providers.length === 0 && <p>暂无启用模型</p>}
                {providers.status === "ready" && providers.providers.length > 0 && (
                  <>
                    <select value={providers.selectedId ?? ""} onChange={(event) => estimateSelectedProvider(Number(event.target.value))}>
                      {providers.providers.map((provider) => (
                        <option key={provider.id} value={provider.id}>
                          {provider.capability} · {provider.name} · x{provider.price_coefficient}
                        </option>
                      ))}
                    </select>
                    <button className="mini-action" onClick={() => providers.selectedId && estimateSelectedProvider(providers.selectedId)}>估算 40 基础积分</button>
                    {providers.estimate !== undefined && <p>预计消耗 {providers.estimate} 积分</p>}
                  </>
                )}
              </div>
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
