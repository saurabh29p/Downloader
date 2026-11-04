"use client";

import { ArrowRightIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import { JobItem } from "@/components/jobs/job-item";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/i18n/navigation";
import { useJobs } from "@/lib/use-jobs";

export function RecentJobs() {
  const t = useTranslations("Home");
  const { data, isPending, isError } = useJobs();
  const recent = data?.slice(0, 5) ?? [];

  return (
    <section aria-labelledby="recent-heading" className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <h2 id="recent-heading" className="text-lg font-semibold">
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
        <div className="flex flex-col gap-2" aria-busy="true">
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
        </div>
      ) : isError ? null : recent.length === 0 ? (
        <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
          {t("noRecent")}
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {recent.map((job) => (
            <JobItem key={job.id} job={job} />
          ))}
        </ul>
      )}
    </section>
  );
}
