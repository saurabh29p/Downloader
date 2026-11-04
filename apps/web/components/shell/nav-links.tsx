"use client";

import { ClapperboardIcon, DownloadIcon, HomeIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";
import { isActive } from "@/lib/jobs";
import { useJobs } from "@/lib/use-jobs";
import { cn } from "@/lib/utils";

const items = [
  { href: "/", key: "home", icon: HomeIcon },
  { href: "/youtube", key: "youtube", icon: ClapperboardIcon },
  { href: "/downloads", key: "downloads", icon: DownloadIcon },
] as const;

function useActiveCount() {
  const { data } = useJobs();
  return data?.filter((job) => isActive(job)).length ?? 0;
}

/** Desktop: inline links in the header. */
export function HeaderNav() {
  const t = useTranslations("Shell.nav");
  const pathname = usePathname();
  const active = useActiveCount();
  return (
    <nav aria-label={t("label")} className="hidden sm:block">
      <ul className="flex gap-1">
        {items.map(({ href, key, icon: Icon }) => {
          const current = pathname === href;
          return (
            <li key={href}>
              <Link
                href={href}
                aria-current={current ? "page" : undefined}
                className={cn(
                  "inline-flex h-11 items-center gap-2 rounded-md px-3 text-sm hover:bg-accent",
                  current && "bg-secondary font-medium",
                )}
              >
                <Icon className="size-4" aria-hidden="true" />
                {t(key)}
                {key === "downloads" && active > 0 && (
                  <span className="rounded-full bg-primary px-1.5 text-xs text-primary-foreground tabular-nums">
                    <span className="sr-only">{t("activeCount", { count: active })}</span>
                    <span aria-hidden="true">{active}</span>
                  </span>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** Phone: fixed bottom bar. */
export function BottomNav() {
  const t = useTranslations("Shell.nav");
  const pathname = usePathname();
  const active = useActiveCount();
  return (
    <nav
      aria-label={t("label")}
      className="fixed inset-x-0 bottom-0 z-40 border-t bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur sm:hidden"
    >
      <ul className="grid h-(--bottom-nav-height) grid-cols-3">
        {items.map(({ href, key, icon: Icon }) => {
          const current = pathname === href;
          return (
            <li key={href} className="flex">
              <Link
                href={href}
                aria-current={current ? "page" : undefined}
                className={cn(
                  "relative flex flex-1 flex-col items-center justify-center gap-1 text-xs text-muted-foreground",
                  current && "font-medium text-foreground",
                )}
              >
                <Icon className="size-5" aria-hidden="true" />
                {t(key)}
                {key === "downloads" && active > 0 && (
                  <span className="absolute start-[calc(50%+0.5rem)] top-2 min-w-5 rounded-full bg-primary px-1 text-center text-[0.7rem] leading-5 text-primary-foreground tabular-nums">
                    <span className="sr-only">{t("activeCount", { count: active })}</span>
                    <span aria-hidden="true">{active}</span>
                  </span>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
