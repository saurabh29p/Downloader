"use client";

import type { ProbeResult } from "@anyget/shared";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DownloadIcon, Loader2Icon } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useId, useMemo, useState } from "react";

import { CheckRow, ChoicePill } from "@/components/media/choice";
import { FormatPicker } from "@/components/media/format-picker";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { createJobItems } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { formatDuration, isolate } from "@/lib/format";
import {
  defaultSelection,
  toJobOptions,
  toYmd,
  type Entry,
  type ListExtra,
  type Tab,
} from "@/lib/media";
import { toast } from "@/lib/toast";
import { JOBS_KEY } from "@/lib/use-jobs";
import { cn } from "@/lib/utils";

type Props = {
  probe: ProbeResult;
  onTab: (tab: Tab) => void;
  loadingTab: boolean;
};

/** A playlist or channel: pick items (select all, first N), dates, quality; queue them. */
export function PlaylistView({ probe, onTab, loadingTab }: Props) {
  const t = useTranslations("Media");
  const tJobs = useTranslations("Jobs");
  const tErrors = useTranslations("Errors");
  const locale = useLocale();
  const queryClient = useQueryClient();
  const id = useId();
  const extra = probe.extra as ListExtra;
  const choosable = useMemo(() => extra.entries.filter((e) => !e.live), [extra.entries]);
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(choosable.filter((e) => !e.saved).map((e) => e.id)),
  );
  const [selection, setSelection] = useState(() => defaultSelection());
  const [after, setAfter] = useState("");
  const [before, setBefore] = useState("");
  const [firstN, setFirstN] = useState("");
  const shortsGrid = extra.tab === "shorts";

  const allChecked = choosable.length > 0 && choosable.every((e) => selected.has(e.id));
  const toggle = (entry: Entry, on: boolean) =>
    setSelected((current) => {
      const next = new Set(current);
      if (on) next.add(entry.id);
      else next.delete(entry.id);
      return next;
    });
  const takeFirst = (value: string) => {
    setFirstN(value);
    const n = Number.parseInt(value, 10);
    if (n > 0) setSelected(new Set(choosable.slice(0, n).map((e) => e.id)));
  };

  const queue = useMutation({
    mutationFn: () => {
      const items = choosable
        .filter((e) => selected.has(e.id))
        .map((e) => ({ url: e.url, options: { index: e.index, archive_id: e.archive_id } }));
      return createJobItems(items, {
        ...toJobOptions(selection),
        folder: probe.title,
        archive: extra.archive,
        ...(after ? { date_after: toYmd(after) } : {}),
        ...(before ? { date_before: toYmd(before) } : {}),
      });
    },
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: JOBS_KEY });
      if (result.jobs.length) toast.success(tJobs("added", { count: result.jobs.length }));
      if (result.skipped?.length) toast.info(t("skippedSaved", { count: result.skipped.length }));
    },
    onError: (err) => toast.error(errorMessage(tErrors, err)),
  });

  return (
    <section
      className="flex flex-col gap-5 rounded-lg border bg-card p-4 shadow-card sm:p-5"
      data-testid="playlist-view"
      aria-labelledby={`${id}-title`}
    >
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap gap-2">
          <Badge variant="secondary">{t(extra.kind === "channel" ? "channel" : "playlist")}</Badge>
          <Badge variant="outline">{t("itemCount", { count: extra.count })}</Badge>
        </div>
        <h2 id={`${id}-title`} className="text-lg font-semibold break-words" dir="auto">
          {probe.title}
        </h2>
        {extra.uploader && <p className="text-sm text-muted-foreground">{extra.uploader}</p>}
      </div>

      {extra.tabs.length > 0 && (
        <div role="radiogroup" aria-label={t("tabs")} className="flex flex-wrap gap-2">
          {extra.tabs.map((tab) => (
            <ChoicePill
              key={tab}
              name={`${id}-tab`}
              value={tab}
              checked={extra.tab === tab}
              disabled={loadingTab}
              onChange={() => onTab(tab)}
            >
              {t(`tab.${tab}`)}
            </ChoicePill>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-end gap-3 text-sm">
        <label className="flex flex-col gap-1">
          {t("dateAfter")}
          <input
            type="date"
            value={after}
            onChange={(e) => setAfter(e.target.value)}
            className="h-11 rounded-md border border-input bg-card px-2"
          />
        </label>
        <label className="flex flex-col gap-1">
          {t("dateBefore")}
          <input
            type="date"
            value={before}
            onChange={(e) => setBefore(e.target.value)}
            className="h-11 rounded-md border border-input bg-card px-2"
          />
        </label>
        <label className="flex flex-col gap-1">
          {t("firstN")}
          <input
            type="number"
            min={1}
            max={choosable.length}
            inputMode="numeric"
            value={firstN}
            onChange={(e) => takeFirst(e.target.value)}
            className="h-11 w-24 rounded-md border border-input bg-card px-2"
          />
        </label>
      </div>
      {(after || before) && <p className="text-sm text-muted-foreground">{t("dateHint")}</p>}

      <div className="flex flex-col gap-1">
        <CheckRow
          checked={allChecked}
          onChange={(on) => setSelected(on ? new Set(choosable.map((e) => e.id)) : new Set())}
        >
          {t("selectAll", { count: choosable.length })}
        </CheckRow>
        <ul
          className={cn(
            shortsGrid
              ? "grid grid-cols-2 gap-3 sm:grid-cols-4"
              : "flex flex-col divide-y rounded-md border",
          )}
          aria-label={t("items")}
        >
          {extra.entries.map((entry) => (
            <li
              key={entry.id}
              className={cn(shortsGrid ? "rounded-md border p-2" : "p-2")}
              data-testid="playlist-item"
            >
              <label
                className={cn(
                  "flex cursor-pointer gap-3",
                  shortsGrid ? "flex-col" : "items-center",
                )}
              >
                <input
                  type="checkbox"
                  checked={selected.has(entry.id)}
                  disabled={entry.live}
                  onChange={(e) => toggle(entry, e.target.checked)}
                  className="size-5 shrink-0 accent-primary"
                  aria-label={entry.title}
                />
                {entry.thumbnail && (
                  // eslint-disable-next-line @next/next/no-img-element -- remote thumbnails
                  <img
                    src={entry.thumbnail}
                    alt=""
                    loading="lazy"
                    referrerPolicy="no-referrer"
                    width={shortsGrid ? 135 : 96}
                    height={shortsGrid ? 240 : 54}
                    className={cn(
                      "rounded bg-muted object-cover",
                      shortsGrid ? "aspect-[9/16] w-full" : "aspect-video w-24 shrink-0",
                    )}
                  />
                )}
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-sm font-medium" dir="auto">
                    <span className="text-muted-foreground tabular-nums">
                      {isolate(String(entry.index))}.{" "}
                    </span>
                    {entry.title}
                  </span>
                  <span className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                    {entry.duration ? (
                      <span className="tabular-nums">
                        {isolate(formatDuration(Math.round(entry.duration)))}
                      </span>
                    ) : null}
                    {entry.saved && <Badge variant="success">{t("savedBefore")}</Badge>}
                    {entry.live && <Badge variant="outline">{t("liveNow")}</Badge>}
                  </span>
                </span>
              </label>
            </li>
          ))}
        </ul>
      </div>

      <FormatPicker value={selection} onChange={setSelection} />

      <Button
        onClick={() => queue.mutate()}
        disabled={queue.isPending || selected.size === 0}
        className="sm:self-end"
      >
        {queue.isPending ? (
          <Loader2Icon className="animate-spin" aria-hidden="true" />
        ) : (
          <DownloadIcon aria-hidden="true" />
        )}
        {t("downloadSelected", { count: selected.size })}
      </Button>
      <p className="sr-only" aria-live="polite">
        {t("selectedCount", {
          count: selected.size,
          total: new Intl.NumberFormat(locale).format(choosable.length),
        })}
      </p>
    </section>
  );
}
