"use client";

import type { BookHit, BookSearch, SourceStatus } from "@anyget/shared";
import { Loader2Icon, SearchIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import { BookCard } from "@/components/books/book-card";
import { SourceStatusList } from "@/components/books/source-status";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { bookStreamUrl, searchBooks, type BookSourcePart } from "@/lib/api-books";
import { errorMessage } from "@/lib/errors";

const LANGS = ["", "en", "fr", "de", "es", "it", "ru", "ja", "zh", "hi", "ar"] as const;

type Run = { q: string; lang: string };
type State = {
  run: Run | null;
  running: boolean;
  /** Sources that answered so far, and their hits (shown before the ranking arrives). */
  sources: SourceStatus[];
  partial: BookHit[];
  done: BookSearch | null;
  error: unknown;
  retrying: string[];
};
const EMPTY: State = {
  run: null,
  running: false,
  sources: [],
  partial: [],
  done: null,
  error: null,
  retrying: [],
};

const key = (hit: BookHit) => `${hit.source}:${hit.id}`;

/** Books: one search across free sources; results stream in, the best legal copy first. */
export function BooksView() {
  const t = useTranslations("Books");
  const tErrors = useTranslations("Errors");
  const id = useId();
  const [text, setText] = useState("");
  const [lang, setLang] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const [state, setState] = useState<State>(EMPTY);
  const stream = useRef<EventSource | null>(null);

  useEffect(() => () => stream.current?.close(), []);

  const start = (run: Run) => {
    stream.current?.close();
    setState({ ...EMPTY, run, running: true });
    const fallback = () => {
      // One plain request instead (and a 401 sends the visitor to sign in).
      searchBooks(run.q, run.lang)
        .then((done) => setState((s) => ({ ...s, done, running: false })))
        .catch((error: unknown) => setState((s) => ({ ...s, error, running: false })));
    };
    if (typeof EventSource === "undefined") return fallback();
    const source = new EventSource(bookStreamUrl(run.q, run.lang));
    stream.current = source;
    let finished = false;
    source.addEventListener("source", (event) => {
      const part = JSON.parse((event as MessageEvent<string>).data) as BookSourcePart;
      setState((s) => ({
        ...s,
        sources: [...s.sources, part.source],
        partial: [...s.partial, ...(part.results ?? [])],
      }));
    });
    source.addEventListener("done", (event) => {
      finished = true;
      source.close();
      const done = JSON.parse((event as MessageEvent<string>).data) as BookSearch;
      setState((s) => ({ ...s, done, running: false }));
    });
    source.onerror = () => {
      if (finished) return;
      finished = true;
      source.close();
      fallback();
    };
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setInputError(null);
    if (!text.trim()) {
      setInputError(t("needQuery"));
      return;
    }
    start({ q: text.trim(), lang });
  };

  /** Ask one source again (it timed out or failed) and add what it finds. */
  const retry = (name: string) => {
    const run = state.run;
    if (!run) return;
    setState((s) => ({ ...s, retrying: [...s.retrying, name] }));
    const settle = (update: (s: State) => Partial<State>) =>
      setState((s) => ({ ...s, ...update(s), retrying: s.retrying.filter((n) => n !== name) }));
    searchBooks(run.q, run.lang, [name])
      .then((again) => {
        const status = again.sources?.find((s) => s.name === name);
        settle((s) => {
          if (!s.done) return {};
          const seen = new Set((s.done.results ?? []).map(key));
          const added = (again.results ?? []).filter((hit) => !seen.has(key(hit)));
          return {
            done: {
              ...s.done,
              best: s.done.best ?? again.best,
              results: [...(s.done.results ?? []), ...added],
              sources: (s.done.sources ?? []).map((old) =>
                old.name === name && status ? status : old,
              ),
            },
          };
        });
      })
      .catch(() => settle(() => ({})));
  };

  const { done, running } = state;
  const others = (done?.results ?? []).filter((h) => h !== done?.results?.[0] || !done?.best);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t("title")}</h1>
        <p className="max-w-prose text-muted-foreground">{t("subtitle")}</p>
      </div>
      <form onSubmit={submit} className="flex flex-col gap-2" noValidate role="search">
        <label htmlFor={`${id}-q`} className="text-sm font-medium">
          {t("searchLabel")}
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            id={`${id}-q`}
            type="search"
            dir="auto"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={t("placeholder")}
            aria-invalid={inputError ? true : undefined}
            className="h-11 w-full min-w-0 rounded-md border border-input bg-card px-3 text-base shadow-xs placeholder:text-muted-foreground"
            data-testid="books-query"
          />
          <select
            value={lang}
            onChange={(e) => setLang(e.target.value)}
            aria-label={t("language")}
            className="h-11 rounded-md border border-input bg-card px-3 text-sm"
          >
            {LANGS.map((code) => (
              <option key={code} value={code}>
                {code ? t(`langs.${code}`) : t("anyLanguage")}
              </option>
            ))}
          </select>
          <Button type="submit" disabled={running}>
            {running ? (
              <Loader2Icon className="animate-spin" aria-hidden="true" />
            ) : (
              <SearchIcon aria-hidden="true" />
            )}
            {t("search")}
          </Button>
        </div>
        <p className="text-sm text-muted-foreground">{t("hint")}</p>
        {inputError && (
          <p role="alert" className="text-sm font-medium text-destructive">
            {inputError}
          </p>
        )}
      </form>

      {running && (
        <div className="flex flex-col gap-3" aria-busy="true" data-testid="books-streaming">
          <p className="text-sm text-muted-foreground" aria-live="polite">
            {t("streaming", { count: state.sources.length })}
          </p>
          {state.partial.map((hit) => (
            <BookCard key={key(hit)} hit={hit} />
          ))}
          <Skeleton className="h-28" />
        </div>
      )}
      {state.error !== null && !running && (
        <div className="flex flex-col gap-2">
          <p role="alert">{errorMessage(tErrors, state.error)}</p>
          <Button
            variant="outline"
            className="self-start"
            onClick={() => state.run && start(state.run)}
          >
            {t("retry")}
          </Button>
        </div>
      )}
      {done && !running && (
        <section className="flex flex-col gap-4" aria-labelledby={`${id}-results`}>
          <h2 id={`${id}-results`} className="sr-only">
            {t("results")}
          </h2>
          <p className="text-sm text-muted-foreground" aria-live="polite">
            {done.best ? t("count", { count: done.results?.length ?? 0 }) : t("noBest")}
          </p>
          {done.best && <BookCard hit={done.best} best />}
          <div className="flex flex-col gap-3">
            {others.map((hit) => (
              <BookCard key={key(hit)} hit={hit} />
            ))}
          </div>
          <SourceStatusList
            sources={done.sources ?? []}
            onRetry={retry}
            retrying={state.retrying}
          />
        </section>
      )}
    </div>
  );
}

export default BooksView;
