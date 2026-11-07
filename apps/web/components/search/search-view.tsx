"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ExternalLinkIcon, Loader2Icon, SearchIcon } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/i18n/navigation";
import { createJobs } from "@/lib/api";
import {
  universalUrl,
  type Media,
  type UniversalDone,
  type ResultCard,
  type RouterPlan,
  type Answer,
  type MovieInfo,
  type SourceDone,
} from "@/lib/api-universal";
import { byOrder } from "@/lib/by-order";
import { errorMessage } from "@/lib/errors";
import { toast } from "@/lib/toast";
import { JOBS_KEY } from "@/lib/use-jobs";
import { cn } from "@/lib/utils";

type Card = ResultCard;
type Plan = RouterPlan;

const MEDIA_ORDER: Media[] = [
  "movie",
  "video",
  "music",
  "book",
  "photo",
  "map",
  "newspaper",
  "manuscript",
  "declassified",
  "other",
];
const LICENCE_VARIANT = {
  public_domain: "success",
  cc: "success",
  rights_reserved: "outline",
  streaming_only: "secondary",
  unknown: "outline",
} as const;

type State = {
  running: boolean;
  plan: Plan | null;
  sources: SourceDone[];
  cards: Card[];
  failed: boolean;
  /** The AI helper's order for the cards (ids), when it sent one. */
  order: string[] | null;
  answer: Answer | null;
  aiIssue: string | null;
};
const EMPTY: State = {
  running: false,
  plan: null,
  sources: [],
  cards: [],
  failed: false,
  order: null,
  answer: null,
  aiIssue: null,
};

