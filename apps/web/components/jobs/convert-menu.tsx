"use client";

import type { Job } from "@anyget/shared";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { WandSparklesIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { NativeSelect } from "@/components/ui/native-select";
import { getHealth } from "@/lib/api";
import { convertJob, type ConvertTarget } from "@/lib/api-convert";
import { errorMessage } from "@/lib/errors";
import { toast } from "@/lib/toast";
import { JOBS_KEY } from "@/lib/use-jobs";

const IMAGE = /\.(jpe?g|png|tiff?|jp2|webp)$/i;
const MEDIA = /\.(mp4|mkv|webm|mov|m4v|mp3|m4a|opus|ogg|flac|wav)$/i;

/** "Convert…" for a finished download: OCR, merge pages into a PDF, extract audio. */
export function ConvertMenu({ job, name }: { job: Job; name: string }) {
  const t = useTranslations("Convert");
  const tJobs = useTranslations("Jobs");
  const tErrors = useTranslations("Errors");
  const queryClient = useQueryClient();
  const health = useQuery({ queryKey: ["health"], queryFn: getHealth, staleTime: 60_000 });
  const [pending, setPending] = useState(false);
  const convert = async (to: ConvertTarget) => {
    setPending(true);
    try {
      await convertJob(job.id, to);
      void queryClient.invalidateQueries({ queryKey: JOBS_KEY });
      toast.success(tJobs("added", { count: 1 }));
    } catch (err) {
      toast.error(errorMessage(tErrors, err));
    }
    setPending(false);
  };
  const files = [job.rel_path ?? "", ...(job.files ?? [])];
  const tools = health.data?.components;
  const hasImages = files.some((f) => IMAGE.test(f));
  const hasPdf = files.some((f) => /\.pdf$/i.test(f));
  const options: ConvertTarget[] = [];
  if (tools?.ocrmypdf && (hasPdf || hasImages)) options.push("ocr");
  if (hasImages || (tools?.calibre && files.some((f) => /\.epub$/i.test(f)))) options.push("pdf");
  if (tools?.ffmpeg && files.some((f) => MEDIA.test(f))) options.push("mp3", "m4a");
  if (!options.length) return null;

  return (
    <NativeSelect
      value=""
      aria-label={`${t("label")}: ${name}`}
      title={t("label")}
      disabled={pending}
      icon={<WandSparklesIcon />}
      iconOnlyOnPhone
      onChange={(e) => {
        if (e.target.value) void convert(e.target.value as ConvertTarget);
      }}
    >
      <option value="">{t("label")}</option>
      {options.map((to) => (
        <option key={to} value={to}>
          {t(`to.${to}`)}
        </option>
      ))}
    </NativeSelect>
  );
}

export default ConvertMenu;
