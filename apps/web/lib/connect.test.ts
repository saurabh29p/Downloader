import { describe, expect, it } from "vitest";

import { connectFor } from "./connect";

describe("connectFor", () => {
  it("offers to connect the site for sign-in errors", () => {
    expect(connectFor("bot_check", "https://www.youtube.com/watch?v=x")).toEqual({
      id: "youtube",
      label: "YouTube",
    });
    expect(connectFor("login_required", "https://x.com/a/status/1")?.label).toBe("X");
    expect(connectFor("forbidden", "https://old.reddit.com/r/a")?.id).toBe("reddit");
    expect(connectFor("login_required", "https://www.example.org/v")?.label).toBe("example.org");
  });

  it("does nothing for other errors or bad links", () => {
    expect(connectFor("geo_blocked", "https://www.youtube.com/watch?v=x")).toBeNull();
    expect(connectFor("members_only", "https://www.youtube.com/watch?v=x")).toBeNull();
    expect(connectFor("login_required", "not a url")).toBeNull();
    expect(connectFor(null, "https://youtu.be/x")).toBeNull();
  });
});
