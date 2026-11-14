# The AnyGet API

Everything the website does goes through a JSON HTTP API, so scripts can do it too.

- **Interactive docs:** open **http://127.0.0.1:3000/api/docs** (Swagger UI) while AnyGet is
  running. The schema is at `/api/openapi.json`.
- The website forwards `/api/*` to the API, so the same paths work on port 3000 (the website)
  and port 8000 (the API itself).
- A typed TypeScript client is generated from the schema in `packages/shared` (`make gen`).

## Signing in

| How you call it | What it needs |
|---|---|
| From the same computer, no owner set | Nothing |
| A script, the command line or the browser extension | `Authorization: Bearer <ANYGET_API_TOKEN>` |
| A browser signed in as the owner | The session cookie, plus `X-Requested-With: anyget` on every write (protects against cross-site requests) |
| Through Cloudflare | A valid Cloudflare Access token, or the bearer token |

When AnyGet is reachable from the internet and no owner is set, every request except
`/api/health` and the sign-in endpoints answers `401` with the code `owner_required`.

## Examples

Check what is behind a link (title, size, and the choices to pick from):

```sh
curl -X POST http://127.0.0.1:3000/api/probe \
  -H 'Content-Type: application/json' -H 'X-Requested-With: anyget' \
  -d '{"url": "https://commons.wikimedia.org/wiki/File:Tsunami_by_hokusai_19th_century.jpg"}'
```

Download one or more links (`items` lets each link have its own options, for example a
video quality or the files to keep):

```sh
curl -X POST http://127.0.0.1:3000/api/jobs \
  -H 'Content-Type: application/json' -H 'X-Requested-With: anyget' \
  -d '{"urls": ["https://commons.wikimedia.org/wiki/File:Tsunami_by_hokusai_19th_century.jpg"]}'
# → {"jobs": [{"id": "…", "state": "queued", …}], "rejected": [], "skipped": []}
```

Follow progress live (Server-Sent Events, one `job.updated` event per change):

```sh
curl -N http://127.0.0.1:3000/api/events
```

List downloads, fetch one, save its file, and pause, resume, retry or cancel it:

```sh
curl http://127.0.0.1:3000/api/jobs
curl http://127.0.0.1:3000/api/jobs/<id>
curl -OJ http://127.0.0.1:3000/api/jobs/<id>/file
curl -X POST -H 'X-Requested-With: anyget' http://127.0.0.1:3000/api/jobs/<id>/pause   # or resume, retry, cancel
```

`/api/health` and `/api/version` say whether the API is up and which versions of AnyGet,
yt-dlp, FFmpeg and Deno it uses. The Library, search, books, watches, settings and
connections all have endpoints too: see `/api/docs`.
