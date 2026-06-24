export type HealthPayload = {
  status: string;
  service: string;
  app: string;
};

export type ClientVersionPayload = {
  platform: string;
  version: string;
  download_url: string;
  notes?: string;
};

export type WorkspaceSummary = {
  id: number;
  name: string;
  role?: string;
};

export type CreditPayload = {
  workspace_id: number;
  balance: number;
  frozen: number;
};

export type CreditTaskPayload = {
  task: {
    id: number;
    title: string;
    status: string;
    estimated_credits: number;
  };
  credits: CreditPayload;
};

export type JobPayload = {
  id: number;
  workspace_id?: number;
  title: string;
  status: string;
  steps: string[];
  current_step: string;
  estimated_wait_seconds: number;
  error_message?: string;
  credit_task_id?: number;
  voiceover_mode?: string;
  voiceover_provider_id?: number;
  source_audio_asset_id?: number;
  output_asset_id?: number;
  audio_placeholder?: string;
  subtitles?: SubtitleCue[];
  render?: { width?: number; height?: number; source_asset_ids?: number[]; subtitles_burned?: boolean };
  created_at?: string;
};
export type SubtitleCue = { start: number; end: number; text: string };
export type JobsPayload = {
  jobs: JobPayload[];
  concurrency_limits: { global: number; workspace: number };
};
export type JobMutationPayload = { job: JobPayload; credits: CreditPayload };
export type JobRenderPayload = JobMutationPayload;
export type BatchRemixPayload = { jobs: JobPayload[]; credits: CreditPayload };

export type AiProvider = {
  id: number;
  capability: string;
  name: string;
  model_name: string;
  price_coefficient: string;
};

export type AiProvidersPayload = { providers: AiProvider[] };
export type AiEstimatePayload = { provider_id: number; estimated_credits: number };

export type CustomerProfile = {
  id?: number;
  workspace_id?: number;
  name: string;
  industry?: string;
  products?: string;
  target_audience?: string;
  selling_points?: string;
  forbidden_words?: string;
  contact_hooks?: string;
  style_preference?: string;
  logo_or_common_assets?: string;
};

export type CustomersPayload = { customers: CustomerProfile[] };

export type Asset = {
  id: number;
  workspace_id?: number;
  filename: string;
  content_type?: string;
  asset_type?: string;
  object_key?: string;
  retention_days?: number;
  suggested_tags?: string[];
  tags?: string[];
  expires_at?: string;
  deleted?: boolean;
  preview_url?: string;
};

export type AssetsPayload = { assets: Asset[] };
export type AssetUploadPayload = {
  asset: Asset;
  upload: { method: string; url: string; headers: Record<string, string> };
};

export type IndustryTemplate = { id: number; name: string; industry?: string; prompt?: string };
export type ViralSample = {
  id?: number;
  scope?: string;
  workspace_id?: number;
  customer_id?: number;
  title?: string;
  source_url?: string;
  copy: string;
  structure_analysis?: string;
  tags?: string[];
  rewrite?: string;
};
export type ScriptAssetsPayload = { templates: IndustryTemplate[]; samples: ViralSample[] };
export type ScriptDraftPayload = {
  id: number;
  workspace_id?: number;
  customer_id: number;
  template_id: number;
  provider_id: number;
  duration_seconds: number;
  sample_ids: number[];
  candidates: string[];
  confirmed_script: string;
  render_ready: boolean;
};
export type GenerateScriptInput = {
  customerId: number;
  templateId: number;
  providerId: number;
  durationSeconds: number;
  sampleIds: number[];
};

export type AuthPayload = {
  token: string;
  user: { id?: number; email: string };
  workspace: { id: number; name: string };
  workspaces: WorkspaceSummary[];
};

export type MePayload = {
  user: { id?: number; email: string };
  workspaces: WorkspaceSummary[];
};

type FetchResponse<T> = {
  ok: boolean;
  status?: number;
  json: () => Promise<T>;
};