/** One box for everything: results stream in per source, grouped by kind of media. */
export function SearchView({
  initialQuery = "",
  section,
  preset,
  presetQuery: givenPresetQuery = "",
  links = [],
}: {
  initialQuery?: string;
  section?: string;
  /** A section's pre-built search to run at once (its query comes from the API). */
  preset?: string;
  /** That preset's query, for the "Search on …" links. */
  presetQuery?: string;
  /** Official sites without an open API: "Search on …" with the query filled in. */
  links?: { label: string; url: string }[];
}) {
  const t = useTranslations("Search");
  const tIssues = useTranslations("AiIssues");
  const locale = useLocale();
  const id = useId();
  const [text, setText] = useState(initialQuery);
  const [inputError, setInputError] = useState<string | null>(null);
  const [state, setState] = useState<State>(EMPTY);
  const [tab, setTab] = useState<Media | "all">("all");
  const stream = useRef<EventSource | null>(null);

  const [asked, setAsked] = useState(initialQuery);
  const start = (q: string, withPreset?: string) => {
    setAsked(q);
    stream.current?.close();
    setTab("all");
    setState({ ...EMPTY, running: true });
    const url = new URL(window.location.href);
    if (q) url.searchParams.set("q", q);
    else url.searchParams.delete("q");
    if (withPreset) url.searchParams.set("preset", withPreset);
    else url.searchParams.delete("preset");
    window.history.replaceState(null, "", url);
    const source = new EventSource(universalUrl(q, section, withPreset));
    stream.current = source;
    let finished = false;
    source.addEventListener("plan", (event) => {
      const plan = JSON.parse((event as MessageEvent<string>).data) as Plan;
      if (plan.kind === "url" && plan.urls?.[0]) {
        // Links: the paste box on Home probes them and opens the preview.
        finished = true;
        source.close();
        // A full load: the target page starts from its address.
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.assign(
          `${window.location.origin}/${locale}?url=${encodeURIComponent(plan.urls[0])}`,
        );
        return;
      }
      setState((s) => ({ ...s, plan }));
    });
    source.addEventListener("source", (event) => {
      const done = JSON.parse((event as MessageEvent<string>).data) as SourceDone;
      setState((s) => ({
        ...s,
        sources: [...s.sources, done],
        cards: [...s.cards, ...(done.results ?? [])].sort(
          (a, b) => (b.score ?? 0) - (a.score ?? 0),
        ),
      }));
    });
    source.addEventListener("rerank", (event) => {
      const { ids } = JSON.parse((event as MessageEvent<string>).data) as { ids: string[] };
      setState((s) => ({ ...s, order: ids }));
    });
    source.addEventListener("answer", (event) => {
      const answer = JSON.parse((event as MessageEvent<string>).data) as Answer;
      setState((s) => ({ ...s, answer }));
    });
    source.addEventListener("done", (event) => {
      finished = true;
      source.close();
      let aiIssue: string | null = null;
      try {
        aiIssue = (JSON.parse((event as MessageEvent<string>).data) as UniversalDone).ai_issue;
      } catch {
        // an older server: no AI status
      }
      setState((s) => ({ ...s, running: false, aiIssue }));
    });
    source.onerror = () => {
      source.close();
      if (!finished) setState((s) => ({ ...s, running: false, failed: true }));
    };
  };

  useEffect(() => {
    // A search handed over in the address (/search?q=…, from Home or Ctrl+K).
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time start from the URL
    if (preset) start("", preset);
    else if (initialQuery.trim()) start(initialQuery.trim());
    return () => stream.current?.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only on first render
  }, []);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setInputError(null);
    if (!text.trim()) {
      setInputError(t("needQuery"));
      return;
    }
    start(text.trim());
  };

  const counts = new Map<Media, number>();
  for (const card of state.cards) counts.set(card.media, (counts.get(card.media) ?? 0) + 1);
  const tabs = MEDIA_ORDER.filter((m) => counts.has(m));
  const ordered = state.order ? byOrder(state.cards, state.order) : state.cards;
  const shown = tab === "all" ? ordered : ordered.filter((c) => c.media === tab);
  const failedSources = state.sources.filter(
    (s) => s.status === "error" || s.status === "timeout" || s.status === "rate_limited",
  );
  const needsKey = state.sources.some((s) => s.status === "needs_key");
  const badKey = state.sources.some((s) => s.status === "bad_key");
  const presetQuery = givenPresetQuery || state.plan?.queries?.[0]?.q || "";
  const linkQuery = asked || presetQuery;

  return (
    <div className="flex flex-col gap-6">
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
            aria-invalid={inputError ? true : undefined}
            className="h-11 w-full min-w-0 rounded-md border border-input bg-card px-3 text-base shadow-xs placeholder:text-muted-foreground"
            data-testid="search-query"
          />
          <Button type="submit" disabled={state.running}>
            {state.running ? (
              <Loader2Icon className="animate-spin" aria-hidden="true" />
            ) : (
              <SearchIcon aria-hidden="true" />
            )}
            {t("search")}
          </Button>
        </div>
        {inputError && (
          <p role="alert" className="text-sm font-medium text-destructive">
            {inputError}
          </p>
        )}
      </form>

      {state.answer ? (
        <AnswerCard answer={state.answer} cards={state.cards} />
      ) : (
        state.plan?.kind === "question" &&
        !state.running &&
        state.plan.router !== "llm" && (
          <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
            {t("questionNote")}
          </p>
        )
      )}

      {tabs.length > 1 && (
        <div role="radiogroup" aria-label={t("tabs")} className="flex flex-wrap gap-2">
          {(["all", ...tabs] as const).map((m) => (
            <label
              key={m}
              className={cn(
                "inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-full border px-4 text-sm has-[:focus-visible]:ring-[3px] has-[:focus-visible]:ring-ring/50",
                tab === m && "border-primary bg-primary text-primary-foreground",
              )}
            >
              <input
                type="radio"
                name={`${id}-tab`}
                className="sr-only"
                checked={tab === m}
                onChange={() => setTab(m)}
              />
              {m === "all" ? t("all") : t(`media.${m}`)}
              <span className="tabular-nums opacity-80">
                {m === "all" ? state.cards.length : counts.get(m)}
              </span>
            </label>
          ))}
        </div>
      )}

      <section
        aria-labelledby={`${id}-results`}
        className="flex flex-col gap-3"
        data-testid="search-results"
      >
        <h2 id={`${id}-results`} className="sr-only">
          {t("results")}
        </h2>
        <p className="text-sm text-muted-foreground" aria-live="polite">
          {state.running
            ? t("streaming", { count: state.sources.length })
            : state.plan
              ? t("count", { count: state.cards.length })
              : t("empty")}
        </p>
        <ul className="flex flex-col gap-3">
          {shown.map((card) => (
            <ResultItem key={card.id} card={card} />
          ))}
        </ul>
        {state.running && <Skeleton className="h-28" aria-hidden="true" />}
        {state.aiIssue && !state.running && (
          <p className="text-sm text-muted-foreground" role="status" data-testid="ai-issue">
            {t("aiIssue", {
              issue: tIssues.has(state.aiIssue as "no_credits")
                ? tIssues(state.aiIssue as "no_credits")
                : tIssues("provider_error"),
            })}
          </p>
        )}
        {(needsKey || badKey) && (
          <p className="text-sm" data-testid="needs-key">
            {badKey ? t("badKeyTmdb") : t("needsTmdb")}{" "}
            <a
              href={`/${locale}/connections#tmdb`}
              className="font-medium text-primary underline underline-offset-4"
            >
              {t("connectTmdb")}
            </a>
          </p>
        )}
        {(state.failed || failedSources.length > 0) && !state.running && (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span role="status">
              {failedSources.length
                ? t("someFailed", {
                    sources: failedSources.map((s) => t(`source.${s.source}`)).join(", "),
                  })
                : t("streamFailed")}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => start(asked, asked ? undefined : preset)}
            >
              {t("retry")}
            </Button>
          </div>
        )}
      </section>

      {links.length > 0 && linkQuery && (
        <nav aria-label={t("alsoOn")} className="flex flex-col gap-2" data-testid="site-links">
          <h2 className="text-sm font-medium">{t("alsoOn")}</h2>
          <ul className="flex flex-wrap gap-2">
            {links.map((link) => (
              <li key={link.label}>
                <a
                  href={link.url.replaceAll("{q}", encodeURIComponent(linkQuery))}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex min-h-11 items-center gap-1 rounded-full border px-4 text-sm hover:bg-accent"
                >
                  {link.label}
                  <ExternalLinkIcon className="size-4" aria-hidden="true" />
                </a>
              </li>
            ))}
          </ul>
        </nav>
      )}
    </div>
  );
}

