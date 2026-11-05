import type { Metadata } from "next";
import { useTranslations } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { use } from "react";

import type { Locale } from "@/i18n/routing";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: Locale }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Legal" });
  return { title: `${t("title")} · AnyGet` };
}

const RULES = ["personal", "drm", "shadow", "bypass", "copyright", "cookies", "etiquette"] as const;

/** The rules AnyGet follows (from CLAUDE.md). Server-rendered: no client JavaScript. */
export default function LegalPage({ params }: { params: Promise<{ locale: Locale }> }) {
  const { locale } = use(params);
  setRequestLocale(locale);
  const t = useTranslations("Legal");
  return (
    <article className="flex max-w-prose flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t("title")}</h1>
        <p className="text-muted-foreground">{t("intro")}</p>
      </div>
      <ul className="flex flex-col gap-4">
        {RULES.map((key) => (
          <li key={key} className="flex flex-col gap-1 rounded-lg border p-4">
            <h2 className="font-semibold">{t(`rules.${key}.title`)}</h2>
            <p>{t(`rules.${key}.text`)}</p>
          </li>
        ))}
      </ul>
      <p className="text-sm text-muted-foreground">{t("disclaimer")}</p>
    </article>
  );
}
