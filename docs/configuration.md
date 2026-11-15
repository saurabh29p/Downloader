# Configuration

AnyGet works without any configuration on your own computer. When you want to change
something, there are three places:

1. **Settings** (in the app): downloads, the AI helper and advanced options. Values saved
   here win over the ones in `.env`.
2. **Connections** (in the app): your own accounts (`cookies.txt`) and free API keys, stored
   encrypted on your machine.
3. **`.env`** (next to `docker-compose.yml`): every setting as an environment variable.
   [`.env.example`](../.env.example) lists all of them with a one-line explanation and safe
   defaults. Copy it to `.env`, change what you need and run `make up` again.

## The Settings page

| Group | What you can change |
|---|---|
| General | Install AnyGet as an app on this device |
| Downloads | Sub-folders for new downloads (for example `{type}/{source}`), downloads at once (in total and per site), a speed limit, whether watches run, and cleanup of old files |
| AI helper | Free mode (only free models) and today's usage. The key itself goes in Connections |
| Connections | A shortcut to the Connections page |
| Advanced | Where files are saved, the outgoing proxy, per-site limits, torrents and the yt-dlp version check |

## Variables that matter most

| Variable | Default | What it does |
|---|---|---|
| `ANYGET_RETENTION_DAYS` | `0` | Remove downloaded files after this many days; `0` keeps them forever |
| `ANYGET_MAX_CONCURRENT_DOWNLOADS` / `ANYGET_MAX_PER_HOST` | `3` / `4` | Downloads at once, in total and per site (archive.org and the big libraries have their own limit of 2) |
| `ANYGET_CONTACT_EMAIL` | empty | Sent in the User-Agent to archive.org and other public APIs, to be a polite client |
| `ANYGET_OWNER_EMAIL`, `ANYGET_OWNER_PASSWORD_HASH`, `ANYGET_SESSION_SECRET` | empty | The owner sign-in. **Required when AnyGet is reachable from the internet**; see [hosted.md](hosted.md) |
| `ANYGET_PUBLIC` | `false` | Says that AnyGet is on the internet when no hosting platform is detected. A public AnyGet without an owner refuses every request |
| `ANYGET_API_TOKEN` | empty | Bearer token for the command line, the browser extension and scripts |
| `ANYGET_ACCESS_TEAM_DOMAIN`, `ANYGET_ACCESS_AUD` | empty | Cloudflare Access checks ([deploy.md](deploy.md)) |
| `ANYGET_TORRENT_ENABLED` | `false` | Allow magnet links and `.torrent` files (needs the optional engine) |
| `ANYGET_OPENROUTER_KEY`, `ANYGET_LLM_FREE_MODE`, `ANYGET_LLM_DAILY_LIMIT` | empty, `false`, `500` | The optional AI helper |
| `ANYGET_PROXY` | empty | A proxy for every outgoing request (`HTTP(S)_PROXY` is ignored on purpose) |
| `ANYGET_WITH_OCR` | `0` | Docker build: `1` adds OCR languages beyond English, Hindi and Arabic |

Keys for GitHub, Hugging Face, Kaggle, TMDB and the library APIs can also be set as
variables (`ANYGET_GITHUB_TOKEN`, `ANYGET_TMDB_KEY`…), but the Connections page is easier and
stores them encrypted. `ANYGET_SECRETS_KEY` sets the key that encrypts them (by default one is
made in `data/secrets.key`; changing it makes saved connections unreadable).

## Notes

- In `.env`, write each `$` of the password hash as `$$`: Docker Compose reads `$` as the
  start of a variable.
- Never commit `.env`, and never paste keys, cookies or passwords into issues or chats.
- `ANYGET_NET_ALLOWLIST` exists only for tests. Never set it in normal use: it lets AnyGet
  reach private addresses.
