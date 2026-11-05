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
]);

type ErrorsT = ReturnType<typeof useTranslations<"Errors">>;

/** A friendly, translated message for an API error code. */
export function errorMessage(t: ErrorsT, error: unknown): string {
  const code = error instanceof ApiError ? error.code : typeof error === "string" ? error : "";
  return KNOWN.has(code) ? t(code as "network") : t("generic");
}
