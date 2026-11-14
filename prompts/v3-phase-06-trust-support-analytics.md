# v3 Phase 6 — Trust, support and analytics

Read `CLAUDE.md` (security, "never log values") and section 7 (metrics) of `docs/business-plan.md` first.

Deliverables:
- Website analytics: cookie-free (Plausible or self-hosted Umami), page views, waitlist and checkout funnel only.
- App telemetry, **opt-in** on the first-run screen and in Settings: install, first successful download, daily active, plan, failures per site **domain** and error code. Never URLs, titles, cookies, keys, file names or IPs. Show the exact payload in Settings ("What we send").
- Crash reports, opt-in (Sentry or self-hosted GlitchTip) for the API, web and desktop shell, with the same scrubbing; a test proves secrets and URLs are stripped.
- In-app "Report a problem": attaches the job's error code, engine and app version, OS; the user can add a link and logs only after seeing them.
- Help centre on the site (install, first download, plans, phone pairing, troubleshooting by error code, refunds) and a support inbox; link from Help in the app.
- A small metrics dashboard (activation, free → paid, refunds, renewals, top failing sites) for the owner.

**Acceptance check:** with telemetry off nothing leaves the machine except downloads and update checks (verified with a proxy log); with it on, the payload matches "What we send".
Commit: `feat: opt-in telemetry, crash reports and support`.
