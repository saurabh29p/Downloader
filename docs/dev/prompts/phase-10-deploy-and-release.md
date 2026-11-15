# Phase 10 — Deploy and release

Read `CLAUDE.md` (security) and the deployment section of `docs/dev/plan.md` first.

Deliverables:
- `docker-compose.tunnel.yml`: cloudflared `2026.10.7`, `tunnel --no-autoupdate run`, token from `TUNNEL_TOKEN`; `make up-public`.
- API middleware that verifies the Cloudflare Access JWT (team domain + AUD from settings, JWKS cached); bearer token option for CLI/extension; local requests from 127.0.0.1 allowed.
- CSP and security headers on web and API; rate limiting per client.
- `docs/deploy.md`: DNS export warning, Cloudflare + Hostinger nameservers, tunnel, routes, Access with One-time PIN; `docs/tailscale.md` fallback with `tailscale serve`.
- Backups: `make backup` / `make restore` for `./data` (SQLite) and settings.
- Release workflow: build and push Docker images on tags; `CHANGELOG.md`; tag `v1.0.0`.

**Acceptance check:** `https://dl.<your-domain>` opens on a phone over mobile data after the email code.
Commit: `feat: phase 10 deploy and release` then tag `v1.0.0`.
