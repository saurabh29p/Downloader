"use client";

import type { LibraryItem } from "@anyget/shared";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DownloadIcon, ExternalLinkIcon, RotateCwIcon, Trash2Icon } from "lucide-react";
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  deleteLibraryItem,
  epubPreview,
  libraryFileUrl,
  redownload,
  updateLibraryItem,
} from "@/lib/api-library";
import { errorMessage } from "@/lib/errors";
import { formatBytes, isolate } from "@/lib/format";
import { toast } from "@/lib/toast";
import { JOBS_KEY } from "@/lib/use-jobs";

const LIBRARY_KEY = ["library"] as const;

/** One library file: a preview for its kind, tags, re-download and remove. */
export function ItemSheet({ item, onClose }: { item: LibraryItem; onClose: () => void }) {
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

        {item.missing ? (
          <p role="alert">{t("missingNote")}</p>
        ) : (
          <Preview kind={item.kind} src={src} id={item.id} title={item.title} />
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

function Preview({
  kind,
  src,
  id,
  title,
}: {
  kind: LibraryItem["kind"];
  src: string;
  id: string;
  title: string;
}) {
  const t = useTranslations("Library");
  if (kind === "video")
    return (
      <video
        src={src}
        controls
        preload="metadata"
        className="w-full rounded bg-black"
        data-testid="preview-video"
      />
    );
  if (kind === "audio")
    return (
      <audio src={src} controls preload="metadata" className="w-full" data-testid="preview-audio" />
    );
  if (kind === "image")
    return (
      // eslint-disable-next-line @next/next/no-img-element -- local files
      <img
        src={src}
        alt={title}
        className="max-h-96 w-full rounded bg-muted object-contain"
        data-testid="preview-image"
      />
    );
  if (kind === "pdf")
    return (
      <iframe
        src={src}
        title={title}
        className="h-96 w-full rounded border"
        data-testid="preview-pdf"
      />
    );
  if (kind === "epub") return <EpubText id={id} />;
  return <p className="text-sm text-muted-foreground">{t("noPreview")}</p>;
}

function EpubText({ id }: { id: string }) {
  const t = useTranslations("Library");
  const tErrors = useTranslations("Errors");
  const preview = useQuery({ queryKey: ["library", "epub", id], queryFn: () => epubPreview(id) });
  if (preview.isPending) return <Skeleton className="h-48" aria-busy="true" />;
  if (preview.isError) return <p role="alert">{errorMessage(tErrors, preview.error)}</p>;
  return (
    <div
      className="max-h-96 overflow-y-auto rounded border p-3 text-sm whitespace-pre-line"
      dir="auto"
      tabIndex={0}
      aria-label={t("epubPreview")}
      data-testid="preview-epub"
    >
      {preview.data.text || t("noPreview")}
      {preview.data.truncated && <p className="mt-2 text-muted-foreground">{t("truncated")}</p>}
    </div>
  );
}
