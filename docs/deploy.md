# Use AnyGet from anywhere: Cloudflare Tunnel + Access

AnyGet runs on your computer. To open it on your phone over mobile data, a
**Cloudflare Tunnel** carries traffic from `https://dl.<your-domain>` to your computer,
and **Cloudflare Access** asks for an email code before anyone gets in. Nothing is opened
on your router, and your home IP address stays private. Everything here fits in
Cloudflare's free plan (Access is free for up to 50 users).

You need a domain you own (for example one bought at Hostinger) and a free Cloudflare
account. No domain? Use [Tailscale](tailscale.md) instead.

> **Before you change nameservers, export your DNS records.** Your website and email
> depend on them. At your registrar, write down or export every record: `A`, `AAAA`,
> `CNAME`, `MX`, and the `TXT` records for SPF, DKIM and DMARC. After moving to Cloudflare,
> check that every one of them was imported. A missing `MX` or SPF record means lost email.

## 1. Move the domain's DNS to Cloudflare

1. In the Cloudflare dashboard, **Add a domain** → enter your domain → **Free** plan.
2. Cloudflare imports the records it finds. Compare them with your export and add any
   that are missing. Mail records (`MX`, and `A`/`CNAME` records for mail hosts) must
   stay **DNS only** (grey cloud), not proxied.
3. Cloudflare shows two nameservers, like `ada.ns.cloudflare.com`.
4. At your registrar, switch the nameservers. On **Hostinger**: hPanel → **Domains** →
   your domain → **DNS / Nameservers** → **Change nameservers** → *Use custom nameservers*
   → paste Cloudflare's two → Save. **Turn DNSSEC off first** if it is on (you can turn it
   on again in Cloudflare later).
5. Wait until Cloudflare says the domain is **Active**. This often takes minutes but can
   take up to a day. Check that your website and email still work.

## 2. Create the tunnel

1. Cloudflare dashboard → **Zero Trust** → **Networks** → **Tunnels** → **Create a
   tunnel** → **Cloudflared** → name it `anyget`.
2. Choose **Docker**. Copy only the token (the long string after `--token`) into `.env`:

   ```sh
   TUNNEL_TOKEN=eyJhIjoi...
   ```

3. **Public hostname** (the route): subdomain `dl`, your domain, service type **HTTP**,
   URL `web:3000`. One route is enough: the website forwards `/api` to the API itself.
   (A separate `dl.<domain>/api/*` → `http://api:8000` route also works if you prefer.)

## 3. Protect it with Access (email code)

1. Zero Trust → **Access** → **Applications** → **Add an application** →
   **Self-hosted**.
2. Name `AnyGet`, domain `dl.<your-domain>`, session duration as you like (for example
   one week).
3. Add a policy: **Allow**, include **Emails** → your email (and anyone you trust).
4. Login methods: **One-time PIN** (Cloudflare emails a code; no password to manage).
5. Save. On the application's **Overview** tab, copy the **Application Audience (AUD)
   Tag**. Your team domain is under Zero Trust → **Settings** → **Custom pages** (it looks
   like `myteam.cloudflareaccess.com`). Put both in `.env`:

   ```sh
   ANYGET_ACCESS_TEAM_DOMAIN=myteam.cloudflareaccess.com
   ANYGET_ACCESS_AUD=4714c1358e65fe4b408ad6d432a5f878f08194bdb4752441fd56faefa9b2b6f2
   ```

AnyGet checks the signed `Cf-Access-Jwt-Assertion` header on every API request that
comes through the tunnel: it verifies the signature against your team's keys, the AUD
tag, the issuer and the expiry. If Access were ever switched off by mistake, requests
through the tunnel would be refused, not let in. Requests from your own computer
(`http://127.0.0.1:3000`) keep working without a login.

## 4. Start it

```sh
make up-public
```

In Zero Trust → Networks → Tunnels, the tunnel should show **Healthy**. On your phone,
turn Wi-Fi off and open `https://dl.<your-domain>`. Cloudflare asks for your email,
sends a code, and then AnyGet opens. Install it (**Settings → Install AnyGet**) to get
it in Android's Share menu.

## The CLI, the browser extension and scripts

These can't type an email code, so give them the access token:

1. Set a long random `ANYGET_API_TOKEN` in `.env` and restart (`make up-public`).
2. Extension: options → AnyGet address `https://dl.<your-domain>`, token = that value.
   Termux: `ANYGET_URL` and `ANYGET_TOKEN` in `~/.config/anyget/termux.env`.
3. Cloudflare Access must let these requests reach AnyGet. Either sign in once in the same
   browser (the extension sends the Access cookie), or create a **Service Token** (Zero
   Trust → Access → Service auth) and add a **Service Auth** policy to the application.
   Scripts then also send `CF-Access-Client-Id` and `CF-Access-Client-Secret`.

## Security notes

- Ports stay bound to `127.0.0.1`. Only cloudflared reaches AnyGet from outside.
- Requests from outside are rate limited per address (`ANYGET_RATE_LIMIT_PER_MINUTE`,
  `ANYGET_RATE_LIMIT_WRITES_PER_MINUTE`).
- `ANYGET_AUTH_MODE=always` also requires Access or the token on this computer. It is
  only useful if other people use your computer.
- Pages and API answers carry a Content Security Policy and other security headers.
- Back up regularly: `make backup` (see the README).

## Troubleshooting

| What you see | What to check |
|---|---|
| Tunnel **Down** | `make logs` → cloudflared lines; a wrong `TUNNEL_TOKEN`; `web` must be healthy |
| Error 1033 | The tunnel isn't connected; start it with `make up-public` |
| `auth_required` from the API | `ANYGET_ACCESS_TEAM_DOMAIN` / `ANYGET_ACCESS_AUD` are missing in `.env` |
| `auth_invalid` | The AUD tag belongs to another application, or the team domain is wrong |
| Email stopped working | A mail record was not imported, or it is proxied; make it DNS only |
