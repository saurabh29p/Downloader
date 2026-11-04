import { defineRouting } from "next-intl/routing";

export const locales = ["en", "hi", "ar"] as const;
export type Locale = (typeof locales)[number];

/** Locales written right to left. */
export const rtlLocales: readonly Locale[] = ["ar"];

export const routing = defineRouting({
  locales,
  defaultLocale: "en",
});

export function dirFor(locale: string): "rtl" | "ltr" {
  return (rtlLocales as readonly string[]).includes(locale) ? "rtl" : "ltr";
}
