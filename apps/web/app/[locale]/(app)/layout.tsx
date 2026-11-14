import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { LanguageSwitcher } from "@/components/language-switcher";
import { PlayerHost } from "@/components/player/player-host";
import { CommandPalette } from "@/components/shell/command-palette";
import { DropAnywhere } from "@/components/shell/drop-anywhere";
import { JobEventsBridge } from "@/components/shell/job-events-bridge";
import { MainNav } from "@/components/shell/nav-links";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { Toaster } from "@/components/ui/toaster";
import { Link } from "@/i18n/navigation";

function Wordmark() {
  return (
    <Link
      href="/"
      className="inline-flex h-11 items-center gap-1.5 font-serif text-xl font-semibold tracking-tight"
    >
      <span aria-hidden="true" className="size-2.5 rounded-full bg-signal" />
      AnyGet
    </Link>
  );
}

export default function AppLayout({ children }: { children: ReactNode }) {
  const t = useTranslations("Shell");
  return (
    <JobEventsBridge>
      <div className="flex min-h-dvh">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:start-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-background focus:px-4 focus:py-2"
        >
          {t("skip")}
        </a>
        {/* Desktop: the left rail. */}
        <div className="hidden w-(--rail-width) shrink-0 border-e bg-rail md:block">
          <aside className="sticky top-0 flex h-dvh flex-col gap-6 overflow-y-auto px-3 py-4">
            <div className="px-2">
              <Wordmark />
            </div>
            <MainNav variant="rail" />
            <div className="mt-auto flex flex-col gap-3 px-1">
              <div className="flex flex-wrap items-center gap-1">
                <LanguageSwitcher />
                <ThemeToggle />
              </div>
              <p className="flex gap-3 px-2 text-xs text-muted-foreground">
                <Link href="/help" className="underline-offset-4 hover:underline">
                  {t("help")}
                </Link>
                <Link href="/legal" className="underline-offset-4 hover:underline">
                  {t("legalShort")}
                </Link>
              </p>
            </div>
          </aside>
        </div>

        <div className="flex min-w-0 flex-1 flex-col">
          {/* Phone and small tablets: a slim top bar. */}
          <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur md:hidden">
            <div className="flex items-center gap-1 px-4 py-1">
              <span className="me-auto">
                <Wordmark />
              </span>
              <LanguageSwitcher />
              <ThemeToggle />
            </div>
          </header>
          <main
            id="main"
            className="mx-auto w-full max-w-[80rem] flex-1 px-4 pt-8 pb-[calc(var(--bottom-nav-height)+2rem)] sm:px-6 md:pb-10 lg:px-10"
          >
            {children}
          </main>
          <footer className="hidden border-t md:block">
            <p className="mx-auto max-w-[80rem] px-4 py-5 text-sm text-muted-foreground sm:px-6 lg:px-10">
              {t("legal")}
            </p>
          </footer>
        </div>
        <MainNav variant="bar" />
      </div>
      <Toaster closeLabel={t("closeToast")} />
      <CommandPalette />
      <DropAnywhere />
      <PlayerHost />
    </JobEventsBridge>
  );
}
