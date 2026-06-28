import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  confirmScript,
  createJob,
  fetchAssetPreviewBlob,
  renderJob,
  uploadAssetFile,
  defaultApiBase,
  fetchAiProviders,
  fetchAssets,
  fetchCredits,
  fetchCustomers,
  fetchJobs,
  fetchMe,
  fetchScriptAssets,
  generateScripts,
  login,
  registerWithInvite,
  saveCustomer,
  type AiProvider,
  type Asset,
  type CreditPayload,
  type CustomerProfile,
  type IndustryTemplate,
  type JobPayload,
  type ScriptDraftPayload,
} from "./api";
import "./prototype.css";

const apiBase = import.meta.env.VITE_API_BASE_URL || defaultApiBase;
const tokenKey = "ai-video-workbench-token";

const modules: Array<[string, string, string, boolean]> = [
  ["爆款文案", "按平台、行业、时长生成 3 条候选脚本", "可用", true],
  ["素材库", "上传素材并进入后续剪辑任务", "可用", true],
  ["任务队列", "查看脚本确认后的制作任务", "可用", true],
  ["AI 一键成片", "自动配音、字幕、剪辑、导出", "未接入", false],
  ["爆款复刻", "粘贴抖音链接，提取结构并生成同款脚本", "未接入", false],
  ["批量混剪", "同一脚本批量换素材、换钩子、换封面", "未接入", false],
];

const scripts = [
  "别滑！夏天穿裙怕显胖的姐妹看过来，QA 家这条显瘦连衣裙，遮肉透气还不挑身材。",
  "130 斤也能放心穿的小裙子来了，腰腹胯全照顾，通勤约会一条搞定。",
  "如果你买裙子总怕显胯，这条先试试。显瘦、透气、不压身高，点左下角看细节。",
];

const tasks = [
  ["服装矩阵号", "15 秒脚本", "已生成"],
  ["珠宝柜台", "黄金手镯口播", "排队中"],
  ["餐饮探店", "套餐种草", "待确认"],
];

const assets = ["门店视频 12 条", "产品图 36 张", "爆款链接 8 条", "可用脚本 24 条"];

function hrefFor(prototype: "cockpit" | "studio") {
  const next = new URLSearchParams(window.location.search);
  next.set("prototype", prototype);
  next.delete("view");
  return `?${next.toString()}`;
}

export function WorkbenchPrototype() {
  const prototype = new URLSearchParams(window.location.search).get("prototype") === "studio" ? "studio" : "cockpit";
  return (
    <main className={`proto-shell ${prototype}`}>
      <aside className="proto-sidebar">
        <div className="proto-logo">
          <span>AI</span>
          <strong>短视频工作台</strong>
        </div>
        {["总览", "AI 成片", "爆款文案", "素材库", "批量混剪", "任务队列", "积分中心"].map((item, index) => (
          <button className={index === 0 ? "active" : ""} key={item}>{item}</button>
        ))}
        <a className="proto-live-link" href="?view=live">进入真实联调版</a>
      </aside>

      <section className="proto-main">
        <header className="proto-hero">
          <div>
            <p className="proto-kicker">Douyin AI Production Cockpit</p>
            <h1>从爆款脚本到批量成片，一条龙生产短视频</h1>
            <p>面向商家、剪辑公司、矩阵号团队：填客户资料、上传素材、选择平台，AI 自动生成脚本并进入制作队列。</p>
          </div>
          <div className="proto-status">
            <span>火山方舟已连接</span>
            <strong>Doubao Seed 2.1 Turbo</strong>
            <small>当前模式：抖音 / 15-60 秒</small>
          </div>
        </header>

        {prototype === "studio" ? <StudioView /> : <CockpitView />}
      </section>

      <nav className="proto-switcher" aria-label="Prototype variants">
        <a className={prototype === "cockpit" ? "active" : ""} href={hrefFor("cockpit")}>驾驶舱版</a>
        <a className={prototype === "studio" ? "active" : ""} href={hrefFor("studio")}>剪辑台版</a>
        <a href="?view=live">真实功能</a>
      </nav>
    </main>
  );
}

