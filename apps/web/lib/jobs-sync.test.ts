import { afterEach, describe, expect, it } from "vitest";

import { makeJob } from "@/test/fixtures";

import { clearJournal, noteEvent, reconcile } from "./jobs-sync";

afterEach(() => clearJournal());

describe("reconcile (list response vs. live events)", () => {
  it("keeps a job created while the list request was on its way", () => {
    const started = 1000;
    noteEvent({ type: "job.created", job: makeJob({ id: "new" }) }, 1500);
    const result = reconcile(undefined, [makeJob({ id: "old" })], started);
    expect(result.map((j) => j.id)).toEqual(["new", "old"]);
  });

  it("does not bring back a job deleted while the request was on its way", () => {
    noteEvent({ type: "job.deleted", job: { id: "gone" } }, 1500);
    const fresh = [makeJob({ id: "gone" }), makeJob({ id: "kept" })];
    expect(reconcile(undefined, fresh, 1000).map((j) => j.id)).toEqual(["kept"]);
  });

  it("never replaces a newer update with an older copy from the response", () => {
    const newer = makeJob({ id: "a", state: "done", updated_at: "2026-11-07T10:00:09Z" });
    const older = makeJob({ id: "a", state: "downloading", updated_at: "2026-11-07T10:00:01Z" });
    noteEvent({ type: "job.updated", job: newer }, 1500);
    expect(reconcile(undefined, [older], 1000)[0]?.state).toBe("done");
    // Without a stream event, the newer cached copy still wins.
    clearJournal();
    expect(reconcile([newer], [older], 1000)[0]?.state).toBe("done");
  });

  it("ignores events the response already includes, and adds no duplicates", () => {
    const job = makeJob({ id: "a", state: "done", updated_at: "2026-11-07T10:00:05Z" });
    noteEvent({ type: "job.created", job }, 500); // before the request started
    noteEvent({ type: "job.updated", job }, 1500);
    const result = reconcile(undefined, [job], 1000);
    expect(result).toHaveLength(1);
  });

  it("a reconnect refetch keeps a finished download (no false empty list)", () => {
    const done = makeJob({ id: "done-1", state: "done" });
    // The first list had it; a reconnect refetch answers before the stream re-sends.
    expect(reconcile([done], [done], 2000).map((j) => j.state)).toEqual(["done"]);
  });
});
