import { describe, expect, it } from "vitest";

import video from "@/test/fixtures/probe-video.json";

import { defaultSelection, parseUploadDate, toJobOptions, toYmd, type VideoExtra } from "./media";

const extra = video.extra as unknown as VideoExtra;

describe("media options", () => {
  it("defaults to 1080p mp4 with thumbnail and metadata", () => {
    const sel = defaultSelection(extra);
    expect(sel.preset).toBe("1080");
    expect(toJobOptions(sel)).toEqual({
      preset: "1080",
      container: "mp4",
      embed_thumbnail: true,
      embed_metadata: true,
      chapters: true,
      write_info_json: false,
    });
  });

  it("maps audio-only, exact format and subtitles", () => {
    const sel = { ...defaultSelection(extra), audioOnly: true, audioFormat: "opus" as const };
    expect(toJobOptions(sel)).toMatchObject({ preset: "audio", audio_format: "opus" });
    expect(toJobOptions(sel)).not.toHaveProperty("container");

    const exact = {
      ...defaultSelection(extra),
      formatId: "137",
      subtitles: ["en", "hi"],
      autoSubtitles: true,
      subtitlesMode: "embed" as const,
    };
    expect(toJobOptions(exact)).toMatchObject({
      format_id: "137",
      subtitles: ["en", "hi"],
      auto_subtitles: true,
      subtitles_mode: "embed",
    });
  });

  it("parses dates", () => {
    expect(parseUploadDate("20140411")?.toISOString()).toBe("2014-04-11T00:00:00.000Z");
    expect(parseUploadDate("bad")).toBeNull();
    expect(toYmd("2024-05-01")).toBe("20240501");
  });
});
