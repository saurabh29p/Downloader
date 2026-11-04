import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { LanguageSwitcher } from "@/components/language-switcher";
import { Link } from "@/i18n/navigation";

export default function AppLayout({ children }: { children: ReactNode }) {
  const t = useTranslations("Shell");
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:start-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-background focus:px-4 focus:py-2"
      >
        {t("skip")}
      </a>
      <header className="border-b">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2 px-4 py-2">
          <Link href="/" className="text-lg font-semibold tracking-tight">
            AnyGet
          </Link>
          <LanguageSwitcher />
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-4 py-10">
        {children}
      </main>
      <footer className="border-t">
        <p className="mx-auto max-w-5xl px-4 py-6 text-sm text-muted-foreground">{t("legal")}</p>
      </footer>
    </div>
  );
}