function CockpitView() {
  return (
    <>
      <LivePanel />

      <section className="proto-metrics">
        {[
          ["今日脚本", "128", "+34%"],
          ["待渲染任务", "19", "允许排队"],
          ["可用积分", "8,420", "人工充值"],
          ["素材命中率", "72%", "AI 标签"],
        ].map(([label, value, note]) => (
          <article className="proto-card metric" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
            <small>{note}</small>
          </article>
        ))}
      </section>

      <section className="proto-grid">
        <article className="proto-card proto-feature-grid">
          <div className="section-title">
            <span>功能入口</span>
            <strong>选择你今天要生产什么</strong>
          </div>
          {modules.map(([title, text, badge, enabled]) => (
            <a className={`module-tile ${enabled ? "" : "disabled"}`} href={enabled ? "#live-panel" : undefined} key={title}>
              <span>{badge}</span>
              <strong>{title}</strong>
              <small>{text}</small>
            </a>
          ))}
        </article>

        <article className="proto-card phone-card">
          <div className="phone-preview">
            <div className="phone-top" />
            <div className="caption-chip">服装 / 15 秒 / 抖音</div>
            <h2>显瘦连衣裙<br />爆款口播</h2>
            <p>钩子 → 痛点 → 卖点 → 行动</p>
            <div className="scan-line" />
          </div>
        </article>

        <article className="proto-card script-panel">
          <div className="section-title">
            <span>AI 候选脚本</span>
            <strong>火山方舟实时生成</strong>
          </div>
          {scripts.map((script, index) => (
            <button className="script-candidate" key={script}>
              <b>候选 {index + 1}</b>
              <span>{script}</span>
            </button>
          ))}
        </article>
      </section>

      <section className="proto-bottom-grid">
        <article className="proto-card">
          <div className="section-title">
            <span>素材资产</span>
            <strong>上传后给 AI 成片使用</strong>
          </div>
          <div className="asset-strip">
            {assets.map((asset) => <span key={asset}>{asset}</span>)}
          </div>
        </article>
        <article className="proto-card">
          <div className="section-title">
            <span>任务队列</span>
            <strong>批量生产进度</strong>
          </div>
          {tasks.map(([name, type, status]) => (
            <div className="task-row" key={name}>
              <span>{name}</span>
              <small>{type}</small>
              <b>{status}</b>
            </div>
          ))}
        </article>
      </section>
    </>
  );
}

