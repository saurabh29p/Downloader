import { useTranslations } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { use } from "react";

import { ApiStatus } from "@/components/api-status";
import { RecentJobs } from "@/components/jobs/recent-jobs";
import { PasteBox } from "@/components/paste/paste-box";
import { SectionsGrid } from "@/components/sections/sections-grid";
import { Link } from "@/i18n/navigation";
import type { Locale } from "@/i18n/routing";
import { MAIN_SECTIONS } from "@/lib/sections";

const SOURCES = [
  { href: "/search", key: "search" },
  { href: "/books", key: "books" },
  { href: "/libraries", key: "libraries" },
  { href: "/library", key: "library" },
  { href: "/watch", key: "watch" },
  { href: "/youtube", key: "youtube" },
  { href: "/archive", key: "archive" },
  { href: "/wayback", key: "wayback" },
  { href: "/code", key: "code" },
  { href: "/images", key: "images" },
] as const;

export default function HomePage({ params }: { params: Promise<{ locale: Locale }> }) {
  const { locale } = use(params);
  setRequestLocale(locale);
  const t = useTranslations("Home");
  const tShell = useTranslations("Shell");

  return (
    <div className="flex flex-col gap-10">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-3">
          <h1 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            {t("title")}
          </h1>
          <p className="max-w-prose text-muted-foreground">{t("subtitle")}</p>
        </div>
        <PasteBox />
      </div>

      <section aria-labelledby="sections-heading" className="flex flex-col gap-3">
        <h2 id="sections-heading" className="text-lg font-semibold">
          {t("sectionsHeading")}
        </h2>
        <SectionsGrid ids={MAIN_SECTIONS} headingId="sections-heading" />
      </section>

      <nav aria-labelledby="sources-heading" className="flex flex-col gap-3">
        <h2 id="sources-heading" className="text-lg font-semibold">
          {t("sources")}
        </h2>
        <ul className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          {SOURCES.map(({ href, key }) => (
            <li key={href}>
              <Link
                href={href}
                className="flex min-h-11 flex-col gap-1 rounded-lg border bg-card p-3 shadow-card hover:bg-accent"
              >
                <span className="font-medium">{t(`source.${key}.title`)}</span>
                <span className="text-sm text-muted-foreground">{t(`source.${key}.text`)}</span>
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      <RecentJobs />

      <section
        aria-labelledby="status-heading"
        className="flex flex-col gap-2 rounded-lg border bg-card p-4"
      >
        <h2 id="status-heading" className="text-sm font-medium">
          {t("statusHeading")}
        </h2>
        <ApiStatus />
      </section>
      <p className="text-sm text-muted-foreground sm:hidden">{tShell("legal")}</p>
    </div>
  );
}
