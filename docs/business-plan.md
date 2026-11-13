# AnyGet — business and launch plan (v3)

Written 13 Nov 2026. This is a working plan, not legal or financial advice. Prices from other companies were checked on secondary sites and should be confirmed on their own pages before you quote them.

## 1. Summary

AnyGet is already a big, finished-feeling product (v1.0.0 shipped, v2 Phases 1–6 done). What it lacks to be **sold** is not features but the parts around them: a desktop installer, licences and plans, a website with checkout, legal pages, support and a phone story.

Decisions taken:

| Question | Decision |
|---|---|
| How we sell | **Desktop app only.** Downloads run on the buyer's own computer: no servers, no bandwidth bill, no blocked server IPs, less risk for payment accounts. |
| Video and social sites | **Fully included**, and usable from the phone (Android app; iPhone as a remote for the computer). |
| First market | **Global English** (US, UK, Canada, Australia, Europe). Regional prices and Hindi/Arabic markets come next. |
| Ads | **Never.** No ads, no selling data, no tracking. That is part of the pitch. |

## 2. What is already built

| Area | What exists |
|---|---|
| Downloads | 14 handlers: yt-dlp (1,800+ video/audio sites, formats, MP3, subtitles, playlists, channels), archive.org, Wayback, GitHub/GitLab/Codeberg, Google Drive/Dropbox/OneDrive/MEGA, gallery-dl image galleries, Wikimedia, Hugging Face/Civitai, IIIF world libraries, web pages, direct files with resume, optional torrents. |
| Search | Universal search that streams results from many sources, Sections (Movies, Books, Music, Video, Declassified, More) with ready-made searches, TMDB "where to watch". |
| Books | 18 legal book sources (Gutenberg, Standard Ebooks, Open Library, HathiTrust, Gallica, Trove, NDL, DPLA, Europeana…) with a ranker that finds the best legal copy and shows library/buy links when there is none. |
| Library | Offline library with previews, full-text search inside files, tags, dedupe, a video/PDF/EPUB/text/image viewer and an audio player that keeps playing. |
| Daily use | Watches (auto-save new items), Connections (encrypted cookies/keys per site), conversion and OCR, retention, backups. |
| Reach | PWA with share target, browser extension, CLI, plugins, English/Hindi/Arabic with right-to-left layout. |
| Quality | Strict security (SSRF guard, path safety, no DRM, no geo-bypass), about 7,300 lines of Python tests, Playwright + axe end-to-end tests, JS budgets, CI. |
| AI | Optional OpenRouter helper (better plans, answers, ordering) that never sees cookies, keys or file contents. |

**Missing for a paid launch:** v2 Phase 7 polish; licence keys and plan limits; a signed desktop installer with auto-update; an Android app and a phone remote; a website with pricing, checkout and legal pages; support, crash reports and analytics; a beta and launch.

## 3. Positioning

> **Paste any link, get the file. No ads, no malware, no tracking — it runs on your computer.**

What makes AnyGet different:

1. **One box for everything**: video, audio, books, archives, code, cloud links, galleries, library scans. Competitors (4K Video Downloader, Downie, JDownloader) are video- or file-only.
2. **Finds the legal copy**: public-domain books, archive.org items, world-library scans and Creative Commons media, with clear "borrow only / in copyright" messages instead of piracy links.
3. **A real library**: everything you saved is searchable (even text inside PDFs and scans), playable and readable in one place.
4. **Clean and private**: no ads, no account needed for the free tier, nothing leaves your computer except the downloads themselves.

## 4. Who needs it (demand)

| Segment | What they want | Likely plan |
|---|---|---|
| Offline savers (commuters, travellers, patchy or costly data) | Lectures, podcasts and playlists saved for later | Free → Plus |
| Students, teachers, researchers | Public-domain books, archive.org, OCR'd scans, world libraries | Free → Plus |
| Creators and editors | Their own uploads, CC footage, reference clips, at work | Pro |
| Data hoarders and archivists | Watches, bulk saves, Wayback, many sites | Lifetime (and they spread the word) |
| People leaving ad-filled download sites; ex-Pocket users | A safe tool and a personal library (Pocket closed in July 2025) | Free → Plus |

**Size of the market.** Research firms put the "online video downloader" market around US$5–6.5 billion for 2025–26, but their figures disagree and the reports are weak, so treat this as "large", not as a number to plan on. Real demand should be measured before building everything:

- Keyword volumes for the use cases on the site (a keyword tool such as Ahrefs or Google Keyword Planner).
- A waitlist page with the launch price: sign-ups per visitor is the first real signal.

