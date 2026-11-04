import { useLocale, useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import { cn } from "@/lib/utils";

const names: Record<string, string> = { en: "English", hi: "हिन्दी", ar: "العربية" };

export function LanguageSwitcher() {
  const t = useTranslations("Nav");
  const current = useLocale();
  return (
    <nav aria-label={t("language")}>
      <ul className="flex gap-1">
        {routing.locales.map((locale) => (
          <li key={locale}>
            <Link
              href="/"
              locale={locale}
              lang={locale}
              aria-current={locale === current ? "true" : undefined}
              className={cn(
                "inline-flex h-11 items-center rounded-md px-3 text-sm hover:bg-accent",
                locale === current && "bg-secondary font-medium",
              )}
            >
              {names[locale]}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
