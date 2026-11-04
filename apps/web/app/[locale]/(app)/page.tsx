import { useTranslations } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { use } from "react";

import { ApiStatus } from "@/components/api-status";
import { RecentJobs } from "@/components/jobs/recent-jobs";
import { PasteBox } from "@/components/paste/paste-box";
import type { Locale } from "@/i18n/routing";

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
