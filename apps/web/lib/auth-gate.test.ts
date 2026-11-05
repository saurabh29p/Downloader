import { afterEach, describe, expect, it, vi } from "vitest";

import { isGated, loginPath, loginRequired, resetLoginCache, safeNext } from "./auth-gate";

const locales = ["en", "hi", "ar"];

describe("auth gate", () => {
  afterEach(() => {
    resetLoginCache();
    vi.unstubAllGlobals();
  });

  it("gates app pages but not the sign-in page", () => {
    expect(isGated("/en", locales)).toBe(true);
    expect(isGated("/ar/library", locales)).toBe(true);
    expect(isGated("/en/login", locales)).toBe(false);
    expect(isGated("/xx/library", locales)).toBe(false);
  });

  it("only returns to same-site paths", () => {
    expect(safeNext("/en/library?q=a")).toBe("/en/library?q=a");
    expect(safeNext("//evil.example")).toBe("/");
    expect(safeNext("https://evil.example")).toBe("/");
    expect(safeNext("/\\evil.example")).toBe("/");
    expect(safeNext(null)).toBe("/");
    expect(loginPath("hi", "/hi/watch")).toBe("/hi/login?next=%2Fhi%2Fwatch");
  });

  it("asks the API once a minute and lets pages through when it is down", async () => {
    const fetchMock = vi.fn(async () => Response.json({ login_required: true }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await loginRequired("http://api", 0)).toBe(true);
    expect(await loginRequired("http://api", 1000)).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    resetLoginCache();
    vi.stubGlobal("fetch", async () => {
      throw new Error("down");
    });
    expect(await loginRequired("http://api", 0)).toBe(false);
  });
});
