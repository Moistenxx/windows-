import { FormEvent, useEffect, useState } from "react";

import {
  createAssetUpload,
  createBatchRemix,
  createJob,
  configureJobVoiceover,
  contentTypeFor,
  deleteAsset,
  defaultApiBase,
  estimateAiCredits,
  fetchClientVersion,
  fetchAiProviders,
  fetchAssetPreviewBlob,
  fetchAssets,
  fetchCredits,
  fetchCustomers,
  fetchHealth,
  fetchJobs,
  fetchScriptAssets,
  fetchMe,
  confirmScript,
  generateScripts,
  login,
  registerWithInvite,
  renderJob,
  saveCustomer,
  saveViralSample,
  submitCreditTask,
  transitionJob,
  updateJobSubtitles,
  updateAssetTags,
  isNewerVersion,
  type AiProvider,
  type Asset,
  type AuthPayload,
  type CreditPayload,
  type ClientVersionPayload,
  type CustomerProfile,
  type HealthPayload,
  type IndustryTemplate,
  type JobsPayload,
  type MePayload,
  type SubtitleCue,
  type ScriptDraftPayload,
  type ViralSample,
} from "./api";
import "./styles.css";

const apiBase = import.meta.env.VITE_API_BASE_URL || defaultApiBase;
const appVersion = import.meta.env.VITE_APP_VERSION || "0.1.0";
const tokenKey = "ai-video-workbench-token";

type HealthState =
  | { status: "loading" }
  | { status: "online"; payload: HealthPayload }
  | { status: "offline"; message: string };

type UpdateState =
  | { status: "idle" }
  | { status: "available"; payload: ClientVersionPayload }
  | { status: "current" }
  | { status: "error"; message: string };

type CreditState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; payload: CreditPayload }
  | { status: "error"; message: string };

type JobState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; payload: JobsPayload; message?: string }
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

type ScriptAssetState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; templates: IndustryTemplate[]; samples: ViralSample[]; selectedTemplateId: number | null; message?: string }
  | { status: "error"; message: string };

