"use client";

import type { Snapshot } from "@anyget/shared";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DownloadIcon, ExternalLinkIcon, Loader2Icon, SearchIcon } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useId, useState, type FormEvent } from "react";

import { ChoicePill } from "@/components/media/choice";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { createJobs } from "@/lib/api";
import { waybackSnapshots } from "@/lib/api-archive";
import { errorMessage } from "@/lib/errors";
import { formatBytes, isolate } from "@/lib/format";
import { toast } from "@/lib/toast";
import { JOBS_KEY } from "@/lib/use-jobs";

function stampDate(ts: string): Date {
  return new Date(
    Date.UTC(
      +ts.slice(0, 4),
      +(ts.slice(4, 6) || 1) - 1,
      +(ts.slice(6, 8) || 1),
      +(ts.slice(8, 10) || 0),
      +(ts.slice(10, 12) || 0),
    ),
  );
}

/** Wayback Machine: snapshot timeline by year, raw (id_) download of any capture. */
export function WaybackView() {
  const t = useTranslations("Wayback");
  const tJobs = useTranslations("Jobs");
  const tErrors = useTranslations("Errors");
  const locale = useLocale();
  const id = useId();
  const queryClient = useQueryClient();
  const [url, setUrl] = useState("");
  const [year, setYear] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const lookup = useMutation({
    mutationFn: (target: string) => waybackSnapshots(target),
    onSuccess: (data) => {
      const years = Object.keys(data.years).sort();
      setYear(years[0] ?? null);
      if (data.total === 0) setError(t("none"));
    },
    onError: (err) => setError(errorMessage(tErrors, err)),
  });
  const queue = useMutation({
    mutationFn: (snapshot: Snapshot) => createJobs([snapshot.view_url]),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: JOBS_KEY });
      if (result.jobs.length) toast.success(tJobs("added", { count: result.jobs.length }));
    },
    onError: (err) => toast.error(errorMessage(tErrors, err)),
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!url.trim()) {
      setError(t("needUrl"));
      return;
    }
    lookup.mutate(url.trim());
  };

  const data = lookup.data;
  const years = data ? Object.entries(data.years).sort(([a], [b]) => a.localeCompare(b)) : [];
  const shown = data?.snapshots.filter((s) => s.timestamp.startsWith(year ?? "")) ?? [];
  const when = new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t("title")}</h1>
        <p className="max-w-prose text-muted-foreground">{t("subtitle")}</p>
      </div>
      <form onSubmit={submit} className="flex flex-col gap-2" noValidate>
        <label htmlFor={`${id}-url`} className="text-sm font-medium">
          {t("urlLabel")}
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            id={`${id}-url`}
            type="url"
            dir="ltr"
            inputMode="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="example.com"
            aria-invalid={error ? true : undefined}
            className="h-11 w-full min-w-0 rounded-md border border-input bg-card px-3 text-base shadow-xs placeholder:text-muted-foreground"
            data-testid="wayback-url"
          />
          <Button type="submit" disabled={lookup.isPending}>
            {lookup.isPending ? (
              <Loader2Icon className="animate-spin" aria-hidden="true" />
            ) : (
              <SearchIcon aria-hidden="true" />
            )}
            {t("find")}
          </Button>
        </div>
        {error && (
          <p role="alert" className="text-sm font-medium text-destructive">
            {error}
          </p>
        )}
      </form>

      {lookup.isPending && <Skeleton className="h-40" aria-busy="true" />}
      {data && data.total > 0 && (
        <section
          className="flex flex-col gap-4"
          aria-label={t("timeline")}
          data-testid="wayback-timeline"
        >
          <p className="text-sm text-muted-foreground" aria-live="polite">
            {t("count", { count: data.total })}
          </p>
          <div role="radiogroup" aria-label={t("years")} className="flex flex-wrap gap-2">
            {years.map(([y, n]) => (
              <ChoicePill
                key={y}
                name={`${id}-year`}
                value={y}
                checked={year === y}
                onChange={() => setYear(y)}
                hint={isolate(String(n))}
              >
                {isolate(y)}
              </ChoicePill>
            ))}
          </div>
          <ul className="flex flex-col divide-y rounded-md border">
            {shown.map((s) => (
              <li
                key={s.timestamp + s.original}
                className="flex flex-col gap-2 p-3 sm:flex-row sm:items-center"
                data-testid="snapshot"
              >
                <div className="flex min-w-0 flex-1 flex-col">
                  <span className="font-medium">{when.format(stampDate(s.timestamp))}</span>
                  <span className="text-sm break-all text-muted-foreground" dir="ltr">
                    {s.original}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {[
                      s.status ? isolate(s.status) : null,
                      s.mimetype,
                      s.length ? isolate(formatBytes(s.length, locale)) : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                </div>
                <div className="flex gap-2">
                  <a
                    href={s.view_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex min-h-11 items-center gap-1 px-2 text-sm font-medium text-primary"
                  >
                    {t("view")}
                    <ExternalLinkIcon className="size-4" aria-hidden="true" />
                  </a>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => queue.mutate(s)}
                    disabled={queue.isPending}
                    aria-label={`${t("downloadRaw")}: ${when.format(stampDate(s.timestamp))}`}
                  >
                    <DownloadIcon aria-hidden="true" />
                    {t("downloadRaw")}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export default WaybackView;
