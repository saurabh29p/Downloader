import { createApiClient, type ApiErrorBody, type Job, type JobItem } from "@anyget/shared";

/** Browser-side client. Same origin: Next.js rewrites /api/* to the FastAPI server. */
export const api = createApiClient("");

/** An error from the API with a stable code the UI can translate. */
export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function toApiError(error: unknown, response?: Response): ApiError {
  const body = error as Partial<ApiErrorBody> | undefined;
  if (body && typeof body.code === "string") {
    return new ApiError(body.code, body.message ?? body.code, response?.status);
  }
  if (!response) return new ApiError("network", "request failed");
  // No JSON code: the API is down (the /api forwarding fails) or crashed.
  const code = response.status >= 500 ? "server_unavailable" : "http";
  return new ApiError(code, "request failed", response.status);
}

export async function call<T>(
  promise: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  let result: { data?: T; error?: unknown; response: Response };
  try {
    result = await promise;
  } catch {
    throw new ApiError("network", "the server could not be reached");
  }
  if (result.error !== undefined || !result.response.ok) {
    const error = toApiError(result.error, result.response);
    // The session ended: sign in again (loaded only when it happens).
    if (error.status === 401) void import("@/lib/sign-in").then((m) => m.toSignIn());
    throw error;
  }
  return result.data as T;
}

export async function getHealth() {
  const { data, error } = await api.GET("/api/health");
  if (error || !data) throw new Error("API health check failed");
  return data;
}

export const probeUrl = (url: string, options: Record<string, unknown> = {}) =>
  call(api.POST("/api/probe", { body: { url, options } }));

export const createJobs = (urls: string[], options: Record<string, unknown> = {}) =>
  call(api.POST("/api/jobs", { body: { urls, options } }));

/** One job per item, each with its own options (playlist entries), plus shared options. */
export const createJobItems = (items: JobItem[], options: Record<string, unknown> = {}) =>
  call(api.POST("/api/jobs", { body: { items, options } }));

export const listJobs = () => call(api.GET("/api/jobs", { params: { query: { limit: 500 } } }));

export type JobAction = "pause" | "resume" | "retry" | "cancel";

export function jobAction(id: string, action: JobAction): Promise<Job> {
  const params = { params: { path: { job_id: id } } };
  switch (action) {
    case "pause":
      return call(api.POST("/api/jobs/{job_id}/pause", params));
    case "resume":
      return call(api.POST("/api/jobs/{job_id}/resume", params));
    case "retry":
      return call(api.POST("/api/jobs/{job_id}/retry", params));
    case "cancel":
      return call(api.POST("/api/jobs/{job_id}/cancel", params));
  }
}

export async function deleteJob(id: string, deleteFile = false): Promise<void> {
  await call(
    api.DELETE("/api/jobs/{job_id}", {
      params: { path: { job_id: id }, query: { delete_file: deleteFile } },
    }),
  );
}

export const fileUrl = (id: string) => `/api/jobs/${encodeURIComponent(id)}/file`;