type Fetcher = <T = unknown>(input: string, init?: RequestInit) => Promise<FetchResponse<T>>;
type BlobFetcher = (input: string, init?: RequestInit) => Promise<{ ok: boolean; status?: number; blob: () => Promise<Blob> }>;

export const defaultApiBase = "http://127.0.0.1:8000";

function apiUrl(apiBase: string, path: string) {
  return `${apiBase.replace(/\/$/, "")}${path}`;
}

async function readJson<T>(response: FetchResponse<T>): Promise<T> {
  const payload = await response.json();
  if (!response.ok) {
    const error = payload && typeof payload === "object" && "error" in payload ? String(payload.error) : `Request failed: ${response.status ?? "unknown"}`;
    throw new Error(error);
  }
  return payload;
}

export async function fetchHealth(
  apiBase = defaultApiBase,
  fetcher: Fetcher = fetch,
): Promise<HealthPayload> {
  const response = await fetcher<HealthPayload>(apiUrl(apiBase, "/api/health/"));
  return readJson(response);
}

export async function fetchClientVersion(
  apiBase = defaultApiBase,
  fetcher: Fetcher = fetch,
): Promise<ClientVersionPayload> {
  const response = await fetcher<ClientVersionPayload>(apiUrl(apiBase, "/api/client/version/"));
  return readJson(response);
}

export function isNewerVersion(remote: string, current: string) {
  const left = remote.split(".").map((part) => Number(part) || 0);
  const right = current.split(".").map((part) => Number(part) || 0);
  for (let index = 0; index < Math.max(left.length, right.length); index += 1) {
    if ((left[index] ?? 0) > (right[index] ?? 0)) return true;
    if ((left[index] ?? 0) < (right[index] ?? 0)) return false;
  }
  return false;
}

export async function registerWithInvite(
  apiBase: string,
  input: { email: string; password: string; inviteCode: string },
  fetcher: Fetcher = fetch,
): Promise<AuthPayload> {
  const response = await fetcher<AuthPayload>(apiUrl(apiBase, "/api/auth/register/"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: input.email,
      password: input.password,
      invite_code: input.inviteCode,
    }),
  });
  return readJson(response);
}

export async function login(
  apiBase: string,
  email: string,
  password: string,
  fetcher: Fetcher = fetch,
): Promise<AuthPayload> {
  const response = await fetcher<AuthPayload>(apiUrl(apiBase, "/api/auth/login/"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return readJson(response);
}

export async function fetchMe(
  apiBase: string,
  token: string,
  fetcher: Fetcher = fetch,
): Promise<MePayload> {
  const response = await fetcher<MePayload>(apiUrl(apiBase, "/api/auth/me/"), {
    headers: { Authorization: `Bearer ${token}` },
  });
  return readJson(response);
}

export async function fetchCredits(
  apiBase: string,
  token: string,
  fetcher: Fetcher = fetch,
): Promise<CreditPayload> {
  const response = await fetcher<CreditPayload>(apiUrl(apiBase, "/api/credits/"), {
    headers: { Authorization: `Bearer ${token}` },
  });
  return readJson(response);
}

export async function submitCreditTask(
  apiBase: string,
  token: string,
  input: { title: string; estimatedCredits: number },
  fetcher: Fetcher = fetch,
): Promise<CreditTaskPayload> {
  const response = await fetcher<CreditTaskPayload>(apiUrl(apiBase, "/api/credit-tasks/"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      title: input.title,
      estimated_credits: input.estimatedCredits,
    }),
  });
  return readJson(response);
}

export async function fetchJobs(
  apiBase: string,
  token: string,
  fetcher: Fetcher = fetch,
): Promise<JobsPayload> {
  const response = await fetcher<JobsPayload>(apiUrl(apiBase, "/api/jobs/"), {
    headers: { Authorization: `Bearer ${token}` },
  });
  return readJson(response);
}

