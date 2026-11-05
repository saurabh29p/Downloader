import { useTranslations } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { redirect } from "next/navigation";
import { use } from "react";

import { Link } from "@/i18n/navigation";
import type { Locale } from "@/i18n/routing";
import { firstLink } from "@/lib/share";

type Shared = { url?: string; text?: string; title?: string };

/** Android share target: find the link in what was shared and open its preview on Home. */
export default function SharePage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: Locale }>;
  searchParams: Promise<Shared>;
}) {
  const { locale } = use(params);
  const shared = use(searchParams);
  setRequestLocale(locale);
  const link = firstLink([shared.url, shared.text, shared.title]);
  if (link) redirect(`/${locale}?url=${encodeURIComponent(link)}`);
  return <NoLink />;
}

function NoLink() {
  const t = useTranslations("Share");
  return (
    <div className="flex max-w-prose flex-col gap-3">
      <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
      <p>{t("noLink")}</p>
      <Link href="/" className="font-medium text-primary underline-offset-4 hover:underline">
        {t("home")}
      </Link>
    </div>
  );
}
