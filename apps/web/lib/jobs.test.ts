import { describe, expect, it } from "vitest";

import { makeJob } from "@/test/fixtures";

import { applyJobEvent, etaSeconds, matchesFilter, mergeJobs, progressPercent } from "./jobs";

describe("applyJobEvent", () => {
  it("adds new jobs to the top", () => {
    const old = makeJob({ id: "a" });
    const result = applyJobEvent([old], { type: "job.created", job: makeJob({ id: "b" }) });
    expect(result.map((j) => j.id)).toEqual(["b", "a"]);
  });

  it("replaces an updated job in place", () => {
    const job = makeJob({ id: "a", downloaded: 1 });
    const updated = makeJob({ id: "a", downloaded: 99, updated_at: "2026-11-04T10:00:05Z" });
    expect(applyJobEvent([job], { type: "job.updated", job: updated })[0]?.downloaded).toBe(99);
  });

  it("ignores a stale copy of the same state", () => {
    const fresh = makeJob({ id: "a", downloaded: 99, updated_at: "2026-11-04T10:00:05Z" });
    const stale = makeJob({ id: "a", downloaded: 1, updated_at: "2026-11-04T10:00:01Z" });
    expect(applyJobEvent([fresh], { type: "job.updated", job: stale })[0]?.downloaded).toBe(99);
  });

  it("removes deleted jobs and handles an empty cache", () => {
    expect(
      applyJobEvent([makeJob({ id: "a" })], { type: "job.deleted", job: { id: "a" } }),
    ).toEqual([]);
    expect(applyJobEvent(undefined, { type: "job.created", job: makeJob() })).toHaveLength(1);
  });
});

describe("progress helpers", () => {
  it("computes percent and eta", () => {
    const job = makeJob({ downloaded: 250, total: 1000, speed: 50 });
    expect(progressPercent(job)).toBe(25);
    expect(etaSeconds(job)).toBe(15);
    expect(progressPercent(makeJob({ total: null }))).toBeNull();
    expect(progressPercent(makeJob({ state: "done", total: null }))).toBe(100);
    expect(etaSeconds(makeJob({ speed: null }))).toBeNull();
  });

  it("filters", () => {
    expect(matchesFilter(makeJob({ state: "paused" }), "active")).toBe(true);
    expect(matchesFilter(makeJob({ state: "canceled" }), "failed")).toBe(true);
    expect(matchesFilter(makeJob({ state: "done" }), "active")).toBe(false);
  });
});

describe("mergeJobs", () => {
  it("keeps a live update when a slower refetch brings an older copy", () => {
    const live = makeJob({ id: "a", state: "done", updated_at: "2026-11-04T10:00:05Z" });
    const stale = makeJob({ id: "a", state: "downloading", updated_at: "2026-11-04T10:00:02Z" });
    const other = makeJob({ id: "b" });
    expect(mergeJobs([live], [stale, other])).toEqual([live, other]);
  });

  it("takes the server copy when it is newer, and drops jobs the server no longer has", () => {
    const old = makeJob({ id: "a", updated_at: "2026-11-04T10:00:01Z" });
    const fresh = makeJob({ id: "a", updated_at: "2026-11-04T10:00:09.5+00:00" });
    expect(mergeJobs([old, makeJob({ id: "gone" })], [fresh])).toEqual([fresh]);
  });
});
