export type HealthPayload = {
  status: string;
  service: string;
  app: string;
};

type Fetcher = (input: string) => Promise<{
  ok: boolean;
  status?: number;
  json: () => Promise<HealthPayload>;
}>;

export const defaultApiBase = "http://127.0.0.1:8000";

export async function fetchHealth(
  apiBase = defaultApiBase,
  fetcher: Fetcher = fetch,
): Promise<HealthPayload> {
  const response = await fetcher(`${apiBase.replace(/\/$/, "")}/api/health/`);
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status ?? "unknown"}`);
  }
  return response.json();
}
