"use client";

import { InboxIcon, RefreshCwIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";

import { JobRow } from "@/components/jobs/job-row";
import { useConnection } from "@/components/shell/job-events-bridge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/i18n/navigation";
import { matchesFilter, type JobFilter } from "@/lib/jobs";
import { useJobs } from "@/lib/use-jobs";
import { cn } from "@/lib/utils";

const FILTERS: JobFilter[] = ["all", "active", "done", "failed"];

export function DownloadsView() {
  const t = useTranslations("Downloads");
  const connection = useConnection();
  const { data, isPending, isError, refetch, isRefetching } = useJobs();
  const [filter, setFilter] = useState<JobFilter>("all");

  const counts = useMemo(
    () =>
      Object.fromEntries(
        FILTERS.map((f) => [f, data?.filter((job) => matchesFilter(job, f)).length ?? 0]),
      ) as Record<JobFilter, number>,
    [data],
  );
  const visible = data?.filter((job) => matchesFilter(job, filter)) ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t("title")}</h1>
          <p className="text-muted-foreground">{t("subtitle")}</p>
        </div>
        <p
          className="flex items-center gap-2 text-sm text-muted-foreground"
          data-testid="connection"
        >
          <span
            aria-hidden="true"
            className={cn(
              "size-2 rounded-full",
              connection === "live" ? "bg-success" : "animate-pulse bg-muted-foreground",
            )}
          />
          {connection === "live" ? t("live") : t("reconnecting")}
        </p>
      </div>

      <div role="group" aria-label={t("filtersLabel")} className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <Button
            key={f}
            variant={filter === f ? "default" : "outline"}
            size="sm"
            aria-pressed={filter === f}
            onClick={() => setFilter(f)}
          >
            {t(`filters.${f}`)}
            <span className="tabular-nums opacity-80">{counts[f]}</span>
          </Button>
        ))}
      </div>

      {isPending ? (
        <div className="flex flex-col gap-2" aria-busy="true">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      ) : isError ? (
        <div
          role="alert"
          className="flex flex-col items-center gap-3 rounded-lg border p-8 text-center"
        >
          <p>{t("loadError")}</p>
          <Button variant="outline" onClick={() => refetch()} disabled={isRefetching}>
            <RefreshCwIcon aria-hidden="true" />
            {t("retry")}
          </Button>
        </div>
      ) : visible.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed p-10 text-center">
          <InboxIcon className="size-8 text-muted-foreground" aria-hidden="true" />
          <p className="text-muted-foreground">{t(`empty.${filter}`)}</p>
          <Link href="/" className={buttonVariants({ variant: "outline" })}>
            {t("emptyAction")}
          </Link>
        </div>
      ) : (
        <ul className="flex flex-col gap-2" aria-label={t(`filters.${filter}`)}>
          {visible.map((job) => (
            <JobRow key={job.id} job={job} />
          ))}
        </ul>
      )}
    </div>
  );
}
