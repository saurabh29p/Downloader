"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DownloadIcon, Loader2Icon, SearchIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useId, useState, type FormEvent } from "react";

import { defaultFiles, FilePicker, galleryImages } from "@/components/files/file-picker";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { createJobs, probeUrl } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { hostOf } from "@/lib/links";
import { toast } from "@/lib/toast";
import { JOBS_KEY } from "@/lib/use-jobs";

/** Paste a code-host or gallery link, pick files, queue one job. Used by /code and /images. */
export function SourceView({ section }: { section: "Code" | "Images" }) {
  const t = useTranslations(section);
  const tFiles = useTranslations("Files");
  const tJobs = useTranslations("Jobs");
  const tErrors = useTranslations("Errors");
  const id = useId();
  const queryClient = useQueryClient();
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const probe = useMutation({
    mutationFn: (target: string) => probeUrl(target),
    onSuccess: (data) => setSelected(defaultFiles(data.choices)),
    onError: (err) => setError(errorMessage(tErrors, err)),
  });
  const queue = useMutation({
    mutationFn: () => createJobs([probe.data!.normalized_url], { files: [...selected] }),
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
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t("title")}</h1>
        <p className="max-w-prose text-muted-foreground">{t("subtitle")}</p>
      </div>
      <form onSubmit={submit} className="flex flex-col gap-2" noValidate>
        <label htmlFor={`${id}-url`} className="text-sm font-medium">
          {t("urlLabel")}
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            id={`${id}-url`}
            type="url"
            dir="ltr"
            inputMode="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder={t("placeholder")}
            aria-invalid={error ? true : undefined}
            aria-describedby={`${id}-hint`}
            className="h-11 w-full min-w-0 rounded-md border border-input bg-card px-3 text-base shadow-xs placeholder:text-muted-foreground"
            data-testid="source-url"
          />
          <Button type="submit" disabled={probe.isPending}>
            {probe.isPending ? (
              <Loader2Icon className="animate-spin" aria-hidden="true" />
            ) : (
              <SearchIcon aria-hidden="true" />
            )}
            {t("find")}
          </Button>
        </div>
        <p id={`${id}-hint`} className="text-sm text-muted-foreground">
          {t("hosts")}
        </p>
        {error && (
          <p role="alert" className="text-sm font-medium text-destructive">
            {error}
          </p>
        )}
      </form>

      {probe.isPending && <Skeleton className="h-48" aria-busy="true" />}
      {data && !probe.isPending && (
        <section className="flex flex-col gap-4" aria-labelledby={`${id}-title`}>
          <div className="flex flex-col gap-1">
            <h2 id={`${id}-title`} className="text-lg font-semibold break-words" dir="auto">
              {data.title}
            </h2>
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <Badge variant="secondary">{hostOf(data.normalized_url)}</Badge>
            </div>
          </div>
          <FilePicker
            choices={data.choices}
            selected={selected}
            onChange={setSelected}
            images={galleryImages(data)}
          />
          <Button
            className="self-start"
            onClick={() => queue.mutate()}
            disabled={queue.isPending || selected.size === 0}
          >
            {queue.isPending ? (
              <Loader2Icon className="animate-spin" aria-hidden="true" />
            ) : (
              <DownloadIcon aria-hidden="true" />
            )}
            {tFiles("download", { count: selected.size })}
          </Button>
        </section>
      )}
    </div>
  );
}

export default SourceView;
