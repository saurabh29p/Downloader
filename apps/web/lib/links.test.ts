import { describe, expect, it } from "vitest";

import { hostOf, parseLinks } from "./links";

describe("parseLinks", () => {
  it("finds one link", () => {
    expect(parseLinks("  https://example.com/a.pdf \n")).toEqual(["https://example.com/a.pdf"]);
  });

  it("splits many links on lines, spaces and commas, and dedupes", () => {
    const text = "https://a.test/1\nhttps://b.test/2, https://a.test/1\t magnet:?xt=urn:btih:abc";
    expect(parseLinks(text)).toEqual([
      "https://a.test/1",
      "https://b.test/2",
      "magnet:?xt=urn:btih:abc",
    ]);
  });

  it("accepts bare domains and strips wrapping punctuation", () => {
    expect(parseLinks("(example.com/file.zip). <https://x.test/y>")).toEqual([
      "example.com/file.zip",
      "https://x.test/y",
    ]);
  });

  it("ignores words, comments and blank lines", () => {
    expect(parseLinks("hello world\n# comment\n\n")).toEqual([]);
  });
});

describe("hostOf", () => {
  it("drops www and falls back to the input", () => {
    expect(hostOf("https://www.example.com/a")).toBe("example.com");
    expect(hostOf("not a url")).toBe("not a url");
  });
});