export async function createJob(
  apiBase: string,
  token: string,
  input: { title: string; estimatedCredits: number; scriptDraftId: number },
  fetcher: Fetcher = fetch,
): Promise<JobMutationPayload> {
  const response = await fetcher<JobMutationPayload>(apiUrl(apiBase, "/api/jobs/"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ title: input.title, estimated_credits: input.estimatedCredits, script_draft_id: input.scriptDraftId }),
  });
  return readJson(response);
}

export async function createBatchRemix(
  apiBase: string,
  token: string,
  input: { assetIds: number[]; variants: number; estimatedCredits: number; scriptDraftId: number },
  fetcher: Fetcher = fetch,
): Promise<BatchRemixPayload> {
  const response = await fetcher<BatchRemixPayload>(apiUrl(apiBase, "/api/jobs/batch-remix/"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      asset_ids: input.assetIds,
      variants: input.variants,
      estimated_credits: input.estimatedCredits,
      script_draft_id: input.scriptDraftId,
    }),
  });
  return readJson(response);
}

export async function transitionJob(
  apiBase: string,
  token: string,
  jobId: number,
  status: string,
  currentStep = "",
  fetcher: Fetcher = fetch,
): Promise<JobMutationPayload> {
  const body: { status: string; current_step?: string } = { status };
  if (currentStep) body.current_step = currentStep;
  const response = await fetcher<JobMutationPayload>(apiUrl(apiBase, `/api/jobs/${jobId}/transition/`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });
  return readJson(response);
}

export async function configureJobVoiceover(
  apiBase: string,
  token: string,
  jobId: number,
  input: { mode: string; providerId?: number; script?: string; assetId?: number; subtitles?: SubtitleCue[] },
  fetcher: Fetcher = fetch,
): Promise<JobMutationPayload> {
  const response = await fetcher<JobMutationPayload>(apiUrl(apiBase, `/api/jobs/${jobId}/voiceover/`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      mode: input.mode,
      provider_id: input.providerId,
      script: input.script,
      asset_id: input.assetId,
      subtitles: input.subtitles,
    }),
  });
  return readJson(response);
}

export async function updateJobSubtitles(
  apiBase: string,
  token: string,
  jobId: number,
  subtitles: SubtitleCue[],
  fetcher: Fetcher = fetch,
): Promise<JobMutationPayload> {
  const response = await fetcher<JobMutationPayload>(apiUrl(apiBase, `/api/jobs/${jobId}/subtitles/`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ subtitles }),
  });
  return readJson(response);
}

export async function renderJob(
  apiBase: string,
  token: string,
  jobId: number,
  assetIds: number[],
  fetcher: Fetcher = fetch,
): Promise<JobRenderPayload> {
  const response = await fetcher<JobRenderPayload>(apiUrl(apiBase, `/api/jobs/${jobId}/render/`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ asset_ids: assetIds }),
  });
  return readJson(response);
}

export async function fetchAssetPreviewBlob(
  apiBase: string,
  token: string,
  previewUrl: string,
  fetcher: BlobFetcher = fetch,
): Promise<Blob> {
  const response = await fetcher(apiUrl(apiBase, previewUrl), {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`Preview failed: ${response.status ?? "unknown"}`);
  return response.blob();
}

export async function fetchAiProviders(
  apiBase: string,
  token: string,
  fetcher: Fetcher = fetch,
): Promise<AiProvidersPayload> {
  const response = await fetcher<AiProvidersPayload>(apiUrl(apiBase, "/api/ai/providers/"), {
    headers: { Authorization: `Bearer ${token}` },
  });
  return readJson(response);
}

export async function estimateAiCredits(
  apiBase: string,
  token: string,
  providerId: number,
  baseCredits: number,
  fetcher: Fetcher = fetch,
): Promise<AiEstimatePayload> {
  const response = await fetcher<AiEstimatePayload>(apiUrl(apiBase, "/api/ai/estimate/"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ provider_id: providerId, base_credits: baseCredits }),
  });
  return readJson(response);
}

