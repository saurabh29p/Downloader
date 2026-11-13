# v3 Phase 5 — Website, pricing and checkout

Read `CLAUDE.md` (frontend rules, commercial rules) and sections 3, 6, 10 and 11 of `docs/business-plan.md` first.

Deliverables:
- `apps/site`: a static site on Cloudflare Pages (reuse the Reading Room tokens and fonts). Pages: Home, Features, Pricing (the plan table from the business plan), Download (detects the OS; Windows, macOS, Linux, Android APK), Help, Changelog (from `CHANGELOG.md`), Waitlist (before launch), use-case pages and honest comparison pages.
- Legal pages (drafts for the lawyer, clearly marked until reviewed): EULA (personal use; Pro adds commercial use), Terms of sale, Privacy, Refunds (14 days), Copyright/DMCA with the designated agent, Acceptable use. Never use site trademarks in titles or ads.
- Paddle checkout (overlay) and customer portal links; a launch coupon for the $29 Lifetime price.
- `apps/licence-worker` (Cloudflare Worker): verifies Paddle webhooks, signs the licence with the Phase 2 private key (Worker secret), emails it with Resend, stores only order id + email hash + plan in D1; "Resend my key" by email; refunds revoke on the next online check (keys still work offline until then).
- Lighthouse 90+/100, axe clean, works at 360 px; cookie-free analytics only.

**Acceptance check:** a Paddle sandbox purchase emails a key that activates Plus in the desktop app; a refund in the sandbox marks it revoked; every legal page is linked from the footer.
Commit: `feat: website, pricing and licence worker`.
