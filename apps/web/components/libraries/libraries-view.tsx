"use client";

import type { Library, ProbeResult } from "@anyget/shared";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  DownloadIcon,
  ExternalLinkIcon,
  KeyRoundIcon,
  Loader2Icon,
  SearchIcon,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useId, useState, type FormEvent } from "react";

import { defaultFiles, FilePicker, galleryImages } from "@/components/files/file-picker";
import { CheckRow, ChoicePill } from "@/components/media/choice";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { createJobs, probeUrl } from "@/lib/api";
import { listLibraries } from "@/lib/api-books";
import { errorMessage } from "@/lib/errors";
import { toast } from "@/lib/toast";
import { JOBS_KEY } from "@/lib/use-jobs";

type Region = "global" | "europe" | "asia" | "oceania" | "middle_east_africa" | "americas";

/** Worldwide libraries by region, plus "paste an item link" for IIIF page downloads. */
export function LibrariesView() {
  const t = useTranslations("Libraries");
  const tErrors = useTranslations("Errors");
  const id = useId();
  const list = useQuery({ queryKey: ["libraries"], queryFn: listLibraries, staleTime: Infinity });
  const [region, setRegion] = useState<Region>("global");

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t("title")}</h1>
        <p className="max-w-prose text-muted-foreground">{t("subtitle")}</p>
      </div>
      <ItemLink />
      <section className="flex flex-col gap-4" aria-labelledby={`${id}-regions`}>
        <h2 id={`${id}-regions`} className="text-lg font-semibold">
          {t("byRegion")}
        </h2>
        <div role="radiogroup" aria-label={t("region")} className="flex flex-wrap gap-2">
          {(list.data?.regions ?? ["global"]).map((r) => (
            <ChoicePill
              key={r}
              name={`${id}-region`}
              value={r}
              checked={region === r}
              onChange={() => setRegion(r as Region)}
            >
              {t(`regions.${r as Region}`)}
            </ChoicePill>
          ))}
        </div>
        {list.isPending && <Skeleton className="h-48" aria-busy="true" />}
        {list.isError && (
          <div className="flex flex-col gap-2">
            <p role="alert">{errorMessage(tErrors, list.error)}</p>
            <Button variant="outline" className="self-start" onClick={() => list.refetch()}>
              {t("retry")}
            </Button>
          </div>
        )}
        <ul className="grid gap-3 sm:grid-cols-2" data-testid="library-list">
          {(list.data?.libraries ?? [])
            .filter((lib) => lib.region === region)
            .map((lib) => (
              <LibraryCard key={lib.id} library={lib} />
            ))}
        </ul>
      </section>
    </div>
  );
}

function LibraryCard({ library }: { library: Library }) {
  const t = useTranslations("Libraries");
  return (
    <li
      className="flex flex-col gap-2 rounded-lg border bg-card p-4 shadow-card"
      data-testid="library"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold" dir="auto">
          {library.name}
        </h3>
        <Badge variant="outline">{library.country}</Badge>
      </div>
      <div className="flex flex-wrap gap-2">
        {library.access.map((a) => (
          <Badge key={a} variant="secondary">
            {t(`access.${a}`)}
          </Badge>
        ))}
      </div>
      {library.key_configured === false && (
        <p className="flex items-center gap-1 text-sm text-muted-foreground">
          <KeyRoundIcon className="size-4" aria-hidden="true" />
          {t("needsKey", { env: `ANYGET_${(library.key_setting ?? "").toUpperCase()}` })}
        </p>
      )}
      <a
        href={library.homepage}
        target="_blank"
        rel="noreferrer"
        className="inline-flex min-h-11 items-center gap-1 self-start text-sm font-medium text-primary"
      >
        {t("visit")}
        <ExternalLinkIcon className="size-4" aria-hidden="true" />
      </a>
    </li>
  );
}

/** Paste a library item link (IIIF): pick pages, optionally merge them into one PDF. */
function ItemLink() {
  const t = useTranslations("Libraries");
  const tFiles = useTranslations("Files");
  const tJobs = useTranslations("Jobs");
  const tErrors = useTranslations("Errors");
  const id = useId();
  const queryClient = useQueryClient();
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [pdf, setPdf] = useState(true);
  const probe = useMutation({
    mutationFn: (target: string) => probeUrl(target),
    onSuccess: (data: ProbeResult) => setSelected(defaultFiles(data.choices)),
    onError: (err) => setError(errorMessage(tErrors, err)),
  });
  const queue = useMutation({
    mutationFn: () =>
      createJobs([probe.data!.normalized_url], {
        files: [...selected],
        ...(probe.data!.handler === "iiif_library" ? { pdf } : {}),
      }),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: JOBS_KEY });
      if (result.jobs.length) toast.success(tJobs("added", { count: result.jobs.length }));
    },
    onError: (err) => toast.error(errorMessage(tErrors, err)),
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!url.trim()) {
      setError(t("needUrl"));
      return;
    }
    probe.mutate(url.trim());
  };
  const data = probe.data;
  const images = data ? galleryImages(data) : undefined;

  return (
    <section className="flex flex-col gap-3" aria-labelledby={`${id}-item`}>
      <form onSubmit={submit} className="flex flex-col gap-2" noValidate>
        <label id={`${id}-item`} htmlFor={`${id}-url`} className="text-sm font-medium">
          {t("itemLabel")}
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            id={`${id}-url`}
            type="url"
            dir="ltr"
            inputMode="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://gallica.bnf.fr/ark:/12148/…"
            aria-invalid={error ? true : undefined}
            aria-describedby={`${id}-hint`}
            className="h-11 w-full min-w-0 rounded-md border border-input bg-card px-3 text-base shadow-xs placeholder:text-muted-foreground"
            data-testid="library-item-url"
          />
          <Button type="submit" disabled={probe.isPending}>
            {probe.isPending ? (
              <Loader2Icon className="animate-spin" aria-hidden="true" />
            ) : (
              <SearchIcon aria-hidden="true" />
            )}
            {t("findPages")}
          </Button>
        </div>
        <p id={`${id}-hint`} className="text-sm text-muted-foreground">
          {t("itemHint")}
        </p>
        {error && (
          <p role="alert" className="text-sm font-medium text-destructive">
            {error}
          </p>
        )}
      </form>
      {probe.isPending && <Skeleton className="h-40" aria-busy="true" />}
      {data && !probe.isPending && (
        <div className="flex flex-col gap-3">
          <h2 className="font-semibold break-words" dir="auto">
            {data.title}
          </h2>
          {data.choices.length > 0 && (
            <FilePicker
              choices={data.choices}
              selected={selected}
              onChange={setSelected}
              images={images}
            />
          )}
          {data.handler === "iiif_library" && (
            <CheckRow checked={pdf} onChange={setPdf}>
              {t("mergePdf")}
            </CheckRow>
          )}
          <Button
            className="self-start"
            onClick={() => queue.mutate()}
            disabled={queue.isPending || (data.choices.length > 0 && selected.size === 0)}
          >
            {queue.isPending ? (
              <Loader2Icon className="animate-spin" aria-hidden="true" />
            ) : (
              <DownloadIcon aria-hidden="true" />
            )}
            {data.choices.length > 0 ? tFiles("download", { count: selected.size }) : t("download")}
          </Button>
        </div>
      )}
    </section>
  );
}

export default LibrariesView;