function LivePanel() {
  const [token, setToken] = useState(() => localStorage.getItem(tokenKey) || "");
  const [email, setEmail] = useState(() => `qa-${Date.now()}@example.com`);
  const [password, setPassword] = useState("Password123!");
  const [inviteCode, setInviteCode] = useState("ALPHA-1");
  const [mode, setMode] = useState<"login" | "register">("register");
  const [message, setMessage] = useState("");
  const [userEmail, setUserEmail] = useState("");
  const [credits, setCredits] = useState<CreditPayload | null>(null);
  const [providers, setProviders] = useState<AiProvider[]>([]);
  const [customers, setCustomers] = useState<CustomerProfile[]>([]);
  const [templates, setTemplates] = useState<IndustryTemplate[]>([]);
  const [jobs, setJobs] = useState<JobPayload[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [selectedProviderId, setSelectedProviderId] = useState<number | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [durationSeconds, setDurationSeconds] = useState(15);
  const [draft, setDraft] = useState<ScriptDraftPayload | null>(null);
  const [scriptText, setScriptText] = useState("");
  const [rendering, setRendering] = useState(false);
  const [customerForm, setCustomerForm] = useState<CustomerProfile>({
    name: "QA服装店",
    industry: "服装",
    products: "夏季显瘦连衣裙",
    target_audience: "25-35岁女性",
    selling_points: "显瘦、透气、不挑身材",
    forbidden_words: "全网最低,绝对",
  });

  const llmProviders = useMemo(() => providers.filter((provider) => provider.capability === "llm"), [providers]);

  useEffect(() => {
    if (!token) return;
    void loadWorkspace(token);
  }, [token]);

  async function loadWorkspace(nextToken = token) {
    if (!nextToken) return;
    try {
      const [me, creditPayload, providerPayload, customerPayload, scriptAssetPayload, jobPayload, assetPayload] = await Promise.all([
        fetchMe(apiBase, nextToken),
        fetchCredits(apiBase, nextToken),
        fetchAiProviders(apiBase, nextToken),
        fetchCustomers(apiBase, nextToken),
        fetchScriptAssets(apiBase, nextToken),
        fetchJobs(apiBase, nextToken),
        fetchAssets(apiBase, nextToken),
      ]);
      setUserEmail(me.user.email);
      setCredits(creditPayload);
      setProviders(providerPayload.providers);
      setCustomers(customerPayload.customers);
      setTemplates(scriptAssetPayload.templates);
      setJobs(jobPayload.jobs);
      setAssets(assetPayload.assets);
      setSelectedProviderId(providerPayload.providers.find((provider) => provider.capability === "llm")?.id ?? null);
      setSelectedTemplateId(scriptAssetPayload.templates[0]?.id ?? null);
      if (customerPayload.customers[0]) setCustomerForm(customerPayload.customers[0]);
      setMessage("真实工作台数据已同步");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "数据加载失败");
    }
  }

  async function submitAuth(event: FormEvent) {
    event.preventDefault();
    setMessage("正在进入工作台...");
    try {
      const payload = mode === "register"
        ? await registerWithInvite(apiBase, { email, password, inviteCode })
        : await login(apiBase, email, password);
      localStorage.setItem(tokenKey, payload.token);
      setToken(payload.token);
      setUserEmail(payload.user.email);
      setMessage("登录成功，正在加载真实功能");
      await loadWorkspace(payload.token);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "登录失败");
    }
  }

  async function submitScript(event: FormEvent) {
    event.preventDefault();
    if (!token || !selectedProviderId || !selectedTemplateId) {
      setMessage("请先登录，并选择模型和模板");
      return;
    }
    setMessage("正在保存客户资料...");
    try {
      const customer = await saveCustomer(apiBase, token, customerForm);
      setCustomers((items) => [customer, ...items.filter((item) => item.id !== customer.id)]);
      setMessage("正在调用火山方舟生成爆款文案...");
      const nextDraft = await generateScripts(apiBase, token, {
        customerId: customer.id!,
        templateId: selectedTemplateId,
        providerId: selectedProviderId,
        durationSeconds,
        sampleIds: [],
      });
      setDraft(nextDraft);
      setScriptText(nextDraft.candidates[0] ?? "");
      setMessage("已生成 3 条候选脚本");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "脚本生成失败");
    }
  }

  async function confirmDraft() {
    if (!token || !draft || !scriptText.trim()) return;
    try {
      const confirmed = await confirmScript(apiBase, token, draft.id, scriptText);
      setDraft(confirmed);
      setMessage("脚本已确认，可以进入视频制作任务");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "确认脚本失败");
    }
  }

  async function addAsset(file: File | undefined) {
    if (!token || !file) return;
    try {
      const payload = await uploadAssetFile(apiBase, token, file);
      setAssets((items) => [payload.asset, ...items]);
      setMessage("???????????????");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "??????");
    }
  }

  async function startRender() {
    if (!token || !draft?.render_ready) {
      setMessage("?????????");
      return;
    }
    const sourceAssets = assets.filter((asset) => asset.asset_type === "video" || asset.asset_type === "image");
    if (!sourceAssets.length) {
      setMessage("???????????");
      return;
    }
    setRendering(true);
    setMessage("????????????? MP4...");
    try {
      const created = await createJob(apiBase, token, {
        title: `${customerForm.name || "AI"} ????`,
        estimatedCredits: 120,
        scriptDraftId: draft.id,
      });
      const payload = await renderJob(apiBase, token, created.job.id, sourceAssets.slice(0, 8).map((asset) => asset.id), true);
      setCredits(payload.credits);
      setJobs((items) => [payload.job, ...items.filter((item) => item.id !== payload.job.id)]);
      if (payload.job.status === "failed") throw new Error(payload.job.error_message || "????");
      if (payload.output_asset) setAssets((items) => [payload.output_asset!, ...items]);
      setMessage(payload.output_asset ? "??????????? MP4" : "???????");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "????");
    } finally {
      setRendering(false);
    }
  }

  async function downloadAsset(asset: Asset) {
    if (!token || !asset.preview_url) return;
    try {
      const blob = await fetchAssetPreviewBlob(apiBase, token, asset.preview_url);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = asset.filename || "ai-video.mp4";
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "????");
    }
  }


  if (!token) {
    return (
      <section className="proto-card live-panel" id="live-panel">
        <div className="section-title">
          <span>真实功能入口</span>
          <strong>先登录，再使用火山方舟生成文案</strong>
        </div>
        <form className="live-form" onSubmit={submitAuth}>
          <div className="mode-row">
            <button type="button" className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>注册</button>
            <button type="button" className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>登录</button>
          </div>
          <input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="邮箱" />
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="密码" />
          {mode === "register" && <input value={inviteCode} onChange={(event) => setInviteCode(event.target.value)} placeholder="邀请码" />}
          <button className="proto-primary">进入真实工作台</button>
          {message && <p>{message}</p>}
        </form>
      </section>
    );
  }

  return (
    <section className="proto-card live-panel" id="live-panel">
      <div className="section-title">
        <span>真实可用工作台</span>
        <strong>{userEmail || "已登录"} · 火山文案主链路</strong>
      </div>

      <div className="live-status-grid">
        <span>积分：{credits ? `${credits.balance} 可用 / ${credits.frozen} 冻结` : "加载中"}</span>
        <span>模型：{llmProviders.find((provider) => provider.id === selectedProviderId)?.name || "未选择"}</span>
        <span>客户：{customers.length}</span>
        <span>任务：{jobs.length}</span>
        <span>素材：{assets.length}</span>
      </div>

      <form className="live-workbench" onSubmit={submitScript}>
        <div className="live-form">
          <input value={customerForm.name} onChange={(event) => setCustomerForm({ ...customerForm, name: event.target.value })} placeholder="客户/品牌名称" />
          <input value={customerForm.industry ?? ""} onChange={(event) => setCustomerForm({ ...customerForm, industry: event.target.value })} placeholder="行业" />
          <input value={customerForm.products ?? ""} onChange={(event) => setCustomerForm({ ...customerForm, products: event.target.value })} placeholder="产品/服务" />
          <input value={customerForm.target_audience ?? ""} onChange={(event) => setCustomerForm({ ...customerForm, target_audience: event.target.value })} placeholder="目标人群" />
          <input value={customerForm.selling_points ?? ""} onChange={(event) => setCustomerForm({ ...customerForm, selling_points: event.target.value })} placeholder="核心卖点" />
          <input value={customerForm.forbidden_words ?? ""} onChange={(event) => setCustomerForm({ ...customerForm, forbidden_words: event.target.value })} placeholder="禁用词" />
        </div>

        <div className="live-form">
          <select value={selectedTemplateId ?? ""} onChange={(event) => setSelectedTemplateId(Number(event.target.value))}>
            {templates.map((template) => <option key={template.id} value={template.id}>{template.industry || "通用"} · {template.name}</option>)}
          </select>
          <select value={selectedProviderId ?? ""} onChange={(event) => setSelectedProviderId(Number(event.target.value))}>
            {llmProviders.map((provider) => <option key={provider.id} value={provider.id}>{provider.name} · {provider.model_name}</option>)}
          </select>
          <select value={durationSeconds} onChange={(event) => setDurationSeconds(Number(event.target.value))}>
            <option value={15}>15 秒</option>
            <option value={30}>30 秒</option>
            <option value={60}>60 秒</option>
          </select>
          <button className="proto-primary">真实生成爆款文案</button>
          <label className="upload-button">上传素材<input type="file" onChange={(event) => addAsset(event.target.files?.[0])} /></label>
        </div>
      </form>

      {message && <p className="live-message">{message}</p>}
      {assets.filter((asset) => asset.asset_type === "output").slice(0, 3).map((asset) => (
        <button className="proto-secondary" type="button" key={asset.id} onClick={() => downloadAsset(asset)}>?? {asset.filename}</button>
      ))}

      {draft && (
        <div className="live-results">
          <div>
            {draft.candidates.map((candidate, index) => (
              <button className="script-candidate" type="button" key={candidate} onClick={() => setScriptText(candidate)}>
                <b>候选 {index + 1}</b>
                <span>{candidate}</span>
              </button>
            ))}
          </div>
          <div className="live-form">
            <textarea value={scriptText} onChange={(event) => setScriptText(event.target.value)} rows={8} />
            <button className="proto-secondary" type="button" onClick={confirmDraft}>{draft.render_ready ? "已确认，可进入制作" : "确认脚本"}</button>
          </div>
        </div>
      )}
    </section>
  );
}

