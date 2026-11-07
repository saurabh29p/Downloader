/** File previews (loaded only with the viewer, or by the Open buttons). */
import type { components, LibraryItem } from "@anyget/shared";

import { api, call } from "@/lib/api";

export type FileInfo = components["schemas"]["FileInfo"];
export type TextPage = components["schemas"]["TextPage"];
export type EpubBook = components["schemas"]["EpubBook"];
export type EpubChapter = components["schemas"]["EpubChapter"];

const path = (id: string) => ({ params: { path: { item_id: id } } });

export const fileUrl = (id: string, download = false) =>
  `/api/library/${encodeURIComponent(id)}/file${download ? "?download=true" : ""}`;

export const subtitleUrl = (id: string, index: number) =>
  `/api/library/${encodeURIComponent(id)}/subtitles/${index}`;

export const fileInfo = (id: string) => call(api.GET("/api/library/{item_id}/info", path(id)));

export const textPage = (id: string, offset: number) =>
  call(
    api.GET("/api/library/{item_id}/text", {
      params: { path: { item_id: id }, query: { offset } },
    }),
  );

export const epubBook = (id: string) => call(api.GET("/api/library/{item_id}/epub", path(id)));

export const epubChapter = (id: string, index: number) =>
  call(
    api.GET("/api/library/{item_id}/epub/{index}", {
      params: { path: { item_id: id, index } },
    }),
  );

export const itemForJob = (jobId: string): Promise<LibraryItem> =>
  call(api.GET("/api/library/by-job/{job_id}", { params: { path: { job_id: jobId } } }));
