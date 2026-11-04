import createMiddleware from "next-intl/middleware";

import { routing } from "./i18n/routing";

export default createMiddleware(routing);

export const config = {
  // Everything except the API rewrite, health check, Next internals and files with an extension.
  matcher: "/((?!api|healthz|_next|_vercel|.*\\..*).*)",
};
