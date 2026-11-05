"use client";

import type { ProbeResult } from "@anyget/shared";
import { useLocale, useTranslations } from "next-intl";

import { CheckRow } from "@/components/media/choice";
import { formatBytes, isolate } from "@/lib/format";
import { cn } from "@/lib/utils";

type Choice = ProbeResult["choices"][number];

export const defaultFiles = (choices: Choice[]) =>
  new Set(choices.filter((c) => c.default).map((c) => c.id));

/** Checkbox list (or image grid) of the files a probe found. */
export function FilePicker({
  choices,
  selected,
  onChange,
  images,
}: {
  choices: Choice[];
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
  /** id → image URL: shows a thumbnail grid instead of a list. */
  images?: Map<string, string>;
}) {
  const t = useTranslations("Files");
  const locale = useLocale();
  const size = choices.filter((c) => selected.has(c.id)).reduce((n, c) => n + (c.size ?? 0), 0);
  const toggle = (id: string, on: boolean) => {
    const next = new Set(selected);
    if (on) next.add(id);
    else next.delete(id);
    onChange(next);
  };

  return (
    <fieldset className="flex min-w-0 flex-col gap-2" data-testid="file-picker">
      <legend className="sr-only">{t("legend")}</legend>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        <span aria-live="polite" className="text-muted-foreground">
          {t("selected", { count: selected.size, total: choices.length })}
          {size > 0 && <> · {isolate(formatBytes(size, locale))}</>}
        </span>
        <button
          type="button"
          className="min-h-11 font-medium text-primary"
          onClick={() => onChange(new Set(choices.map((c) => c.id)))}
        >
          {t("all")}
        </button>
        <button
          type="button"
          className="min-h-11 font-medium text-primary"
          onClick={() => onChange(new Set())}
        >
          {t("none")}
        </button>
      </div>
      {images ? (
        <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
          {choices.map((c) => {
            const on = selected.has(c.id);
            return (
              <li key={c.id}>
                <label
                  className={cn(
                    "flex cursor-pointer flex-col gap-1 rounded-md border p-1 text-xs",
                    "has-[:focus-visible]:ring-[3px] has-[:focus-visible]:ring-ring/50",
                    on ? "border-primary" : "opacity-70",
                  )}
                  data-testid="file-choice"
                >
                  {images.get(c.id) ? (
                    // eslint-disable-next-line @next/next/no-img-element -- remote gallery images
                    <img
                      src={images.get(c.id)}
                      alt=""
                      loading="lazy"
                      referrerPolicy="no-referrer"
                      className="aspect-square w-full rounded bg-muted object-cover"
                    />
                  ) : (
                    <span className="aspect-square w-full rounded bg-muted" aria-hidden="true" />
                  )}
                  <span className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={(e) => toggle(c.id, e.target.checked)}
                      className="size-5 shrink-0 accent-primary"
                    />
                    <span className="truncate" dir="auto">
                      {c.label}
                    </span>
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
      ) : (
        <ul className="flex max-h-80 flex-col divide-y overflow-y-auto rounded-md border px-3">
          {choices.map((c) => (
            <li key={c.id} className="flex items-center gap-2" data-testid="file-choice">
              <div className="min-w-0 flex-1">
                <CheckRow checked={selected.has(c.id)} onChange={(on) => toggle(c.id, on)}>
                  <span className="break-all" dir="auto">
                    {c.label}
                  </span>
                </CheckRow>
              </div>
              <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                {c.size ? isolate(formatBytes(c.size, locale)) : t(`kinds.${kindKey(c.kind)}`)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </fieldset>
  );
}

const KINDS = ["page", "document", "image", "video", "audio", "archive", "file"] as const;
const kindKey = (kind: string) =>
  (KINDS as readonly string[]).includes(kind) ? (kind as (typeof KINDS)[number]) : "file";

/** Image URLs a gallery probe carries in `extra.items`. */
export function galleryImages(probe: ProbeResult): Map<string, string> | undefined {
  const items = (probe.extra as { items?: { index: number; url: string }[] }).items;
  if (probe.handler !== "gallery" || !items) return undefined;
  return new Map(items.map((i) => [String(i.index), i.url]));
}
