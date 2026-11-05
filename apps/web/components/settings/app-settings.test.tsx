import { describe, expect, it } from "vitest";

import { example } from "./app-settings";

describe("folder template example", () => {
  it("fills placeholders and ends with a file name", () => {
    expect(example("{type}/{source}")).toBe("videos/youtube.com/video.mp4");
    expect(example("{year}-{month}")).toBe("2026-11/video.mp4");
    expect(example("")).toBe("video.mp4");
  });
});
