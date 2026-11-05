"use client";

import type { ArchiveHit, BookSearch, VideoHit } from "@anyget/shared";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DownloadIcon, Loader2Icon, SearchIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useId, useState, type FormEvent } from "react";

import { BookCard } from "@/components/books/book-card";
import { SourceStatusList } from "@/components/books/source-status";
import { ChoicePill } from "@/components/media/choice";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/i18n/navigation";
import { createJobs } from "@/lib/api";
import { universalSearch, type SearchTab } from "@/lib/api-books";
import { errorMessage } from "@/lib/errors";
import { formatDuration, isolate } from "@/lib/format";
import { toast } from "@/lib/toast";
import { JOBS_KEY } from "@/lib/use-jobs";

const TABS: SearchTab[] = ["books", "libraries", "archive", "videos"];

/** One search box across books, libraries, archive.org and videos; one tab is fetched at a time. */
export function SearchView() {
  const t = useTranslations("Search");
  const tErrors = useTranslations("Errors");
  const id = useId();
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const [tab, setTab] = useState<SearchTab>("books");
  const [error, setError] = useState<string | null>(null);
  const result = useQuery({
    queryKey: ["search", q, tab],
    queryFn: () => universalSearch(q, [tab]),
    enabled: q !== "",
    staleTime: 5 * 60_000,
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!text.trim()) {
      setError(t("needQuery"));
      return;
    }
    setQ(text.trim());
  };
  const data = result.data;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t("title")}</h1>
        <p className="max-w-prose text-muted-foreground">{t("subtitle")}</p>
      </div>
      <form onSubmit={submit} className="flex flex-col gap-2" noValidate role="search">
        <label htmlFor={`${id}-q`} className="text-sm font-medium">
          {t("label")}
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            id={`${id}-q`}
            type="search"
            dir="auto"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={t("placeholder")}
            aria-invalid={error ? true : undefined}
            className="h-11 w-full min-w-0 rounded-md border border-input bg-card px-3 text-base shadow-xs placeholder:text-muted-foreground"
            data-testid="search-query"
          />
          <Button type="submit" disabled={result.isFetching}>
            {result.isFetching ? (
              <Loader2Icon className="animate-spin" aria-hidden="true" />
            ) : (
              <SearchIcon aria-hidden="true" />
            )}
            {t("search")}
          </Button>
        </div>
        {error && (
          <p role="alert" className="text-sm font-medium text-destructive">
            {error}
          </p>
        )}
      </form>

      <div role="radiogroup" aria-label={t("tabs")} className="flex flex-wrap gap-2">
        {TABS.map((name) => (
          <ChoicePill
            key={name}
            name={`${id}-tab`}
            value={name}
            checked={tab === name}
            onChange={() => setTab(name)}
          >
            {t(`tab.${name}`)}
          </ChoicePill>
        ))}
      </div>

      {q === "" && <p className="text-muted-foreground">{t("empty")}</p>}
      {result.isFetching && <Skeleton className="h-48" aria-busy="true" />}
      {result.isError && !result.isFetching && (
        <div className="flex flex-col gap-2">
          <p role="alert">{errorMessage(tErrors, result.error)}</p>
          <Button variant="outline" className="self-start" onClick={() => result.refetch()}>
            {t("retry")}
          </Button>
        </div>
      )}
      {data && !result.isFetching && (
        <section
          aria-labelledby={`${id}-results`}
          className="flex flex-col gap-3"
          data-testid="search-results"
        >
          <h2 id={`${id}-results`} className="sr-only">
            {t(`tab.${tab}`)}
          </h2>
          {(tab === "books" || tab === "libraries") && data[tab] && (
            <BookResults search={data[tab]} />
          )}
          {tab === "archive" && data.archive && (
            <GroupState status={data.archive.status}>
              <ArchiveResults items={data.archive.items ?? []} />
            </GroupState>
          )}
          {tab === "videos" && data.videos && (
            <GroupState status={data.videos.status}>
              <VideoResults items={data.videos.items ?? []} />
            </GroupState>
          )}
        </section>
      )}
    </div>
  );
}

function GroupState({ status, children }: { status?: string; children: React.ReactNode }) {
  const t = useTranslations("Search");
  if (status && status !== "ok") return <p role="alert">{t(`groupStatus.${status as "error"}`)}</p>;
  return <>{children}</>;
}

function BookResults({ search }: { search: BookSearch }) {
  const t = useTranslations("Search");
  const results = search.results ?? [];
  return (
    <>
      <p className="text-sm text-muted-foreground" aria-live="polite">
        {t("count", { count: results.length })}
      </p>
      {results.map((hit, i) => (
        <BookCard key={`${hit.source}:${hit.id}`} hit={hit} best={i === 0 && !!search.best} />
      ))}
      <SourceStatusList sources={search.sources ?? []} />
    </>
  );
}

function useQueue() {
  const tJobs = useTranslations("Jobs");
  const tErrors = useTranslations("Errors");
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (url: string) => createJobs([url]),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: JOBS_KEY });
      if (result.jobs.length) toast.success(tJobs("added", { count: result.jobs.length }));
    },
    onError: (err) => toast.error(errorMessage(tErrors, err)),
  });
}

function ArchiveResults({ items }: { items: ArchiveHit[] }) {
  const t = useTranslations("Search");
  if (!items.length) return <p>{t("none")}</p>;
  return (
    <ul className="flex flex-col divide-y rounded-md border">
      {items.map((item) => (
        <li key={item.identifier} className="flex items-center gap-3 p-3">
          <div className="min-w-0 flex-1">
            <p className="font-medium break-words" dir="auto">
              {item.title}
            </p>
            <p className="text-sm text-muted-foreground" dir="auto">
              {[item.creator, item.year ? isolate(item.year) : null].filter(Boolean).join(" · ")}
            </p>
          </div>
          <Link
            href={{ pathname: "/archive", query: { id: item.identifier } }}
            className={buttonVariants({ variant: "outline", size: "sm" })}
          >
            {t("openItem")}
          </Link>
        </li>
      ))}
    </ul>
  );
}

function VideoResults({ items }: { items: VideoHit[] }) {
  const t = useTranslations("Search");
  const queue = useQueue();
  if (!items.length) return <p>{t("none")}</p>;
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {items.map((video) => (
        <li key={video.id} className="flex gap-3 rounded-md border p-2">
          {video.thumbnail && (
            // eslint-disable-next-line @next/next/no-img-element -- remote thumbnails
            <img
              src={video.thumbnail}
              alt=""
              width={120}
              height={68}
              loading="lazy"
              referrerPolicy="no-referrer"
              className="aspect-video w-30 shrink-0 rounded bg-muted object-cover"
            />
          )}
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <p className="line-clamp-2 text-sm font-medium" dir="auto">
              {video.title}
            </p>
            <p className="text-xs text-muted-foreground" dir="auto">
              {[video.channel, video.duration ? isolate(formatDuration(video.duration)) : null]
                .filter(Boolean)
                .join(" · ")}
            </p>
            <div className="flex gap-2">
              <Link
                href={{ pathname: "/youtube", query: { url: video.url } }}
                className={buttonVariants({ variant: "outline", size: "sm" })}
              >
                {t("chooseFormat")}
              </Link>
              <Button
                size="sm"
                disabled={queue.isPending}
                onClick={() => queue.mutate(video.url)}
                aria-label={`${t("download")}: ${video.title}`}
              >
                <DownloadIcon aria-hidden="true" />
                {t("download")}
              </Button>
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

export default SearchView;
