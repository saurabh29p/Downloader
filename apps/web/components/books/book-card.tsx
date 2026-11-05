"use client";

import type { BookFormat, BookHit } from "@anyget/shared";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BookOpenIcon, DownloadIcon, ExternalLinkIcon, Loader2Icon } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { createJobs } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { formatBytes, isolate } from "@/lib/format";
import { toast } from "@/lib/toast";
import { JOBS_KEY } from "@/lib/use-jobs";
import { cn } from "@/lib/utils";

type Format = BookFormat;

/** One book: title, source, access, and a download button per format (or where to read it). */
export function BookCard({ hit, best = false }: { hit: BookHit; best?: boolean }) {
  const t = useTranslations("Books");
  const tJobs = useTranslations("Jobs");
  const tErrors = useTranslations("Errors");
  const locale = useLocale();
  const queryClient = useQueryClient();
  const queue = useMutation({
    mutationFn: (format: Format) => createJobs([format.url]),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: JOBS_KEY });
      if (result.jobs.length) toast.success(tJobs("added", { count: result.jobs.length }));
    },
    onError: (err) => toast.error(errorMessage(tErrors, err)),
  });
  const formats = hit.formats ?? [];
  const downloadable = hit.access === "full_view" && formats.length > 0;
  const meta = [hit.authors?.slice(0, 2).join(", "), hit.year ? isolate(hit.year) : null]
    .filter(Boolean)
    .join(" · ");

  return (
    <article
      className={cn(
        "index-card flex-row gap-4 p-4 pb-7",
        best && "border-primary ring-1 ring-primary/40",
      )}
      data-testid={best ? "best-copy" : "book-hit"}
      aria-labelledby={`book-${hit.source}-${hit.id}`}
    >
      {hit.thumbnail ? (
        // eslint-disable-next-line @next/next/no-img-element -- remote covers
        <img
          src={hit.thumbnail}
          alt=""
          width={72}
          height={108}
          loading="lazy"
          referrerPolicy="no-referrer"
          className="h-27 w-18 shrink-0 rounded bg-muted object-cover"
        />
      ) : (
        <span
          className="flex h-27 w-18 shrink-0 items-center justify-center rounded bg-muted"
          aria-hidden="true"
        >
          <BookOpenIcon className="size-6 text-muted-foreground" />
        </span>
      )}
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        {best && <p className="text-xs font-semibold text-primary uppercase">{t("bestCopy")}</p>}
        <h3 id={`book-${hit.source}-${hit.id}`} className="font-semibold break-words" dir="auto">
          {hit.title}
        </h3>
        {meta && (
          <p className="text-sm text-muted-foreground" dir="auto">
            {meta}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">{hit.source_label ?? hit.source}</Badge>
          <Badge variant={downloadable ? "success" : "outline"}>{t(`access.${hit.access}`)}</Badge>
          {hit.partial && <Badge variant="outline">{t("partial")}</Badge>}
        </div>
        {downloadable ? (
          <div className="flex flex-wrap gap-2">
            {formats.map((format, i) => (
              <Button
                key={format.kind + format.url}
                size="sm"
                variant={i === 0 ? "default" : "outline"}
                disabled={queue.isPending}
                onClick={() => queue.mutate(format)}
                aria-label={`${t("download")} ${t(`formats.${format.kind}`)}: ${hit.title}`}
              >
                {queue.isPending && queue.variables === format ? (
                  <Loader2Icon className="animate-spin" aria-hidden="true" />
                ) : (
                  <DownloadIcon aria-hidden="true" />
                )}
                {t(`formats.${format.kind}`)}
                {format.size ? (
                  <span className="opacity-80">{isolate(formatBytes(format.size, locale))}</span>
                ) : null}
              </Button>
            ))}
          </div>
        ) : (
          <div className="flex flex-col gap-1 text-sm">
            {hit.access !== "view_online" && <p className="font-medium">{t("notDownloadable")}</p>}
            <ul className="flex flex-wrap gap-x-4">
              {[
                { label: t("readOnSite"), url: hit.details_url },
                ...(hit.library_links ?? []).map((l) => ({
                  label: t("borrowAt", { place: l.label }),
                  url: l.url,
                })),
                ...(hit.buy_links ?? []).map((l) => ({
                  label: t("buyAt", { place: l.label }),
                  url: l.url,
                })),
              ].map((link) => (
                <li key={link.url}>
                  <a
                    href={link.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex min-h-11 items-center gap-1 font-medium text-primary"
                  >
                    {link.label}
                    <ExternalLinkIcon className="size-4" aria-hidden="true" />
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </article>
  );
}
