/**
 * Keeping the job list right while the live stream and list requests race.
 *
 * Every stream event is noted with the time it arrived. When a list response comes
 * back, events that arrived after its request started are applied on top of it:
 * a job created meanwhile is kept, a job deleted meanwhile stays deleted, and a newer
 * copy of a job is never replaced by the older one in the response.
 */
import type { Job } from "@anyget/shared";

import { applyJobEvent, mergeJobs, type JobEvent } from "@/lib/jobs";

type Entry = { at: number; job: Job | null }; // null: deleted
const journal = new Map<string, Entry>();
const KEEP_MS = 5 * 60_000;

export function noteEvent(event: JobEvent, at = Date.now()) {
  journal.set(event.job.id, { at, job: event.type === "job.deleted" ? null : (event.job as Job) });
  for (const [id, entry] of journal) if (at - entry.at > KEEP_MS) journal.delete(id);
}

export function clearJournal() {
  journal.clear();
}

/** The list to show: a fresh response, reconciled with the cache and recent events. */
export function reconcile(
  cached: readonly Job[] | undefined,
  fresh: readonly Job[],
  startedAt: number,
): Job[] {
  let list = mergeJobs(cached, fresh);
  for (const [id, entry] of journal) {
    if (entry.at < startedAt) continue; // the response already includes it
    list =
      entry.job === null
        ? list.filter((job) => job.id !== id)
        : applyJobEvent(list, { type: "job.updated", job: entry.job });
  }
  return list;
}
