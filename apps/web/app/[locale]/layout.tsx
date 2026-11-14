import "@fontsource-variable/inter";
import "@fontsource-variable/fraunces";
import "@fontsource-variable/jetbrains-mono";
// Script fonts load only when a page shows those characters (unicode-range).
import "@fontsource/noto-sans-devanagari/devanagari-400.css";
import "@fontsource/noto-sans-devanagari/devanagari-600.css";
import "@fontsource/noto-naskh-arabic/arabic-400.css";
import "@fontsource/noto-naskh-arabic/arabic-600.css";
import "@/styles/globals.css";

import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { notFound } from "next/navigation";
import { hasLocale, NextIntlClientProvider } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import type { ReactNode } from "react";

import { dirFor, routing } from "@/i18n/routing";
import { Providers } from "@/lib/providers";
import { pwaScript } from "@/lib/pwa";
import { themeScript } from "@/lib/theme";

// The Latin files the first paint needs, preloaded (next/font adds the <link rel=preload>).
// Same Fontsource files; the Fontsource CSS above still serves every other subset, and the
// script fonts load only when a page shows those characters.
const inter = localFont({
  src: "../../node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2",
  weight: "100 900",
  variable: "--font-inter",
  display: "swap",
  // No metric-matched Arial in between: it would also win for Latin Extended letters
  // (ő, ș…) that Fontsource's "Inter Variable" serves after this file.
  adjustFontFallback: false,
});
const fraunces = localFont({
  src: "../../node_modules/@fontsource-variable/fraunces/files/fraunces-latin-wght-normal.woff2",
  weight: "100 900",
  variable: "--font-fraunces",
  display: "swap",
  adjustFontFallback: false,
});

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const requested = (await params).locale;
  const locale = hasLocale(routing.locales, requested) ? requested : routing.defaultLocale;
  const t = await getTranslations({ locale, namespace: "Meta" });
  return {
    title: t("title"),
    description: t("description"),
    icons: { icon: "/favicon.png", apple: "/icons/apple-touch-icon.png" },
    appleWebApp: { capable: true, title: "AnyGet", statusBarStyle: "default" },
  };
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    // Teal like the manifest's theme_color, so an installed app keeps one bar colour.
    { media: "(prefers-color-scheme: light)", color: "#0e5a5c" },
    { media: "(prefers-color-scheme: dark)", color: "#0d1517" },
  ],
};

export default async function LocaleLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);

  return (
    <html
      lang={locale}
      dir={dirFor(locale)}
      className={`${inter.variable} ${fraunces.variable}`}
      suppressHydrationWarning
    >
      <head>
        {/* Static theme script (no user input); runs before paint to avoid a flash. */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        {/* Static PWA script: service worker registration and the install prompt. */}
        <script dangerouslySetInnerHTML={{ __html: pwaScript }} />
      </head>
      <body className="min-h-dvh">
        <NextIntlClientProvider>
          <Providers>{children}</Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
