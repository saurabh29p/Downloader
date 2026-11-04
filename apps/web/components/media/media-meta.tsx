import { useLocale, useTranslations } from "next-intl";

import { formatDuration, isolate } from "@/lib/format";
import { parseUploadDate } from "@/lib/media";

/** "Blender · 10:35 · 11 Apr 2014", localized. */
export function MediaMeta({
  uploader,
  duration,
  uploadDate,
}: {
  uploader?: string | null;
  duration?: number | null;
  uploadDate?: string | null;
}) {
  const locale = useLocale();
  const t = useTranslations("Media");
  const date = parseUploadDate(uploadDate);
  const parts = [
    uploader,
    duration ? t("duration", { time: isolate(formatDuration(Math.round(duration))) }) : null,
    date
      ? new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: "UTC" }).format(date)
      : null,
  ].filter(Boolean);
  return (
    <p className="text-sm text-muted-foreground">
      {parts.map((part, i) => (
        <span key={i}>
          {i > 0 && <span aria-hidden="true"> · </span>}
          {part}
        </span>
      ))}
    </p>
  );
}
