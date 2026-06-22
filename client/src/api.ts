export type HealthPayload = {
  status: string;
  service: string;
  app: string;
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

export type AiProvider = {
  id: number;
  capability: string;
  name: string;
  model_name: string;
  price_coefficient: string;
};

export type AiProvidersPayload = { providers: AiProvider[] };
export type AiEstimatePayload = { provider_id: number; estimated_credits: number };

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
