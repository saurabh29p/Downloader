/**
 * Typed client for the AnyGet API.
 * `schema.ts` is generated from the FastAPI OpenAPI schema: run `make gen` after API changes.
 */
import type { Client } from "openapi-fetch";

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
export type ToolVersions = components["schemas"]["ToolVersions"];

/** Sent with every call: the API refuses cookie-signed writes without it (CSRF). */
export const CSRF_HEADERS = { "X-Requested-With": "anyget" } as const;

type Init = {
  params?: { path?: Record<string, unknown>; query?: Record<string, unknown> };
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
};

/**
 * The typed client. Types come from openapi-fetch; the runtime is this small
 * fetch wrapper with the same results ({ data } | { error }, plus `response`),
 * which keeps ~2.5 KB off every page. JSON bodies only; arrays in the query
 * repeat the key (`k=a&k=b`).
 */
export function createApiClient(baseUrl = "", init?: { fetch?: typeof fetch }): Client<paths> {
  const send = async (method: string, path: string, options: Init = {}) => {
    const { params = {}, body, headers, signal } = options;
    let url =
      baseUrl +
      path.replace(/\{(\w+)\}/g, (_, key: string) =>
        encodeURIComponent(String(params.path?.[key])),
      );
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params.query ?? {})) {
      if (value == null) continue;
      for (const item of Array.isArray(value) ? value : [value]) query.append(key, String(item));
    }
    const search = String(query);
    if (search) url += `?${search}`;
    const json = body === undefined ? undefined : JSON.stringify(body);
    const request = new Request(url, {
      method,
      body: json,
      signal,
      headers: {
        ...(json === undefined ? {} : { "Content-Type": "application/json" }),
        ...CSRF_HEADERS,
        ...headers,
      },
    });
    const response = await (init?.fetch ?? globalThis.fetch)(request);
    if (response.status === 204 || response.headers.get("Content-Length") === "0") {
      return response.ok ? { data: undefined, response } : { error: undefined, response };
    }
    const text = await response.text();
    let parsed: unknown = text || undefined;
    try {
      parsed = text ? JSON.parse(text) : undefined;
    } catch {
      // not JSON: keep the text (errors) as openapi-fetch does
    }
    return response.ok ? { data: parsed, response } : { error: parsed, response };
  };
  const method = (name: string) => (path: string, options?: Init) => send(name, path, options);
  return {
    GET: method("GET"),
    POST: method("POST"),
    PUT: method("PUT"),
    PATCH: method("PATCH"),
    DELETE: method("DELETE"),
  } as unknown as Client<paths>;
}

export type ApiClient = Client<paths>;
export type ArchiveItem = components["schemas"]["ArchiveItemOut"];
export type ArchiveFile = components["schemas"]["ArchiveFile"];
export type ArchiveSearchPage = components["schemas"]["SearchPage"];
export type ArchiveHit = components["schemas"]["SearchHit"];
export type SnapshotList = components["schemas"]["SnapshotList"];
export type Snapshot = components["schemas"]["Snapshot"];
export type BookHit = components["schemas"]["BookHit"];
export type BookFormat = components["schemas"]["BookFormat"];
export type BookSearch = components["schemas"]["BookSearch"];
export type SourceStatus = components["schemas"]["SourceStatus"];
export type Library = components["schemas"]["LibraryOut"];
export type LibraryList = components["schemas"]["LibraryList"];
export type UniversalSearch = components["schemas"]["UniversalSearch"];
export type VideoHit = components["schemas"]["VideoHit"];
export type LibraryItem = components["schemas"]["LibraryItemOut"];
export type LibraryPage = components["schemas"]["LibraryPage"];
export type EpubPreview = components["schemas"]["EpubPreview"];
export type Watch = components["schemas"]["WatchOut"];
export type WatchRunResult = components["schemas"]["WatchRunResult"];
export type SettingsView = components["schemas"]["SettingsView"];
export type SettingsUpdate = components["schemas"]["SettingsUpdate"];
export type YtDlpVersion = components["schemas"]["YtDlpVersion"];
export type Me = components["schemas"]["Me"];
