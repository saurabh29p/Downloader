# syntax=docker/dockerfile:1
# AnyGet web: Next.js standalone on Node 24. Build context is the repo root.
FROM node:24-slim AS base
ENV PNPM_HOME=/pnpm PATH="/pnpm:$PATH" NEXT_TELEMETRY_DISABLED=1
RUN corepack enable
WORKDIR /repo

FROM base AS build
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY apps/web/package.json apps/web/
COPY packages/shared/package.json packages/shared/
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile --filter @anyget/web...
COPY packages/shared packages/shared
COPY apps/web apps/web
# Rewrites are baked in at build time: inside Compose the API is reachable as http://api:8000.
ARG API_URL=http://api:8000
ENV API_URL=$API_URL
# sharp (Next's image optimizer and its libvips builds, ~38 MB) comes in through Next's
# own server trace; images are unoptimized (next.config.ts), so it is never loaded.
RUN pnpm --filter @anyget/web build \
    && rm -rf apps/web/.next/standalone/node_modules/.pnpm/@img+* \
              apps/web/.next/standalone/node_modules/.pnpm/sharp@*

# The standalone server is plain JavaScript (no native modules: sharp is left out in
# next.config.ts), so the runtime can use the smaller Alpine image.
FROM node:24-alpine AS runtime
# API_URL is also read at run time (the sign-in gate in proxy.ts and the sign-in page);
# without it they would look for the API on 127.0.0.1:8000 inside this container.
ARG API_URL=http://api:8000
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000 API_URL=$API_URL
WORKDIR /app
COPY --from=build --chown=node:node /repo/apps/web/.next/standalone ./
COPY --from=build --chown=node:node /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=node:node /repo/apps/web/public ./apps/web/public
USER node
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD node -e "fetch('http://127.0.0.1:3000/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "apps/web/server.js"]
