import { createApiClient } from "@anyget/shared";

/** Browser-side client. Same origin: Next.js rewrites /api/* to the FastAPI server. */
export const api = createApiClient("");

export async function getHealth() {
  const { data, error } = await api.GET("/api/health");
  if (error || !data) throw new Error("API health check failed");
  return data;
}
