/** Books, libraries, universal search and conversions (own module: only those pages load it). */
import { api, call } from "@/lib/api";

export type SearchTab = "books" | "libraries" | "archive" | "videos";
export type ConvertTarget = "pdf" | "ocr" | "mp3" | "m4a";

export const searchBooks = (q: string, lang?: string) =>
  call(api.GET("/api/books/search", { params: { query: { q, lang: lang || undefined } } }));

export const listLibraries = () => call(api.GET("/api/libraries"));

export const universalSearch = (q: string, types: SearchTab[]) =>
  call(api.GET("/api/search", { params: { query: { q, types } } }));

export const convertJob = (job_id: string, to: ConvertTarget, lang?: string) =>
  call(api.POST("/api/convert", { body: { job_id, to, lang: lang || null } }));
