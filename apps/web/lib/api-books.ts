/** Books, libraries, universal search and conversions (own module: only those pages load it). */
import type { BookHit, SourceStatus } from "@anyget/shared";

import { api, call } from "@/lib/api";

export type SearchTab = "books" | "libraries" | "archive" | "videos";
export type ConvertTarget = "pdf" | "ocr" | "mp3" | "m4a";

export const searchBooks = (q: string, lang?: string, sources?: string[]) =>
  call(
    api.GET("/api/books/search", {
      params: {
        query: { q, lang: lang || undefined, sources: sources?.length ? sources : undefined },
      },
    }),
  );

/** One source's answer while a book search streams (not ranked yet). */
export type BookSourcePart = { source: SourceStatus; results?: BookHit[] };

/** Server-Sent Events URL: `source` events as each source answers, then `done`. */
export function bookStreamUrl(q: string, lang?: string): string {
  const params = new URLSearchParams({ q });
  if (lang) params.set("lang", lang);
  return `/api/books/search/stream?${params}`;
}

export const listLibraries = () => call(api.GET("/api/libraries"));

export const universalSearch = (q: string, types: SearchTab[]) =>
  call(api.GET("/api/search", { params: { query: { q, types } } }));

export const convertJob = (job_id: string, to: ConvertTarget, lang?: string) =>
  call(api.POST("/api/convert", { body: { job_id, to, lang: lang || null } }));
