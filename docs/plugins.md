# Plugins

A plugin adds a site to AnyGet from its own Python package, without changing AnyGet's code.
[`examples/anyget-plugin-example`](../examples/anyget-plugin-example) is a complete, tested
example: paste an xkcd link and AnyGet saves the comic (xkcd is licensed CC BY-NC 2.5).

## How a plugin works

- It is a Python package with an entry point in the **`anyget.handlers`** group:

  ```toml
  [project.entry-points."anyget.handlers"]
  xkcd = "anyget_plugin_example:make"
  ```

- The entry point is a factory, `make(net, settings)`, that returns a handler with the same
  contract as AnyGet's built-in ones: `name`, `can_handle(url)`, `probe(url, options)` and
  `download(job, options, progress_cb)`.
- An optional `priority` attribute sets when it is asked (lower runs first). The default, 85,
  comes after the built-in site handlers and yt-dlp (80) and before image galleries (90) and
  the direct-file fallback; give a lower number to run before yt-dlp.
- Use the `net` it receives for **every** request: that keeps AnyGet's network guard,
  per-site limits and retries. Save files with `anyget.core.filenames` so names stay safe.
- Plugins follow the same legal rules as AnyGet: no DRM removal, no getting around logins,
  paywalls or region blocks, no shadow libraries.

## Try the example

```sh
cd examples/anyget-plugin-example
uv sync
uv run pytest
```

## Use a plugin

Install it into the API's environment and list it in `ANYGET_PLUGINS`:

```sh
cd apps/api
uv pip install -e ../../examples/anyget-plugin-example
ANYGET_PLUGINS=xkcd uv run uvicorn anyget.main:app
```

Plugins are code that runs inside AnyGet, so **none load unless they are listed** in
`ANYGET_PLUGINS` (`*` loads every installed plugin). Install only plugins you trust.
`GET /api/health` lists the installed plugins and whether each one loaded.

With Docker, add the plugin to the API image (for example a small Dockerfile `FROM` the AnyGet
API image that runs `uv pip install` for your plugin) and set `ANYGET_PLUGINS` in `.env`.
