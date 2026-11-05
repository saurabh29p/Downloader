"use client";

import type { ProbeResult } from "@anyget/shared";
import { DownloadIcon, Loader2Icon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { defaultFiles, FilePicker, galleryImages } from "@/components/files/file-picker";
import { Button } from "@/components/ui/button";
import { SheetClose, SheetFooter } from "@/components/ui/sheet";

/** Inside the Home preview drawer: pick which files of a repo, gallery or web page to save. */
export function FilesPreview({
  probe,
  onDownload,
  pending,
}: {
  probe: ProbeResult;
  onDownload: (options: Record<string, unknown>) => void;
  pending: boolean;
}) {
  const t = useTranslations("Files");
  const tPreview = useTranslations("Preview");
  const [selected, setSelected] = useState(() => defaultFiles(probe.choices));

  return (
    <>
      {probe.handler === "http" && <p className="text-sm">{t("webpageNote")}</p>}
      <FilePicker
        choices={probe.choices}
        selected={selected}
        onChange={setSelected}
        images={galleryImages(probe)}
      />
      <SheetFooter>
        <SheetClose asChild>
          <Button variant="outline">{tPreview("cancel")}</Button>
        </SheetClose>
        <Button
          onClick={() => onDownload({ files: [...selected] })}
          disabled={pending || selected.size === 0}
        >
          {pending ? (
            <Loader2Icon className="animate-spin" aria-hidden="true" />
          ) : (
            <DownloadIcon aria-hidden="true" />
          )}
          {t("download", { count: selected.size })}
        </Button>
      </SheetFooter>
    </>
  );
}
