import type { Metadata } from "next";
import { useTranslations } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { use } from "react";

import { Link } from "@/i18n/navigation";
import type { Locale } from "@/i18n/routing";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: Locale }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Help" });
  return { title: `${t("title")} · AnyGet` };
}

const SECTIONS = ["paste", "sources", "library", "watch", "convert", "cli", "remote"] as const;
const KEYS = ["palette", "submit", "close"] as const;

/** How to use AnyGet. Server-rendered: no client JavaScript. */
export default function HelpPage({ params }: { params: Promise<{ locale: Locale }> }) {
  const { locale } = use(params);
  setRequestLocale(locale);
  const t = useTranslations("Help");
  return (
    <article className="flex max-w-prose flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t("title")}</h1>
        <p className="text-muted-foreground">{t("intro")}</p>
      </div>
      {SECTIONS.map((key) => (
        <section key={key} className="flex flex-col gap-2" aria-labelledby={`help-${key}`}>
          <h2 id={`help-${key}`} className="text-lg font-semibold">
            {t(`sections.${key}.title`)}
          </h2>
          <p>{t(`sections.${key}.text`)}</p>
        </section>
      ))}
      <section className="flex flex-col gap-2" aria-labelledby="help-keys">
        <h2 id="help-keys" className="text-lg font-semibold">
          {t("keysTitle")}
        </h2>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
          {KEYS.map((key) => (
            <div key={key} className="contents">
              <dt>
                <kbd dir="ltr" className="rounded border bg-muted px-1.5 py-0.5 font-mono text-sm">
                  {t(`keys.${key}.combo`)}
                </kbd>
              </dt>
              <dd>{t(`keys.${key}.text`)}</dd>
            </div>
          ))}
        </dl>
      </section>
      <p>
        <Link href="/legal" className="font-medium text-primary underline-offset-4 hover:underline">
          {t("legalLink")}
        </Link>
      </p>
    </article>
  );
}
