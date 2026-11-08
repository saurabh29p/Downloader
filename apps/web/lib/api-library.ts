/** Library, watches and app settings (own module: only those pages load it). */
import type { SettingsUpdate } from "@anyget/shared";

import { api, call } from "@/lib/api";

export type LibraryKind =
  "video" | "audio" | "image" | "pdf" | "epub" | "text" | "archive" | "other";
export type LibraryQuery = {
  q?: string;
  kind?: LibraryKind;
  tag?: string;
  duplicates?: boolean;
  section?: string;
  source?: string;
  licence?: "public_domain" | "cc" | "rights_reserved" | "streaming_only" | "unknown";
};

export const listLibrary = (query: LibraryQuery) =>
  call(api.GET("/api/library", { params: { query: { ...query, limit: 200 } } }));

export const scanLibrary = () => call(api.POST("/api/library/scan"));

export const updateLibraryItem = (id: string, body: { title?: string; tags?: string[] }) =>
  call(api.PATCH("/api/library/{item_id}", { params: { path: { item_id: id } }, body }));

export async function deleteLibraryItem(id: string, deleteFile: boolean): Promise<void> {
  await call(
    api.DELETE("/api/library/{item_id}", {
      params: { path: { item_id: id }, query: { delete_file: deleteFile } },
    }),
  );
}

export const redownload = (id: string) =>
  call(api.POST("/api/library/{item_id}/redownload", { params: { path: { item_id: id } } }));

export const epubPreview = (id: string) =>
  call(api.GET("/api/library/{item_id}/preview", { params: { path: { item_id: id } } }));

export const libraryFileUrl = (id: string, download = false) =>
  `/api/library/${encodeURIComponent(id)}/file${download ? "?download=true" : ""}`;

export const listWatches = () => call(api.GET("/api/watches"));

export const createWatch = (url: string, interval_minutes: number, initial: number) =>
  call(api.POST("/api/watches", { body: { url, interval_minutes, initial, options: {} } }));

export const updateWatch = (id: string, body: { enabled?: boolean; interval_minutes?: number }) =>
  call(api.PATCH("/api/watches/{watch_id}", { params: { path: { watch_id: id } }, body }));

export async function deleteWatch(id: string): Promise<void> {
  await call(api.DELETE("/api/watches/{watch_id}", { params: { path: { watch_id: id } } }));
}

export const runWatch = (id: string) =>
  call(api.POST("/api/watches/{watch_id}/run", { params: { path: { watch_id: id } } }));

export const getSettings = () => call(api.GET("/api/settings"));

export const putSettings = (body: SettingsUpdate) => call(api.PUT("/api/settings", { body }));

export const checkYtDlp = () => call(api.GET("/api/settings/ytdlp"));

export const getLlm = () => call(api.GET("/api/llm"));

export const getRetention = () => call(api.GET("/api/retention"));
