import { type NextRequest, NextResponse } from "next/server";

import { HINT_COOKIE } from "@/components/home/first-run-hint";
import { routing } from "@/i18n/routing";

/** Hides Home's first-run hint for a year (a plain form post, so it works without JS). */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ locale: string }> },
) {
  const { locale } = await params;
  const home = (routing.locales as readonly string[]).includes(locale)
    ? locale
    : routing.defaultLocale;
  // A relative Location: request.url can carry another host name (e.g. localhost for
  // 127.0.0.1, or the platform's internal host), and the cookie must stay on this one.
  const response = new NextResponse(null, { status: 303, headers: { Location: `/${home}` } });
  response.cookies.set(HINT_COOKIE, "hidden", {
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
    sameSite: "lax",
    httpOnly: true,
    secure: request.nextUrl.protocol === "https:",
  });
  return response;
}
