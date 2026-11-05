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
import dynamic from "next/dynamic";

import { JobItem } from "@/components/jobs/job-item";
import { Button, buttonVariants } from "@/components/ui/button";
import { deleteJob, fileUrl, jobAction, type JobAction } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { applyJobEvent, isActive, jobName } from "@/lib/jobs";
import { toast, withUndo } from "@/lib/toast";
import { JOBS_KEY } from "@/lib/use-jobs";

// Loaded only for finished files that can be converted (PDF, images, EPUB, audio, video).
const ConvertMenu = dynamic(() =>
  import("@/components/jobs/convert-menu").then((m) => m.ConvertMenu),
);
const CONVERTIBLE =
  /\.(pdf|jpe?g|png|tiff?|jp2|webp|epub|mp4|mkv|webm|mov|m4v|mp3|m4a|opus|ogg|flac|wav)$/i;

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
  const busy = action.isPending;

  // Hidden at once; deleted when the Undo toast ends (the row is gone by then).
  function remove() {
    const at = queryClient.getQueryData<Job[]>(JOBS_KEY)?.findIndex((j) => j.id === job.id) ?? 0;
    const restore = () =>
      queryClient.setQueryData<Job[]>(JOBS_KEY, (jobs = []) => {
        if (jobs.some((j) => j.id === job.id)) return jobs;
        const list = [...jobs];
        list.splice(Math.max(0, at), 0, job);
        return list;
      });
    queryClient.setQueryData<Job[]>(JOBS_KEY, (jobs) =>
      applyJobEvent(jobs, { type: "job.deleted", job: { id: job.id } }),
    );
    withUndo(
      t("removed", { name }),
      t("undo"),
      () =>
        deleteJob(job.id).catch((err: unknown) => {
          restore();
          toast.error(errorMessage(tErrors, err));
        }),
      restore,
    );
  }

  const iconButton = (kind: JobAction | "remove", label: string, Icon: typeof PauseIcon) => (
    <Button
      variant="ghost"
      size="icon"
      aria-label={`${label}: ${name}`}
      title={label}
      disabled={busy}
      onClick={() => (kind === "remove" ? remove() : action.mutate(kind))}
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
          {job.state === "done" && CONVERTIBLE.test(job.rel_path ?? "") && (
            <ConvertMenu job={job} name={name} />
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
