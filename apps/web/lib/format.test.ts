import { describe, expect, it } from "vitest";

import { formatBytes, formatDuration } from "./format";

describe("formatBytes", () => {
  it("picks a unit", () => {
    expect(formatBytes(512, "en")).toBe("512\u00a0B");
    expect(formatBytes(1536, "en")).toBe("1.5\u00a0KB");
    expect(formatBytes(5 * 1024 ** 3, "en")).toBe("5\u00a0GB");
    expect(formatBytes(null, "en")).toBe("—");
  });

  it("uses the locale's digits", () => {
    expect(formatBytes(1536, "ar-EG")).toContain("KB");
  });
});

describe("formatDuration", () => {
  it("formats minutes and hours", () => {
    expect(formatDuration(65)).toBe("1:05");
    expect(formatDuration(3725)).toBe("1:02:05");
  });
});
