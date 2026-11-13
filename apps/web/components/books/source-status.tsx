"use client";

import type { SourceStatus } from "@anyget/shared";
import { ExternalLinkIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";

/** Which sources answered, which need a key, and where to search by hand. */
export function SourceStatusList({
  sources,
  onRetry,
  retrying = [],
}: {
  sources: SourceStatus[];
  onRetry?: (name: string) => void;
  retrying?: string[];
}) {
  const t = useTranslations("Books");
  if (!sources.length) return null;
  const failed = sources.some((s) => s.status === "timeout" || s.status === "error");
  return (
    <details
      className="rounded-md border p-3 text-sm"
      data-testid="source-status"
      open={failed && !!onRetry ? true : undefined}
    >
      <summary className="min-h-11 cursor-pointer content-center font-medium">
        {t("sourcesSummary", {
          ok: sources.filter((s) => s.status === "ok").length,
          total: sources.length,
        })}
      </summary>
      <ul className="mt-2 grid gap-1 sm:grid-cols-2">
        {sources.map((s) => (
          <li key={s.name} className="flex flex-wrap items-center gap-x-2">
            <span className="font-medium">{s.label}</span>
            <span className="text-muted-foreground">
              {s.status === "ok"
                ? t("sourceFound", { count: s.count ?? 0 })
                : t(`sourceStatus.${s.status}`)}
            </span>
            {s.status === "needs_key" && (
              <Link
                href={`/connections#${s.name}`}
                className="inline-flex min-h-11 items-center font-medium text-primary underline underline-offset-4"
              >
                {t("addKey")}
              </Link>
            )}
            {onRetry && (s.status === "timeout" || s.status === "error") && (
              <button
                type="button"
                onClick={() => onRetry(s.name)}
                disabled={retrying.includes(s.name)}
                className="inline-flex min-h-11 items-center font-medium text-primary underline underline-offset-4 disabled:opacity-60"
                data-testid="retry-source"
              >
                {retrying.includes(s.name) ? t("retrying") : t("retrySource")}
              </button>
            )}
            {s.search_url && (
              <a
                href={s.search_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex min-h-11 items-center gap-1 font-medium text-primary"
              >
                {t("searchThere")}
                <ExternalLinkIcon className="size-4" aria-hidden="true" />
              </a>
            )}
          </li>
        ))}
      </ul>
    </details>
  );
}
