/** Saved playback positions ("resume where you left off"), per file, on this device. */
const KEY = (id: string) => `anyget-pos:${id}`;
const MIN_RESUME = 10; // seconds: shorter is not worth resuming
const END_MARGIN = 5; // seconds before the end count as finished

export function savedPosition(id: string): number | null {
  try {
    const value = Number(localStorage.getItem(KEY(id)));
    return Number.isFinite(value) && value > 0 ? value : null;
  } catch {
    return null;
  }
}

export function savePosition(id: string, seconds: number, duration: number) {
  try {
    if (!Number.isFinite(duration) || seconds < MIN_RESUME || duration - seconds < END_MARGIN) {
      localStorage.removeItem(KEY(id));
    } else {
      localStorage.setItem(KEY(id), String(Math.floor(seconds)));
    }
  } catch {
    // storage blocked: resuming is a convenience only
  }
}

/** Where to resume, or null to start at the beginning. */
export function resumeFrom(id: string, duration: number): number | null {
  const saved = savedPosition(id);
  if (saved == null || saved < MIN_RESUME) return null;
  if (Number.isFinite(duration) && duration - saved < END_MARGIN) return null;
  return saved;
}