function StudioView() {
  return (
    <section className="studio-layout">
      <article className="proto-card studio-assets">
        <div className="section-title">
          <span>素材库</span>
          <strong>按场景自动归类</strong>
        </div>
        {["门头", "产品特写", "真人试穿", "顾客反馈", "收银台"].map((item) => (
          <div className="asset-cell" key={item}>{item}<small>AI 标签</small></div>
        ))}
      </article>

      <article className="proto-card studio-stage">
        <div className="phone-preview large">
          <div className="caption-chip">正在预览：候选 1</div>
          <h2>别滑！显瘦裙来了</h2>
          <p>字幕区：遮肉、透气、不挑身材</p>
        </div>
        <div className="timeline">
          <span style={{ width: "28%" }}>钩子</span>
          <span style={{ width: "34%" }}>痛点</span>
          <span style={{ width: "24%" }}>卖点</span>
          <span style={{ width: "14%" }}>行动</span>
        </div>
      </article>

      <article className="proto-card inspector">
        <div className="section-title">
          <span>AI 参数</span>
          <strong>控制生成口径</strong>
        </div>
        {["平台：抖音", "行业：服装", "时长：15 秒", "模型：火山方舟", "字幕：自动生成", "配音：接口预留"].map((item) => (
          <label key={item}><input type="checkbox" defaultChecked /> {item}</label>
        ))}
        <button className="proto-primary">生成 3 条脚本</button>
        <button className="proto-secondary">确认并进入剪辑</button>
      </article>
    </section>
  );
}
