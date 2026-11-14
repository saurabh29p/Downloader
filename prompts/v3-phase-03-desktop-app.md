# v3 Phase 3 — Desktop app

Read `CLAUDE.md` (gotchas: `API_URL`, `proxy.ts`, net guard, PUID) and sections 8–9 of `docs/business-plan.md` first.

Deliverables:
- `apps/desktop` (Electron): starts the Python API (frozen with PyInstaller, one folder) and the Next.js standalone server on free 127.0.0.1 ports, then opens the window. Shuts both down cleanly; restarts them if they crash.
- Bundle ffmpeg (an **LGPL** build) and the JavaScript runtime yt-dlp needs (Deno, or Electron's Node with `ELECTRON_RUN_AS_NODE` if yt-dlp supports a Node runtime — check the yt-dlp docs first and record the result in CLAUDE.md).
- Data and downloads in the OS locations (app-data folder; `~/Downloads/AnyGet` by default). First-run wizard: downloads folder, language, theme, optional "start with the computer".
- Tray/menu-bar icon with the queue, clipboard watch (reuse `anyget watch-clipboard` logic), `anyget://` deep links, and pairing for the browser extension (reuse the bearer `api_token`).
- Auto-update with electron-updater from a generic feed on Cloudflare R2. The engine updater from Phase 2 stays separate.
- `.github/workflows/release.yml`: build Windows (signed with Azure Artifact Signing), macOS universal (signed + notarized), Linux AppImage and Flatpak; upload to R2; third-party licence notices in the app's About screen.
- Smoke test with Playwright's Electron support: launch, paste a fixture link, file appears.

**Acceptance check:** a fresh Windows and macOS machine installs without security warnings, downloads a CC video and a Gutenberg EPUB, and updates itself to a newer test build.
Commit: `feat: desktop app`.
