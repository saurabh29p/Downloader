"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { SearchView } from "@/components/search/search-view";
import { Skeleton } from "@/components/ui/skeleton";
import { api, call } from "@/lib/api";
import type { SectionId } from "@/lib/sections";
import { cn } from "@/lib/utils";

const getSection = (id: string) =>
  call(api.GET("/api/sections/{section_id}", { params: { path: { section_id: id } } }));

/** A section: its pre-built searches, then the section-scoped search and results. */
export function SectionView({
  id,
  initialQuery,
  initialPreset,
}: {
  id: SectionId;
  initialQuery: string;
  initialPreset?: string;
}) {
  const t = useTranslations("Sections");
  const section = useQuery({ queryKey: ["section", id], queryFn: () => getSection(id) });
  // Each run gets a new key so the search view starts fresh.
  const [run, setRun] = useState({ key: 0, preset: initialPreset });
  const presets = section.data?.presets ?? [];

  return (
    <div className="flex flex-col gap-6">
      <section aria-labelledby="presets-heading" className="flex flex-col gap-3">
        <h2 id="presets-heading" className="text-lg font-semibold">
          {t("presetsTitle")}
        </h2>
        {section.isPending ? (
          <Skeleton className="h-24" aria-busy="true" />
        ) : (
          <ul className="flex flex-wrap gap-2" data-testid="presets">
            {presets.map((preset) => (
              <li key={preset.id}>
                <button
                  type="button"
                  onClick={() => setRun((r) => ({ key: r.key + 1, preset: preset.id }))}
                  aria-pressed={run.preset === preset.id}
                  className={cn(
                    "inline-flex min-h-11 items-center rounded-full border px-4 text-sm",
                    run.preset === preset.id
                      ? "border-primary bg-primary text-primary-foreground"
                      : "hover:bg-accent",
                  )}
                >
                  {t.has(`presets.${preset.id as "jfk"}`)
                    ? t(`presets.${preset.id as "jfk"}`)
                    : preset.query}
                </button>
              </li>
            ))}
          </ul>
        )}
        {section.data?.needs_key?.includes("tmdb") && (
          <p className="text-sm text-muted-foreground">{t("tmdbHint")}</p>
        )}
      </section>
      <SearchView
        key={run.key}
        initialQuery={run.preset ? "" : initialQuery}
        section={id}
        preset={run.preset}
        presetQuery={presets.find((p) => p.id === run.preset)?.query}
        links={section.data?.links ?? []}
      />
    </div>
  );
}

export default SectionView;
