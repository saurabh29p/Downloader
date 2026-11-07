"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { epubBook, epubChapter, type EpubChapter } from "@/lib/api-viewer";
import { errorMessage } from "@/lib/errors";

const SIZES = [14, 16, 18, 20, 23, 26] as const;
const FONT_KEY = "anyget-reader-size";
const POS_KEY = (id: string) => `anyget-read:${id}`;

type Place = { chapter: number; ratio: number };

function load<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function store(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // storage blocked: the reader still works, it just won't remember
  }
}

/**
 * EPUB reader: contents, previous/next chapter, font size and the reading position
 * (chapter + scroll), remembered on this device. Chapters arrive as plain text
 * blocks from the API, so nothing in the book can run or load remote resources.
 */
export function EpubView({ id }: { id: string }) {
  const t = useTranslations("Viewer");
  const tErrors = useTranslations("Errors");
  const select = useId();
  const page = useRef<HTMLDivElement>(null);
  const [saved] = useState(() => load<Place | null>(POS_KEY(id), null));
  const [chapter, setChapter] = useState(saved?.chapter ?? 0);
  const [resumed, setResumed] = useState(!!saved && (saved.chapter > 0 || saved.ratio > 0.02));
  const [size, setSize] = useState<number>(() => load(FONT_KEY, 18));
  const book = useQuery({ queryKey: ["library", "epub", id], queryFn: () => epubBook(id) });
  const total = book.data?.chapters.length ?? 0;
  const current = useQuery({
    queryKey: ["library", "epub", id, chapter],
    queryFn: () => epubChapter(id, chapter),
    enabled: total > 0 && chapter < total,
  });

  // Back to where you were in this chapter, once it has rendered.
  useEffect(() => {
    const el = page.current;
    if (!el || !current.data) return;
    el.scrollTop = saved && saved.chapter === chapter ? saved.ratio * el.scrollHeight : 0;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only when a chapter arrives
  }, [current.data]);

  const remember = () => {
    const el = page.current;
    if (!el) return;
    const ratio = el.scrollHeight > el.clientHeight ? el.scrollTop / el.scrollHeight : 0;
    store(POS_KEY(id), { chapter, ratio } satisfies Place);
  };

  const go = (to: number) => {
    if (to < 0 || to >= total) return;
    setChapter(to);
    store(POS_KEY(id), { chapter: to, ratio: 0 } satisfies Place);
  };

  if (book.isPending) return <Skeleton className="m-4 h-64" aria-busy="true" />;
  if (book.isError)
    return (
      <p role="alert" className="p-6" data-testid="epub-error">
        {errorMessage(tErrors, book.error)}
      </p>
    );

  const title = (i: number) => book.data.chapters[i]?.title || t("section", { n: i + 1 });

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b px-3 py-2 text-sm">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => go(chapter - 1)}
          disabled={chapter === 0}
          aria-label={t("previousChapter")}
        >
          <ChevronLeftIcon aria-hidden="true" data-flip-rtl />
        </Button>
        <label htmlFor={select} className="sr-only">
          {t("contents")}
        </label>
        <select
          id={select}
          value={chapter}
          onChange={(e) => go(Number(e.target.value))}
          className="h-9 max-w-[60vw] rounded-md border border-input bg-card px-2"
          data-testid="epub-toc"
        >
          {book.data.chapters.map((c) => (
            <option key={c.index} value={c.index}>
              {title(c.index)}
            </option>
          ))}
        </select>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => go(chapter + 1)}
          disabled={chapter >= total - 1}
          aria-label={t("nextChapter")}
        >
          <ChevronRightIcon aria-hidden="true" data-flip-rtl />
        </Button>
        <span className="ms-auto flex items-center gap-1" role="group" aria-label={t("textSize")}>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              const next = SIZES[Math.max(0, SIZES.indexOf(size as 18) - 1)] ?? 16;
              setSize(next);
              store(FONT_KEY, next);
            }}
            aria-label={t("smaller")}
          >
            A−
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              const next = SIZES[Math.min(SIZES.length - 1, SIZES.indexOf(size as 18) + 1)] ?? 20;
              setSize(next);
              store(FONT_KEY, next);
            }}
            aria-label={t("larger")}
          >
            A+
          </Button>
        </span>
      </div>
      {resumed && (
        <p className="flex items-center gap-2 border-b bg-muted px-3 py-1.5 text-sm" role="status">
          {t("resumedChapter", { chapter: title(chapter) })}
          <button
            type="button"
            className="font-medium text-primary underline underline-offset-2"
            onClick={() => {
              setResumed(false);
              go(0);
              if (page.current) page.current.scrollTop = 0;
            }}
          >
            {t("startOver")}
          </button>
        </p>
      )}
      <div
        ref={page}
        tabIndex={0}
        onScroll={remember}
        className="min-h-0 flex-1 overflow-y-auto bg-card focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
        aria-label={t("chapterArea", { chapter: title(chapter) })}
        role="region"
        data-testid="epub-page"
      >
        <article
          className="mx-auto max-w-[38rem] px-5 py-8 font-serif leading-relaxed"
          style={{ fontSize: size }}
          dir="auto"
          lang={undefined}
        >
          {current.isPending ? (
            <Skeleton className="h-64" aria-busy="true" />
          ) : current.isError ? (
            <p role="alert">{errorMessage(tErrors, current.error)}</p>
          ) : (
            <Blocks chapter={current.data} />
          )}
        </article>
      </div>
    </div>
  );
}

function Blocks({ chapter }: { chapter: EpubChapter }) {
  const t = useTranslations("Viewer");
  if (chapter.blocks.length === 0)
    return <p className="text-muted-foreground">{t("emptyChapter")}</p>;
  return (
    <>
      {chapter.blocks.map((block, i) => {
        switch (block.kind) {
          case "h1":
            return (
              <h2 key={i} className="mt-2 mb-4 text-[1.6em] leading-tight font-semibold">
                {block.text}
              </h2>
            );
          case "h2":
          case "h3":
          case "h4":
            return (
              <h3 key={i} className="mt-6 mb-2 text-[1.25em] font-semibold">
                {block.text}
              </h3>
            );
          case "li":
            return (
              <p key={i} className="ms-5 mb-1 list-item list-disc">
                {block.text}
              </p>
            );
          case "quote":
            return (
              <blockquote key={i} className="my-3 border-s-2 ps-4 italic">
                {block.text}
              </blockquote>
            );
          case "pre":
            return (
              <pre
                key={i}
                className="my-3 overflow-x-auto font-mono text-[0.85em] whitespace-pre-wrap"
              >
                {block.text}
              </pre>
            );
          default:
            return (
              <p key={i} className="mb-3">
                {block.text}
              </p>
            );
        }
      })}
      {chapter.truncated && <p className="text-muted-foreground">{t("chapterTruncated")}</p>}
    </>
  );
}
