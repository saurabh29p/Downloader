import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";

import { LineArt } from "@/components/art/line-art";
import { Link } from "@/i18n/navigation";
import type { SectionId } from "@/lib/sections";

/** Server-rendered section cards, drawn as card-catalogue drawers (no client JS). */
export function SectionsGrid({
  ids,
  headingId,
}: {
  ids: readonly SectionId[];
  headingId?: string;
}) {
  const t = useTranslations("Sections");
  return (
    <ul
      className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
      aria-labelledby={headingId}
      data-testid="sections-grid"
    >
      {ids.map((id) => (
        <li key={id} style={{ "--tint": `var(--tint-${id})` } as CSSProperties}>
          <Link
            href={`/sections/${id}`}
            className="group relative flex h-full min-h-11 flex-col gap-3 overflow-hidden rounded-md border bg-card p-4 pt-5 shadow-card transition-transform duration-(--duration-normal) hover:-translate-y-0.5 hover:bg-accent"
          >
            <span aria-hidden="true" className="absolute inset-x-0 top-0 h-1.5 bg-(color:--tint)" />
            <span className="flex items-center gap-3">
              <LineArt name={id} className="size-10 shrink-0 text-(color:--tint)" />
              {id === "declassified" ? (
                <span className="stamp text-sm">{t(`${id}.title`)}</span>
              ) : (
                // The brass label holder of a catalogue drawer.
                <span className="rounded-sm border-2 border-(color:--tint)/40 bg-background px-2.5 py-0.5 font-serif text-lg font-semibold">
                  {t(`${id}.title`)}
                </span>
              )}
            </span>
            <span className="text-sm text-muted-foreground">{t(`${id}.text`)}</span>
            {/* The drawer's pull. */}
            <span
              aria-hidden="true"
              className="mx-auto mt-auto h-2 w-14 rounded-full border-2 border-(color:--tint)/50"
            />
          </Link>
        </li>
      ))}
    </ul>
  );
}
