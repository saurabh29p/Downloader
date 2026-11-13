"use client";

import type { ProbeResult } from "@anyget/shared";
import { useMutation } from "@tanstack/react-query";
import { Loader2Icon, SearchIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/i18n/navigation";
import { probeUrl } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { parseLinks } from "@/lib/links";
import { isList, isVideo, type Tab } from "@/lib/media";

// Loaded after the first probe: keeps the page's first load small.
const VideoCard = dynamic(() => import("@/components/media/video-card").then((m) => m.VideoCard));
const PlaylistView = dynamic(() =>
  import("@/components/media/playlist-view").then((m) => m.PlaylistView),
);

/** The YouTube (and other video/audio sites) page. */
export function YouTubeView() {
  const t = useTranslations("Media");
  const tErrors = useTranslations("Errors");
  const params = useSearchParams();
  const inputId = useId();
  const [text, setText] = useState(() => params.get("url") ?? "");
  const [probe, setProbe] = useState<ProbeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const autoRan = useRef(false);

  const run = useMutation({
    mutationFn: ({ url, tab }: { url: string; tab?: Tab }) => probeUrl(url, tab ? { tab } : {}),
    onSuccess: (result) => {
      if (result.handler !== "ytdlp") {
        setProbe(null);
        setError(t("notMedia"));
        return;
      }
      setProbe(result);
    },
    onError: (err) => setError(errorMessage(tErrors, err)),
  });

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    setError(null);
    const [url] = parseLinks(text);
    if (!url) {
      setError(t("needLink"));
      return;
    }
    setProbe(null);
    run.mutate({ url });
  };

  useEffect(() => {
    if (!autoRan.current && params.get("url")) {
      autoRan.current = true;
      submit();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once for ?url=
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t("title")}</h1>
        <p className="max-w-prose text-muted-foreground">{t("subtitle")}</p>
      </div>

      <form onSubmit={submit} className="flex flex-col gap-2" noValidate>
        <label htmlFor={inputId} className="text-sm font-medium">
          {t("linkLabel")}
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            id={inputId}
            type="url"
            inputMode="url"
            dir="ltr"
            value={text}
            onChange={(event) => {
              setText(event.target.value);
              setError(null);
            }}
            placeholder="https://www.youtube.com/watch?v=…"
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? `${inputId}-error` : undefined}
            className="h-11 w-full min-w-0 rounded-md border border-input bg-card px-3 text-base shadow-xs placeholder:text-muted-foreground"
            data-testid="media-input"
          />
          <Button type="submit" disabled={run.isPending}>
            {run.isPending ? (
              <Loader2Icon className="animate-spin" aria-hidden="true" />
            ) : (
              <SearchIcon aria-hidden="true" />
            )}
            {t("check")}
          </Button>
        </div>
        {error && (
          <p id={`${inputId}-error`} role="alert" className="text-sm font-medium text-destructive">
            {error}
          </p>
        )}
        <p className="text-sm text-muted-foreground">
          {t.rich("cookiesHint", {
            link: (chunks) => (
              <Link
                href="/connections"
                className="font-medium text-primary underline-offset-4 hover:underline"
              >
                {chunks}
              </Link>
            ),
          })}
        </p>
      </form>

      {run.isPending && !probe && (
        <div className="flex flex-col gap-3" aria-busy="true">
          <Skeleton className="h-40" />
          <Skeleton className="h-24" />
        </div>
      )}
      {probe && isVideo(probe.extra) && <VideoCard key={probe.normalized_url} probe={probe} />}
      {probe && isList(probe.extra) && (
        <PlaylistView
          key={`${probe.normalized_url}-${(probe.extra as { tab?: string }).tab ?? ""}`}
          probe={probe}
          loadingTab={run.isPending}
          onTab={(tab) => run.mutate({ url: probe.url, tab })}
        />
      )}
      <p className="text-sm text-muted-foreground">{t("legal")}</p>
    </div>
  );
}

export default YouTubeView;
