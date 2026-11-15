import { cookies } from "next/headers";
import { getTranslations } from "next-intl/server";

import type { Locale } from "@/i18n/routing";

export const HINT_COOKIE = "anyget_hint";

// Public-domain or openly licensed examples (checked by hand, Nov 2026).
const EXAMPLES = [
  { key: "book", url: "https://archive.org/details/alicesadventures19033gut" },
  {
    key: "image",
    url: "https://commons.wikimedia.org/wiki/File:Tsunami_by_hokusai_19th_century.jpg",
  },
  { key: "video", url: "https://framatube.org/w/9c9de5e8-0a1e-484a-b099-e80766180a6d" },
] as const;

/**
 * First-run hint under Home's paste box: safe examples to try. Server-rendered with no
 * client JavaScript; "Hide" posts to /<locale>/hide-hint, which sets a cookie.
 * Each example is a plain link to /<locale>?url=… so the paste box probes it on load.
 */
export async function FirstRunHint({ locale }: { locale: Locale }) {
  const store = await cookies();
  if (store.get(HINT_COOKIE)?.value === "hidden") return null;
  const t = await getTranslations({ locale, namespace: "Home.firstRun" });
  return (
    <aside
      aria-labelledby="first-run-title"
      className="flex flex-col gap-3 rounded-lg border bg-card p-4 text-sm"
      data-testid="first-run-hint"
    >
      <div className="flex items-start justify-between gap-3">
        <h2 id="first-run-title" className="text-base font-semibold">
          {t("title")}
        </h2>
        <form method="post" action={`/${locale}/hide-hint`}>
          <button
            type="submit"
            className="min-h-11 shrink-0 px-2 font-medium text-muted-foreground underline-offset-4 hover:underline"
          >
            {t("hide")}
          </button>
        </form>
      </div>
      <p className="text-muted-foreground">{t("text")}</p>
      <ul className="flex flex-col gap-1">
        {EXAMPLES.map(({ key, url }) => (
          <li key={key}>
            <a
              href={`/${locale}?url=${encodeURIComponent(url)}`}
              className="inline-flex min-h-11 items-center font-medium text-primary underline-offset-4 hover:underline"
            >
              {t(key)}
            </a>
          </li>
        ))}
      </ul>
    </aside>
  );
}
