import "./prototype.css";

const modules = [
  ["爆款文案", "按平台、行业、时长生成 3 条候选脚本", "已接火山"],
  ["AI 一键成片", "素材上传后自动拆分镜、配音、字幕、剪辑", "规划中"],
  ["爆款复刻", "粘贴抖音链接，提取结构并生成同款脚本", "接口预留"],
  ["批量混剪", "同一脚本批量换素材、换钩子、换封面", "队列就绪"],
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
          {modules.map(([title, text, badge]) => (
            <button className="module-tile" key={title}>
              <span>{badge}</span>
              <strong>{title}</strong>
              <small>{text}</small>
            </button>
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
