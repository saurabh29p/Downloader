"use client";

import { useLocale, useTranslations } from "next-intl";

import { Globe } from "@/components/ui/icons";
import { NativeSelect } from "@/components/ui/native-select";
import { usePathname, useRouter } from "@/i18n/navigation";
import { routing, type Locale } from "@/i18n/routing";

export const localeNames: Record<Locale, string> = { en: "English", hi: "हिन्दी", ar: "العربية" };

export function LanguageSwitcher() {
  const t = useTranslations("Nav");
  const current = useLocale() as Locale;
  const pathname = usePathname();
  const router = useRouter();

  return (
    <NativeSelect
      aria-label={t("language")}
      value={current}
      icon={<Globe />}
      onChange={(event) => router.replace(pathname, { locale: event.target.value as Locale })}
    >
      {routing.locales.map((locale) => (
        <option key={locale} value={locale} lang={locale}>
          {localeNames[locale]}
        </option>
      ))}
    </NativeSelect>
  );
}
