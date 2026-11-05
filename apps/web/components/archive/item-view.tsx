"use client";

import type { ArchiveFile } from "@anyget/shared";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeftIcon, DownloadIcon, ExternalLinkIcon, Loader2Icon } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { CheckRow } from "@/components/media/choice";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { createJobs } from "@/lib/api";
import { archiveItem } from "@/lib/api-archive";
import { errorMessage } from "@/lib/errors";
import { formatBytes, isolate } from "@/lib/format";
import { toast } from "@/lib/toast";
import { JOBS_KEY } from "@/lib/use-jobs";

/** One archive.org item: details, "all of format X" shortcuts, file table with checkboxes. */
export function ItemView({ identifier, onBack }: { identifier: string; onBack: () => void }) {
  const t = useTranslations("Archive");
  const tJobs = useTranslations("Jobs");
  const tErrors = useTranslations("Errors");
  const locale = useLocale();
  const queryClient = useQueryClient();
  const item = useQuery({
    queryKey: ["archive-item", identifier],
    queryFn: () => archiveItem(identifier),
    select: (data) => ({ ...data, files: data.files ?? [], collections: data.collections ?? [] }),
  });
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!item.data) return;
    const preferred = ["Text PDF", "EPUB", "VBR MP3", "h.264", "MPEG4", "PDF"];
    const fmt = preferred.find((f) => item.data.files.some((x) => x.format === f));
    // Pre-select the best format once the item loads.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- derived default, set once per item
    setSelected(new Set(item.data.files.filter((f) => f.format === fmt).map((f) => f.name)));
  }, [item.data]);

  const queue = useMutation({
    mutationFn: () => createJobs([item.data!.details_url], { files: [...selected] }),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: JOBS_KEY });
      if (result.jobs.length) toast.success(tJobs("added", { count: result.jobs.length }));
    },
    onError: (err) => toast.error(errorMessage(tErrors, err)),
  });

  const back = (
    <button
      type="button"
      onClick={onBack}
      className="inline-flex min-h-11 items-center gap-2 self-start text-sm font-medium text-primary"
    >
      <ArrowLeftIcon className="size-4" aria-hidden="true" data-flip-rtl />
      {t("backToResults")}
    </button>
  );

  if (item.isPending)
    return (
      <div className="flex flex-col gap-3" aria-busy="true">
        {back}
        <Skeleton className="h-32" />
        <Skeleton className="h-64" />
      </div>
    );
  if (item.isError)
    return (
      <div className="flex flex-col gap-3">
        {back}
        <p role="alert">{errorMessage(tErrors, item.error)}</p>
        <Button variant="outline" onClick={() => item.refetch()} className="self-start">
          {t("retry")}
        </Button>
      </div>
    );

  const data = item.data;
  const toggleFormat = (format: string) => {
    const names = data.files.filter((f) => f.format === format).map((f) => f.name);
    const allOn = names.every((n) => selected.has(n));
    setSelected((cur) => {
      const next = new Set(cur);
      names.forEach((n) => (allOn ? next.delete(n) : next.add(n)));
      return next;
    });
  };
  const toggle = (file: ArchiveFile, on: boolean) =>
    setSelected((cur) => {
      const next = new Set(cur);
      if (on) next.add(file.name);
      else next.delete(file.name);
      return next;
    });
  const selectedSize = data.files
    .filter((f) => selected.has(f.name))
    .reduce((n, f) => n + (f.size ?? 0), 0);

  return (
    <article className="flex flex-col gap-5" data-testid="archive-item">
      {back}
      <div className="flex flex-col gap-4 sm:flex-row">
        {/* eslint-disable-next-line @next/next/no-img-element -- archive.org thumbnail */}
        <img
          src={data.thumbnail_url}
          alt=""
          width={160}
          height={160}
          referrerPolicy="no-referrer"
          className="size-40 shrink-0 rounded-md bg-muted object-cover"
        />
        <div className="flex min-w-0 flex-col gap-2">
          <h1 className="text-2xl font-semibold tracking-tight break-words" dir="auto">
            {data.title}
          </h1>
          <p className="text-sm text-muted-foreground" dir="auto">
            {[data.creator, data.date ? isolate(data.date) : null].filter(Boolean).join(" · ")}
          </p>
          <div className="flex flex-wrap gap-2">
            {data.mediatype && <Badge variant="secondary">{data.mediatype}</Badge>}
            {data.collections.slice(0, 4).map((c) => (
              <Badge key={c} variant="outline">
                {c}
              </Badge>
            ))}
          </div>
          <a
            href={data.details_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex min-h-11 items-center gap-1 text-sm font-medium text-primary"
          >
            {t("viewOnArchive")}
            <ExternalLinkIcon className="size-4" aria-hidden="true" />
          </a>
        </div>
      </div>

      {data.restricted ? (
        <p role="alert" className="rounded-lg border border-destructive/40 p-4 text-sm">
          {t(data.restricted === "borrow_only" ? "borrowOnly" : "restrictedNote")}
        </p>
      ) : (
        <>
          <div className="flex flex-col gap-2">
            <h2 className="text-sm font-medium">{t("allOfFormat")}</h2>
            <div className="flex flex-wrap gap-2">
              {data.formats.map((f) => {
                const format = String(f.format);
                const names = data.files.filter((x) => x.format === format);
                const on = names.length > 0 && names.every((x) => selected.has(x.name));
                return (
                  <Button
                    key={format}
                    variant={on ? "default" : "outline"}
                    size="sm"
                    aria-pressed={on}
                    onClick={() => toggleFormat(format)}
                  >
                    {format}
                    <span className="opacity-80">{isolate(String(f.count))}</span>
                  </Button>
                );
              })}
            </div>
          </div>

          <div className="overflow-x-auto rounded-md border">
            <table className="w-full text-sm">
              <caption className="sr-only">{t("filesCaption")}</caption>
              <thead className="bg-muted/50 text-start">
                <tr>
                  <th scope="col" className="w-12 p-2">
                    <span className="sr-only">{t("select")}</span>
                  </th>
                  <th scope="col" className="p-2 text-start font-medium">
                    {t("fileName")}
                  </th>
                  <th scope="col" className="hidden p-2 text-start font-medium sm:table-cell">
                    {t("format")}
                  </th>
                  <th scope="col" className="p-2 text-end font-medium">
                    {t("size")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.files.map((file) => (
                  <tr key={file.name} className="border-t" data-testid="archive-file">
                    <td className="p-2">
                      <CheckRow
                        checked={selected.has(file.name)}
                        onChange={(on) => toggle(file, on)}
                      >
                        <span className="sr-only">{file.name}</span>
                      </CheckRow>
                    </td>
                    <td className="p-2 break-all" dir="auto">
                      {file.name}
                    </td>
                    <td className="hidden p-2 sm:table-cell">{file.format}</td>
                    <td className="p-2 text-end whitespace-nowrap tabular-nums">
                      {file.size ? isolate(formatBytes(file.size, locale)) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
            <p className="text-sm text-muted-foreground" aria-live="polite">
              {t("selected", {
                count: selected.size,
                size: isolate(formatBytes(selectedSize, locale)),
              })}
            </p>
            <Button
              onClick={() => queue.mutate()}
              disabled={selected.size === 0 || queue.isPending}
            >
              {queue.isPending ? (
                <Loader2Icon className="animate-spin" aria-hidden="true" />
              ) : (
                <DownloadIcon aria-hidden="true" />
              )}
              {t("downloadSelected", { count: selected.size })}
            </Button>
          </div>
        </>
      )}
      {data.restricted && (
        <a
          href={data.details_url}
          target="_blank"
          rel="noreferrer"
          className={buttonVariants({ variant: "outline" })}
        >
          {t("openOnArchive")}
        </a>
      )}
    </article>
  );
}
