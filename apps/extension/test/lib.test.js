import { describe, expect, it } from "vitest";

import {
  describeResult,
  isLocal,
  jobsRequest,
  normalizeBase,
  originPattern,
  sendable,
} from "../src/lib.js";

describe("extension helpers", () => {
  it("normalizes the AnyGet address", () => {
    expect(normalizeBase("")).toBe("http://127.0.0.1:3000");
    expect(normalizeBase("127.0.0.1:3000/")).toBe("http://127.0.0.1:3000");
    expect(normalizeBase("https://dl.example.org/?x=1#y")).toBe("https://dl.example.org");
    expect(() => normalizeBase("ftp://x")).toThrow();
    expect(isLocal("http://localhost:3000")).toBe(true);
    expect(isLocal("https://dl.example.org")).toBe(false);
    expect(originPattern("https://dl.example.org:8443")).toBe("https://dl.example.org/*");
  });

  it("only sends web links", () => {
    expect(sendable("https://example.org/a.pdf")).toBe(true);
    expect(sendable("chrome://extensions")).toBe(false);
    expect(sendable("file:///etc/passwd")).toBe(false);
    expect(sendable("javascript:alert(1)")).toBe(false);
    expect(sendable(undefined)).toBe(false);
  });

  it("builds the jobs request with an optional token", () => {
    const plain = jobsRequest("http://127.0.0.1:3000", "", ["https://a.test/x"]);
    expect(plain.url).toBe("http://127.0.0.1:3000/api/jobs");
    expect(plain.init.headers.Authorization).toBeUndefined();
    expect(JSON.parse(plain.init.body)).toEqual({ urls: ["https://a.test/x"], options: {} });
    const withToken = jobsRequest("https://dl.example.org/", "s3cret", ["https://a.test/x"]);
    expect(withToken.init.headers.Authorization).toBe("Bearer s3cret");
  });

  it("describes what AnyGet answered", () => {
    expect(describeResult(201, { jobs: [{}], rejected: [], skipped: [] })).toEqual({
      ok: true,
      text: "Added 1 download",
    });
    expect(describeResult(401, null).ok).toBe(false);
    expect(
      describeResult(201, { jobs: [], rejected: [{ message: "private address" }], skipped: [] })
        .text,
    ).toBe("private address");
    expect(describeResult(502, { message: "down" }).text).toBe("AnyGet: down");
  });
});
