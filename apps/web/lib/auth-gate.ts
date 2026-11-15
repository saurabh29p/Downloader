/** Sign-in gate for page loads (used by proxy.ts). The API is the real gate. */

export const SESSION_COOKIE = "anyget_session";

/** Pages that open without a session. */
const OPEN_PAGES = new Set(["login"]);

/** True when this page path (e.g. "/en/library") needs a signed-in visitor. */
export function isGated(pathname: string, locales: readonly string[]): boolean {
  const [, locale, page = ""] = pathname.split("/");
  if (!locale || !locales.includes(locale)) return false;
  return !OPEN_PAGES.has(page);
}

/** A same-site path to return to after signing in ("/" when missing or unsafe). */
export function safeNext(next: string | null | undefined): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.includes("\\")) return "/";
  return next;
}

export function loginPath(locale: string, next: string): string {
  return `/${locale}/login?next=${encodeURIComponent(safeNext(next))}`;
}

type Cached = { required: boolean; until: number };
let cached: Cached | undefined;
const TTL_MS = 60_000;

/** Whether the API asks for a sign-in (owner set or hosted). Cached for a minute. */
export async function loginRequired(apiUrl: string, now = Date.now()): Promise<boolean> {
  if (cached && cached.until > now) return cached.required;
  try {
    const response = await fetch(`${apiUrl}/api/auth/me`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (!response.ok) return false;
    const me = (await response.json()) as { login_required?: boolean };
    cached = { required: me.login_required === true, until: now + TTL_MS };
    return cached.required;
  } catch {
    return false; // API unreachable: pages show their own error state
  }
}

/** Uncached: does this AnyGet need a sign-in, and is an owner set? null when unreachable. */
export async function authStatus(
  apiUrl: string,
): Promise<{ loginRequired: boolean; ownerConfigured: boolean } | null> {
  try {
    const response = await fetch(`${apiUrl}/api/auth/me`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (!response.ok) return null;
    const me = (await response.json()) as { login_required?: boolean; owner_configured?: boolean };
    return {
      loginRequired: me.login_required === true,
      ownerConfigured: me.owner_configured === true,
    };
  } catch {
    return null;
  }
}

export function resetLoginCache() {
  cached = undefined;
}
