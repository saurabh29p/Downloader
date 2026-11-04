import { useTranslations } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { use } from "react";

import { ApiStatus } from "@/components/api-status";
import { Button } from "@/components/ui/button";
import type { Locale } from "@/i18n/routing";

export default function HomePage({ params }: { params: Promise<{ locale: Locale }> }) {
  const { locale } = use(params);
  setRequestLocale(locale);
  const t = useTranslations("Home");

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-3">
        <h1 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
          {t("title")}
        </h1>
        <p className="max-w-prose text-muted-foreground">{t("subtitle")}</p>
      </div>

      <form className="flex flex-col gap-2" aria-describedby="paste-note">
        <label htmlFor="paste" className="text-sm font-medium">
          {t("pasteLabel")}
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            id="paste"
            name="url"
            type="url"
            inputMode="url"
            dir="ltr"
            placeholder="https://"
            disabled
            className="h-11 w-full min-w-0 rounded-md border border-input bg-card px-3 text-base shadow-xs placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-60"
          />
          <Button type="submit" disabled>
            {t("download")}
          </Button>
        </div>
        <p id="paste-note" className="text-sm text-muted-foreground">
          {t("comingSoon")}
        </p>
      </form>

      <section
        aria-labelledby="status-heading"
        className="rounded-lg border bg-card p-4 shadow-card"
      >
        <h2 id="status-heading" className="mb-2 text-sm font-medium">
          {t("statusHeading")}
        </h2>
        <ApiStatus />
      </section>
    </div>
  );
}
