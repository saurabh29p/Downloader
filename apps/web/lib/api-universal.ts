/**
 * Universal search events (GET /api/universal, Server-Sent Events). The stream is not in
 * the OpenAPI schema, so these mirror apps/api/anyget/universal/models.py by hand.
 */
export type Media =
  | "movie"
  | "book"
  | "music"
  | "video"
  | "declassified"
  | "map"
  | "newspaper"
  | "photo"
  | "manuscript"
  | "other";
export type Licence = "public_domain" | "cc" | "rights_reserved" | "streaming_only" | "unknown";
export type UniversalSource = "archive" | "books" | "videos" | "libraries" | "tmdb" | "commons";

export type ResultCard = {
  id: string;
  source: UniversalSource;
  source_label: string;
  title: string;
  url: string;
  download: string | null;
  media: Media;
  licence: Licence;
  year: string | null;
  creator: string | null;
  formats: string[];
  thumbnail: string | null;
  score: number;
  movie?: MovieInfo | null;
};

export type Provider = { name: string; logo: string | null };
export type MovieInfo = {
  tmdb_id: number;
  overview: string | null;
  rating: number | null;
  cast: string[];
  trailer: string | null;
  region: string;
  stream: Provider[];
  free: Provider[];
  rent: Provider[];
  buy: Provider[];
  watch_link: string | null;
};

export type RouterPlan = {
  kind: "url" | "search" | "question";
  intent: string;
  media: Media[];
  language: string;
  queries: { source: UniversalSource; q: string; filters: Record<string, string> }[];
  answer_needed: boolean;
  urls: string[];
  router: "keyword" | "llm";
};

export type SourceDone = {
  source: UniversalSource;
  status: "ok" | "timeout" | "error" | "needs_key";
  message: string | null;
  results: ResultCard[];
};

export function universalUrl(q: string, section?: string, preset?: string): string {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (section) params.set("section", section);
  if (preset) params.set("preset", preset);
  return `/api/universal?${params}`;
}
