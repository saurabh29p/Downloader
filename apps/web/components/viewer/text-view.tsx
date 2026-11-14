"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { ChevronDownIcon, ChevronUpIcon } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { textPage } from "@/lib/api-viewer";
import { errorMessage } from "@/lib/errors";
import { formatBytes, isolate } from "@/lib/format";

const MAX_LOADED = 4 * 1024 * 1024; // stop offering "Load more" after ~4 MB of text
const MAX_MARKS = 2000;

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Text files, a page (256 KB) at a time: wrap, search (with next/previous match). */
export function TextView({ id, size }: { id: string; size: number }) {
  const t = useTranslations("Viewer");
  const tErrors = useTranslations("Errors");
  const locale = useLocale();
  const field = useId();
  const box = useRef<HTMLDivElement>(null);
  const [wrap, setWrap] = useState(true);
  const [query, setQuery] = useState("");
  const [at, setAt] = useState(0);
  const pages = useInfiniteQuery({
    queryKey: ["library", "text", id],
    queryFn: ({ pageParam }) => textPage(id, pageParam),
    initialPageParam: 0,
    getNextPageParam: (last) => last.next_offset ?? undefined,
  });
  const text = useMemo(() => pages.data?.pages.map((p) => p.text).join("") ?? "", [pages.data]);
  const loaded = text.length;

  const parts = useMemo(() => {
    if (query.trim().length < 2) return null;
    return text.split(new RegExp(`(${escape(query.trim())})`, "giu"));
  }, [text, query]);
  const matches = parts ? Math.min((parts.length - 1) / 2, MAX_MARKS) : 0;

  useEffect(() => {
    if (!matches) return;
    const marks = box.current?.querySelectorAll("mark");
    const mark = marks?.[Math.min(at, marks.length - 1)];
    mark?.scrollIntoView({ block: "center" });
  }, [at, matches]);

  if (pages.isPending) return <Skeleton className="m-4 h-64" aria-busy="true" />;
  if (pages.isError)
    return (
      <p role="alert" className="p-6">
        {errorMessage(tErrors, pages.error)}
      </p>
    );

  let markIndex = -1;
  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b px-3 py-2 text-sm">
        <label htmlFor={field} className="sr-only">
          {t("findInText")}
        </label>
        <input
          id={field}
          type="search"
          dir="auto"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setAt(0);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && matches) {
              e.preventDefault();
              setAt((n) => (n + (e.shiftKey ? matches - 1 : 1)) % matches);
            }
          }}
          placeholder={t("findInText")}
          className="h-9 w-48 rounded-md border border-input bg-card px-2"
          data-testid="text-search"
        />
        <span className="call-number" aria-live="polite" data-testid="text-matches">
          {query.trim().length >= 2 ? t("matches", { count: matches }) : ""}
        </span>
        <Button
          variant="ghost"
          size="sm"
          disabled={!matches}
          onClick={() => setAt((n) => (n + matches - 1) % matches)}
          aria-label={t("previousMatch")}
        >
          <ChevronUpIcon aria-hidden="true" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          disabled={!matches}
          onClick={() => setAt((n) => (n + 1) % matches)}
          aria-label={t("nextMatch")}
        >
          <ChevronDownIcon aria-hidden="true" />
        </Button>
        <label className="ms-auto flex items-center gap-2">
          <input
            type="checkbox"
            checked={wrap}
            onChange={(e) => setWrap(e.target.checked)}
            className="size-4 accent-primary"
          />
          {t("wrap")}
        </label>
        <span className="call-number">{isolate(formatBytes(size, locale))}</span>
      </div>
      <div
        ref={box}
        tabIndex={0}
        dir="auto"
        aria-label={t("textArea")}
        className={`min-h-0 flex-1 overflow-auto bg-card p-4 font-mono text-sm leading-relaxed focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none ${wrap ? "break-words whitespace-pre-wrap" : "whitespace-pre"}`}
        role="region"
        data-testid="viewer-text"
      >
        {parts
          ? parts.map((part, i) => {
              if (i % 2 === 0) return part;
              markIndex += 1;
              return markIndex < MAX_MARKS ? (
                <mark
                  key={i}
                  className={
                    markIndex === at
                      ? "bg-signal text-signal-foreground"
                      : "bg-signal/30 text-foreground"
                  }
                >
                  {part}
                </mark>
              ) : (
                part
              );
            })
          : text}
        {pages.hasNextPage && loaded < MAX_LOADED && (
          <div className="mt-4 font-sans">
            <Button
              variant="outline"
              onClick={() => void pages.fetchNextPage()}
              disabled={pages.isFetchingNextPage}
            >
              {t("loadMore")}
            </Button>
          </div>
        )}
        {pages.hasNextPage && loaded >= MAX_LOADED && (
          <p className="mt-4 font-sans text-muted-foreground">{t("tooLongText")}</p>
        )}
      </div>
    </div>
  );
}
