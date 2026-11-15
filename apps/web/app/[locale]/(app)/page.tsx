import { useTranslations } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { use } from "react";

import { LineArt } from "@/components/art/line-art";
import { FirstRunHint } from "@/components/home/first-run-hint";
import { RecentJobs } from "@/components/jobs/recent-jobs";
import { PasteBox } from "@/components/paste/paste-box";
import { SectionsGrid } from "@/components/sections/sections-grid";
import { Link } from "@/i18n/navigation";
import type { Locale } from "@/i18n/routing";
import { MAIN_SECTIONS } from "@/lib/sections";

// Server-rendered (no client JS): pages that aren't in the nav.
const SOURCES = [
  { href: "/books", key: "books" },
  { href: "/libraries", key: "libraries" },
  { href: "/archive", key: "archive" },
  { href: "/wayback", key: "wayback" },
  { href: "/code", key: "code" },
  { href: "/images", key: "images" },
] as const;

const TRY = ["a", "b", "c", "d", "e", "f"] as const;

export default function HomePage({ params }: { params: Promise<{ locale: Locale }> }) {
  const { locale } = use(params);
  setRequestLocale(locale);
  const t = useTranslations("Home");
  const tShell = useTranslations("Shell");

  return (
    <div className="flex flex-col gap-14">
      <section aria-labelledby="home-title" className="flex flex-col gap-6">
        <div className="flex items-end gap-6">
          <div className="flex flex-1 flex-col gap-3">
            <p className="call-number uppercase">{t("kicker")}</p>
            <h1
              id="home-title"
              className="text-4xl font-semibold tracking-tight text-balance sm:text-5xl"
            >
              {t("title")}
            </h1>
            <p className="max-w-prose text-lg text-muted-foreground">{t("subtitle")}</p>
          </div>
          <LineArt name="lamp" className="hidden size-28 shrink-0 text-signal-ink lg:block" />
        </div>
        <PasteBox />
        <FirstRunHint locale={locale} />
      </section>

      <section aria-labelledby="sections-heading" className="flex flex-col gap-4">
        <div className="flex items-baseline justify-between gap-3">
          <h2 id="sections-heading" className="text-2xl font-semibold">
            {t("sectionsHeading")}
          </h2>
          <Link href="/sections" className="text-sm font-medium text-primary hover:underline">
            {t("allSections")}
          </Link>
        </div>
        <SectionsGrid ids={MAIN_SECTIONS} headingId="sections-heading" />
      </section>

      <RecentJobs />

      <section aria-labelledby="try-heading" className="flex flex-col gap-3">
        <h2 id="try-heading" className="text-2xl font-semibold">
          {t("tryHeading")}
        </h2>
        <ul className="flex flex-wrap gap-2">
          {TRY.map((key) => (
            <li key={key}>
              <Link
                href={`/search?q=${encodeURIComponent(t(`try.${key}`))}`}
                className="inline-flex min-h-11 items-center rounded-full border bg-card px-4 text-sm hover:bg-accent"
                dir="auto"
              >
                {t(`try.${key}`)}
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <nav aria-labelledby="sources-heading" className="flex flex-col gap-3">
        <h2 id="sources-heading" className="text-2xl font-semibold">
          {t("sources")}
        </h2>
        <ul className="grid grid-cols-1 gap-x-6 sm:grid-cols-2 lg:grid-cols-3">
          {SOURCES.map(({ href, key }) => (
            <li key={href} className="border-b border-dashed">
              <Link href={href} className="flex min-h-11 flex-col py-2.5 hover:text-primary">
                <span className="font-medium">{t(`source.${key}.title`)}</span>
                <span className="text-sm text-muted-foreground">{t(`source.${key}.text`)}</span>
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      <p className="text-sm text-muted-foreground md:hidden">{tShell("legal")}</p>
    </div>
  );
}
