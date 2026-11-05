import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { useTranslations } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { use } from "react";

import { SectionView } from "@/components/sections/section-view";
import { SectionsGrid } from "@/components/sections/sections-grid";
import { Link } from "@/i18n/navigation";
import { locales, type Locale } from "@/i18n/routing";
import { ALL_SECTIONS, isSection, MORE_SECTIONS } from "@/lib/sections";

const MORE_PAGES = ["archive", "wayback", "code", "images", "libraries"] as const;

export function generateStaticParams() {
  return locales.flatMap((locale) => ALL_SECTIONS.map((id) => ({ locale, id })));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: Locale; id: string }>;
}): Promise<Metadata> {
  const { locale, id } = await params;
  if (!isSection(id)) return {};
  const t = await getTranslations({ locale, namespace: "Sections" });
  return { title: `${t(`${id}.title`)} · AnyGet` };
}

export default function SectionPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: Locale; id: string }>;
  searchParams: Promise<{ q?: string; preset?: string }>;
}) {
  const { locale, id } = use(params);
  const { q, preset } = use(searchParams);
  if (!isSection(id)) notFound();
  setRequestLocale(locale);
  const t = useTranslations("Sections");
  const tHome = useTranslations("Home");
  return (
    <div className="flex flex-col gap-6" data-section={id}>
      <div className="flex flex-col gap-2">
        <Link href="/sections" className="self-start text-sm text-muted-foreground hover:underline">
          {t("back")}
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t(`${id}.title`)}</h1>
        <p className="max-w-prose text-muted-foreground">{t(`${id}.hero`)}</p>
      </div>
      {id === "more" ? (
        <>
          <SectionsGrid ids={MORE_SECTIONS} />
          <ul className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            {MORE_PAGES.map((page) => (
              <li key={page}>
                <Link
                  href={`/${page}`}
                  className="flex min-h-11 flex-col gap-1 rounded-lg border bg-card p-3 shadow-card hover:bg-accent"
                >
                  <span className="font-medium">{tHome(`source.${page}.title`)}</span>
                  <span className="text-sm text-muted-foreground">
                    {tHome(`source.${page}.text`)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <SectionView
          id={id}
          initialQuery={typeof q === "string" ? q.slice(0, 300) : ""}
          initialPreset={typeof preset === "string" ? preset.slice(0, 40) : undefined}
        />
      )}
    </div>
  );
}
