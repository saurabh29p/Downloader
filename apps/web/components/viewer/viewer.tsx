"use client";

import type { LibraryItem } from "@anyget/shared";
import { useQuery } from "@tanstack/react-query";
import { DownloadIcon, ExternalLinkIcon, PlayIcon, XIcon } from "lucide-react";
import dynamic from "next/dynamic";
import { useLocale, useTranslations } from "next-intl";
import { Dialog } from "radix-ui";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { fileInfo, fileUrl, subtitleUrl, type FileInfo } from "@/lib/api-viewer";
import { errorMessage } from "@/lib/errors";
import { formatDuration } from "@/lib/format";
import { playTrack } from "@/lib/player";
import { trackOf } from "@/lib/track";
import { resumeFrom, savePosition } from "@/lib/positions";
import { signedOut } from "@/lib/signed-out";

import { EpubView } from "./epub-view";
import { ImageView } from "./image-view";
import { TextView } from "./text-view";

// pdf.js is big: it loads only when a PDF is opened.
const PdfView = dynamic(() => import("./pdf-view").then((m) => m.PdfView), {
  ssr: false,
  loading: () => <Skeleton className="h-full min-h-64" aria-busy="true" />,
});

/** Start an audio file in the app's mini-player (call from a click). */
export function playItem(item: LibraryItem) {
  playTrack(trackOf(item));
}

/**
 * Full-screen viewer for a saved file. Picks the reader from the file's real type
 * (/info): video, image (with the list for previous/next), PDF, EPUB, text; audio
 * goes to the mini-player; anything else gets a reason plus Download / Open.
 */
