"use client";

import type { Job } from "@anyget/shared";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CircleXIcon,
  DownloadIcon,
  PauseIcon,
  PlayIcon,
  RotateCwIcon,
  Trash2Icon,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { JobItem } from "@/components/jobs/job-item";
import { Button, buttonVariants } from "@/components/ui/button";
import { deleteJob, fileUrl, jobAction, type JobAction } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { applyJobEvent, isActive, jobName } from "@/lib/jobs";
import { toast } from "@/lib/toast";
import { JOBS_KEY } from "@/lib/use-jobs";

/** A job with its controls: save, pause, resume, retry, cancel, remove. */
export function JobRow({ job }: { job: Job }) {
  const t = useTranslations("Jobs");
  const tErrors = useTranslations("Errors");
  const queryClient = useQueryClient();
  const name = jobName(job);

  const action = useMutation({
    mutationFn: (kind: JobAction) => jobAction(job.id, kind),
    onSuccess: (updated) =>
      queryClient.setQueryData<Job[]>(JOBS_KEY, (jobs) =>
        applyJobEvent(jobs, { type: "job.updated", job: updated }),
      ),
    onError: (err) => toast.error(errorMessage(tErrors, err)),
  });
  const remove = useMutation({
    mutationFn: () => deleteJob(job.id),
    onSuccess: () =>
      queryClient.setQueryData<Job[]>(JOBS_KEY, (jobs) =>
        applyJobEvent(jobs, { type: "job.deleted", job: { id: job.id } }),
      ),
    onError: (err) => toast.error(errorMessage(tErrors, err)),
  });
  const busy = action.isPending || remove.isPending;

  const iconButton = (kind: JobAction | "remove", label: string, Icon: typeof PauseIcon) => (
    <Button
      variant="ghost"
      size="icon"
      aria-label={`${label}: ${name}`}
      title={label}
      disabled={busy}
      onClick={() => (kind === "remove" ? remove.mutate() : action.mutate(kind))}
    >
      <Icon aria-hidden="true" />
    </Button>
  );

  return (
    <JobItem
      job={job}
      actions={
        <>
          {job.state === "done" && (
            <a
              href={fileUrl(job.id)}
              download
              aria-label={`${t("actions.save")}: ${name}`}
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              <DownloadIcon aria-hidden="true" />
              <span className="hidden sm:inline">{t("actions.save")}</span>
            </a>
          )}
          {isActive(job) && iconButton("pause", t("actions.pause"), PauseIcon)}
          {job.state === "paused" && iconButton("resume", t("actions.resume"), PlayIcon)}
          {(job.state === "failed" || job.state === "canceled") &&
            iconButton("retry", t("actions.retry"), RotateCwIcon)}
          {(isActive(job) || job.state === "paused") &&
            iconButton("cancel", t("actions.cancel"), CircleXIcon)}
          {!isActive(job) && iconButton("remove", t("actions.remove"), Trash2Icon)}
        </>
      }
    />
  );
}
