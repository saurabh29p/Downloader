# Phase 3 — Website foundation

Read `CLAUDE.md` (frontend rules, budgets) first.

Deliverables:
- Design tokens in `styles/globals.css` (color, type scale, 4px spacing, radius, shadow, motion; light/dark, system default). Inter + Noto fallbacks for CJK, Arabic, Devanagari.
- App shell: header, side nav on desktop, bottom nav on phone (works at 360px), theme toggle, language switcher (en, hi, ar; RTL via logical properties).
- shadcn parts: button, input, dialog, drawer, tabs, table, toast, command palette, skeleton, progress.
- Home: universal paste box with auto-detect chip (calls `/api/probe`), batch drop (many links or `.txt`), recent jobs.
- Preview drawer: title, thumbnail, size, choices; Download button.
- Downloads page: live queue via SSE, pause/resume/retry/cancel, `aria-live` progress.
- Loading skeletons, empty states and error states with retry everywhere.
- Playwright: paste a (mocked) direct-file link → preview → download → done. axe clean on every page. Lighthouse check script.

**Acceptance check:** Playwright paste-to-done passes; axe clean; Lighthouse Performance 90+ and Accessibility 100.
Commit: `feat: phase 3 website foundation`.
