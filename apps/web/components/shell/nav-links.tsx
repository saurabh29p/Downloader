"use client";

import {
  BookMarkedIcon,
  DownloadIcon,
  EyeIcon,
  HomeIcon,
  LayoutGridIcon,
  PlugIcon,
  SettingsIcon,
  WrenchIcon,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";
import { isActive } from "@/lib/jobs";
import { useJobs } from "@/lib/use-jobs";
import { cn } from "@/lib/utils";

// The main five, in the rail and in the phone's bottom bar (five fit at 360 px).
const items = [
  { href: "/", key: "home", icon: HomeIcon },
  { href: "/sections", key: "sections", icon: LayoutGridIcon },
  { href: "/downloads", key: "downloads", icon: DownloadIcon },
  { href: "/library", key: "library", icon: BookMarkedIcon },
  { href: "/settings", key: "settings", icon: SettingsIcon },
] as const;

// Rarely used pages: a small group under the rail. Every tool (and these) is also on the
// Sections page (/sections#tools, phones too) and in Ctrl+K; their URLs are unchanged.
const more = [
  { href: "/sections#tools", key: "tools", icon: WrenchIcon },
  { href: "/watch", key: "watch", icon: EyeIcon },
  { href: "/connections", key: "connections", icon: PlugIcon },
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
        {items.map(({ href, key, icon: Icon }) => {
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
                      ? "bg-card font-medium shadow-card before:absolute before:inset-y-2 before:start-0 before:w-1 before:rounded-full before:bg-signal"
                      : "font-medium text-foreground"),
                )}
              >
                <Icon className={rail ? "size-4" : "size-5"} aria-hidden="true" />
                {t(key)}
                {key === "downloads" && active > 0 && (
                  <span
                    className={cn(
                      "min-w-5 rounded-full bg-signal px-1 text-center text-xs leading-5 text-signal-foreground tabular-nums",
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
      {rail && (
        <div className="flex flex-col gap-0.5">
          <p className="px-3 text-xs font-medium text-muted-foreground" id="nav-more">
            {t("more")}
          </p>
          <ul aria-labelledby="nav-more" className="flex flex-col gap-0.5">
            {more.map(({ href, key, icon: Icon }) => {
              const current =
                href.startsWith("/watch") || href.startsWith("/connections")
                  ? pathname.startsWith(href)
                  : false;
              return (
                <li key={href}>
                  <Link
                    href={href}
                    aria-current={current ? "page" : undefined}
                    className={cn(
                      "flex h-9 items-center gap-3 rounded-md px-3 text-sm text-muted-foreground hover:bg-accent hover:text-foreground",
                      current && "bg-card font-medium text-foreground shadow-card",
                    )}
                  >
                    <Icon className="size-4" aria-hidden="true" />
                    {t(key)}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </nav>
  );
}
