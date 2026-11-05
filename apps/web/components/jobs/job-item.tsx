"use client";

import type { Job } from "@anyget/shared";
import { ShieldCheckIcon } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { Badge, type badgeVariants } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { errorMessage } from "@/lib/errors";
import { formatBytes, formatDuration, isolate } from "@/lib/format";
import { etaSeconds, isActive, jobName, progressPercent } from "@/lib/jobs";
import { hostOf } from "@/lib/links";
import type { VariantProps } from "class-variance-authority";

type BadgeVariant = VariantProps<typeof badgeVariants>["variant"];

const STATE_VARIANT: Record<Job["state"], BadgeVariant> = {
  queued: "secondary",
  probing: "secondary",
  downloading: "default",
  paused: "outline",
  done: "success",
  failed: "destructive",
  canceled: "outline",
};

const NOTES: ReadonlySet<string> = new Set<Note>([
  "merging",
  "extracting_audio",
  "remuxing",
  "embedding_subtitles",
  "converting_subtitles",
  "adding_metadata",
  "embedding_thumbnail",
  "converting_thumbnail",
  "already_downloaded",
  "outside_date_range",
]);

type Note =
  | "merging"
  | "extracting_audio"
  | "remuxing"
  | "embedding_subtitles"
  | "converting_subtitles"
  | "adding_metadata"
  | "embedding_thumbnail"
  | "converting_thumbnail"
  | "already_downloaded"
  | "outside_date_range";

/** One job as a list item: name, state, details, progress and errors. `actions` sit at the end. */
export function JobItem({ job, actions }: { job: Job; actions?: ReactNode }) {
  const t = useTranslations("Jobs");
  const locale = useLocale();
  const name = jobName(job);
  const percent = progressPercent(job);
  const eta = etaSeconds(job);
  const showProgress = isActive(job) || job.state === "paused";

  const sizeText =
    job.total != null
      ? t("progress", {
          done: isolate(formatBytes(job.downloaded, locale)),
          total: isolate(formatBytes(job.total, locale)),
        })
      : job.downloaded > 0
        ? formatBytes(job.downloaded, locale)
        : null;
  // The host is an LTR name; the rest are translated phrases that follow the page
  // direction (their numbers are isolated, so they stay in order in RTL).
  const details = [
    isolate(hostOf(job.url)),
    sizeText,
    job.state === "downloading" && job.speed
      ? isolate(t("speed", { speed: formatBytes(job.speed, locale) }))
      : null,
    job.state === "downloading" && eta != null
      ? t("eta", { time: isolate(formatDuration(eta)) })
      : null,
    job.note && NOTES.has(job.note) ? t(`notes.${job.note as Note}`) : null,
  ].filter(Boolean);

  return (
    <li
      className="flex flex-col gap-1.5 rounded-md border bg-card px-3 py-2.5 shadow-card"
      data-testid="job-row"
      data-state={job.state}
      data-name={name}
    >
      <div className="flex items-start gap-3">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <h3
              className="min-w-0 truncate text-sm font-medium sm:text-base"
              dir="auto"
              title={name}
            >
              {name}
            </h3>
            <Badge variant={STATE_VARIANT[job.state]}>{t(`states.${job.state}`)}</Badge>
            {job.checksum_ok && (
              <Badge variant="success">
                <ShieldCheckIcon aria-hidden="true" />
                {t("checksumOk")}
              </Badge>
            )}
          </div>
          <p className="call-number tabular-nums">
            {details.map((part, i) => (
              <span key={i}>
                {i > 0 && <span aria-hidden="true"> · </span>}
                {part}
              </span>
            ))}
          </p>
        </div>
        {actions && <div className="flex shrink-0 items-center gap-0.5">{actions}</div>}
      </div>

      {showProgress && (
        <Progress
          value={job.state === "queued" || job.state === "probing" ? null : percent}
          aria-label={t("progressLabel", { name })}
        />
      )}
      {job.state === "failed" && <FailedNote job={job} />}
    </li>
  );
}

function FailedNote({ job }: { job: Job }) {
  const t = useTranslations("Jobs");
  const tErrors = useTranslations("Errors");
  const locale = useLocale();
  // Codes with their own message hide the raw server text under "Details".
  const code = (job.error_code ?? "") as "network";
  const known = !!code && code !== ("upstream" as string) && tErrors.has(code);
  return (
    <div className="flex flex-col gap-1 text-sm" data-testid="job-error">
      <p className="text-destructive">
        {errorMessage(tErrors, job.error_code ?? "")}
        {job.error && !known && (
          <span className="text-muted-foreground">
            {" ("}
            <bdi>{job.error}</bdi>)
          </span>
        )}
      </p>
      {job.connect && (
        <a
          href={`/${locale}/connections#${job.connect}`}
          className="self-start font-medium text-primary underline underline-offset-4"
          data-testid="connect-site"
        >
          {t("connect", { site: job.connect_label ?? job.connect })}
        </a>
      )}
      {job.error && known && (
        <details className="text-muted-foreground">
          <summary className="cursor-pointer select-none">{t("details")}</summary>
          <bdi className="break-words">{job.error}</bdi>
        </details>
      )}
    </div>
  );
}
