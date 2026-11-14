import { getTranslations } from "next-intl/server";

import type { Locale } from "@/i18n/routing";
import { REPO_URL } from "@/lib/project";

const code = "block overflow-x-auto rounded-md bg-muted px-3 py-2 font-mono text-xs";

/** Shown instead of the sign-in form when AnyGet is public but has no owner (fails closed). */
export async function OwnerSetup({ locale }: { locale: Locale }) {
  const t = await getTranslations({ locale, namespace: "Login" });
  return (
    <section
      className="flex flex-col gap-3 text-sm"
      aria-labelledby="owner-setup"
      data-testid="owner-setup"
    >
      <h2 id="owner-setup" className="text-base font-semibold">
        {t("setupTitle")}
      </h2>
      <p>{t("setupText")}</p>
      <ol className="list-decimal space-y-3 ps-5">
        <li className="space-y-1.5">
          {t("setupHash")}
          <code dir="ltr" className={code}>
            docker compose run --rm api anyget hash-password
          </code>
          <span className="text-muted-foreground">{t("setupHashSource")}</span>
          <code dir="ltr" className={code}>
            cd apps/api && uv run anyget hash-password
          </code>
        </li>
        <li className="space-y-1.5">
          {t("setupVars")}
          <code dir="ltr" className={code}>
            ANYGET_OWNER_EMAIL=you@example.com
            <br />
            ANYGET_OWNER_PASSWORD_HASH=$argon2id$…
            <br />
            ANYGET_SESSION_SECRET=…
          </code>
        </li>
        <li>{t("setupRestart")}</li>
      </ol>
      <a
        href={`${REPO_URL}/blob/main/docs/hosted.md`}
        className="self-start font-medium text-primary underline underline-offset-4"
      >
        {t("setupGuide")}
      </a>
    </section>
  );
}
