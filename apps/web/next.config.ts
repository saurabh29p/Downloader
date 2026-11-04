import path from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const here = path.dirname(fileURLToPath(import.meta.url));

// Where the FastAPI server lives. Read at build time (rewrites are baked into the build).
const apiUrl = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: path.join(here, "../.."),
  transpilePackages: ["@anyget/shared"],
  poweredByHeader: false,
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
