/** archive.org and Wayback calls (own module: only the archive pages load it). */
import { api, call } from "@/lib/api";

export type ArchiveQuery = {
  q: string;
  mediatype?: string;
  collection?: string;
  year_from?: number;
  year_to?: number;
  language?: string;
  creator?: string;
  page?: number;
};

export const archiveSearch = (query: ArchiveQuery) =>
  call(api.GET("/api/archive/search", { params: { query } }));

export const archiveItem = (identifier: string) =>
  call(api.GET("/api/archive/items/{identifier}", { params: { path: { identifier } } }));

export const waybackSnapshots = (url: string) =>
  call(api.GET("/api/wayback/snapshots", { params: { query: { url } } }));