type ScriptDraftState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; draft: ScriptDraftPayload; message?: string }
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
  const [update, setUpdate] = useState<UpdateState>({ status: "idle" });
  const [auth, setAuth] = useState<AuthState>({ status: "anonymous" });
  const [credits, setCredits] = useState<CreditState>({ status: "idle" });
  const [jobs, setJobs] = useState<JobState>({ status: "idle" });
  const [providers, setProviders] = useState<ProviderState>({ status: "idle" });
  const [customers, setCustomers] = useState<CustomerState>({ status: "idle" });
  const [assets, setAssets] = useState<AssetState>({ status: "idle" });
  const [previewUrls, setPreviewUrls] = useState<Record<number, string>>({});
  const [scriptAssets, setScriptAssets] = useState<ScriptAssetState>({ status: "idle" });
  const [scriptDraft, setScriptDraft] = useState<ScriptDraftState>({ status: "idle" });
  const [customerForm, setCustomerForm] = useState<CustomerProfile>({ name: "", industry: "", products: "", selling_points: "" });
  const [sampleForm, setSampleForm] = useState({ source_url: "", copy: "", tags: "" });
  const [durationSeconds, setDurationSeconds] = useState(30);
  const [selectedSampleIds, setSelectedSampleIds] = useState<number[]>([]);
  const [scriptText, setScriptText] = useState("");
  const [variantCount, setVariantCount] = useState(3);
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
    let cancelled = false;
    fetchClientVersion(apiBase)
      .then((payload) => {
        if (!cancelled) setUpdate(isNewerVersion(payload.version, appVersion) ? { status: "available", payload } : { status: "current" });
      })
      .catch((error) => {
        if (!cancelled) setUpdate({ status: "error", message: error instanceof Error ? error.message : "Update check failed" });
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
      setJobs({ status: "idle" });
      setProviders({ status: "idle" });
      setCustomers({ status: "idle" });
      setAssets({ status: "idle" });
      setScriptAssets({ status: "idle" });
      setScriptDraft({ status: "idle" });
      setSelectedSampleIds([]);
      setScriptText("");
      return;
    }
    setCredits({ status: "loading" });
    fetchCredits(apiBase, auth.token)
      .then((payload) => setCredits({ status: "ready", payload }))
      .catch((error) => setCredits({ status: "error", message: error instanceof Error ? error.message : "Credit load failed" }));
    setJobs({ status: "loading" });
    fetchJobs(apiBase, auth.token)
      .then((payload) => setJobs({ status: "ready", payload }))
      .catch((error) => setJobs({ status: "error", message: error instanceof Error ? error.message : "Job load failed" }));
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
    setScriptAssets({ status: "loading" });
    fetchScriptAssets(apiBase, auth.token)
      .then((payload) => setScriptAssets({
        status: "ready",
        templates: payload.templates,
        samples: payload.samples,
        selectedTemplateId: payload.templates[0]?.id ?? null,
      }))
      .catch((error) => setScriptAssets({ status: "error", message: error instanceof Error ? error.message : "Script asset load failed" }));
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

  function upsertJobList(payload: JobsPayload, job: JobsPayload["jobs"][number]): JobsPayload {
    return { ...payload, jobs: [job, ...payload.jobs.filter((item) => item.id !== job.id)] };
  }

  async function submitDemoJob() {
    if (auth.status !== "authenticated") return;
    if (scriptDraft.status !== "ready" || !scriptDraft.draft.render_ready) {
      setTaskMessage("请先生成并确认脚本，再创建渲染任务");
      return;
    }
    setTaskMessage("正在创建队列任务...");
    try {
      const payload = await createJob(apiBase, auth.token, { title: "9:16 render smoke job", estimatedCredits: 120, scriptDraftId: scriptDraft.draft.id });
      setCredits({ status: "ready", payload: payload.credits });
      setJobs((state) => state.status === "ready"
        ? { status: "ready", payload: upsertJobList(state.payload, payload.job), message: "任务已进入队列" }
        : state);
      setTaskMessage(`任务 #${payload.job.id} 已排队`);
    } catch (error) {
      setTaskMessage(error instanceof Error ? error.message : "Job create failed");
    }
  }

  async function moveJob(jobId: number, status: string, currentStep = "") {
    if (auth.status !== "authenticated" || jobs.status !== "ready") return;
    try {
      const payload = await transitionJob(apiBase, auth.token, jobId, status, currentStep);
      setCredits({ status: "ready", payload: payload.credits });
      setJobs({ status: "ready", payload: upsertJobList(jobs.payload, payload.job), message: `任务已变为 ${payload.job.status}` });
    } catch (error) {
      const payload = await fetchJobs(apiBase, auth.token);
      setJobs({ status: "ready", payload, message: error instanceof Error ? error.message : "Job transition failed" });
    }
  }

  async function setJobVoiceover(jobId: number, mode: "none" | "tts" | "asr") {
    if (auth.status !== "authenticated" || jobs.status !== "ready") return;
    const provider = providers.status === "ready" ? providers.providers.find((item) => item.capability === mode) : undefined;
    const source = assets.status === "ready" ? assets.assets.find((item) => ["audio", "video"].includes(item.asset_type ?? "")) : undefined;
    if (mode !== "none" && !provider) {
      setJobs({ ...jobs, message: `缺少 ${mode.toUpperCase()} 模型` });
      return;
    }
    if (mode === "asr" && !source) {
      setJobs({ ...jobs, message: "缺少可做 ASR 的音频/视频素材" });
      return;
    }
    const voiceScript = scriptDraft.status === "ready" ? scriptDraft.draft.confirmed_script || scriptText : scriptText;
    if (mode === "tts" && !voiceScript.trim()) {
      setJobs({ ...jobs, message: "请先生成或填写脚本" });
      return;
    }
    try {
      const payload = await configureJobVoiceover(apiBase, auth.token, jobId, {
        mode,
        providerId: provider?.id,
        script: voiceScript,
        assetId: source?.id,
      });
      setJobs({ status: "ready", payload: upsertJobList(jobs.payload, payload.job), message: "配音/字幕已更新" });
    } catch (error) {
      setJobs({ ...jobs, message: error instanceof Error ? error.message : "Voiceover update failed" });
    }
  }

  async function saveJobSubtitleText(job: JobsPayload["jobs"][number], value: string) {
    if (auth.status !== "authenticated" || jobs.status !== "ready") return;
    const lines = value.split("\n").map((line) => line.trim()).filter(Boolean);
    const subtitles: SubtitleCue[] = lines.map((text, index) => ({
      start: job.subtitles?.[index]?.start ?? index * 2,
      end: job.subtitles?.[index]?.end ?? index * 2 + 2,
      text,
    }));
    const payload = await updateJobSubtitles(apiBase, auth.token, job.id, subtitles);
    setJobs({ status: "ready", payload: upsertJobList(jobs.payload, payload.job), message: "字幕已保存" });
  }

  async function renderSelectedJob(job: JobsPayload["jobs"][number]) {
    if (auth.status !== "authenticated" || jobs.status !== "ready" || assets.status !== "ready") return;
    const sourceIds = job.render?.source_asset_ids?.length ? job.render.source_asset_ids : assets.assets.filter((asset) => asset.asset_type !== "output").map((asset) => asset.id);
    if (sourceIds.length === 0) {
      setJobs({ ...jobs, message: "请先上传素材再渲染" });
      return;
    }
    try {
      const payload = await renderJob(apiBase, auth.token, job.id, sourceIds);
      setCredits({ status: "ready", payload: payload.credits });
      setJobs({ status: "ready", payload: upsertJobList(jobs.payload, payload.job), message: "已提交云端渲染队列，worker 完成后可预览下载" });
    } catch (error) {
      const payload = await fetchJobs(apiBase, auth.token);
      setJobs({ status: "ready", payload, message: error instanceof Error ? error.message : "Render failed" });
      fetchCredits(apiBase, auth.token).then((payload) => setCredits({ status: "ready", payload }));
    }
  }

  async function createRemixBatch() {
    if (auth.status !== "authenticated" || jobs.status !== "ready" || assets.status !== "ready") return;
    if (scriptDraft.status !== "ready" || !scriptDraft.draft.render_ready) {
      setJobs({ ...jobs, message: "请先生成并确认脚本，再批量混剪" });
      return;
    }
    const sourceIds = assets.assets.filter((asset) => asset.asset_type !== "output").map((asset) => asset.id);
    if (sourceIds.length === 0) {
      setJobs({ ...jobs, message: "请先上传素材再批量混剪" });
      return;
    }
    try {
      const payload = await createBatchRemix(apiBase, auth.token, {
        assetIds: sourceIds,
        variants: variantCount,
        estimatedCredits: 50,
        scriptDraftId: scriptDraft.draft.id,
      });
      setCredits({ status: "ready", payload: payload.credits });
      setJobs({ status: "ready", payload: { ...jobs.payload, jobs: [...payload.jobs, ...jobs.payload.jobs] }, message: `已创建 ${payload.jobs.length} 条混剪任务` });
    } catch (error) {
      setJobs({ ...jobs, message: error instanceof Error ? error.message : "Batch remix failed" });
    }
  }

  async function loadPreview(asset: Asset) {
    if (auth.status !== "authenticated" || !asset.preview_url) return;
    const blob = await fetchAssetPreviewBlob(apiBase, auth.token, asset.preview_url);
    const url = URL.createObjectURL(blob);
    setPreviewUrls((current) => {
      if (current[asset.id]) URL.revokeObjectURL(current[asset.id]);
      return { ...current, [asset.id]: url };
    });
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

  function selectTemplate(templateId: number) {
    if (scriptAssets.status !== "ready") return;
    setScriptAssets({ ...scriptAssets, selectedTemplateId: templateId });
  }

  function toggleSample(sampleId: number | undefined, checked: boolean) {
    if (!sampleId) return;
    setSelectedSampleIds((ids) => checked ? Array.from(new Set([...ids, sampleId])) : ids.filter((id) => id !== sampleId));
  }

  async function submitSample(event: FormEvent) {
    event.preventDefault();
    if (auth.status !== "authenticated" || scriptAssets.status !== "ready") return;
    const copy = sampleForm.copy.trim();
    if (!copy) {
      setScriptAssets({ ...scriptAssets, message: "请先粘贴爆款文案" });
      return;
    }
    const saved = await saveViralSample(apiBase, auth.token, {
      customer_id: customers.status === "ready" ? customers.selectedId ?? undefined : undefined,
      source_url: sampleForm.source_url.trim(),
      copy,
      tags: sampleForm.tags.split(",").map((tag) => tag.trim()).filter(Boolean),
    });
    setScriptAssets({ ...scriptAssets, samples: [saved, ...scriptAssets.samples], message: "爆款样本已保存" });
    if (saved.id) setSelectedSampleIds((ids) => Array.from(new Set([...ids, saved.id as number])));
    setSampleForm({ source_url: "", copy: "", tags: "" });
  }

  async function generateScriptCandidates() {
    if (auth.status !== "authenticated") return;
    const customerId = customers.status === "ready" ? customers.selectedId : null;
    const templateId = scriptAssets.status === "ready" ? scriptAssets.selectedTemplateId : null;
    const llmProviders = providers.status === "ready" ? providers.providers.filter((provider) => provider.capability === "llm") : [];
    const provider = providers.status === "ready"
      ? llmProviders.find((item) => item.id === providers.selectedId) ?? llmProviders[0]
      : undefined;
    if (!customerId || !templateId || !provider) {
      setScriptDraft({ status: "error", message: "请先选择客户、行业模板和 LLM 模型" });
      return;
    }
    setScriptDraft({ status: "loading" });
    try {
      const draft = await generateScripts(apiBase, auth.token, {
        customerId,
        templateId,
        providerId: provider.id,
        durationSeconds,
        sampleIds: selectedSampleIds,
      });
      setScriptText(draft.candidates[0] ?? "");
      setScriptDraft({ status: "ready", draft, message: "候选脚本已生成，确认前不会冻结渲染积分" });
    } catch (error) {
      setScriptDraft({ status: "error", message: error instanceof Error ? error.message : "Script generation failed" });
    }
  }

  async function confirmSelectedScript() {
    if (auth.status !== "authenticated" || scriptDraft.status !== "ready") return;
    const script = scriptText.trim();
    if (!script) {
      setScriptDraft({ status: "error", message: "确认前请保留脚本文案" });
      return;
    }
    const draft = await confirmScript(apiBase, auth.token, scriptDraft.draft.id, script);
    setScriptDraft({ status: "ready", draft, message: draft.render_ready ? "已确认，可进入后续渲染" : undefined });
  }

  return (
    <main className="app-shell">
      <section className="hero-card">
        <p className="eyebrow">Windows client shell</p>
        <h1>AI 短视频批量生产工作台</h1>
        <p className="subtitle">
          从客户档案、爆款样本到 AI 脚本确认；确认后再进入后续渲染扣费。
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
        {update.status === "available" && (
          <div className="status-card" data-state="online">
            <span className="status-dot" />
            <div>
              <strong>发现新版本 {update.payload.version}</strong>
              <p>{update.payload.notes || "建议更新 Windows 客户端"} · <a href={update.payload.download_url}>下载更新</a></p>
            </div>
          </div>
        )}

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
                <b>任务队列</b>
                <p>并发限制：{jobs.status === "ready" ? `全局 ${jobs.payload.concurrency_limits.global} / workspace ${jobs.payload.concurrency_limits.workspace}` : "加载中"}</p>
                <button className="mini-action" onClick={submitDemoJob}>创建 120 积分渲染任务</button>
                <input type="number" aria-label="Batch remix variants" min={1} max={20} value={variantCount} onChange={(event) => setVariantCount(Number(event.target.value))} />
                <button className="mini-action" onClick={createRemixBatch}>批量混剪</button>
                {jobs.status === "loading" && <p>任务加载中...</p>}
                {jobs.status === "error" && <p>{jobs.message}</p>}
                {jobs.status === "ready" && jobs.message && <p>{jobs.message}</p>}
                {jobs.status === "ready" && jobs.payload.jobs.length === 0 && <p>暂无任务</p>}
                {jobs.status === "ready" && jobs.payload.jobs.length > 0 && (
                  <ul className="workspace-list">
                    {jobs.payload.jobs.map((job) => (
                      <li key={job.id}>
                        <div>
                          #{job.id} {job.title} <span>{job.status} · {job.current_step || "等待"} · 预计等待 {job.estimated_wait_seconds}s</span>
                          <p>配音：{job.voiceover_mode || "none"} {job.audio_placeholder ? `· ${job.audio_placeholder}` : ""}</p>
                          {job.subtitles && job.subtitles.length > 0 && (
                            <textarea aria-label="Edit subtitles"
                              defaultValue={job.subtitles.map((cue) => cue.text).join("\n")}
                              rows={Math.min(6, job.subtitles.length + 1)}
                              onBlur={(event) => saveJobSubtitleText(job, event.target.value)}
                            />
                          )}
                          {assets.status === "ready" && (() => {
                            const output = assets.assets.find((asset) => asset.id === job.output_asset_id);
                            const src = output ? previewUrls[output.id] : "";
                            return output ? (
                              <div>
                                {src ? (
                                  <>
                                    <video controls src={src} width={180} />
                                    <a href={src} download={output.filename}>下载 MP4</a>
                                  </>
                                ) : (
                                  <button className="mini-action" onClick={() => loadPreview(output)}>加载预览</button>
                                )}
                              </div>
                            ) : null;
                          })()}
                        </div>
                        {job.status === "pending" && <button className="mini-action" onClick={() => moveJob(job.id, "running", "script")}>开始</button>}
                        {job.status === "running" && <button className="mini-action" onClick={() => moveJob(job.id, "succeeded")}>完成</button>}
                        {["pending", "running"].includes(job.status) && <button className="mini-action" onClick={() => moveJob(job.id, "failed")}>失败退款</button>}
                        {["pending", "running"].includes(job.status) && <button className="mini-action" onClick={() => renderSelectedJob(job)}>渲染预览</button>}
                        <button className="mini-action" onClick={() => setJobVoiceover(job.id, "none")}>无配音</button>
                        <button className="mini-action" onClick={() => setJobVoiceover(job.id, "tts")}>AI配音</button>
                        <button className="mini-action" onClick={() => setJobVoiceover(job.id, "asr")}>ASR字幕</button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="credit-card">
                <b>客户/品牌档案</b>
                {customers.status === "loading" && <p>客户加载中...</p>}
                {customers.status === "error" && <p>{customers.message}</p>}
                {customers.status === "ready" && customers.customers.length > 0 && (
                  <select aria-label="Select customer" value={customers.selectedId ?? ""} onChange={(event) => selectCustomer(Number(event.target.value))}>
                    {customers.customers.map((customer) => (
                      <option key={customer.id} value={customer.id}>{customer.name} · {customer.industry || "未填行业"}</option>
                    ))}
                  </select>
                )}
                <form className="mini-form" onSubmit={submitCustomer}>
                  <input aria-label="客户/品牌名称" placeholder="客户/品牌名称" value={customerForm.name} onChange={(event) => setCustomerForm({ ...customerForm, name: event.target.value })} />
                  <input aria-label="行业" placeholder="行业" value={customerForm.industry ?? ""} onChange={(event) => setCustomerForm({ ...customerForm, industry: event.target.value })} />
                  <input aria-label="产品/服务" placeholder="产品/服务" value={customerForm.products ?? ""} onChange={(event) => setCustomerForm({ ...customerForm, products: event.target.value })} />
                  <input aria-label="目标人群" placeholder="目标人群" value={customerForm.target_audience ?? ""} onChange={(event) => setCustomerForm({ ...customerForm, target_audience: event.target.value })} />
                  <input aria-label="核心卖点" placeholder="核心卖点" value={customerForm.selling_points ?? ""} onChange={(event) => setCustomerForm({ ...customerForm, selling_points: event.target.value })} />
                  <input aria-label="禁用词/不能说的话" placeholder="禁用词/不能说的话" value={customerForm.forbidden_words ?? ""} onChange={(event) => setCustomerForm({ ...customerForm, forbidden_words: event.target.value })} />
                  <input aria-label="联系方式/引流话术" placeholder="联系方式/引流话术" value={customerForm.contact_hooks ?? ""} onChange={(event) => setCustomerForm({ ...customerForm, contact_hooks: event.target.value })} />
                  <input aria-label="文案风格偏好" placeholder="文案风格偏好" value={customerForm.style_preference ?? ""} onChange={(event) => setCustomerForm({ ...customerForm, style_preference: event.target.value })} />
                  <input aria-label="Logo/常用素材备注" placeholder="Logo/常用素材备注" value={customerForm.logo_or_common_assets ?? ""} onChange={(event) => setCustomerForm({ ...customerForm, logo_or_common_assets: event.target.value })} />
                  <button className="mini-action">保存档案</button>
                </form>
                {customers.status === "ready" && customers.selectedId && <p>项目创建将使用当前选中的客户档案。</p>}
              </div>
              <div className="credit-card">
                <b>AI 爆款脚本</b>
                <p>选择客户、抖音行业模板、时长、参考样本和 LLM；生成候选不会冻结视频渲染积分。</p>
                {scriptAssets.status === "loading" && <p>脚本模板加载中...</p>}
                {scriptAssets.status === "error" && <p>{scriptAssets.message}</p>}
                {scriptAssets.status === "ready" && (
                  <>
                    <select aria-label="Select industry template" value={scriptAssets.selectedTemplateId ?? ""} onChange={(event) => selectTemplate(Number(event.target.value))}>
                      {scriptAssets.templates.map((template) => (
                        <option key={template.id} value={template.id}>{template.industry || "通用"} · {template.name}</option>
                      ))}
                    </select>
                    <select aria-label="Select script duration" value={durationSeconds} onChange={(event) => setDurationSeconds(Number(event.target.value))}>
                      <option value={15}>15秒</option>
                      <option value={30}>30秒</option>
                      <option value={60}>60秒</option>
                    </select>
                    {providers.status === "ready" && (
                      <select aria-label="Select LLM provider"
                        value={providers.providers.find((provider) => provider.id === providers.selectedId && provider.capability === "llm")?.id ?? providers.providers.find((provider) => provider.capability === "llm")?.id ?? ""}
                        onChange={(event) => setProviders({ ...providers, selectedId: Number(event.target.value) })}
                      >
                        {providers.providers.filter((provider) => provider.capability === "llm").map((provider) => (
                          <option key={provider.id} value={provider.id}>{provider.name} · {provider.model_name}</option>
                        ))}
                      </select>
                    )}
                    <form className="mini-form" onSubmit={submitSample}>
                      <input aria-label="抖音链接（可选）" placeholder="抖音链接（可选）" value={sampleForm.source_url} onChange={(event) => setSampleForm({ ...sampleForm, source_url: event.target.value })} />
                      <input aria-label="粘贴爆款文案" placeholder="粘贴爆款文案" value={sampleForm.copy} onChange={(event) => setSampleForm({ ...sampleForm, copy: event.target.value })} />
                      <input aria-label="标签：hook, price" placeholder="标签：hook, price" value={sampleForm.tags} onChange={(event) => setSampleForm({ ...sampleForm, tags: event.target.value })} />
                      <button className="mini-action">保存参考样本</button>
                    </form>
                    {scriptAssets.message && <p>{scriptAssets.message}</p>}
                    {scriptAssets.samples.length > 0 && (
                      <ul className="workspace-list">
                        {scriptAssets.samples.map((sample) => (
                          <li key={sample.id ?? sample.copy}>
                            <label>
                              <input
                                type="checkbox"
                                checked={Boolean(sample.id && selectedSampleIds.includes(sample.id))}
                                onChange={(event) => toggleSample(sample.id, event.target.checked)}
                              />
                              {sample.title || sample.copy.slice(0, 40)}
                            </label>
                          </li>
                        ))}
                      </ul>
                    )}
                    <button className="mini-action" type="button" onClick={generateScriptCandidates}>生成 3 条候选脚本</button>
                  </>
                )}
                {scriptDraft.status === "loading" && <p>AI 正在生成候选...</p>}
                {scriptDraft.status === "error" && <p>{scriptDraft.message}</p>}
                {scriptDraft.status === "ready" && (
                  <>
                    <p>{scriptDraft.message}</p>
                    <div className="mode-row">
                      {scriptDraft.draft.candidates.map((candidate, index) => (
                        <button type="button" key={candidate} onClick={() => setScriptText(candidate)}>候选 {index + 1}</button>
                      ))}
                    </div>
                    <textarea aria-label="Edit confirmed script" value={scriptText} rows={8} onChange={(event) => setScriptText(event.target.value)} />
                    <button className="mini-action" type="button" onClick={confirmSelectedScript}>确认脚本</button>
                    {scriptDraft.draft.render_ready && <p>已确认，可进入后续渲染。</p>}
                  </>
                )}
              </div>
              <div className="credit-card">
                <b>团队素材库</b>
                <input
                  aria-label="Upload asset"
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
                            aria-label="Edit asset tags"
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
                    <select aria-label="Select AI provider" value={providers.selectedId ?? ""} onChange={(event) => estimateSelectedProvider(Number(event.target.value))}>
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
