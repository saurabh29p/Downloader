"use client";

import type { Watch } from "@anyget/shared";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Loader2Icon,
  PauseIcon,
  PlayIcon,
  PlusIcon,
  RefreshCwIcon,
  Trash2Icon,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useId, useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { createWatch, deleteWatch, listWatches, runWatch, updateWatch } from "@/lib/api-library";
import { errorMessage } from "@/lib/errors";
import { isolate } from "@/lib/format";
import { toast } from "@/lib/toast";
import { JOBS_KEY } from "@/lib/use-jobs";

const KEY = ["watches"] as const;
const INTERVALS = [60, 180, 360, 720, 1440, 10080] as const;

/** Watches: channels, playlists and archive.org collections checked on a schedule. */
export function WatchView() {
  const t = useTranslations("Watch");
  const tErrors = useTranslations("Errors");
  const id = useId();
  const queryClient = useQueryClient();
  const [url, setUrl] = useState("");
  const [interval, setInterval] = useState<number>(360);
  const [initial, setInitial] = useState(5);
  const [error, setError] = useState<string | null>(null);
  const list = useQuery({ queryKey: KEY, queryFn: listWatches });
  const add = useMutation({
    mutationFn: () => createWatch(url.trim(), interval, initial),
    onSuccess: () => {
      setUrl("");
      void queryClient.invalidateQueries({ queryKey: KEY });
      toast.success(t("added"));
    },
    onError: (err) => setError(errorMessage(tErrors, err)),
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!url.trim()) {
      setError(t("needUrl"));
      return;
    }
    add.mutate();
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t("title")}</h1>
        <p className="max-w-prose text-muted-foreground">{t("subtitle")}</p>
      </div>
      <form onSubmit={submit} className="flex flex-col gap-3 rounded-lg border p-4" noValidate>
        <div className="flex flex-col gap-2">
          <label htmlFor={`${id}-url`} className="text-sm font-medium">
            {t("urlLabel")}
          </label>
          <input
            id={`${id}-url`}
            type="url"
            dir="ltr"
            inputMode="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://www.youtube.com/@channel"
            aria-invalid={error ? true : undefined}
            className="h-11 w-full min-w-0 rounded-md border border-input bg-card px-3 text-base shadow-xs placeholder:text-muted-foreground"
            data-testid="watch-url"
          />
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm font-medium">
            {t("every")}
            <select
              value={interval}
              onChange={(e) => setInterval(Number(e.target.value))}
              className="h-11 rounded-md border border-input bg-card px-3 text-sm"
            >
              {INTERVALS.map((m) => (
                <option key={m} value={m}>
                  {t(`intervals.m${m}`)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            {t("initial")}
            <input
              type="number"
              min={0}
              max={50}
              value={initial}
              onChange={(e) => setInitial(Math.max(0, Math.min(50, Number(e.target.value) || 0)))}
              className="h-11 w-24 rounded-md border border-input bg-card px-3 text-base"
            />
          </label>
          <Button type="submit" disabled={add.isPending}>
            {add.isPending ? (
              <Loader2Icon className="animate-spin" aria-hidden="true" />
            ) : (
              <PlusIcon aria-hidden="true" />
            )}
            {t("add")}
          </Button>
        </div>
        <p className="text-sm text-muted-foreground">{t("hint")}</p>
        {error && (
          <p role="alert" className="text-sm font-medium text-destructive">
            {error}
          </p>
        )}
      </form>

      {list.isPending && <Skeleton className="h-32" aria-busy="true" />}
      {list.isError && (
        <div className="flex flex-col gap-2">
          <p role="alert">{errorMessage(tErrors, list.error)}</p>
          <Button variant="outline" className="self-start" onClick={() => list.refetch()}>
            {t("retry")}
          </Button>
        </div>
      )}
      {list.isSuccess && list.data.length === 0 && (
        <p className="rounded-lg border border-dashed p-6 text-center text-muted-foreground">
          {t("empty")}
        </p>
      )}
      {list.isSuccess && list.data.length > 0 && (
        <ul className="flex flex-col gap-3" data-testid="watch-list">
          {list.data.map((watch) => (
            <WatchRow key={watch.id} watch={watch} />
          ))}
        </ul>
      )}
    </div>
  );
}

function WatchRow({ watch }: { watch: Watch }) {
  const t = useTranslations("Watch");
  const tErrors = useTranslations("Errors");
  const locale = useLocale();
  const queryClient = useQueryClient();
  const refresh = () => void queryClient.invalidateQueries({ queryKey: KEY });
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });
  const run = useMutation({
    mutationFn: () => runWatch(watch.id),
    onSuccess: (result) => {
      refresh();
      void queryClient.invalidateQueries({ queryKey: JOBS_KEY });
      toast.success(t("ran", { count: result.queued }));
    },
    onError: (err) => {
      refresh();
      toast.error(errorMessage(tErrors, err));
    },
  });
  const toggle = useMutation({
    mutationFn: () => updateWatch(watch.id, { enabled: !watch.enabled }),
    onSuccess: refresh,
    onError: (err) => toast.error(errorMessage(tErrors, err)),
  });
  const remove = useMutation({
    mutationFn: () => deleteWatch(watch.id),
    onSuccess: refresh,
    onError: (err) => toast.error(errorMessage(tErrors, err)),
  });
  const busy = run.isPending || toggle.isPending || remove.isPending;

  return (
    <li
      className="flex flex-col gap-2 rounded-lg border bg-card p-4 shadow-card"
      data-testid="watch-row"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="font-semibold break-words" dir="auto">
            {watch.title}
          </h2>
          <p className="text-sm break-all text-muted-foreground" dir="ltr">
            {watch.url}
          </p>
        </div>
        <Badge variant={watch.enabled ? "secondary" : "outline"}>
          {watch.enabled ? t(`kinds.${watch.kind}`) : t("paused")}
        </Badge>
      </div>
      <p className="text-sm text-muted-foreground" data-testid="watch-status">
        {[
          (INTERVALS as readonly number[]).includes(watch.interval_minutes)
            ? t(`intervals.m${watch.interval_minutes as (typeof INTERVALS)[number]}`)
            : t("everyMinutes", { count: watch.interval_minutes }),
          watch.last_run
            ? t("lastRun", { when: isolate(when.format(new Date(watch.last_run))) })
            : t("neverRun"),
          watch.last_new != null ? t("lastNew", { count: watch.last_new }) : null,
          t("seen", { count: watch.seen }),
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>
      {watch.last_error && (
        <p role="alert" className="text-sm text-destructive">
          {watch.last_error}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          onClick={() => run.mutate()}
          disabled={busy}
          aria-label={`${t("runNow")}: ${watch.title}`}
        >
          {run.isPending ? (
            <Loader2Icon className="animate-spin" aria-hidden="true" />
          ) : (
            <RefreshCwIcon aria-hidden="true" />
          )}
          {t("runNow")}
        </Button>
        <Button size="sm" variant="outline" onClick={() => toggle.mutate()} disabled={busy}>
          {watch.enabled ? <PauseIcon aria-hidden="true" /> : <PlayIcon aria-hidden="true" />}
          {watch.enabled ? t("pause") : t("resume")}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => remove.mutate()}
          disabled={busy}
          aria-label={`${t("delete")}: ${watch.title}`}
        >
          <Trash2Icon aria-hidden="true" />
          {t("delete")}
        </Button>
      </div>
    </li>
  );
}

export default WatchView;