## 5. How users adopt it

1. **Discover** through a specific need: a search ("save playlist offline", "download archive.org book as PDF"), a Reddit thread, a YouTube tutorial.
2. **Install** a signed app (no SmartScreen or Gatekeeper warnings — these kill conversion).
3. **First success in under 60 seconds**: paste a link, get the file. This is the activation moment; measure it.
4. **Habit**: the browser button, the phone share sheet, watches that save new uploads, a library that grows.
5. **Upgrade** when a limit is hit naturally: 4K, a 60-item playlist, a second watch, OCR. Each limit shows one calm screen with what Plus adds and the price — never a nag.
6. **Refer**: a share link that gives both people a discount (later).

## 6. Plans and prices

| | Free | Plus | Lifetime | Pro |
|---|---|---|---|---|
| Price | $0 | **$19 / year** | **$39 once** ($29 launch price) | **$79 once** |
| Quality | up to 1080p, MP3 | up to 8K, all audio formats | same as Plus | same as Plus |
| Parallel downloads | 2 | 5 | 5 | 5 |
| Playlists / channels | up to 25 items | unlimited | unlimited | unlimited |
| Watches (auto-save new items) | — | ✓ | ✓ | ✓ |
| Batch import, conversion, OCR | — | ✓ | ✓ | ✓ |
| Legal search, books, libraries, library, viewer, player | ✓ | ✓ | ✓ | ✓ |
| Browser button, phone remote | ✓ | ✓ | ✓ | ✓ |
| Android app | basic (Free limits) | ✓ | ✓ | ✓ |
| AI helper (your own OpenRouter key) | — | ✓ | ✓ | ✓ |
| Devices | any | 3 | 3 | 5 |
| CLI, plugins, commercial-use licence, priority support | — | — | — | ✓ |

Rules that keep the plans fair and trusted:

- **Site fixes are free for everyone, forever.** The download engine (yt-dlp) updates on its own, separately from app releases, on every plan. 4K Video Downloader drew complaints when its old lifetime keys did not carry over to its new app; we promise in writing that Lifetime covers all future versions of AnyGet.
- **14-day refunds**, no questions.
- **No account for Free.** A licence key unlocks paid plans; the key is checked offline.
- Price anchors (secondary sources, Nov 2026): 4K Video Downloader Plus about $15/year (Lite) and about $25–45 one-time; Downie about $20 one-time; JDownloader free; Raindrop.io Pro about $28/year; Readwise Reader about $96–120/year.
- **Regional prices later**: India/South Asia, MENA and LatAm at 40–60% off the US price through the payment provider's localized pricing (Paddle supports UPI for India), checked against billing country to limit VPN abuse.

## 7. Economics

Desktop-only means the cost of one more user is almost zero: no servers do the downloading.

**Per sale** (assuming a merchant of record at about 5% + $0.50):

| Plan | Price | Net |
|---|---|---|
| Plus | $19 | ≈ $17.55 |
| Lifetime (launch) | $29 | ≈ $27.05 |
| Lifetime | $39 | ≈ $36.55 |
| Pro | $79 | ≈ $74.55 |

**Fixed yearly costs** (approximate):

