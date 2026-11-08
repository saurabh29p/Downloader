import type { Track } from "@/lib/player";

/** A library item as a track (its file URL is authorised by the session cookie). */
export function trackOf(item: {
  id: string;
  title: string;
  thumbnail?: string | null;
  source?: string | null;
}): Track {
  return {
    id: item.id,
    title: item.title,
    src: `/api/library/${encodeURIComponent(item.id)}/file`,
    artwork: item.thumbnail,
    source: item.source,
  };
}
