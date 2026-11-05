"use client";

import type { SourceStatus } from "@anyget/shared";
import { ExternalLinkIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import { isolate } from "@/lib/format";

/** Which sources answered, which need a key, and where to search by hand. */
export function SourceStatusList({ sources }: { sources: SourceStatus[] }) {
  const t = useTranslations("Books");
  if (!sources.length) return null;
  return (
    <details className="rounded-md border p-3 text-sm" data-testid="source-status">
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
              {s.status === "needs_key" && s.message ? (
                <> ({isolate(s.message.replace(/^set /, ""))})</>
              ) : null}
            </span>
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
