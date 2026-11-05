// Pure helpers shared by the background worker and the options page (tested in Node).

export const DEFAULT_BASE = "http://127.0.0.1:3000";

/** "127.0.0.1:3000/" → "http://127.0.0.1:3000"; only http(s) base URLs are accepted. */
export function normalizeBase(input) {
  let text = String(input ?? "").trim();
  if (!text) return DEFAULT_BASE;
  if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(text)) text = `http://${text}`;
  const url = new URL(text);
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("The AnyGet address must start with http:// or https://");
  }
  url.hash = "";
  url.search = "";
  return url.toString().replace(/\/+$/, "");
}

/** Is this base on the user's own computer (allowed without asking for permission)? */
export function isLocal(base) {
  const host = new URL(base).hostname;
  return host === "127.0.0.1" || host === "localhost" || host === "[::1]";
}

/** The permission pattern Chrome/Firefox need to talk to a non-local AnyGet. */
export function originPattern(base) {
  const url = new URL(base);
  return `${url.protocol}//${url.hostname}/*`;
}

/** Only web links are sent; extension pages, file: and data: URLs are not downloads. */
export function sendable(url) {
  try {
    const parsed = new URL(url);
    return (parsed.protocol === "http:" || parsed.protocol === "https:") && !!parsed.hostname;
  } catch {
    return false;
  }
}

/**
 * fetch() arguments for POST /api/jobs.
 * @returns {{ url: string, init: RequestInit }}
 */
export function jobsRequest(base, token, urls) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  return {
    url: `${normalizeBase(base)}/api/jobs`,
    // credentials: a signed-in Cloudflare Access session (cookie) is sent along.
    init: {
      method: "POST",
      headers,
      credentials: "include",
      body: JSON.stringify({ urls, options: {} }),
    },
  };
}

/** A one-line result for the badge/notification. */
export function describeResult(status, body) {
  if (status === 401 || status === 403) return { ok: false, text: "AnyGet refused the token" };
  if (status >= 400 || !body) {
    return {
      ok: false,
      text: body?.message ? `AnyGet: ${body.message}` : `AnyGet answered ${status}`,
    };
  }
  const added = body.jobs?.length ?? 0;
  const skipped = (body.skipped?.length ?? 0) + (body.rejected?.length ?? 0);
  if (added === 0 && skipped > 0) {
    return { ok: false, text: body.rejected?.[0]?.message ?? "Already downloaded" };
  }
  return { ok: true, text: added === 1 ? "Added 1 download" : `Added ${added} downloads` };
}
