"use client";

import {
  BookMarkedIcon,
  DownloadIcon,
  EyeIcon,
  HomeIcon,
  LayoutGridIcon,
  PlugIcon,
  SettingsIcon,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";
import { isActive } from "@/lib/jobs";
import { useJobs } from "@/lib/use-jobs";
import { cn } from "@/lib/utils";

// `phone`: also in the bottom bar (five fit at 360 px); the rest are in Settings and Ctrl+K.
const items = [
  { href: "/", key: "home", icon: HomeIcon, phone: true },
  { href: "/sections", key: "sections", icon: LayoutGridIcon, phone: true },
  { href: "/downloads", key: "downloads", icon: DownloadIcon, phone: true },
  { href: "/library", key: "library", icon: BookMarkedIcon, phone: true },
  { href: "/watch", key: "watch", icon: EyeIcon, phone: false },
  { href: "/connections", key: "connections", icon: PlugIcon, phone: false },
  { href: "/settings", key: "settings", icon: SettingsIcon, phone: true },
] as const;

/** Opens the Ctrl+K menu (CommandPalette listens for this event). */
export const PALETTE_EVENT = "anyget:palette";

/** Desktop: the left rail. Phone: the fixed bottom bar. */
export function MainNav({ variant }: { variant: "rail" | "bar" }) {
  const t = useTranslations("Shell.nav");
  const pathname = usePathname();
  const { data } = useJobs();
  const active = data?.filter((job) => isActive(job)).length ?? 0;
  const rail = variant === "rail";

  return (
    <nav
      aria-label={t("label")}
      className={
        rail
          ? "flex flex-col gap-4"
          : "fixed inset-x-0 bottom-0 z-40 border-t bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
      }
    >
      {rail && (
        <button
          type="button"
          onClick={() => window.dispatchEvent(new Event(PALETTE_EVENT))}
          className="flex h-10 items-center gap-2 rounded-md border bg-card px-3 text-sm text-muted-foreground hover:bg-accent"
        >
          <span className="me-auto">{t("quick")}</span>
          <kbd className="font-mono text-xs" dir="ltr">
            Ctrl K
          </kbd>
        </button>
      )}
      <ul className={rail ? "flex flex-col gap-0.5" : "grid h-(--bottom-nav-height) grid-cols-5"}>
        {items
          .filter((item) => rail || item.phone)
          .map(({ href, key, icon: Icon }) => {
            const current = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <li key={href} className={rail ? undefined : "flex"}>
                <Link
                  href={href}
                  aria-current={current ? "page" : undefined}
                  className={cn(
                    rail
                      ? "relative flex h-10 items-center gap-3 rounded-md px-3 text-sm hover:bg-accent"
                      : "relative flex flex-1 flex-col items-center justify-center gap-1 text-xs text-muted-foreground",
                    current &&
                      (rail
                        ? "bg-card font-medium shadow-card before:absolute before:inset-y-2 before:start-0 before:w-1 before:rounded-full before:bg-saffron"
                        : "font-medium text-foreground"),
                  )}
                >
                  <Icon className={rail ? "size-4" : "size-5"} aria-hidden="true" />
                  {t(key)}
                  {key === "downloads" && active > 0 && (
                    <span
                      className={cn(
                        "min-w-5 rounded-full bg-saffron px-1 text-center text-xs leading-5 text-saffron-foreground tabular-nums",
                        rail ? "ms-auto" : "absolute start-[calc(50%+0.5rem)] top-1.5",
                      )}
                    >
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
