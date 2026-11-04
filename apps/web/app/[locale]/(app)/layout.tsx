import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { LanguageSwitcher } from "@/components/language-switcher";
import { CommandPalette } from "@/components/shell/command-palette";
import { JobEventsBridge } from "@/components/shell/job-events-bridge";
import { BottomNav, HeaderNav } from "@/components/shell/nav-links";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { Toaster } from "@/components/ui/toaster";
import { Link } from "@/i18n/navigation";

export default function AppLayout({ children }: { children: ReactNode }) {
  const t = useTranslations("Shell");
  return (
    <JobEventsBridge>
      <div className="flex min-h-dvh flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:start-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-background focus:px-4 focus:py-2"
        >
          {t("skip")}
        </a>
        <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur">
          <div className="mx-auto flex max-w-5xl items-center gap-2 px-4 py-1.5">
            <Link
              href="/"
              className="me-auto inline-flex h-11 items-center text-lg font-semibold tracking-tight sm:me-4"
            >
              AnyGet
            </Link>
            <HeaderNav />
            <div className="flex items-center gap-1 sm:ms-auto">
              <LanguageSwitcher />
              <ThemeToggle />
            </div>
          </div>
        </header>
        <main
          id="main"
          className="mx-auto w-full max-w-5xl flex-1 px-4 pt-8 pb-[calc(var(--bottom-nav-height)+2rem)] sm:pb-10"
        >
          {children}
        </main>
        <footer className="hidden border-t sm:block">
          <p className="mx-auto max-w-5xl px-4 py-6 text-sm text-muted-foreground">{t("legal")}</p>
        </footer>
        <BottomNav />
      </div>
      <Toaster closeLabel={t("closeToast")} />
      <CommandPalette />
    </JobEventsBridge>
  );
}
