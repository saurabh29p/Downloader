# Hosted AnyGet: Railway (API) + Vercel (website)

This is one worked example of hosting AnyGet on the internet. Any host that runs the two
Docker images (or the API and the Next.js app) works the same way; the names below
(`anyget-api`, `anyget-web`, `anyget.example.com`) are placeholders for your own.

The website runs on Vercel and sends every `/api/*` request to the API on Railway
(`API_URL`). Both are on the internet, so AnyGet needs a sign-in. Without one, the API
refuses every request except `/api/health`. It detects Railway from Railway's own
environment variables; on other hosts, set `ANYGET_PUBLIC=true`.

Never paste a password, key, cookie or token into a chat, an issue or a commit. Put them
only in Railway's or Vercel's variables, or on AnyGet's Connections page.

## 1. Make a password hash (once)

On your computer, in `apps/api`:

```bash
uv run anyget hash-password
```

Type a long password twice. The command prints a line that starts with `$argon2id$`.
Keep the password in your password manager. The hash is safe to store in Railway.

## 2. Railway: an API service (for example `anyget-api`)

### Required

| Variable | Value |
|---|---|
| `ANYGET_OWNER_EMAIL` | your email (used only to sign in) |
| `ANYGET_OWNER_PASSWORD_HASH` | the `$argon2id$…` line from step 1, pasted as it is |
| `ANYGET_SESSION_SECRET` | a long random string: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `ANYGET_SECRETS_KEY` | encrypts saved Connections: output of `uv run anyget gen-key`. Set it before connecting sites; connections saved with another key can't be read. Don't replace it once set. |

Keep the volume mounted at `/data`: the database, thumbnails and keys live there.

### Optional

| Variable | What it does |
|---|---|
| `ANYGET_DOWNLOADS_DIR` | Where files are saved. If it is not set, the image uses `/downloads`. Check where your Railway volume is mounted: files are kept across deploys only if this folder is on the volume (for example `/data/downloads` with the volume at `/data`). |
| `ANYGET_RETENTION_DAYS` | Remove downloaded files after this many days (`0` = keep forever; the code's default is `7`). **Set `0` for the first deploy** (see "Retention" below). |
| `ANYGET_API_TOKEN` | A long random string for the CLI and the browser extension (Bearer token). |
| `OPENROUTER_API_KEY` | The optional AI helper (or add it on the Connections page). |
| `ANYGET_LLM_DAILY_LIMIT` | AI calls per day (default `500`; `0` turns AI off). |
| `ANYGET_LLM_FREE_MODE` | `true`: only free OpenRouter models (also a Settings switch). |
| `TMDB_API_KEY` | Movies: where to watch in India (or add it on the Connections page). |
| `ANYGET_CONTACT_EMAIL` | Sent to archive.org and other APIs in the User-Agent (a polite client). |
| `ANYGET_GITHUB_TOKEN`, `ANYGET_HF_TOKEN`, library keys… | Higher limits for those sources; see `.env.example`. All also settable in Connections. |

Don't set `ANYGET_NET_ALLOWLIST` (tests only) or `ANYGET_AUTH_MODE` (the default is right).

## 3. Vercel: a website project (for example `anyget-web`)

| Variable | Required | Value |
|---|---|---|
| `API_URL` | yes | your Railway address, e.g. `https://anyget-api.example.com` (your Railway service's public address) |

It is read at build time for the `/api` rewrite and at run time to check whether sign-in
is on. Nothing else is needed on Vercel. Redeploy after changing it.

## 4. Retention (read before deploying this version)

**First deploy: set `ANYGET_RETENTION_DAYS=0` on Railway before you deploy.** Cleanup is
then off: nothing is ever removed. Switch it on later (Railway variable or Settings →
Downloads) once you have checked where files are stored and what the policy would remove.

When it is on, cleanup runs once a day in the API: downloaded files AnyGet saved more than
N days ago are removed. Safety:

- **Grace period:** the first removals happen N days after retention is first switched on.
  Deploying never deletes files on day one. You have N days to change your mind.
- To keep everything, set `ANYGET_RETENTION_DAYS=0` (or Settings → Downloads → 0).
- Files tagged `keep` (Library → a file → Tags) are never removed, and neither are
  running or paused downloads.
- Only files in the downloads folder that AnyGet indexed in its Library are considered.
  If the data folder is inside the downloads folder, cleanup refuses to run at all.
- A removed file keeps its Library entry ("Removed", with **Download again**), and its
  row in Downloads offers Download again.

See what a cleanup would do without deleting anything: Settings → Downloads shows when
removals start, and `GET /api/retention` answers the policy (read-only). The CLI's
`anyget cleanup` (without `--apply`) lists the files it would remove.

## 5. Check after a deploy (safe, read-only)

1. `https://<your-railway-domain>/api/health` answers `"status": "ok"`. Any other API path
   opened in a private window answers `401`.
2. Open your Vercel address, e.g. `https://anyget.example.com`. You land on **Sign in**. Sign in; you
   come back to the page you asked for, and Settings shows **Sign out**.
3. **Settings → AI helper** shows today's calls and, if something is wrong, the reason
   (for example "credits have run out"). No key value is ever shown.
4. **Settings → Downloads** shows the retention days and when removals start.
5. **Library:** pick a PDF, a picture or a video and press **Open**; press **Play** on an
   audio file and move to Downloads: the player keeps going.
6. Searching still works with AI off: results come from the sources, and a note says AI
   couldn't help (no answer card is made up).

Don't delete, retry or change existing downloads or Connections just to test. Use a new,
small public-domain file if you want to try a download.

## 6. Background audio on phones (manual check)

Browsers decide whether audio keeps playing with the screen locked. AnyGet uses the
standard `<audio>` element and Media Session (title, play/pause, seek on the lock
screen), with no tricks. Check on a real phone:

**Android (Chrome):**
1. Open AnyGet in Chrome and sign in. Library → an audio file → **Play**.
2. Move to Downloads and Settings: the player at the bottom keeps playing.
3. Lock the screen. Audio should continue, and the lock screen should show the title with
   play/pause. Press pause and play there.
4. Unlock, switch to another app for a minute, come back: still playing (or paused, if you
   paused it).
5. Repeat 1 to 4 with AnyGet installed as an app (Settings → Install AnyGet).

**iPhone (Safari):**
1. Open AnyGet in Safari (a normal tab) and sign in. Library → an audio file → **Play**.
2. Move between pages: the player keeps playing.
3. Lock the screen. Audio usually continues, with title and controls on the lock screen.
4. Switch to another app and back.
5. Repeat with the app added to the Home Screen. Background audio is less reliable there
   on some iOS versions.

Write down per step whether it worked, with the phone model and OS version. Battery saver
modes can stop background audio on both systems.

## Notes

- Changing the password hash signs every session out.
- The session cookie is HTTP-only, `Secure` and `SameSite=Lax`. Files, video and audio
  are fetched with that cookie, so media links never contain a token. Website writes
  carry an `X-Requested-With: anyget` header; cookie-signed writes without it are refused
  (CSRF).
- Sign-in attempts are limited to 5 a minute per visitor and 30 a minute in total.
- After the first start with an owner, the old shared job list is cleared once. Files
  stay on the volume and in the Library.
