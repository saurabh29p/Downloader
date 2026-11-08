"use client";

import type { LibraryItem } from "@anyget/shared";
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  ExpandIcon,
  MaximizeIcon,
  ZoomInIcon,
  ZoomOutIcon,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { fileUrl } from "@/lib/api-viewer";

const STEPS = [0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4, 6, 8];

/**
 * Pictures in a list: zoom, fit, actual size, fullscreen, previous/next. Keys: ←/→
 * (or Page Up/Down), + / −, 0 = fit, 1 = actual size, F = fullscreen. Images are
 * shown with <img>, so an SVG can never run scripts on the page.
 */
export function ImageView({
  item,
  images,
  onChange,
}: {
  item: LibraryItem;
  images: LibraryItem[];
  onChange: (item: LibraryItem) => void;
}) {
  const t = useTranslations("Viewer");
  const box = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState<number | null>(null); // null = fit to screen
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);
  const [broken, setBroken] = useState(false);
  const index = Math.max(
    0,
    images.findIndex((i) => i.id === item.id),
  );
  const count = images.length;

  const go = (by: number) => {
    if (count < 2) return;
    const next = images[(index + by + count) % count]!;
    setScale(null);
    setNatural(null);
    setBroken(false);
    onChange(next);
  };
  const zoom = (dir: 1 | -1) => {
    const now = scale ?? fitScale();
    const next =
      dir > 0
        ? STEPS.find((s) => s > now + 0.01)
        : [...STEPS].reverse().find((s) => s < now - 0.01);
    setScale(next ?? now);
  };
  const fitScale = () => {
    const el = box.current;
    if (!el || !natural) return 1;
    return Math.min(el.clientWidth / natural.w, el.clientHeight / natural.h, 1);
  };
  const fullscreen = () => {
    const el = box.current;
    if (!el) return;
    if (document.fullscreenElement) void document.exitFullscreen();
    else void el.requestFullscreen?.().catch(() => undefined);
  };

  useEffect(() => box.current?.focus(), []);

  const onKey = (event: KeyboardEvent) => {
    const actions: Record<string, () => void> = {
      ArrowRight: () => go(1),
      ArrowLeft: () => go(-1),
      PageDown: () => go(1),
      PageUp: () => go(-1),
      "+": () => zoom(1),
      "=": () => zoom(1),
      "-": () => zoom(-1),
      "0": () => setScale(null),
      "1": () => setScale(1),
      f: fullscreen,
    };
    // RTL: the arrows keep their visual meaning (→ is "next" on screen).
    const action = actions[event.key];
    if (action) {
      event.preventDefault();
      action();
    }
  };

  const tool =
    "inline-flex size-11 items-center justify-center rounded-md hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none disabled:opacity-40";

  return (
    <div className="flex h-full flex-col">
      <div
        className="flex flex-wrap items-center gap-1 border-b px-2 py-1"
        role="toolbar"
        aria-label={t("imageTools")}
      >
        <button
          type="button"
          className={tool}
          onClick={() => go(-1)}
          disabled={count < 2}
          aria-label={t("previous")}
        >
          <ChevronLeftIcon className="size-5" aria-hidden="true" data-flip-rtl />
        </button>
        <span className="call-number tabular-nums" aria-live="polite" data-testid="image-position">
          {index + 1} / {count}
        </span>
        <button
          type="button"
          className={tool}
          onClick={() => go(1)}
          disabled={count < 2}
          aria-label={t("next")}
        >
          <ChevronRightIcon className="size-5" aria-hidden="true" data-flip-rtl />
        </button>
        <span className="mx-1 h-6 w-px bg-border" aria-hidden="true" />
        <button type="button" className={tool} onClick={() => zoom(-1)} aria-label={t("zoomOut")}>
          <ZoomOutIcon className="size-5" aria-hidden="true" />
        </button>
        <span className="call-number w-12 text-center tabular-nums" data-testid="image-zoom">
          {scale == null ? t("fit") : `${Math.round(scale * 100)}%`}
        </span>
        <button type="button" className={tool} onClick={() => zoom(1)} aria-label={t("zoomIn")}>
          <ZoomInIcon className="size-5" aria-hidden="true" />
        </button>
        <button
          type="button"
          className={tool}
          onClick={() => setScale(null)}
          aria-label={t("fitScreen")}
        >
          <ExpandIcon className="size-5" aria-hidden="true" />
        </button>
        <button type="button" className={tool} onClick={fullscreen} aria-label={t("fullscreen")}>
          <MaximizeIcon className="size-5" aria-hidden="true" />
        </button>
      </div>
      <div
        ref={box}
        tabIndex={0}
        onKeyDown={onKey}
        aria-label={t("imageArea", { title: item.title })}
        className="relative flex min-h-0 flex-1 overflow-auto bg-muted outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
        role="region"
        data-testid="image-area"
      >
        {broken ? (
          <p className="m-auto p-6 text-center">{t("reasons.unsupported_format")}</p>
        ) : (
          // eslint-disable-next-line @next/next/no-img-element -- a saved file, any size
          <img
            key={item.id}
            src={fileUrl(item.id)}
            alt={item.title}
            onLoad={(e) =>
              setNatural({
                w: e.currentTarget.naturalWidth || 1,
                h: e.currentTarget.naturalHeight || 1,
              })
            }
            onError={() => setBroken(true)}
            draggable={false}
            className={
              scale == null ? "m-auto max-h-full max-w-full object-contain" : "m-auto max-w-none"
            }
            style={
              scale == null || !natural
                ? undefined
                : { width: natural.w * scale, height: natural.h * scale }
            }
            data-testid="viewer-image"
          />
        )}
      </div>
    </div>
  );
}