export async function fetchCustomers(
  apiBase: string,
  token: string,
  fetcher: Fetcher = fetch,
): Promise<CustomersPayload> {
  const response = await fetcher<CustomersPayload>(apiUrl(apiBase, "/api/customers/"), {
    headers: { Authorization: `Bearer ${token}` },
  });
  return readJson(response);
}

export async function saveCustomer(
  apiBase: string,
  token: string,
  input: CustomerProfile,
  fetcher: Fetcher = fetch,
): Promise<CustomerProfile> {
  const { id, workspace_id, ...body } = input;
  const response = await fetcher<CustomerProfile>(apiUrl(apiBase, id ? `/api/customers/${id}/` : "/api/customers/"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });
  return readJson(response);
}

export async function fetchAssets(
  apiBase: string,
  token: string,
  fetcher: Fetcher = fetch,
): Promise<AssetsPayload> {
  const response = await fetcher<AssetsPayload>(apiUrl(apiBase, "/api/assets/"), {
    headers: { Authorization: `Bearer ${token}` },
  });
  return readJson(response);
}

export async function createAssetUpload(
  apiBase: string,
  token: string,
  filename: string,
  contentType: string,
  fetcher: Fetcher = fetch,
): Promise<AssetUploadPayload> {
  const response = await fetcher<AssetUploadPayload>(apiUrl(apiBase, "/api/assets/"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ filename, content_type: contentType }),
  });
  return readJson(response);
}

export function contentTypeFor(filename: string, browserType = "") {
  const type = browserType.trim();
  if (type) return type;
  const ext = filename.toLowerCase().split(".").pop();
  return {
    mp4: "video/mp4",
    mov: "video/quicktime",
    jpg: "image/jpeg",
    jpeg: "image/jpeg",
    png: "image/png",
    webp: "image/webp",
    mp3: "audio/mpeg",
    wav: "audio/wav",
  }[ext ?? ""] ?? "";
}

export async function deleteAsset(
  apiBase: string,
  token: string,
  assetId: number,
  fetcher: Fetcher = fetch,
): Promise<Asset> {
  const response = await fetcher<Asset>(apiUrl(apiBase, `/api/assets/${assetId}/delete/`), {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  return readJson(response);
}

export async function updateAssetTags(
  apiBase: string,
  token: string,
  assetId: number,
  tags: string[],
  fetcher: Fetcher = fetch,
): Promise<Asset> {
  const response = await fetcher<Asset>(apiUrl(apiBase, `/api/assets/${assetId}/tags/`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ tags }),
  });
  return readJson(response);
}

export async function fetchScriptAssets(
  apiBase: string,
  token: string,
  fetcher: Fetcher = fetch,
): Promise<ScriptAssetsPayload> {
  const response = await fetcher<ScriptAssetsPayload>(apiUrl(apiBase, "/api/script-assets/"), {
    headers: { Authorization: `Bearer ${token}` },
  });
  return readJson(response);
}

export async function saveViralSample(
  apiBase: string,
  token: string,
  input: ViralSample,
  fetcher: Fetcher = fetch,
): Promise<ViralSample> {
  const response = await fetcher<ViralSample>(apiUrl(apiBase, "/api/viral-samples/"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(input),
  });
  return readJson(response);
}

export async function generateScripts(
  apiBase: string,
  token: string,
  input: GenerateScriptInput,
  fetcher: Fetcher = fetch,
): Promise<ScriptDraftPayload> {
  const response = await fetcher<ScriptDraftPayload>(apiUrl(apiBase, "/api/scripts/generate/"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      customer_id: input.customerId,
      template_id: input.templateId,
      provider_id: input.providerId,
      duration_seconds: input.durationSeconds,
      sample_ids: input.sampleIds,
    }),
  });
  return readJson(response);
}

export async function confirmScript(
  apiBase: string,
  token: string,
  scriptId: number,
  script: string,
  fetcher: Fetcher = fetch,
): Promise<ScriptDraftPayload> {
  const response = await fetcher<ScriptDraftPayload>(apiUrl(apiBase, `/api/scripts/${scriptId}/confirm/`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ script }),
  });
  return readJson(response);
}
