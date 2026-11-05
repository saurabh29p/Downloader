/**
 * Typed client for the AnyGet API.
 * `schema.ts` is generated from the FastAPI OpenAPI schema: run `make gen` after API changes.
 */
import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

export type { components, paths };
export type Health = components["schemas"]["Health"];
export type VersionInfo = components["schemas"]["VersionInfo"];
export type Job = components["schemas"]["JobOut"];
export type JobState = Job["state"];
export type ProbeResult = components["schemas"]["ProbeResult"];
export type CreateJobsResult = components["schemas"]["CreateJobsResult"];
export type RejectedUrl = components["schemas"]["RejectedUrl"];
export type ApiErrorBody = components["schemas"]["ApiError"];
export type JobItem = components["schemas"]["JobItem"];
export type CookiesStatus = components["schemas"]["CookiesStatus"];
export type ToolVersions = components["schemas"]["ToolVersions"];

export function createApiClient(baseUrl = "", init?: { fetch?: typeof fetch }) {
  return createClient<paths>({ baseUrl, ...init });
}

export type ApiClient = ReturnType<typeof createApiClient>;
