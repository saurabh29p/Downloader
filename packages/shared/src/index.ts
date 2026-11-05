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
export type KeyStatus = components["schemas"]["KeyStatus"];
export type LibraryItem = components["schemas"]["LibraryItemOut"];
export type LibraryPage = components["schemas"]["LibraryPage"];
export type EpubPreview = components["schemas"]["EpubPreview"];
export type Watch = components["schemas"]["WatchOut"];
export type WatchRunResult = components["schemas"]["WatchRunResult"];
export type SettingsView = components["schemas"]["SettingsView"];
export type SettingsUpdate = components["schemas"]["SettingsUpdate"];
export type YtDlpVersion = components["schemas"]["YtDlpVersion"];
