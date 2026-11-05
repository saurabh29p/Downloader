import type { useTranslations } from "next-intl";

import { ApiError } from "@/lib/api";

const KNOWN = new Set([
  "blocked_url",
  "unsupported",
  "not_found",
  "upstream",
  "network",
  "invalid_state",
  "checksum",
  "incomplete",
  "unsafe_path",
  "drm",
  "members_only",
  "paid",
  "private",
  "age_restricted",
  "login_required",
  "bot_check",
  "geo_blocked",
  "live_not_finished",
  "unavailable",
  "invalid_cookies",
  "restricted",
  "borrow_only",
  "rate_limited",
  "in_copyright",
  "needs_key",
  "tool_missing",
  "forbidden",
  "not_a_file",
  "auth_required",
  "auth_invalid",
  "owner_required",
  "csrf",
]);

type ErrorsT = ReturnType<typeof useTranslations<"Errors">>;

/** A friendly, translated message for an API error code. */
export function errorMessage(t: ErrorsT, error: unknown): string {
  const code = error instanceof ApiError ? error.code : typeof error === "string" ? error : "";
  return KNOWN.has(code) ? t(code as "network") : t("generic");
}

/** Errors that signing in on the user's own account usually fixes. */
const CONNECT_CODES = new Set(["login_required", "bot_check", "age_restricted", "forbidden"]);

const SITES: ReadonlyArray<readonly [RegExp, string, string]> = [
  [/(^|\.)(youtube\.com|youtu\.be)$/, "youtube", "YouTube"],
  [/(^|\.)(x\.com|twitter\.com)$/, "x", "X"],
  [/(^|\.)reddit\.com$/, "reddit", "Reddit"],
  [/(^|\.)vimeo\.com$/, "vimeo", "Vimeo"],
  [/(^|\.)instagram\.com$/, "instagram", "Instagram"],
  [/(^|\.)(facebook\.com|fb\.watch)$/, "facebook", "Facebook"],
  [/(^|\.)patreon\.com$/, "patreon", "Patreon"],
];

/** The site to connect (id for links, label to show) when that fixes this error, else null. */
export function connectFor(
  code: string | null | undefined,
  url: string,
): { id: string; label: string } | null {
  if (!code || !CONNECT_CODES.has(code)) return null;
  let host = "";
  try {
    host = new URL(url).hostname.toLowerCase();
  } catch {
    return null;
  }
  for (const [pattern, id, label] of SITES) {
    if (pattern.test(host)) return { id, label };
  }
  const label = host.replace(/^www\./, "");
  return label ? { id: label, label } : null;
}

/** Codes whose own message says it all (the raw server text goes under "Details"). */
export function isKnownError(code: string | null | undefined): boolean {
  return !!code && KNOWN.has(code) && code !== "upstream";
}
