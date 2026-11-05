# anyget-plugin-example

An example AnyGet plugin: paste an xkcd link (`https://xkcd.com/353/`) and AnyGet saves the comic image. xkcd is licensed [CC BY-NC 2.5](https://xkcd.com/license.html).

## How a plugin works

- A plugin is a Python package with an entry point in the `anyget.handlers` group (see `pyproject.toml`).
- The entry point is a factory `make(net, settings)` that returns a handler with `name`, `can_handle(url)`, `probe(url, options)` and `download(job, options, progress_cb)`, the same contract as AnyGet's built-in handlers.
- An optional `priority` attribute sets where it runs. Lower runs first; the default is 85.
- Use the `net` it receives for every request. That keeps AnyGet's SSRF guard, per-site limits and retries.

## Try it

```sh
cd examples/anyget-plugin-example
uv sync
uv run pytest
```

To use it in your AnyGet, install it into the API's environment and enable it:

```sh
cd apps/api
uv pip install -e ../../examples/anyget-plugin-example
ANYGET_PLUGINS=xkcd uv run uvicorn anyget.main:app
```

Plugins are code that runs inside AnyGet, so none load unless they are listed in `ANYGET_PLUGINS`. Use `*` to load every installed plugin. `GET /api/health` lists installed plugins and says whether each one loaded.
