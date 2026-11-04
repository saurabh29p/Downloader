import type { Job, JobState } from "@anyget/shared";

export const ACTIVE_STATES: readonly JobState[] = ["queued", "probing", "downloading"];
export const FINISHED_STATES: readonly JobState[] = ["done", "failed", "canceled"];

export type JobFilter = "all" | "active" | "done" | "failed";

export const isActive = (job: Pick<Job, "state">) => ACTIVE_STATES.includes(job.state);

export function matchesFilter(job: Job, filter: JobFilter): boolean {
  switch (filter) {
    case "all":
      return true;
    case "active":
      return isActive(job) || job.state === "paused";
    case "done":
      return job.state === "done";
    case "failed":
      return job.state === "failed" || job.state === "canceled";
  }
}

/** Percent 0–100, or null when the size is unknown. */
export function progressPercent(job: Pick<Job, "downloaded" | "total" | "state">): number | null {
  if (job.state === "done") return 100;
  if (!job.total) return null;
  return Math.min(100, Math.round((job.downloaded / job.total) * 100));
}

/** Seconds left at the current speed, or null. */
export function etaSeconds(job: Pick<Job, "downloaded" | "total" | "speed">): number | null {
  if (!job.total || !job.speed || job.speed <= 0) return null;
  return Math.max(0, Math.round((job.total - job.downloaded) / job.speed));
}

export type JobEvent =
  { type: "job.created" | "job.updated"; job: Job } | { type: "job.deleted"; job: { id: string } };

/** Apply one server event to the cached job list (newest first). */
export function applyJobEvent(jobs: readonly Job[] | undefined, event: JobEvent): Job[] {
  const list = jobs ? [...jobs] : [];
  const index = list.findIndex((job) => job.id === event.job.id);
  if (event.type === "job.deleted") {
    if (index >= 0) list.splice(index, 1);
    return list;
  }
  if (index >= 0) {
    const current = list[index]!;
    // Events can arrive out of order with a refetch; keep the newer copy.
    if (isNewer(current, event.job)) return list;
    list[index] = event.job;
  } else {
    list.unshift(event.job);
  }
  return list;
}

const time = (value: string) => Date.parse(value) || 0;

/** True if a is a strictly newer copy of the same job than b. */
export function isNewer(a: Pick<Job, "updated_at">, b: Pick<Job, "updated_at">): boolean {
  return time(a.updated_at) > time(b.updated_at);
}

/**
 * Merge a fresh job list from the server with the cached one, keeping whichever
 * copy of each job is newer. A slow refetch can then never undo a live update.
 */
export function mergeJobs(cached: readonly Job[] | undefined, fresh: readonly Job[]): Job[] {
  if (!cached?.length) return [...fresh];
  const byId = new Map(cached.map((job) => [job.id, job]));
  return fresh.map((job) => {
    const old = byId.get(job.id);
    return old && isNewer(old, job) ? old : job;
  });
}

export function jobName(job: Pick<Job, "filename" | "title" | "url">): string {
  return job.filename || job.title || job.url;
}