export function Viewer({
  item,
  images = [],
  onClose,
}: {
  item: LibraryItem;
  images?: LibraryItem[];
  onClose: () => void;
}) {
  const t = useTranslations("Viewer");
  const [current, setCurrent] = useState(item);
  // Opened from a button that may re-render: remember it and give focus back on close.
  const [returnTo] = useState(() =>
    typeof document === "undefined" ? null : (document.activeElement as HTMLElement | null),
  );
  const info = useQuery({
    queryKey: ["library", "info", current.id],
    queryFn: () => fileInfo(current.id),
    enabled: !current.expired,
  });

  return (
    <Dialog.Root open onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60" />
        <Dialog.Content
          className="fixed inset-0 z-50 flex flex-col bg-background outline-none md:inset-4 md:rounded-md md:border md:shadow-lg"
          data-testid="viewer"
          data-preview={info.data?.preview}
          aria-describedby={undefined}
          onCloseAutoFocus={(event) => {
            if (returnTo?.isConnected) {
              event.preventDefault();
              returnTo.focus();
            }
          }}
        >
          <header className="flex items-center gap-2 border-b px-3 py-2">
            <Dialog.Title
              className="min-w-0 flex-1 truncate font-serif text-lg font-semibold"
              dir="auto"
            >
              {current.title}
            </Dialog.Title>
            {!current.missing && (
              <>
                <a
                  href={fileUrl(current.id, true)}
                  className={buttonVariants({ variant: "ghost", size: "sm" })}
                  aria-label={t("download")}
                >
                  <DownloadIcon aria-hidden="true" />
                  <span className="hidden sm:inline">{t("download")}</span>
                </a>
                <a
                  href={fileUrl(current.id)}
                  target="_blank"
                  rel="noreferrer"
                  className={buttonVariants({ variant: "ghost", size: "sm" })}
                  aria-label={t("openTab")}
                >
                  <ExternalLinkIcon aria-hidden="true" />
                  <span className="hidden sm:inline">{t("openTab")}</span>
                </a>
              </>
            )}
            <Dialog.Close
              className="inline-flex size-11 items-center justify-center rounded-md hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
              aria-label={t("close")}
            >
              <XIcon className="size-5" aria-hidden="true" />
            </Dialog.Close>
          </header>
          <div className="min-h-0 flex-1 overflow-hidden">
            {current.expired ? (
              <Fallback reason="expired" item={current} />
            ) : info.isPending ? (
              <Skeleton className="m-4 h-64" aria-busy="true" />
            ) : info.isError ? (
              <InfoError error={info.error} retry={() => void info.refetch()} />
            ) : (
              <Body
                item={current}
                info={info.data}
                images={images}
                onImage={setCurrent}
                onClose={onClose}
              />
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export default Viewer;

function InfoError({ error, retry }: { error: unknown; retry: () => void }) {
  const t = useTranslations("Viewer");
  const tErrors = useTranslations("Errors");
  return (
    <div className="flex flex-col items-start gap-3 p-6" role="alert">
      <p>{errorMessage(tErrors, error)}</p>
      <Button variant="outline" onClick={retry}>
        {t("retry")}
      </Button>
    </div>
  );
}

function Body({
  item,
  info,
  images,
  onImage,
  onClose,
}: {
  item: LibraryItem;
  info: FileInfo;
  images: LibraryItem[];
  onImage: (item: LibraryItem) => void;
  onClose: () => void;
}) {
  const t = useTranslations("Viewer");
  switch (info.preview) {
    case "video":
      return <VideoView item={item} info={info} />;
    case "audio":
      return (
        <div className="flex flex-col items-center justify-center gap-4 p-8 text-center">
          <p className="text-muted-foreground">{t("audioHint")}</p>
          <Button
            variant="signal"
            onClick={() => {
              playItem(item);
              onClose();
            }}
          >
            <PlayIcon aria-hidden="true" />
            {t("playAudio")}
          </Button>
        </div>
      );
    case "image":
      return <ImageView item={item} images={images.length ? images : [item]} onChange={onImage} />;
    case "pdf":
      return <PdfView id={item.id} title={item.title} />;
    case "epub":
      return <EpubView id={item.id} />;
    case "text":
      return <TextView id={item.id} size={info.size} />;
    default:
      return <Fallback reason={info.reason ?? "unsupported_format"} item={item} mime={info.mime} />;
  }
}

/** No preview: say why, and offer Download / Open (never a broken player). */
export function Fallback({
  reason,
  item,
  mime,
  extra,
}: {
  reason: string;
  item: LibraryItem;
  mime?: string;
  extra?: ReactNode;
}) {
  const t = useTranslations("Viewer");
  const known = [
    "unsupported_format",
    "office",
    "archive",
    "too_large",
    "empty",
    "missing",
    "expired",
    "codec",
    "protected",
    "malformed",
  ];
  const key = (known.includes(reason) ? reason : "unsupported_format") as "office";
  return (
    <div
      className="flex flex-col items-start gap-3 p-6"
      data-testid="viewer-fallback"
      data-reason={reason}
    >
      <p className="max-w-prose">{t(`reasons.${key}`)}</p>
      {mime && <p className="call-number">{mime}</p>}
      {mime === "image/tiff" && <p className="text-sm text-muted-foreground">{t("convertHint")}</p>}
      {extra}
      {!item.missing && reason !== "missing" && reason !== "expired" && (
        <div className="flex flex-wrap gap-2">
          <a href={fileUrl(item.id, true)} className={buttonVariants({ variant: "outline" })}>
            <DownloadIcon aria-hidden="true" />
            {t("download")}
          </a>
          <a
            href={fileUrl(item.id)}
            target="_blank"
            rel="noreferrer"
            className={buttonVariants({ variant: "outline" })}
          >
            <ExternalLinkIcon aria-hidden="true" />
            {t("openTab")}
          </a>
        </div>
      )}
    </div>
  );
}

const SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2] as const;

function VideoView({ item, info }: { item: LibraryItem; info: FileInfo }) {
  const t = useTranslations("Viewer");
  const tPlayer = useTranslations("Player");
  const locale = useLocale();
  const ref = useRef<HTMLVideoElement>(null);
  const [speed, setSpeed] = useState(1);
  const [resumed, setResumed] = useState<number | null>(null);
  const [failed, setFailed] = useState<"codec" | "expired" | null>(null);
  const [tryAnyway, setTryAnyway] = useState(false);
  const [playable] = useState(
    () =>
      typeof document === "undefined" ||
      document.createElement("video").canPlayType(info.mime) !== "",
  );

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let last = 0;
    const save = () => {
      if (Date.now() - last < 5000 && !el.paused) return;
      last = Date.now();
      savePosition(item.id, el.currentTime, el.duration);
    };
    el.addEventListener("timeupdate", save);
    el.addEventListener("pause", save);
    return () => {
      save();
      el.removeEventListener("timeupdate", save);
      el.removeEventListener("pause", save);
    };
  }, [item.id, tryAnyway]);

  if (failed || (!playable && !tryAnyway)) {
    return (
      <Fallback
        reason={failed === "expired" ? "missing" : "codec"}
        item={item}
        mime={info.mime}
        extra={
          failed === "expired" ? (
            <a href={`/${locale}/login`} className="font-medium text-primary underline">
              {tPlayer("signInAgain")}
            </a>
          ) : !failed ? (
            <Button variant="outline" onClick={() => setTryAnyway(true)}>
              {t("tryAnyway")}
            </Button>
          ) : null
        }
      />
    );
  }

  return (
    <div className="flex h-full flex-col gap-2 p-2 sm:p-4">
      <video
        ref={ref}
        src={fileUrl(item.id)}
        controls
        playsInline
        preload="metadata"
        className="min-h-0 w-full flex-1 rounded bg-black"
        data-testid="viewer-video"
        onLoadedMetadata={(e) => {
          const el = e.currentTarget;
          const at = resumeFrom(item.id, el.duration);
          if (at != null) {
            el.currentTime = at;
            setResumed(at);
          }
        }}
        onError={() => void signedOut().then((out) => setFailed(out ? "expired" : "codec"))}
      >
        {info.subtitles.map((sub) => (
          <track
            key={sub.index}
            kind="subtitles"
            src={subtitleUrl(item.id, sub.index)}
            srcLang={sub.lang ?? undefined}
            label={sub.label}
          />
        ))}
      </video>
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2">
          {tPlayer("speed")}
          <select
            value={speed}
            onChange={(e) => {
              const value = Number(e.target.value);
              setSpeed(value);
              if (ref.current) ref.current.playbackRate = value;
            }}
            className="h-9 rounded-md border border-input bg-card px-2 font-mono text-xs"
          >
            {SPEEDS.map((s) => (
              <option key={s} value={s}>
                {s}×
              </option>
            ))}
          </select>
        </label>
        {info.subtitles.length > 0 && (
          <span className="text-muted-foreground">{t("subtitlesHint")}</span>
        )}
        {info.may_not_play && <span className="text-muted-foreground">{t("mayNotPlay")}</span>}
        {resumed != null && (
          <span role="status" className="flex items-center gap-2 text-muted-foreground">
            {tPlayer("resumed", { time: formatDuration(Math.floor(resumed)) })}
            <button
              type="button"
              className="font-medium text-primary underline underline-offset-2"
              onClick={() => {
                if (ref.current) ref.current.currentTime = 0;
                setResumed(null);
              }}
            >
              {tPlayer("startOver")}
            </button>
          </span>
        )}
      </div>
    </div>
  );
}
