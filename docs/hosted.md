# Hosted AnyGet: Railway (API) + Vercel (website)

The website runs on Vercel and sends every `/api/*` request to the API on Railway
(`API_URL`). Both are on the internet, so AnyGet needs a sign-in. Without one, the API
refuses every request except `/api/health`. It detects Railway from Railway's own
environment variables; on other hosts, set `ANYGET_PUBLIC=true`.

## 1. Make a password hash (once)

On your computer, in `apps/api`:

```bash
uv run anyget hash-password
```

Type a long password twice. The command prints a line that starts with `$argon2id$`.
Keep the password in your password manager. The hash is safe to store in Railway.

## 2. Railway: service `anyget-api`

Variables:

| Variable | Value |
|---|---|
| `ANYGET_OWNER_EMAIL` | your email (used only to sign in) |
| `ANYGET_OWNER_PASSWORD_HASH` | the `$argon2id$…` line from step 1, pasted as it is |
| `ANYGET_SESSION_SECRET` | a long random string: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `ANYGET_API_TOKEN` | optional: a long random string for the CLI and browser extension |

Keep the volume mounted at `/data`: the database and the thumbnails live there.
Redeploy, then open `https://<your-railway-domain>/api/health`. It should answer with
`"status": "ok"`. Any other API path should answer `401`.

## 3. Vercel: project `downloader-web`

Nothing new is required: `API_URL` (your Railway address) is all the website needs. It is
read at build time for the `/api` rewrite and at run time to check whether sign-in is on.
Redeploy so the build includes the sign-in page.

## 4. Check

1. Open `https://downloader-web-neon.vercel.app`. You should land on **Sign in**.
2. Sign in with the email and password from step 1. You come back to the page you
   asked for, and Settings shows **Sign out**.
3. In a private window, open `https://downloader-web-neon.vercel.app/api/jobs`. It
   should answer `401`.

## Notes

- Changing the password hash signs every session out.
- The session cookie is HTTP-only, `Secure` and `SameSite=Lax`. Website writes carry an
  `X-Requested-With: anyget` header; cookie-signed writes without it are refused (CSRF).
- Sign-in attempts are limited to 5 a minute per visitor and 30 a minute in total.
- After the first start with an owner, the old shared job list is cleared once. Files
  stay on the volume and in the Library.
