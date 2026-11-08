"use client";

import type { Job } from "@anyget/shared";
import { useQueryClient } from "@tanstack/react-query";
import {
  CircleXIcon,
  DownloadIcon,
  EyeIcon,
  PauseIcon,
  PlayIcon,
  RotateCwIcon,
  Trash2Icon,
} from "lucide-react";
import type { LibraryItem } from "@anyget/shared";
import { useState } from "react";
import { useTranslations } from "next-intl";
import dynamic from "next/dynamic";

import { JobItem } from "@/components/jobs/job-item";
import { Button, buttonVariants } from "@/components/ui/button";
import { deleteJob, fileUrl, jobAction, type JobAction } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { applyJobEvent, isActive, jobName } from "@/lib/jobs";
import { noteEvent } from "@/lib/jobs-sync";
import { playTrack } from "@/lib/player";
import { toast, withUndo } from "@/lib/toast";
import { JOBS_KEY } from "@/lib/use-jobs";

// Loaded only for finished files that can be converted (PDF, images, EPUB, audio, video).
const ConvertMenu = dynamic(() =>
  import("@/components/jobs/convert-menu").then((m) => m.ConvertMenu),
);
const CONVERTIBLE =
  /\.(pdf|jpe?g|png|tiff?|jp2|webp|epub|mp4|mkv|webm|mov|m4v|mp3|m4a|opus|ogg|flac|wav)$/i;
// The viewer loads only when a finished file is opened.
const Viewer = dynamic(() => import("@/components/viewer/viewer").then((m) => m.Viewer));
// Audio plays at once in the mini-player (from the tap itself, as phones require);
// these kinds open in the viewer (the server checks the real type).
const AUDIO = /\.(mp3|m4a|m4b|aac|opus|ogg|oga|flac|wav)$/i;
const VIEWABLE =
  /\.(mp4|webm|mkv|mov|m4v|ogv|pdf|epub|txt|md|srt|vtt|csv|json|html?|jpe?g|png|gif|webp|avif|svg|bmp)$/i;

/** A job with its controls: save, pause, resume, retry, cancel, remove. */
export function JobRow({ job }: { job: Job }) {
  const t = useTranslations("Jobs");
  const tErrors = useTranslations("Errors");
  const queryClient = useQueryClient();
  const name = jobName(job);

  // A plain async call (not useMutation): keeps Downloads under the JS budget.
  const [busy, setBusy] = useState(false);
  const act = async (kind: JobAction) => {
    setBusy(true);
    try {
      const updated = await jobAction(job.id, kind);
      queryClient.setQueryData<Job[]>(JOBS_KEY, (jobs) =>
        applyJobEvent(jobs, { type: "job.updated", job: updated }),
      );
    } catch (err) {
      toast.error(errorMessage(tErrors, err));
    }
    setBusy(false);
  };
  const [viewing, setViewing] = useState<LibraryItem | null>(null);
  const expired = job.note === "expired";
  const path = job.rel_path ?? "";

  async function open() {
    try {
      const { itemForJob } = await import("@/lib/api-viewer");
      setViewing(await itemForJob(job.id));
    } catch {
      toast.info(t("notInLibrary"));
    }
  }

  // Hidden at once; deleted when the Undo toast ends (the row is gone by then).
  function remove() {
    const at = queryClient.getQueryData<Job[]>(JOBS_KEY)?.findIndex((j) => j.id === job.id) ?? 0;
    const restore = () => {
      noteEvent({ type: "job.updated", job });
      queryClient.setQueryData<Job[]>(JOBS_KEY, (jobs = []) => {
        if (jobs.some((j) => j.id === job.id)) return jobs;
        const list = [...jobs];
        list.splice(Math.max(0, at), 0, job);
        return list;
      });
    };
    // Noted, so a list request already on its way can't bring the row back.
    noteEvent({ type: "job.deleted", job: { id: job.id } });
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
      onClick={() => (kind === "remove" ? remove() : void act(kind))}
    >
      <Icon aria-hidden="true" />
    </Button>
  );

  return (
    <>
      {viewing && <Viewer item={viewing} onClose={() => setViewing(null)} />}
      <JobItem
        job={job}
        actions={
          <>
            {job.state === "done" &&
              !expired &&
              (AUDIO.test(path) || VIEWABLE.test(path)) &&
              (() => {
                // Audio: play now, from this tap (phones need that). Others: the viewer.
                const audio = AUDIO.test(path);
                const label = t(audio ? "actions.play" : "actions.open");
                const Icon = audio ? PlayIcon : EyeIcon;
                return (
                  <Button
                    variant="outline"
                    size="sm"
                    aria-label={`${label}: ${name}`}
                    onClick={() =>
                      audio
                        ? playTrack({ id: `job-${job.id}`, title: name, src: fileUrl(job.id) })
                        : void open()
                    }
                  >
                    <Icon aria-hidden="true" />
                    <span className="hidden sm:inline">{label}</span>
                  </Button>
                );
              })()}
            {/* Retention removed the file: Retry downloads it again into this row. */}
            {expired && iconButton("retry", t("actions.downloadAgain"), RotateCwIcon)}
            {job.state === "done" && !expired && (
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
            {job.state === "done" && !expired && CONVERTIBLE.test(path) && (
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
    </>
  );
}
