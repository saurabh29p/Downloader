import { describe, expect, it } from "vitest";

import { ApiError, call } from "./api";

async function codeOf(promise: Promise<unknown>) {
  try {
    await promise;
  } catch (error) {
    return error instanceof ApiError ? error.code : String(error);
  }
  return "no error";
}

const answer = (response: Response) =>
  Promise.resolve({ data: undefined, error: undefined, response });

describe("call()", () => {
  it("names a server that isn't answering, so the message can say so", async () => {
    // The API is down (the website's /api forwarding fails) or crashed: plain-text 5xx.
    const down = answer(new Response("Internal Server Error", { status: 500 }));
    expect(await codeOf(call(down))).toBe("server_unavailable");
    expect(await codeOf(call(answer(new Response("", { status: 502 }))))).toBe(
      "server_unavailable",
    );
  });

  it("keeps the API's own code, and says network when nothing answered", async () => {
    const coded = Promise.resolve({
      error: { code: "not_found", message: "no such job" },
      response: new Response(null, { status: 404 }),
    });
    expect(await codeOf(call(coded))).toBe("not_found");
    expect(await codeOf(call(Promise.reject(new TypeError("Failed to fetch"))))).toBe("network");
  });
});
