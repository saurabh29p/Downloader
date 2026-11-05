import { createApiClient } from "@anyget/shared";
import { describe, expect, it, vi } from "vitest";

function client(response: Response) {
  const fetch = vi.fn<(request: Request) => Promise<Response>>(async () => response);
  return {
    api: createApiClient("http://api.test", { fetch: fetch as typeof globalThis.fetch }),
    fetch,
  };
}

describe("createApiClient", () => {
  it("fills path and query params, sends JSON with the CSRF header", async () => {
    const { api, fetch } = client(Response.json({ id: "a b" }));
    const { data } = await api.DELETE("/api/jobs/{job_id}", {
      params: { path: { job_id: "a b" }, query: { delete_file: true } },
    });
    expect(data).toEqual({ id: "a b" });
    const request = fetch.mock.calls[0]![0];
    expect(request.method).toBe("DELETE");
    expect(request.url).toBe("http://api.test/api/jobs/a%20b?delete_file=true");
    expect(request.headers.get("x-requested-with")).toBe("anyget");
    expect(request.headers.get("content-type")).toBeNull();

    const posted = client(Response.json({ jobs: [], rejected: [] }));
    await posted.api.POST("/api/jobs", { body: { urls: ["https://x.test/1"], options: {} } });
    const sent = posted.fetch.mock.calls[0]![0];
    expect(sent.headers.get("content-type")).toBe("application/json");
    expect(await sent.json()).toEqual({ urls: ["https://x.test/1"], options: {} });
  });

  it("repeats array query keys and skips empty values", async () => {
    const { api, fetch } = client(Response.json({}));
    await api.GET("/api/books/search", {
      params: { query: { q: "gita", sources: ["gutendex", "openlibrary"], limit: undefined } },
    } as never);
    expect(fetch.mock.calls[0]![0].url).toBe(
      "http://api.test/api/books/search?q=gita&sources=gutendex&sources=openlibrary",
    );
  });

  it("returns errors (JSON or text) and no data for 204", async () => {
    const failed = client(Response.json({ code: "not_found", message: "no" }, { status: 404 }));
    const result = await failed.api.GET("/api/jobs/{job_id}", {
      params: { path: { job_id: "x" } },
    });
    expect(result.error).toEqual({ code: "not_found", message: "no" });
    expect(result.response.status).toBe(404);

    const text = client(new Response("bad gateway", { status: 502 }));
    expect((await text.api.GET("/api/health")).error).toBe("bad gateway");

    const empty = client(new Response(null, { status: 204 }));
    const none = await empty.api.DELETE("/api/jobs/{job_id}", {
      params: { path: { job_id: "x" } },
    });
    expect(none.data).toBeUndefined();
    expect(none.error).toBeUndefined();
  });
});
