import createMiddleware from "next-intl/middleware";
import { NextResponse, type NextRequest } from "next/server";

import { routing } from "./i18n/routing";
import { isGated, loginPath, loginRequired, SESSION_COOKIE } from "./lib/auth-gate";

const intl = createMiddleware(routing);
// Read at run time here (the /api rewrite in next.config.ts is fixed at build time).
const apiUrl = process.env.API_URL ?? "http://127.0.0.1:8000";

export default async function proxy(request: NextRequest) {
  const response = intl(request);
  if (response.headers.has("location")) return response; // locale redirect comes first
  const { pathname, search } = request.nextUrl;
  if (!isGated(pathname, routing.locales)) return response;
  if (request.cookies.has(SESSION_COOKIE)) return response;
  if (!(await loginRequired(apiUrl))) return response;
  const locale = pathname.split("/")[1] ?? routing.defaultLocale;
  return NextResponse.redirect(new URL(loginPath(locale, pathname + search), request.url));
}

export const config = {
  // Everything except the API rewrite, health check, Next internals and files with an extension.
  matcher: "/((?!api|healthz|_next|_vercel|.*\\..*).*)",
};
