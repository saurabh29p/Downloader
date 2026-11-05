"use client";

import type { ArchiveHit } from "@anyget/shared";
import { useInfiniteQuery } from "@tanstack/react-query";
import { Loader2Icon, SearchIcon } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import { useId, useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { archiveSearch, type ArchiveQuery } from "@/lib/api-archive";
import { errorMessage } from "@/lib/errors";
import { isolate } from "@/lib/format";

const ItemView = dynamic(() => import("@/components/archive/item-view").then((m) => m.ItemView));

const MEDIATYPES = ["", "texts", "audio", "movies", "image", "software", "etree"] as const;
const input =
  "h-11 w-full min-w-0 rounded-md border border-input bg-card px-3 text-base shadow-xs placeholder:text-muted-foreground";

/** archive.org: search with filters, result cards, and an item page with a file picker. */
export function ArchiveView() {
  const t = useTranslations("Archive");
  const tErrors = useTranslations("Errors");
  const locale = useLocale();
  const id = useId();
  const params = useSearchParams();
  const [form, setForm] = useState({
    q: "",
    mediatype: "",
    collection: "",
    yearFrom: "",
    yearTo: "",
    creator: "",
  });
  const [query, setQuery] = useState<ArchiveQuery | null>(null);
  const [itemId, setItemId] = useState<string | null>(() => params.get("id"));

  const results = useInfiniteQuery({
    queryKey: ["archive-search", query],
    enabled: query !== null,
    initialPageParam: 1,
    queryFn: ({ pageParam }) => archiveSearch({ ...query!, page: pageParam }),
    getNextPageParam: (last, pages) =>
      pages.reduce((n, p) => n + p.items.length, 0) < last.total && pages.length < 100
        ? pages.length + 1
        : undefined,
  });
  const hits: ArchiveHit[] = results.data?.pages.flatMap((p) => p.items) ?? [];
  const total = results.data?.pages[0]?.total ?? 0;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setItemId(null);
    const num = (v: string) => (/^\d{1,4}$/.test(v) ? Number(v) : undefined);
    setQuery({
      q: form.q.trim(),
      mediatype: form.mediatype || undefined,
      collection: form.collection.trim() || undefined,
      creator: form.creator.trim() || undefined,
      year_from: num(form.yearFrom),
      year_to: num(form.yearTo),
    });
  };
  const field = (key: keyof typeof form) => ({
    value: form[key],
    onChange: (e: { target: { value: string } }) =>
      setForm((f) => ({ ...f, [key]: e.target.value })),
  });

  if (itemId) return <ItemView identifier={itemId} onBack={() => setItemId(null)} />;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t("title")}</h1>
        <p className="max-w-prose text-muted-foreground">{t("subtitle")}</p>
      </div>

      <form
        onSubmit={submit}
        className="flex flex-col gap-3"
        role="search"
        aria-label={t("searchLabel")}
      >
        <label htmlFor={`${id}-q`} className="text-sm font-medium">
          {t("searchLabel")}
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            id={`${id}-q`}
            type="search"
            {...field("q")}
            placeholder={t("searchPlaceholder")}
            className={input}
            data-testid="archive-q"
          />
          <Button type="submit" disabled={results.isFetching && !results.isFetchingNextPage}>
            {results.isFetching && !results.isFetchingNextPage ? (
              <Loader2Icon className="animate-spin" aria-hidden="true" />
            ) : (
              <SearchIcon aria-hidden="true" />
            )}
            {t("search")}
          </Button>
        </div>
        <details className="text-sm">
          <summary className="flex min-h-11 cursor-pointer items-center font-medium">
            {t("filters")}
          </summary>
          <div className="grid grid-cols-1 gap-3 pt-2 sm:grid-cols-3">
            <label className="flex flex-col gap-1">
              {t("mediatype")}
              <NativeSelect {...field("mediatype")} className="w-full border-input bg-card">
                {MEDIATYPES.map((m) => (
                  <option key={m} value={m}>
                    {m ? t(`types.${m}`) : t("anyType")}
                  </option>
                ))}
              </NativeSelect>
            </label>
            <label className="flex flex-col gap-1">
              {t("collection")}
              <input {...field("collection")} placeholder="gutenberg" className={input} dir="ltr" />
            </label>
            <label className="flex flex-col gap-1">
              {t("creator")}
              <input {...field("creator")} className={input} />
            </label>
            <label className="flex flex-col gap-1">
              {t("yearFrom")}
              <input {...field("yearFrom")} inputMode="numeric" maxLength={4} className={input} />
            </label>
            <label className="flex flex-col gap-1">
              {t("yearTo")}
              <input {...field("yearTo")} inputMode="numeric" maxLength={4} className={input} />
            </label>
          </div>
        </details>
      </form>

      {results.isError && (
        <div role="alert" className="flex flex-col items-start gap-2 rounded-lg border p-4">
          <p>{errorMessage(tErrors, results.error)}</p>
          <Button variant="outline" onClick={() => results.refetch()}>
            {t("retry")}
          </Button>
        </div>
      )}
      {results.isPending && query && (
        <div className="flex flex-col gap-2" aria-busy="true">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      )}
      {results.isSuccess && (
        <section aria-labelledby={`${id}-results`} className="flex flex-col gap-3">
          <h2 id={`${id}-results`} className="text-sm text-muted-foreground" aria-live="polite">
            {t("resultCount", {
              count: total,
              shown: isolate(new Intl.NumberFormat(locale).format(total)),
            })}
          </h2>
          {hits.length === 0 ? (
            <p className="rounded-lg border border-dashed p-6 text-center text-muted-foreground">
              {t("noResults")}
            </p>
          ) : (
            <ul className="flex flex-col gap-2" data-testid="archive-results">
              {hits.map((hit) => (
                <li key={hit.identifier}>
                  <button
                    type="button"
                    onClick={() => setItemId(hit.identifier)}
                    className="flex w-full items-start gap-3 rounded-lg border bg-card p-3 text-start shadow-card hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element -- archive.org thumbnails */}
                    <img
                      src={hit.thumbnail}
                      alt=""
                      width={64}
                      height={64}
                      loading="lazy"
                      referrerPolicy="no-referrer"
                      className="size-16 shrink-0 rounded bg-muted object-cover"
                    />
                    <span className="flex min-w-0 flex-col gap-1">
                      <span className="font-medium break-words" dir="auto">
                        {hit.title}
                      </span>
                      <span className="text-sm text-muted-foreground" dir="auto">
                        {[hit.creator, hit.year ? isolate(hit.year) : null]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                      {hit.mediatype && (
                        <Badge variant="secondary">
                          {MEDIATYPES.includes(hit.mediatype as (typeof MEDIATYPES)[number])
                            ? t(`types.${hit.mediatype as "texts"}`)
                            : hit.mediatype}
                        </Badge>
                      )}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {results.hasNextPage && (
            <Button
              variant="outline"
              onClick={() => results.fetchNextPage()}
              disabled={results.isFetchingNextPage}
              className="self-center"
            >
              {results.isFetchingNextPage && (
                <Loader2Icon className="animate-spin" aria-hidden="true" />
              )}
              {t("loadMore")}
            </Button>
          )}
        </section>
      )}
      <p className="text-sm text-muted-foreground">{t("etiquette")}</p>
    </div>
  );
}

export default ArchiveView;
