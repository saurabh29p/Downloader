"use client";

import type { ProbeResult } from "@anyget/shared";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DownloadIcon, Loader2Icon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { FormatPicker } from "@/components/media/format-picker";
import { MediaMeta } from "@/components/media/media-meta";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { createJobs } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { defaultSelection, toJobOptions, type VideoExtra } from "@/lib/media";
import { toast } from "@/lib/toast";
import { JOBS_KEY } from "@/lib/use-jobs";
import { cn } from "@/lib/utils";

/** One video: thumbnail, details, format picker and Download. */
export function VideoCard({ probe }: { probe: ProbeResult }) {
  const t = useTranslations("Media");
  const tJobs = useTranslations("Jobs");
  const tErrors = useTranslations("Errors");
  const queryClient = useQueryClient();
  const extra = probe.extra as VideoExtra;
  const [selection, setSelection] = useState(() => defaultSelection(extra));

  const queue = useMutation({
    mutationFn: () => createJobs([probe.normalized_url], toJobOptions(selection)),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: JOBS_KEY });
      if (result.jobs.length) toast.success(tJobs("added", { count: result.jobs.length }));
    },
    onError: (err) => toast.error(errorMessage(tErrors, err)),
  });

  return (
    <article
      className="flex flex-col gap-5 rounded-lg border bg-card p-4 shadow-card sm:p-5"
      data-testid="video-card"
    >
      <div className="flex flex-col gap-4 sm:flex-row">
        {probe.thumbnail && (
          // eslint-disable-next-line @next/next/no-img-element -- remote thumbnails, no optimizer
          <img
            src={probe.thumbnail}
            alt=""
            width={extra.is_short ? 180 : 320}
            height={extra.is_short ? 320 : 180}
            loading="lazy"
            referrerPolicy="no-referrer"
            className={cn(
              "shrink-0 rounded-md bg-muted object-cover",
              extra.is_short ? "aspect-[9/16] w-32" : "aspect-video w-full sm:w-64",
            )}
          />
        )}
        <div className="flex min-w-0 flex-col gap-2">
          <div className="flex flex-wrap gap-2">
            <Badge variant="secondary">{extra.extractor}</Badge>
            {extra.is_short && <Badge variant="outline">{t("short")}</Badge>}
            {extra.saved && <Badge variant="success">{t("savedBefore")}</Badge>}
          </div>
          <h2 className="text-lg font-semibold break-words" dir="auto">
            {probe.title}
          </h2>
          <MediaMeta
            uploader={extra.uploader}
            duration={extra.duration}
            uploadDate={extra.upload_date}
          />
        </div>
      </div>

      <FormatPicker value={selection} onChange={setSelection} extra={extra} />

      <Button onClick={() => queue.mutate()} disabled={queue.isPending} className="sm:self-end">
        {queue.isPending ? (
          <Loader2Icon className="animate-spin" aria-hidden="true" />
        ) : (
          <DownloadIcon aria-hidden="true" />
        )}
        {selection.audioOnly ? t("downloadAudio") : t("downloadVideo")}
      </Button>
    </article>
  );
}
