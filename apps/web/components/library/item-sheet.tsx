"use client";

import type { LibraryItem } from "@anyget/shared";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  DownloadIcon,
  ExternalLinkIcon,
  EyeIcon,
  PlayIcon,
  RotateCwIcon,
  Trash2Icon,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useId, useState, type FormEvent } from "react";

import { CheckRow } from "@/components/media/choice";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  deleteLibraryItem,
  libraryFileUrl,
  redownload,
  updateLibraryItem,
} from "@/lib/api-library";
import { errorMessage } from "@/lib/errors";
import { formatBytes, isolate } from "@/lib/format";
import { playTrack } from "@/lib/player";
import { trackOf } from "@/lib/track";
import { toast } from "@/lib/toast";
import { JOBS_KEY } from "@/lib/use-jobs";

const LIBRARY_KEY = ["library"] as const;
const VIEWABLE = new Set(["video", "image", "pdf", "epub", "text"]);

/** One library file: a preview for its kind, tags, re-download and remove. */
export function ItemSheet({
  item,
  onClose,
  onOpen,
}: {
  item: LibraryItem;
  onClose: () => void;
  onOpen: (item: LibraryItem) => void;
}) {
  const t = useTranslations("Library");
  const tErrors = useTranslations("Errors");
  const tJobs = useTranslations("Jobs");
  const locale = useLocale();
  const id = useId();
  const queryClient = useQueryClient();
  const [tags, setTags] = useState((item.tags ?? []).join(", "));
  const [removeFile, setRemoveFile] = useState(false);
  const src = libraryFileUrl(item.id);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: LIBRARY_KEY });

  const save = useMutation({
    mutationFn: () =>
      updateLibraryItem(item.id, {
        tags: tags
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      }),
    onSuccess: () => {
      refresh();
      toast.success(t("saved"));
    },
    onError: (err) => toast.error(errorMessage(tErrors, err)),
  });
  const again = useMutation({
    mutationFn: () => redownload(item.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: JOBS_KEY });
      toast.success(tJobs("added", { count: 1 }));
    },
    onError: (err) => toast.error(errorMessage(tErrors, err)),
  });
  const remove = useMutation({
    mutationFn: () => deleteLibraryItem(item.id, removeFile),
    onSuccess: () => {
      refresh();
      toast.success(t("removed"));
      onClose();
    },
    onError: (err) => toast.error(errorMessage(tErrors, err)),
  });
  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };

  return (
    <Sheet open onOpenChange={(open) => !open && onClose()}>
      <SheetContent closeLabel={t("close")} data-testid="library-sheet" className="overflow-y-auto">
        <SheetHeader>
          <SheetTitle dir="auto" className="break-words">
            {item.title}
          </SheetTitle>
          <SheetDescription dir="ltr" className="text-start break-all">
            {item.rel_path} · {isolate(formatBytes(item.size, locale))}
          </SheetDescription>
        </SheetHeader>

        {item.expired ? (
          <p role="status" data-testid="expired-note">
            {t("expiredNote")}
          </p>
        ) : item.missing ? (
          <p role="alert">{t("missingNote")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            {item.thumbnail && (
              // eslint-disable-next-line @next/next/no-img-element -- local thumbnail
              <img
                src={item.thumbnail}
                alt=""
                className="max-h-56 w-full rounded bg-muted object-contain"
              />
            )}
            {item.kind === "audio" ? (
              <Button variant="signal" onClick={() => playTrack(trackOf(item))}>
                <PlayIcon aria-hidden="true" />
                {t("play")}
              </Button>
            ) : VIEWABLE.has(item.kind) ? (
              <Button variant="signal" onClick={() => onOpen(item)} data-testid="sheet-open">
                <EyeIcon aria-hidden="true" />
                {t("open")}
              </Button>
            ) : (
              <p className="text-sm text-muted-foreground">{t("noPreview")}</p>
            )}
          </div>
        )}

        <form onSubmit={onSubmit} className="flex flex-col gap-2">
          <label htmlFor={`${id}-tags`} className="text-sm font-medium">
            {t("tagsLabel")}
          </label>
          <div className="flex gap-2">
            <input
              id={`${id}-tags`}
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder={t("tagsPlaceholder")}
              dir="auto"
              className="h-11 w-full min-w-0 rounded-md border border-input bg-card px-3 text-base"
            />
            <Button type="submit" variant="outline" disabled={save.isPending}>
              {t("save")}
            </Button>
          </div>
        </form>

        <div className="flex flex-wrap gap-2">
          {!item.missing && (
            <>
              <a
                href={libraryFileUrl(item.id, true)}
                className={buttonVariants({ variant: "outline", size: "sm" })}
              >
                <DownloadIcon aria-hidden="true" />
                {t("saveFile")}
              </a>
              <a
                href={src}
                target="_blank"
                rel="noreferrer"
                className={buttonVariants({ variant: "outline", size: "sm" })}
              >
                <ExternalLinkIcon aria-hidden="true" />
                {t("openTab")}
              </a>
            </>
          )}
          {item.source_url && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => again.mutate()}
              disabled={again.isPending}
            >
              <RotateCwIcon aria-hidden="true" />
              {t("redownload")}
            </Button>
          )}
        </div>
        {item.source_url && (
          <p className="text-sm text-muted-foreground">
            {t("source")}{" "}
            <a
              href={item.source_url}
              target="_blank"
              rel="noreferrer"
              dir="ltr"
              className="break-all text-primary"
            >
              {item.source_url}
            </a>
          </p>
        )}

        <SheetFooter className="flex-col items-stretch gap-2 border-t pt-4">
          <CheckRow checked={removeFile} onChange={setRemoveFile}>
            {t("alsoDeleteFile")}
          </CheckRow>
          <Button variant="destructive" onClick={() => remove.mutate()} disabled={remove.isPending}>
            <Trash2Icon aria-hidden="true" />
            {t("remove")}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
