"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2Icon, SearchIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useId, useState, type FormEvent } from "react";

import { BookCard } from "@/components/books/book-card";
import { SourceStatusList } from "@/components/books/source-status";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { searchBooks } from "@/lib/api-books";
import { errorMessage } from "@/lib/errors";

const LANGS = ["", "en", "fr", "de", "es", "it", "ru", "ja", "zh", "hi", "ar"] as const;

/** Books: one search across free sources; the best legal copy comes first. */
export function BooksView() {
  const t = useTranslations("Books");
  const tErrors = useTranslations("Errors");
  const id = useId();
  const [text, setText] = useState("");
  const [lang, setLang] = useState("");
  const [query, setQuery] = useState<{ q: string; lang: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const result = useQuery({
    queryKey: ["books", query],
    queryFn: () => searchBooks(query!.q, query!.lang),
    enabled: query !== null,
    staleTime: 5 * 60_000,
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!text.trim()) {
      setError(t("needQuery"));
      return;
    }
    setQuery({ q: text.trim(), lang });
  };

  const data = result.data;
  const others = (data?.results ?? []).filter((h) => h !== data?.results?.[0] || !data?.best);

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
            aria-invalid={error ? true : undefined}
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
          <Button type="submit" disabled={result.isFetching}>
            {result.isFetching ? (
              <Loader2Icon className="animate-spin" aria-hidden="true" />
            ) : (
              <SearchIcon aria-hidden="true" />
            )}
            {t("search")}
          </Button>
        </div>
        <p className="text-sm text-muted-foreground">{t("hint")}</p>
        {error && (
          <p role="alert" className="text-sm font-medium text-destructive">
            {error}
          </p>
        )}
      </form>

      {result.isFetching && (
        <div className="flex flex-col gap-3" aria-busy="true">
          <Skeleton className="h-36" />
          <Skeleton className="h-28" />
        </div>
      )}
      {result.isError && !result.isFetching && (
        <div className="flex flex-col gap-2">
          <p role="alert">{errorMessage(tErrors, result.error)}</p>
          <Button variant="outline" className="self-start" onClick={() => result.refetch()}>
            {t("retry")}
          </Button>
        </div>
      )}
      {data && !result.isFetching && (
        <section className="flex flex-col gap-4" aria-labelledby={`${id}-results`}>
          <h2 id={`${id}-results`} className="sr-only">
            {t("results")}
          </h2>
          <p className="text-sm text-muted-foreground" aria-live="polite">
            {data.best ? t("count", { count: data.results?.length ?? 0 }) : t("noBest")}
          </p>
          {data.best && <BookCard hit={data.best} best />}
          <div className="flex flex-col gap-3">
            {others.map((hit) => (
              <BookCard key={`${hit.source}:${hit.id}`} hit={hit} />
            ))}
          </div>
          <SourceStatusList sources={data.sources ?? []} />
        </section>
      )}
    </div>
  );
}

export default BooksView;
