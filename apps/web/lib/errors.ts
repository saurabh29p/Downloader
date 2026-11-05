import type { useTranslations } from "next-intl";

import { ApiError } from "@/lib/api";

type ErrorsT = ReturnType<typeof useTranslations<"Errors">>;

export function errorCode(error: unknown): string {
  return error instanceof ApiError ? error.code : typeof error === "string" ? error : "";
}

/** A friendly, translated message for an API error code (every code has an Errors entry). */
export function errorMessage(t: ErrorsT, error: unknown): string {
  const code = errorCode(error) as "network";
  return code && t.has(code) ? t(code) : t("generic");
}