const SECTION_OF: Partial<Record<Media, string>> = {
  movie: "movies",
  book: "books",
  music: "music",
  video: "video",
  declassified: "declassified",
  map: "maps",
  newspaper: "newspapers",
  photo: "photos",
  manuscript: "manuscripts",
};

function ResultItem({ card }: { card: Card }) {
  const t = useTranslations("Search");
  const tJobs = useTranslations("Jobs");
  const tErrors = useTranslations("Errors");
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState<"download" | "save" | null>(null);
  const queue = async (kind: "download" | "save") => {
    if (!card.download) return;
    setBusy(kind);
    try {
      // The section and licence go with the file into the Library (its filters).
      const info = { section: SECTION_OF[card.media], licence: card.licence ?? "unknown" };
      const result = await createJobs(
        [card.download],
        kind === "save" ? { ...info, tags: ["saved"] } : info,
      );
      void queryClient.invalidateQueries({ queryKey: JOBS_KEY });
      if (result.jobs.length) toast.success(tJobs("added", { count: result.jobs.length }));
    } catch (err) {
      toast.error(errorMessage(tErrors, err));
    }
    setBusy(null);
  };
  const meta = [card.source_label, card.year, card.creator].filter(Boolean).join(" · ");

  return (
    <li className="index-card gap-3 p-4 pb-7" data-testid="result-card" data-media={card.media}>
      {/* The card's head: a call number (kind · source · year), then the title. */}
      <div className="index-card-head flex flex-col gap-1 pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="call-number" dir="auto">
            {t(`media.${card.media}`)} · {meta}
          </p>
          <Badge variant={LICENCE_VARIANT[card.licence ?? "unknown"]}>
            {t(`licence.${card.licence ?? "unknown"}`)}
          </Badge>
        </div>
        <h3 className="font-serif text-lg leading-snug font-semibold break-words" dir="auto">
          {card.title}
        </h3>
      </div>
      <div className="flex gap-4">
        {card.thumbnail ? (
          // eslint-disable-next-line @next/next/no-img-element -- remote thumbnails
          <img
            src={card.thumbnail}
            alt=""
            width={96}
            height={72}
            loading="lazy"
            referrerPolicy="no-referrer"
            className="h-18 w-24 shrink-0 rounded-sm bg-muted object-cover"
          />
        ) : null}
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          {card.movie && <MovieDetails movie={card.movie} />}
          {card.formats && card.formats.length > 0 && (
            <p className="flex flex-wrap gap-1">
              {card.formats.map((f) => (
                <Badge key={f} variant="secondary">
                  {f.replace("_", " ").toUpperCase()}
                </Badge>
              ))}
            </p>
          )}
          <div className="flex flex-wrap items-center gap-2">
            {card.download && (
              <>
                {/* In-app navigation: a playing audio file keeps playing. */}
                <Link
                  href={`/?url=${encodeURIComponent(card.download)}`}
                  className="inline-flex h-9 items-center rounded-md border px-3 text-sm font-medium hover:bg-accent"
                >
                  {t("preview")}
                </Link>
                <Button size="sm" onClick={() => void queue("download")} disabled={busy !== null}>
                  {busy === "download" && (
                    <Loader2Icon className="animate-spin" aria-hidden="true" />
                  )}
                  {t("download")}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => void queue("save")}
                  disabled={busy !== null}
                >
                  {t("save")}
                </Button>
              </>
            )}
            <a
              href={card.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex min-h-9 items-center gap-1 text-sm font-medium text-primary"
            >
              {t("openSource")}
              <ExternalLinkIcon className="size-4" aria-hidden="true" />
            </a>
          </div>
        </div>
      </div>
    </li>
  );
}

