# v3 Phase 4 — Phone: remote for the computer, and the Android app

Read `CLAUDE.md` (PWA, share target, auth gotchas) and section 8 of `docs/business-plan.md` first.

Deliverables:
- **Phone remote (iPhone and Android):** a "Connect your phone" screen on the desktop shows a QR code with a one-time pairing code; pairing issues a phone-scoped bearer token (revocable in Settings). LAN listening is **off by default** and only turns on while a phone is paired. The phone uses the existing PWA and share target; add "Save to phone" (download a finished file from the Library to the phone). Document away-from-home use through Tailscale in `docs/tailscale.md`.
- **Android app, step 1 — a spike (time-box one week):** prove yt-dlp + ffmpeg + a JS runtime run on the device (Chaquopy first; compare one alternative). Do not use GPL libraries inside our closed-source app. Write the result and the chosen design in `docs/android.md` before building.
- **Android app, step 2:** paste or share a link → formats → download into shared storage (Movies/Music/Download/AnyGet), background downloads with a notification, Free limits and licence unlock from Phase 2, engine updates, in-app app updates from our site, signed APK. English first, then hi/ar strings.
- Store copy for the APK page and any alternative store: no site trademarks.

**Acceptance check:** an iPhone on the same Wi-Fi shares a link that downloads on the computer and saves back to the phone; the Android APK installs on a clean phone and downloads a CC video and an MP3 without a computer.
Commit: `feat: phone remote and Android app`.
