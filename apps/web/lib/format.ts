/**
 * Wrap a left-to-right value (like "1.4 MB") in Unicode isolate marks so it
 * keeps its order inside right-to-left sentences.
 */
export const isolate = (value: string) => `\u2066${value}\u2069`;

const UNITS = ["B", "KB", "MB", "GB", "TB"] as const;

/** 1536 → "1.5 KB" using the locale's digits. */
export function formatBytes(bytes: number | null | undefined, locale: string): string {
  if (bytes == null || !Number.isFinite(bytes)) return "—";
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const digits = unit === 0 || value >= 100 ? 0 : 1;
  // Non-breaking space: the number and its unit never split across lines.
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(value)}\u00a0${UNITS[unit]}`;
}

/** Seconds → "1:05" or "1:02:05". */
export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m);
  return `${h > 0 ? `${h}:` : ""}${mm}:${String(s).padStart(2, "0")}`;
}