export default SearchView;

function MovieDetails({ movie }: { movie: MovieInfo }) {
  const t = useTranslations("Search");
  const groups = [
    ["stream", movie.stream],
    ["free", movie.free],
    ["rent", movie.rent],
    ["buy", movie.buy],
  ] as const;
  const any = groups.some(([, list]) => list.length > 0);
  return (
    <div className="flex flex-col gap-2 text-sm" data-testid="movie-details">
      {movie.overview && <p className="line-clamp-3 text-muted-foreground">{movie.overview}</p>}
      <p className="text-muted-foreground">
        {[
          movie.rating ? t("rating", { rating: movie.rating }) : null,
          movie.cast.length ? movie.cast.slice(0, 3).join(", ") : null,
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>
      <div className="flex flex-col gap-1">
        <span className="font-medium">{t("whereToWatch", { region: movie.region })}</span>
        {any ? (
          groups
            .filter(([, list]) => list.length > 0)
            .map(([kind, list]) => (
              <p key={kind} className="flex flex-wrap items-center gap-1">
                <span className="text-muted-foreground">{t(`watch.${kind}`)}:</span>
                {list.map((p) => (
                  <Badge key={p.name} variant={kind === "free" ? "success" : "secondary"}>
                    {p.name}
                  </Badge>
                ))}
              </p>
            ))
        ) : (
          <span className="text-muted-foreground">{t("notStreaming")}</span>
        )}
      </div>
      <p className="flex flex-wrap gap-3">
        {movie.trailer && (
          <a
            href={movie.trailer}
            target="_blank"
            rel="noreferrer"
            className="font-medium text-primary"
          >
            {t("trailer")}
          </a>
        )}
        {movie.watch_link && (
          <a
            href={movie.watch_link}
            target="_blank"
            rel="noreferrer"
            className="font-medium text-primary"
          >
            {t("watchOptions")}
          </a>
        )}
      </p>
    </div>
  );
}

/** Cards in the AI helper's order; cards it didn't rank keep their place at the end. */
export { byOrder };

function AnswerCard({ answer, cards }: { answer: Answer; cards: Card[] }) {
  const t = useTranslations("Search");
  const cited = answer.citations
    .map((id) => cards.find((c) => c.id === id))
    .filter((c): c is Card => Boolean(c));
  return (
    <section
      aria-labelledby="answer-heading"
      className="flex flex-col gap-2 rounded-lg border border-primary/40 bg-card p-4 shadow-card"
      data-testid="answer-card"
    >
      <h2 id="answer-heading" className="text-sm font-semibold">
        {t("answerTitle")}
      </h2>
      <p dir="auto" className="whitespace-pre-line">
        {answer.text}
      </p>
      {cited.length > 0 && (
        <ol className="flex list-decimal flex-col gap-1 ps-5 text-sm">
          {cited.map((c) => (
            <li key={c.id}>
              <a href={c.url} target="_blank" rel="noreferrer" className="text-primary underline">
                {c.title}
              </a>{" "}
              <span className="text-muted-foreground">· {c.source_label}</span>
            </li>
          ))}
        </ol>
      )}
      <p className="text-xs text-muted-foreground">{t("answerNote")}</p>
    </section>
  );
}
