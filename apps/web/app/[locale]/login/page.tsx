import type { Metadata } from "next";
import { useTranslations } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { use } from "react";

import { LoginForm } from "@/components/auth/login-form";
import { OwnerSetup } from "@/components/auth/owner-setup";
import type { Locale } from "@/i18n/routing";
import { authStatus, safeNext } from "@/lib/auth-gate";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: Locale }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Login" });
  return { title: `${t("title")} · AnyGet`, robots: { index: false } };
}

export default function LoginPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: Locale }>;
  searchParams: Promise<{ next?: string }>;
}) {
  const { locale } = use(params);
  const { next } = use(searchParams);
  setRequestLocale(locale);
  const t = useTranslations("Login");
  const status = use(authStatus(process.env.API_URL ?? "http://127.0.0.1:8000"));
  return (
    <main className="flex min-h-dvh items-center justify-center bg-background px-4 py-10">
      <div className="flex w-full max-w-sm flex-col gap-6 rounded-xl border bg-card p-6 shadow-sm">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        {/* A public AnyGet without an owner refuses everything: say how to set one up. */}
        {status?.loginRequired && !status.ownerConfigured ? (
          <OwnerSetup locale={locale} />
        ) : (
          <LoginForm next={safeNext(next ?? `/${locale}`)} />
        )}
      </div>
    </main>
  );
}
