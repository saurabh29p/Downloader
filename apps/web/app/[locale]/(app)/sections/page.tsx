import type { Metadata } from "next";
import { useTranslations } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { use } from "react";

import { SectionsGrid } from "@/components/sections/sections-grid";
import type { Locale } from "@/i18n/routing";
import { MAIN_SECTIONS, MORE_SECTIONS } from "@/lib/sections";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: Locale }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Sections" });
  return { title: `${t("title")} · AnyGet` };
}

export default function SectionsPage({ params }: { params: Promise<{ locale: Locale }> }) {
  const { locale } = use(params);
  setRequestLocale(locale);
  const t = useTranslations("Sections");
  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t("title")}</h1>
        <p className="max-w-prose text-muted-foreground">{t("subtitle")}</p>
      </div>
      <SectionsGrid ids={MAIN_SECTIONS.filter((id) => id !== "more")} />
      <section className="flex flex-col gap-3" aria-labelledby="more-heading">
        <h2 id="more-heading" className="text-lg font-semibold">
          {t("more.title")}
        </h2>
        <SectionsGrid ids={MORE_SECTIONS} headingId="more-heading" />
      </section>
    </div>
  );
}
