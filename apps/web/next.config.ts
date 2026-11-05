import path from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const here = path.dirname(fileURLToPath(import.meta.url));

// Where the FastAPI server lives. Read at build time (rewrites are baked into the build).
const apiUrl = process.env.API_URL ?? "http://127.0.0.1:8000";

// Thumbnails and covers come from many sites, so images may load from any https host.
// Scripts stay same-origin; the two small inline scripts (theme, service worker) and
// Next's own inline bootstrap need 'unsafe-inline' (no eval is allowed).
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "media-src 'self' blob:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "frame-src 'self'",
  "worker-src 'self'",
  "manifest-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const SECURITY_HEADERS = [
  { key: "Content-Security-Policy", value: CSP },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
];

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: path.join(here, "../.."),
  transpilePackages: ["@anyget/shared"],
  poweredByHeader: false,
  async headers() {
    // Pages only: API answers carry the API's own headers (apps/api/anyget/core/auth.py).
    // Dev mode needs eval for fast refresh, so the CSP is for production builds.
    const headers =
      process.env.NODE_ENV === "production"
        ? SECURITY_HEADERS
        : SECURITY_HEADERS.filter((h) => h.key !== "Content-Security-Policy");
    return [{ source: "/((?!api/).*)", headers }];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
};

const withNextIntl = createNextIntlPlugin({
  requestConfig: "./i18n/request.ts",
  // Compile ICU messages at build time so the message parser is not shipped to browsers.
  experimental: {
    messages: { format: "json", path: "./messages", locales: "infer", precompile: true },
  },
});
export default withNextIntl(nextConfig);
