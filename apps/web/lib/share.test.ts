import { describe, expect, it } from "vitest";

import { firstLink } from "./share";

describe("firstLink", () => {
  it("finds the link in what Android apps share", () => {
    expect(firstLink([undefined, "Look at this https://example.org/a.pdf!"])).toBe(
      "https://example.org/a.pdf",
    );
    expect(firstLink(["https://a.test/x", "https://b.test/y"])).toBe("https://a.test/x");
    expect(firstLink([undefined, "(see https://a.test/x?y=1)."])).toBe("https://a.test/x?y=1");
    expect(firstLink(["no link", undefined])).toBeNull();
    expect(firstLink(["javascript:alert(1) ftp://x"])).toBeNull();
  });
});
