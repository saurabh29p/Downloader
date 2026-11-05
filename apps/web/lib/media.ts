/** Types and helpers for media (yt-dlp) probes and the format picker. */

export type Preset = "best" | "2160" | "1440" | "1080" | "720" | "480" | "360" | "audio";
export type Container = "mp4" | "mkv" | "webm";
export type AudioFormat = "mp3" | "m4a" | "opus";

export type MediaFormat = {
  id: string;
  ext: string;
  kind: "video" | "audio" | "video+audio";
  height: number | null;
  fps: number | null;
  vcodec: string | null;
  acodec: string | null;
  abr: number | null;
  size: number | null;
  size_is_estimate: boolean;
  label: string;
};

export type VideoExtra = {
  kind: "video";
  extractor: string;
  id: string;
  webpage_url: string;
  duration: number | null;
  uploader: string | null;
  upload_date: string | null;
  is_short: boolean;
  formats: MediaFormat[];
  presets: Preset[];
  preset_sizes: Partial<Record<Preset, number | null>>;
  subtitles: string[];
  auto_captions: string[];
  chapters: number;
  archive: string;
  saved: boolean;
};

export type Entry = {
  index: number;
  id: string;
  url: string;
  title: string;
  duration: number | null;
  thumbnail: string | null;
  is_short: boolean;
  live: boolean;
  archive_id: string;
  saved: boolean;
};

export type Tab = "videos" | "shorts" | "streams";

export type ListExtra = {
  kind: "playlist" | "channel";
  extractor: string;
  id: string | null;
  webpage_url: string;
  uploader: string | null;
  count: number;
  entries: Entry[];
  tabs: Tab[];
  tab: Tab | null;
  archive: string;
};

export type MediaExtra = VideoExtra | ListExtra;

export const isVideo = (extra: unknown): extra is VideoExtra =>
  !!extra && (extra as { kind?: string }).kind === "video";
export const isList = (extra: unknown): extra is ListExtra =>
  !!extra && ["playlist", "channel"].includes((extra as { kind?: string }).kind ?? "");

/** What the user picked. */
export type Selection = {
  preset: Exclude<Preset, "audio">;
  audioOnly: boolean;
  audioFormat: AudioFormat;
  container: Container;
  formatId: string | null;
  subtitles: string[];
  autoSubtitles: boolean;
  subtitlesMode: "srt" | "embed";
  embedThumbnail: boolean;
  embedMetadata: boolean;
  chapters: boolean;
  infoJson: boolean;
};

export const BATCH_PRESETS: Exclude<Preset, "audio">[] = [
  "best",
  "2160",
  "1440",
  "1080",
  "720",
  "480",
  "360",
];

export function defaultSelection(extra?: VideoExtra): Selection {
  const presets = (extra?.presets ?? BATCH_PRESETS).filter(
    (p): p is Exclude<Preset, "audio"> => p !== "audio",
  );
  const preferred = presets.includes("1080") ? "1080" : (presets[0] ?? "best");
  return {
    preset: preferred,
    audioOnly: false,
    audioFormat: "mp3",
    container: "mp4",
    formatId: null,
    subtitles: [],
    autoSubtitles: false,
    subtitlesMode: "srt",
    embedThumbnail: true,
    embedMetadata: true,
    chapters: true,
    infoJson: false,
  };
}

/** Job options the API understands (see MediaOptions in the API). */
export function toJobOptions(sel: Selection): Record<string, unknown> {
  const options: Record<string, unknown> = {
    preset: sel.audioOnly ? "audio" : sel.preset,
    embed_thumbnail: sel.embedThumbnail,
    embed_metadata: sel.embedMetadata,
    chapters: sel.chapters,
    write_info_json: sel.infoJson,
  };
  if (sel.audioOnly) {
    options.audio_format = sel.audioFormat;
  } else {
    options.container = sel.container;
    if (sel.formatId) options.format_id = sel.formatId;
  }
  if (sel.subtitles.length > 0) {
    options.subtitles = sel.subtitles;
    options.auto_subtitles = sel.autoSubtitles;
    options.subtitles_mode = sel.audioOnly ? "srt" : sel.subtitlesMode;
  }
  return options;
}

/** "20140411" → Date (UTC), or null. */
export function parseUploadDate(value: string | null | undefined): Date | null {
  if (!value || !/^\d{8}$/.test(value)) return null;
  return new Date(Date.UTC(+value.slice(0, 4), +value.slice(4, 6) - 1, +value.slice(6, 8)));
}

/** <input type="date"> value "2024-05-01" → "20240501". */
export const toYmd = (value: string) => value.replaceAll("-", "");