| Item | Cost |
|---|---|
| Apple Developer Program (macOS signing + notarization) | $99 |
| Windows signing (Azure Artifact Signing, Basic) | ≈ $120 |
| Domain | ≈ $15 |
| Website (Cloudflare Pages; Vercel's free Hobby plan is non-commercial) | $0 |
| Installers and update feed (Cloudflare R2: ≈ $0.015/GB-month, free egress) | ≈ $0–10 |
| Licence webhook (Cloudflare Worker free tier) | $0 |
| Email for licences (Resend free tier, paid if volume grows) | $0–240 |
| Website analytics (cookie-free, self-hosted or paid) | $0–110 |
| **Total** | **≈ $250–600** |

One-off: forming a company and a lawyer's review of the EULA, Terms and Privacy policy — roughly $500–2,000 depending on country.

**Break-even** on running costs: about 20–35 sales a year.

**Year-1 illustration — assumptions, not a forecast:** 30,000 installs → 3% pay → 900 buyers; mix 50% Plus, 40% Lifetime, 10% Pro → about $31 net per buyer → **about $28,000**. Plus renewals add to year 2. Halve or double the install number and the result scales with it; the conversion rate is the number to watch.

**Metrics to track from day one**

| Metric | Target |
|---|---|
| Activation (installs that finish a first download) | ≥ 60% |
| Free → paid (of installs, within 90 days) | 2–5% |
| Refund rate | < 5% |
| Plus renewal | ≥ 55% |
| Time from a site breaking to a fix reaching users | < 48 h |

## 8. Mobile

- **Android — a full app.** Downloads happen on the phone itself, into the phone's storage, and links arrive from the share sheet. Google Play removes YouTube downloaders, so the app ships as a **signed APK from our website** (with in-app updates) plus alternative stores. The same licence key unlocks Plus.
- **iPhone — a remote for your computer.** Apple does not accept downloader apps. On the desktop app the user scans a QR code; the phone becomes a remote (the existing PWA, with the iOS share sheet). Links shared on the phone download on the computer; "Save to phone" sends the finished file back. Away from home it works through Tailscale (`docs/tailscale.md`). A small link relay could come later, but that is a server and we are not running servers now.

## 9. Distribution

| Channel | Notes |
|---|---|
| Our website | Main channel. Signed installers for Windows, macOS (universal) and Linux. |
| winget, Homebrew cask, Flathub, AppImage | Free listings where power users look. |
| Setapp (Mac) | Downie and Pulltube are listed there; apply and confirm we are accepted. |
| Android | Signed APK on our site; alternative Android stores. |
| Microsoft Store, Mac App Store, Google Play, Apple App Store | Unlikely to accept a downloader; not planned. |
| Browser extension | Firefox Add-ons and the Chrome Web Store. Chrome rejects YouTube download extensions; ours only sends links to the desktop app and its listing must say exactly that. |

## 10. Go-to-market (organic)

Google restricts ads for downloaders, so growth is organic.

- **Before launch:** a landing page with a waitlist and the $29 launch price; a closed beta with about 100 people from communities that already want this (r/DataHoarder, r/selfhosted, r/software, r/macapps, archivist and teacher forums).
- **Launch week:** Product Hunt, Show HN, Reddit posts written as "what I built and why", AlternativeTo listing, a 2-minute demo video.
- **Ongoing:** search pages for each use case ("save a playlist for offline", "download an archive.org book as PDF", "find a free legal copy of a book", "download from Wayback"), honest comparison pages (vs 4K Video Downloader, vs JDownloader, vs online download sites), a changelog people can follow, and fast fixes when sites change.
- **Wording rule:** never "YouTube to MP3" or other site trademarks in ads, names or headlines. Say "1,800+ video and audio sites".

## 11. Legal and risks

| Risk | What we do |
|---|---|
| YouTube's Terms forbid downloading except through YouTube's own features. In the US, whether YouTube downloaders break DMCA §1201 is unsettled: in Yout v. RIAA the district court ruled against Yout and the Second Circuit appeal was still pending in late 2026. | Form a company so the owner is not personally exposed. Have a lawyer review the EULA, Terms and marketing. Keep today's hard rules: no DRM, no geo-block bypass, no paywalls, no shadow libraries. Personal-use EULA (Pro adds commercial use for content the buyer has rights to). Register a DMCA agent and publish a takedown process. |
| Payment provider refuses or freezes the account (Stripe's rules ban services that "facilitate" infringement). | Apply to Paddle early with an honest description; have a second merchant of record ready before launch. Keep refunds and complaints low. |
| Sites change and downloads break. | Separate engine updater (free for all), the existing live-test workflow, a public status note of the engine version. |
| Open-source licences of bundled tools. | Ship third-party notices. gallery-dl (GPL) stays a separate process with its source linked. Use an LGPL ffmpeg build. `ia` (AGPL) is not bundled. Avoid GPL libraries inside our own closed-source apps (Android). |
| App stores refuse us. | Direct downloads, package managers and Setapp are the plan already. |
| Cracked licence keys. | Accept some piracy; offline-signed keys, no heavy copy protection (it would hurt paying users). |
| Privacy laws (GDPR, UK GDPR, CCPA). | Collect almost nothing: payment data stays with the merchant of record; app telemetry and crash reports are opt-in and never include URLs, cookies or file names. |

## 12. The owner's checklist (not code)

- [ ] Form a company (LLC / Pvt Ltd) and open a business bank account.
- [ ] Lawyer review: EULA, Terms of sale, Privacy, Refunds, Copyright/DMCA, marketing wording.
- [ ] Trademark search for "AnyGet" (and a fallback name) before buying ads, domains or store listings.
- [ ] Domain and a support email.
- [ ] Apple Developer Program and a Windows signing identity.
- [ ] Apply to Paddle (and a second merchant of record).
- [ ] Register a DMCA designated agent.
- [ ] Recruit about 100 beta testers.

## 13. Build roadmap (v3 "Launch")

One prompt per phase in `prompts/`, built one at a time like v1 and v2:

| Phase | Prompt | Goal |
|---|---|---|
| 1 | `prompts/v3-phase-01-finish-v2-and-rules.md` | Finish v2 polish, tag v2.0.0, commercial rules in CLAUDE.md |
| 2 | `prompts/v3-phase-02-licensing-and-plans.md` | Licence keys, plan limits, free engine updater |
| 3 | `prompts/v3-phase-03-desktop-app.md` | Signed desktop app with auto-update |
| 4 | `prompts/v3-phase-04-phone.md` | Phone remote (iPhone + Android) and the Android app |
| 5 | `prompts/v3-phase-05-storefront.md` | Website, pricing, checkout, licence emails, legal pages |
| 6 | `prompts/v3-phase-06-trust-support-analytics.md` | Opt-in telemetry and crash reports, help centre, support |
| 7 | `prompts/v3-phase-07-beta-and-launch.md` | Beta, launch, v3.0.0, 30-day review |

**Later (v3.1+):** regional prices (UPI via Paddle), India and MENA launches (Hindi and Arabic are ready), Spanish, Portuguese and Indonesian, and an optional link relay for iPhone away from home.

## Sources

- 4K Video Downloader Plus plans and the lifetime-licence change: [Capterra](https://www.capterra.com/p/10038360/4K-Video-Downloader-Plus/), [VideoProc review](https://videoproc.com/download-record-video/4k-video-downloader-plus-review.htm), [TidBITS](https://talk.tidbits.com/t/4k-video-downloader-plus-26-2/33921)
- Downie and Pulltube: [The Sweet Bits review](https://thesweetbits.com/tools/downie-video-downloader/), [Downie vs Pulltube](https://thesweetbits.com/pulltube-vs-downie/), [Charlie Monroe Software](https://software.charliemonroe.net/downie/)
- Raindrop.io and Readwise prices, Pocket shutdown: [9to5Mac](https://9to5mac.com/2025/05/28/pocket-read-it-later-alternatives/), [TechCrunch](https://techcrunch.com/2025/05/27/read-it-later-app-pocket-is-shutting-down-here-are-the-best-alternatives)
- Market size estimates (weak, conflicting): [Global Growth Insights](https://www.globalgrowthinsights.com/market-reports/online-video-downloader-market-127984), [Market Reports World](https://www.marketreportsworld.com/market-reports/online-video-downloader-market-14728911)
- Yout v. RIAA: [TorrentFreak — appeal and Cox ruling](https://torrentfreak.com/yout-com-hopes-supreme-courts-cox-ruling-helps-its-case-riaa-disagrees/), [Digital Music News](https://www.digitalmusicnews.com/2023/05/08/riaa-yout-appeal-answer-may-2023/)
- Google Play and downloaders: [Android Headlines](https://www.androidheadlines.com/2026/05/beyond-the-app-store-why-the-best-media-downloaders-arent-on-google-play.html), [TorrentFreak — RIAA vs download apps](https://torrentfreak.com/riaa-ramps-up-efforts-to-remove-music-download-apps-from-google-play-230929/)
- Stripe restricted businesses: [stripe.com](https://stripe.com/legal/restricted-businesses); Paddle: [what you can't sell](https://www.paddle.com/help/start/account-verification/what-am-i-not-allowed-to-sell-on-paddle), [localized pricing](https://developer.paddle.com/build/products/offer-localized-pricing/), [UPI Autopay](https://developer.paddle.com/changelog/2026/upi-autopay/)
- Regional pricing benchmarks: [Fungies](https://fungies.io/purchasing-power-parity-saas-pricing-2026), [Paddle blog](https://www.paddle.com/blog/saas-localized-pricing)
- YouTube blocking data-centre IPs (why hosted downloading was ruled out): [DEV Community](https://dev.to/osovsky/i-was-building-a-cloud-video-service-youtube-turned-me-into-an-ip-trafficker-1l9o), [yt-dlp issue](https://github.com/yt-dlp/yt-dlp/issues/15897)
- Windows signing: [Azure Artifact Signing pricing](https://azure.microsoft.com/pricing/details/trusted-signing/); Cloudflare R2: [R2 pricing overview](https://filebase.com/blog/cloudflare-r2-pricing-costs-savings-and-alternatives-in-2026/)
