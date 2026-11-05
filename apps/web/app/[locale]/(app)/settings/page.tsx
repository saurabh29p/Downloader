import type { Metadata } from "next";
import { useTranslations } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { use } from "react";

import { AppSettings } from "@/components/settings/app-settings";
import { InstallApp } from "@/components/settings/install-app";
import { SignOut } from "@/components/auth/sign-out";
import type { Locale } from "@/i18n/routing";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: Locale }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Settings" });
  return { title: `${t("title")} · AnyGet` };
}

const GROUPS = ["general", "downloads", "ai", "connections", "advanced"] as const;

export default function SettingsPage({ params }: { params: Promise<{ locale: Locale }> }) {
  const { locale } = use(params);
  setRequestLocale(locale);
  const t = useTranslations("Settings");
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t("title")}</h1>
        <p className="text-muted-foreground">{t("subtitle")}</p>
      </div>
      <nav aria-label={t("groupsLabel")}>
        <ul className="flex flex-wrap gap-2 text-sm">
          {GROUPS.map((group) => (
            <li key={group}>
              <a
                href={`#${group}`}
                className="inline-flex min-h-11 items-center rounded-full border bg-card px-4 hover:bg-accent"
              >
                {t(group === "connections" ? "connectionsGroup" : group)}
              </a>
            </li>
          ))}
        </ul>
      </nav>
      <section
        id="general"
        aria-labelledby="general-heading"
        className="flex scroll-mt-20 flex-col gap-4 rounded-md border bg-card p-4"
      >
        <h2 id="general-heading" className="text-xl font-semibold">
          {t("general")}
        </h2>
        <SignOut />
        <InstallApp />
      </section>
      <AppSettings />
    </div>
  );
}
