"use client";

import { ArrowRightIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/i18n/navigation";
import { hostOf } from "@/lib/links";
import { isActive, jobName, progressPercent } from "@/lib/jobs";
import { useJobs } from "@/lib/use-jobs";
import { cn } from "@/lib/utils";

/** Home's "Continue": the latest few downloads as small index cards (details live in Downloads). */
export function RecentJobs() {
  const t = useTranslations("Home");
  const tJobs = useTranslations("Jobs");
  const { data, isPending, isError } = useJobs();
  const recent = data?.slice(0, 4) ?? [];
  if (isError) return null;

  return (
    <section aria-labelledby="recent-heading" className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <h2 id="recent-heading" className="text-2xl font-semibold">
          {t("recent")}
        </h2>
        {recent.length > 0 && (
          <Link
            href="/downloads"
            className="inline-flex h-11 items-center gap-1 text-sm font-medium text-primary hover:underline"
          >
            {t("viewAll")}
            <ArrowRightIcon className="size-4" aria-hidden="true" data-flip-rtl />
          </Link>
        )}
      </div>
      {isPending ? (
        <div className="grid gap-3 sm:grid-cols-2" aria-busy="true">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      ) : recent.length === 0 ? (
        <p className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
          {t("noRecent")}
        </p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {recent.map((job) => {
            const name = jobName(job);
            const moving = isActive(job) || job.state === "paused";
            return (
              <li
                key={job.id}
                className="index-card gap-2 p-3 pb-5"
                data-testid="job-row"
                data-state={job.state}
                data-name={name}
              >
                <div className="index-card-head flex items-center gap-2 pb-1.5">
                  <span className="call-number min-w-0 truncate" dir="ltr">
                    {hostOf(job.url)}
                  </span>
                  <span
                    className={cn(
                      "ms-auto shrink-0 text-xs font-medium",
                      job.state === "done" && "text-success",
                      job.state === "failed" && "text-destructive",
                    )}
                  >
                    {tJobs(`states.${job.state}`)}
                  </span>
                </div>
                <p className="truncate font-medium" dir="auto" title={name}>
                  {name}
                </p>
                {moving && (
                  <Progress
                    value={
                      job.state === "queued" || job.state === "probing"
                        ? null
                        : progressPercent(job)
                    }
                    aria-label={tJobs("progressLabel", { name })}
                  />
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
