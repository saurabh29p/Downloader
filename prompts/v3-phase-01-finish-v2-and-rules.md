# v3 Phase 1 — Finish v2 and set the commercial rules

Read `CLAUDE.md`, `docs/business-plan.md` and the `[Unreleased]` part of `CHANGELOG.md` first.

Deliverables:
- v2 Phase 7 "polish and ship": fix every open bug and rough edge you find while using each page at 360 px and desktop width (loading, empty and error states, keyboard, RTL). The original v2 prompt is not in the repo; polish means `make check` and `make e2e` green, axe clean, every page under the 170 KB JS budget, Lighthouse 90+/100 on Home, Downloads and Library.
- Move `[Unreleased]` to `[2.0.0]` in `CHANGELOG.md`; tag `v2.0.0`.
- `CLAUDE.md`: tick v2 Phase 7; confirm the "Commercial rules" section matches `docs/business-plan.md` (no ads, no data selling, plan gating only in `anyget/licensing`, engine updates free for every plan, no site trademarks in marketing). Legal rules stay unchanged.
- Remove wording in the web app and docs that says AnyGet is "free tools only / personal server only" where it would contradict the desktop product (Help, Legal, README); keep the self-host docs as an advanced option.

**Acceptance check:** `make check` and `make e2e` pass; `git tag` shows `v2.0.0`; no page says the product can never be paid.
Commit: `chore: v2 polish and release 2.0.0` then tag `v2.0.0`.
