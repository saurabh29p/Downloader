"use client";

import type { ProbeResult } from "@anyget/shared";
import { DownloadIcon, ListVideoIcon, Loader2Icon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { FormatPicker } from "@/components/media/format-picker";
import { MediaMeta } from "@/components/media/media-meta";
import { Button, buttonVariants } from "@/components/ui/button";
import { SheetClose, SheetFooter } from "@/components/ui/sheet";
import { Link } from "@/i18n/navigation";
import { defaultSelection, isList, isVideo, toJobOptions } from "@/lib/media";

/** Inside the Home preview drawer: format picker for one video, or a hand-off for playlists. */
export function MediaPreview({
  probe,
  onDownload,
  pending,
}: {
  probe: ProbeResult;
  onDownload: (options: Record<string, unknown>) => void;
  pending: boolean;
}) {
  const t = useTranslations("Media");
  const tPreview = useTranslations("Preview");
  const extra = probe.extra;
  const [selection, setSelection] = useState(() =>
    defaultSelection(isVideo(extra) ? extra : undefined),
  );

  if (isList(extra)) {
    return (
      <>
        <p className="text-sm">{t("listInPreview", { count: extra.count })}</p>
        <SheetFooter>
          <SheetClose asChild>
            <Button variant="outline">{tPreview("cancel")}</Button>
          </SheetClose>
          <Link
            href={{ pathname: "/youtube", query: { url: probe.normalized_url } }}
            className={buttonVariants()}
          >
            <ListVideoIcon aria-hidden="true" />
            {t("chooseVideos")}
          </Link>
        </SheetFooter>
      </>
    );
  }
  if (!isVideo(extra)) return null;

  return (
    <>
      {probe.thumbnail && (
        // eslint-disable-next-line @next/next/no-img-element -- remote thumbnails
        <img
          src={probe.thumbnail}
          alt=""
          width={320}
          height={180}
          referrerPolicy="no-referrer"
          className="aspect-video w-full rounded-md bg-muted object-cover"
        />
      )}
      <MediaMeta
        uploader={extra.uploader}
        duration={extra.duration}
        uploadDate={extra.upload_date}
      />
      <FormatPicker value={selection} onChange={setSelection} extra={extra} />
      <SheetFooter>
        <SheetClose asChild>
          <Button variant="outline">{tPreview("cancel")}</Button>
        </SheetClose>
        <Button onClick={() => onDownload(toJobOptions(selection))} disabled={pending}>
          {pending ? (
            <Loader2Icon className="animate-spin" aria-hidden="true" />
          ) : (
            <DownloadIcon aria-hidden="true" />
          )}
          {selection.audioOnly ? t("downloadAudio") : t("downloadVideo")}
        </Button>
      </SheetFooter>
    </>
  );
}
